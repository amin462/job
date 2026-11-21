"""Mart builder generating aggregate mart tables and seed_marts.json (T3.7).

Enforces:
- Weighted proportions using sample_weight (PLAN D13).
- Weekly demand trends with active vs new counts (PLAN D14).
- n >= 5 suppression on all public marts (PLAN D4, ARCHITECTURE §3.4).
- ZERO description/qualifications text anywhere in seed_marts.json.
"""
from __future__ import annotations

import datetime as dt
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from pipeline.etl.clean import PROVINCE_META
from pipeline.etl.extract_skills import SkillExtractor
from pipeline.etl.map_taxonomy import OccupationMapper

MIN_PUBLIC_N = 5


def _quantile(sorted_vals: list[float], q: float) -> float:
    """Linear-interpolated percentile matching Postgres percentile_cont()."""
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    if n == 1:
        return float(sorted_vals[0])
    pos = q * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return float(sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo]))


def _week_start(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def _parse_date(val: Any) -> dt.date | None:
    if not val:
        return None
    try:
        return dt.date.fromisoformat(str(val)[:10])
    except ValueError:
        return None


def build_all_marts(
    postings: list[dict[str, Any]],
    dq_results: list[dict[str, Any]],
    pending_aliases: list[dict[str, Any]],
    extractor: SkillExtractor,
    mapper: OccupationMapper,
    run_timestamp: str | None = None,
) -> dict[str, Any]:
    """Compute all 12 mart objects + dimension references from cleaned DW records."""
    now_iso = run_timestamp or dt.datetime.now(dt.timezone.utc).isoformat()
    n_total = len(postings)

    # 1. public_summary (1-row summary)
    salaried = [p for p in postings if p.get("has_salary")]
    with_skills = [p for p in postings if int(p.get("n_skills") or 0) > 0]
    provinces_real = {
        p["province_th"]
        for p in postings
        if p.get("province_th") and p["province_th"] not in {"หลายจังหวัด", "ต่างประเทศ", "ไม่ระบุ"}
    }
    occ_clusters_present = {p["occupation_cluster"] for p in postings if p.get("occupation_cluster")}
    dates_posted = [str(p["date_posted"])[:10] for p in postings if p.get("date_posted")]
    avg_skills = round(sum(int(p.get("n_skills") or 0) for p in postings) / n_total, 1) if n_total else None

    public_summary = {
        "n_postings": n_total,
        "n_with_salary": len(salaried),
        "pct_with_salary": round(100.0 * len(salaried) / n_total, 1) if n_total >= MIN_PUBLIC_N else None,
        "n_with_skills": len(with_skills),
        "pct_with_skills": round(100.0 * len(with_skills) / n_total, 1) if n_total >= MIN_PUBLIC_N else None,
        "avg_skills_per_posting": avg_skills if n_total >= MIN_PUBLIC_N else None,
        "n_provinces": len(provinces_real),
        "n_occupations": len(occ_clusters_present),
        "n_skills_catalog": len(extractor.skills_by_key),
        "min_date_posted": min(dates_posted) if dates_posted else None,
        "max_date_posted": max(dates_posted) if dates_posted else None,
        "last_updated_at": now_iso,
    }

    # 2. skill_demand_weekly (weighted, active vs new, national / region / province)
    posting_seen_pairs: list[tuple[dict[str, Any], dt.date, dt.date]] = []
    all_weeks: set[dt.date] = set()
    for p in postings:
        fs = _parse_date(p.get("first_seen_date") or p.get("date_posted"))
        ls = _parse_date(p.get("last_seen_date") or p.get("first_seen_date") or p.get("date_posted"))
        if fs is None:
            continue
        if ls is None or ls < fs:
            ls = fs
        posting_seen_pairs.append((p, fs, ls))
        cur_w = _week_start(fs)
        end_w = _week_start(ls)
        while cur_w <= end_w:
            all_weeks.add(cur_w)
            cur_w += dt.timedelta(days=7)

    skill_demand_weekly: list[dict[str, Any]] = []
    for wk in sorted(all_weeks):
        wk_end = wk + dt.timedelta(days=6)
        scope_buckets: dict[tuple[str, str, str, bool | None], list[tuple[dict[str, Any], bool]]] = defaultdict(list)
        for p, fs, ls in posting_seen_pairs:
            if fs <= wk_end and ls >= wk:
                is_new = _week_start(fs) == wk
                reg = str(p.get("region") or "ไม่ระบุ")
                prov = str(p.get("province_th") or "ไม่ระบุ")
                s14 = bool(p.get("is_south14"))
                scope_buckets[("national", "ทั้งประเทศ", "ทั้งประเทศ", None)].append((p, is_new))
                scope_buckets[("region", reg, "ทั้งหมดในภาค", reg == "ใต้")].append((p, is_new))
                scope_buckets[("province", reg, prov, s14)].append((p, is_new))

        for (scope_level, reg, prov, s14), items in sorted(scope_buckets.items()):
            n_scope = len(items)
            w_scope = sum(float(p.get("sample_weight") or 1.0) for p, _ in items)
            w_scope_new = sum(float(p.get("sample_weight") or 1.0) for p, is_new in items if is_new)

            skill_stats: dict[str, dict[str, Any]] = {}
            for p, is_new in items:
                w = float(p.get("sample_weight") or 1.0)
                for sk_name in p.get("skills_list") or []:
                    st = skill_stats.setdefault(sk_name, {"n": 0, "n_new": 0, "w": 0.0, "w_new": 0.0})
                    st["n"] += 1
                    st["w"] += w
                    if is_new:
                        st["n_new"] += 1
                        st["w_new"] += w

            for sk_name, st in sorted(skill_stats.items()):
                rec = extractor.skills_by_name[sk_name]
                n_p = st["n"]
                n_new = st["n_new"]
                suppressed = n_p < MIN_PUBLIC_N or n_scope < MIN_PUBLIC_N
                skill_demand_weekly.append(
                    {
                        "week_start": wk.isoformat(),
                        "scope_level": scope_level,
                        "region": reg,
                        "province_th": prov,
                        "is_south14": s14,
                        "skill_key": rec.skill_key,
                        "skill_canonical": rec.skill_canonical,
                        "skill_slug": rec.skill_slug,
                        "skill_name_th": rec.skill_name_th,
                        "skill_type": rec.skill_type,
                        "skill_group": rec.skill_group,
                        "n_postings": n_p,
                        "n_new_postings": n_new,
                        "n_scope_postings": n_scope,
                        "weighted_active_sum": round(st["w"], 2) if not suppressed else None,
                        "weighted_new_sum": round(st["w_new"], 2) if (n_new >= MIN_PUBLIC_N and n_scope >= MIN_PUBLIC_N) else None,
                        "weighted_share": round(st["w"] / w_scope, 4) if (not suppressed and w_scope > 0) else None,
                        "weighted_new_share": round(st["w_new"] / w_scope_new, 4)
                        if (n_new >= MIN_PUBLIC_N and w_scope_new > 0)
                        else None,
                        "is_suppressed": suppressed,
                    }
                )

    # 3. skill_cooccurrence (top 15 per skill, strictly n_postings >= 5)
    skill_posting_counts: Counter[int] = Counter()
    pair_counts: Counter[tuple[int, int]] = Counter()
    pair_weights: defaultdict[tuple[int, int], float] = defaultdict(float)
    for p in postings:
        w = float(p.get("sample_weight") or 1.0)
        keys = sorted({extractor.skills_by_name[s].skill_key for s in (p.get("skills_list") or []) if s in extractor.skills_by_name})
        for k in keys:
            skill_posting_counts[k] += 1
        for k1, k2 in combinations(keys, 2):
            pair_counts[(k1, k2)] += 1
            pair_counts[(k2, k1)] += 1
            pair_weights[(k1, k2)] += w
            pair_weights[(k2, k1)] += w

    co_by_skill: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for (k1, k2), cnt in pair_counts.items():
        if cnt < MIN_PUBLIC_N:
            continue
        s1 = extractor.skills_by_key[k1]
        s2 = extractor.skills_by_key[k2]
        n1 = skill_posting_counts[k1]
        n2 = skill_posting_counts[k2]
        union_n = n1 + n2 - cnt
        co_by_skill[k1].append(
            {
                "skill_key": s1.skill_key,
                "skill_canonical": s1.skill_canonical,
                "skill_slug": s1.skill_slug,
                "skill_name_th": s1.skill_name_th,
                "skill_group": s1.skill_group,
                "co_skill_key": s2.skill_key,
                "co_skill_canonical": s2.skill_canonical,
                "co_skill_slug": s2.skill_slug,
                "co_skill_name_th": s2.skill_name_th,
                "co_skill_group": s2.skill_group,
                "n_postings": cnt,
                "weighted_co_count": round(pair_weights[(k1, k2)], 2),
                "co_share": round(cnt / n1, 4) if n1 else 0.0,
                "jaccard_similarity": round(cnt / union_n, 4) if union_n else 0.0,
            }
        )

    skill_cooccurrence: list[dict[str, Any]] = []
    for k1 in sorted(co_by_skill.keys()):
        rows = sorted(co_by_skill[k1], key=lambda r: (-r["n_postings"], -r["weighted_co_count"], r["co_skill_key"]))[:15]
        for idx, row in enumerate(rows, start=1):
            row["rank_order"] = idx
            skill_cooccurrence.append(row)

    # 4. occupation_skill_profile + curriculum_coverage_ref
    occ_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in postings:
        occ_groups[str(p["occupation_cluster"])].append(p)

    occupation_skill_profile: list[dict[str, Any]] = []
    curriculum_coverage_ref: list[dict[str, Any]] = []
    for occ_cluster, occ_rows in sorted(occ_groups.items()):
        n_occ = len(occ_rows)
        w_occ = sum(float(p.get("sample_weight") or 1.0) for p in occ_rows)
        occ_slug = occ_rows[0]["occupation_slug"]
        occ_name_th = occ_rows[0]["occupation_name_th"]

        sk_counts: Counter[str] = Counter()
        sk_weights: defaultdict[str, float] = defaultdict(float)
        for p in occ_rows:
            w = float(p.get("sample_weight") or 1.0)
            for sk_name in p.get("skills_list") or []:
                sk_counts[sk_name] += 1
                sk_weights[sk_name] += w

        ranked_skills = sorted(
            sk_counts.keys(),
            key=lambda s: (-sk_counts[s], -sk_weights[s], extractor.skills_by_name[s].skill_key),
        )
        profile_rows_for_occ: list[dict[str, Any]] = []
        for rank_idx, sk_name in enumerate(ranked_skills, start=1):
            rec = extractor.skills_by_name[sk_name]
            n_sk = sk_counts[sk_name]
            suppressed = n_sk < MIN_PUBLIC_N or n_occ < MIN_PUBLIC_N
            w_share = round(sk_weights[sk_name] / w_occ, 4) if (not suppressed and w_occ > 0) else None
            r_share = round(n_sk / n_occ, 4) if (not suppressed and n_occ > 0) else None
            row = {
                "occupation_cluster": occ_cluster,
                "occupation_slug": occ_slug,
                "occupation_name_th": occ_name_th,
                "skill_key": rec.skill_key,
                "skill_canonical": rec.skill_canonical,
                "skill_slug": rec.skill_slug,
                "skill_name_th": rec.skill_name_th,
                "skill_type": rec.skill_type,
                "skill_group": rec.skill_group,
                "n_occ_postings": n_occ,
                "n_postings": n_sk,
                "weighted_share": w_share,
                "raw_share": r_share,
                "rank_in_occupation": rank_idx,
                "is_suppressed": suppressed,
            }
            occupation_skill_profile.append(row)
            if rank_idx <= 30:
                profile_rows_for_occ.append(row)

        sum_top_share = sum(float(r["weighted_share"] or 0.0) for r in profile_rows_for_occ)
        for r in profile_rows_for_occ:
            imp = (
                round(float(r["weighted_share"]) / sum_top_share, 4)
                if (not r["is_suppressed"] and r["weighted_share"] is not None and sum_top_share > 0)
                else None
            )
            curriculum_coverage_ref.append(
                {
                    "occupation_cluster": r["occupation_cluster"],
                    "occupation_slug": r["occupation_slug"],
                    "occupation_name_th": r["occupation_name_th"],
                    "skill_key": r["skill_key"],
                    "skill_canonical": r["skill_canonical"],
                    "skill_slug": r["skill_slug"],
                    "skill_name_th": r["skill_name_th"],
                    "skill_type": r["skill_type"],
                    "skill_group": r["skill_group"],
                    "n_occ_postings": r["n_occ_postings"],
                    "n_postings": r["n_postings"],
                    "weighted_share": r["weighted_share"],
                    "importance_weight": imp,
                    "rank_order": r["rank_in_occupation"],
                    "is_core_skill": r["rank_in_occupation"] <= 15,
                    "is_suppressed": r["is_suppressed"],
                }
            )

    # 5. salary_stats (matching all grouping sets in 004_marts_and_ml_grants.sql)
    salary_buckets: dict[tuple[str, str, str, str, str, str], list[float]] = defaultdict(list)
    for p in salaried:
        s_mid = float(p["salary_mid"])
        occ = str(p.get("occupation_cluster") or "ไม่ระบุ")
        occ_slug = str(p.get("occupation_slug") or "all")
        reg = str(p.get("region") or "ไม่ระบุ")
        prov = str(p.get("province_th") or "ไม่ระบุ")
        exp = str(p.get("experience_band") or "ไม่ระบุ/ไม่จำเป็น")

        salary_buckets[("national", "ทั้งหมด", "all", "ทั้งประเทศ", "ทั้งประเทศ", "ทั้งหมด")].append(s_mid)
        salary_buckets[("reg", "ทั้งหมด", "all", reg, "ทั้งหมดในภาค", "ทั้งหมด")].append(s_mid)
        salary_buckets[("prov", "ทั้งหมด", "all", reg, prov, "ทั้งหมด")].append(s_mid)
        salary_buckets[("occ", occ, occ_slug, "ทั้งประเทศ", "ทั้งประเทศ", "ทั้งหมด")].append(s_mid)
        salary_buckets[("occ_reg", occ, occ_slug, reg, "ทั้งหมดในภาค", "ทั้งหมด")].append(s_mid)
        salary_buckets[("occ_exp", occ, occ_slug, "ทั้งประเทศ", "ทั้งประเทศ", exp)].append(s_mid)
        salary_buckets[("occ_reg_exp", occ, occ_slug, reg, "ทั้งหมดในภาค", exp)].append(s_mid)
        salary_buckets[("occ_prov_exp", occ, occ_slug, reg, prov, exp)].append(s_mid)

    salary_stats: list[dict[str, Any]] = []
    for (scope_type, occ, occ_slug, reg, prov, exp), vals in sorted(salary_buckets.items()):
        cnt = len(vals)
        suppressed = cnt < MIN_PUBLIC_N
        s_vals = sorted(vals)
        salary_stats.append(
            {
                "scope_type": scope_type,
                "occupation_cluster": occ,
                "occupation_slug": occ_slug,
                "region": reg,
                "province_th": prov,
                "experience_band": exp,
                "n_postings": cnt,
                "salary_p25": round(_quantile(s_vals, 0.25)) if not suppressed else None,
                "salary_p50": round(_quantile(s_vals, 0.50)) if not suppressed else None,
                "salary_p75": round(_quantile(s_vals, 0.75)) if not suppressed else None,
                "salary_mean": round(sum(s_vals) / cnt) if not suppressed else None,
                "salary_min_obs": round(s_vals[0]) if not suppressed else None,
                "salary_max_obs": round(s_vals[-1]) if not suppressed else None,
                "is_suppressed": suppressed,
            }
        )

    # 6. posting_volume_daily
    vol_buckets: dict[tuple[dt.date, str, str, str, bool | None], list[dict[str, Any]]] = defaultdict(list)
    for p in postings:
        d_obj = _parse_date(p.get("date_posted") or p.get("first_seen_date"))
        if d_obj is None:
            continue
        reg = str(p.get("region") or "ไม่ระบุ")
        prov = str(p.get("province_th") or "ไม่ระบุ")
        s14 = bool(p.get("is_south14"))
        vol_buckets[(d_obj, "national", "ทั้งประเทศ", "ทั้งประเทศ", None)].append(p)
        vol_buckets[(d_obj, "region", reg, "ทั้งหมดในภาค", reg == "ใต้")].append(p)
        vol_buckets[(d_obj, "province", reg, prov, s14)].append(p)

    posting_volume_daily: list[dict[str, Any]] = []
    for (d_obj, scope_level, reg, prov, s14), rows in sorted(vol_buckets.items()):
        cnt = len(rows)
        n_sal = sum(1 for r in rows if r.get("has_salary"))
        suppressed = cnt < MIN_PUBLIC_N
        posting_volume_daily.append(
            {
                "date_key": int(d_obj.strftime("%Y%m%d")),
                "full_date": d_obj.isoformat(),
                "year": d_obj.year,
                "month": d_obj.month,
                "week": d_obj.isocalendar().week,
                "week_start": _week_start(d_obj).isoformat(),
                "scope_level": scope_level,
                "region": reg,
                "province_th": prov,
                "is_south14": s14,
                "n_postings": cnt,
                "n_with_salary": n_sal,
                "weighted_volume": round(sum(float(r.get("sample_weight") or 1.0) for r in rows), 2) if not suppressed else None,
                "salary_share": round(n_sal / cnt, 4) if not suppressed else None,
                "is_suppressed": suppressed,
            }
        )

    # 7. top_links (max 5 per occ x prov AND occ national, n >= 5, NO description/qualifications)
    top_links: list[dict[str, Any]] = []
    occ_prov_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for p in postings:
        occ_prov_groups[(str(p["occupation_cluster"]), str(p.get("province_th") or "ไม่ระบุ"))].append(p)

    for (occ, prov), rows in sorted(occ_prov_groups.items()):
        if len(rows) < MIN_PUBLIC_N:
            continue
        sorted_rows = sorted(
            rows,
            key=lambda r: (str(r.get("date_posted") or ""), str(r.get("source_job_id") or "")),
            reverse=True,
        )[:5]
        for idx, r in enumerate(sorted_rows, start=1):
            top_links.append(
                {
                    "occupation_cluster": occ,
                    "occupation_slug": r["occupation_slug"],
                    "province_th": prov,
                    "region": r["region"],
                    "source_name": r["source"],
                    "source_url": r["source_url"],
                    "title_short": str(r["title_short"])[:120],
                    "date_posted": r.get("date_posted"),
                    "n_postings": len(rows),
                    "rank_order": idx,
                }
            )

    for occ, rows in sorted(occ_groups.items()):
        if len(rows) < MIN_PUBLIC_N:
            continue
        sorted_rows = sorted(
            rows,
            key=lambda r: (str(r.get("date_posted") or ""), str(r.get("source_job_id") or "")),
            reverse=True,
        )[:5]
        for idx, r in enumerate(sorted_rows, start=1):
            top_links.append(
                {
                    "occupation_cluster": occ,
                    "occupation_slug": r["occupation_slug"],
                    "province_th": "ทั้งประเทศ",
                    "region": "ทั้งประเทศ",
                    "source_name": r["source"],
                    "source_url": r["source_url"],
                    "title_short": str(r["title_short"])[:120],
                    "date_posted": r.get("date_posted"),
                    "n_postings": len(rows),
                    "rank_order": idx,
                }
            )

    # 8. pipeline_status & dq_summary (Admin-only views)
    pipeline_status = [
        {
            "scrape_run_id": 1,
            "source": "jobthai",
            "scope": "spike_sample_and_by_province",
            "started_at": now_iso,
            "finished_at": now_iso,
            "status": "done",
            "n_discovered": n_total,
            "n_fetched": n_total,
            "n_failed": 0,
            "is_blocked_flag": False,
            "duration_seconds": 1.0,
            "n_listings_seen": n_total,
        }
    ]
    dq_summary = [
        {
            "dq_id": idx,
            "scrape_run_id": 1,
            "source": "jobthai",
            "dimension": dq["dimension"],
            "check_name": dq["check_name"],
            "table_name": dq["table_name"],
            "n_total": dq["n_total"],
            "n_fail": dq["n_fail"],
            "fail_rate": round(100.0 * dq["n_fail"] / dq["n_total"], 2) if dq["n_total"] else 0.0,
            "pass": dq["pass"],
            "details": dq["details"],
            "checked_at": now_iso,
        }
        for idx, dq in enumerate(dq_results, start=1)
    ]

    # 9. pending_aliases (NO raw descriptions!)
    pending_out = [
        {
            "suggestion_id": idx,
            "pending_alias": item["alias"],
            "freq": item["freq"],
            "status": "pending",
            "suggested_skill_key": item.get("suggested_skill_key"),
            "suggested_skill_canonical": item.get("suggested_skill_canonical"),
            "suggested_matched_alias": item.get("suggested_matched_alias"),
            "similarity_score": item.get("similarity_score"),
        }
        for idx, item in enumerate(pending_aliases, start=1)
    ]

    # 10. Dimension references for offline/seed parity with RPCs
    aliases_by_skill: dict[str, list[str]] = defaultdict(list)
    for ca in extractor.aliases:
        aliases_by_skill[ca.skill_canonical].append(ca.alias)

    dim_skills = [
        {
            "skill_key": rec.skill_key,
            "skill_canonical": rec.skill_canonical,
            "skill_slug": rec.skill_slug,
            "skill_name_th": rec.skill_name_th,
            "skill_type": rec.skill_type,
            "skill_group": rec.skill_group,
            "onet_ref": rec.onet_ref,
            "esco_ref": rec.esco_ref,
            "aliases": sorted(aliases_by_skill.get(rec.skill_canonical, [])),
        }
        for rec in sorted(extractor.skills_by_key.values(), key=lambda r: r.skill_canonical)
    ]

    title_counts = Counter(p["occupation_cluster"] for p in postings)
    dim_occupations = [
        {
            "occupation_cluster": occ.occupation_cluster,
            "occupation_slug": occ.occupation_slug,
            "occupation_name_th": occ.occupation_name_th,
            "onet_ref": occ.onet_ref,
            "n_titles": int(title_counts.get(occ.occupation_cluster, 0)),
        }
        for occ in sorted(mapper.clusters, key=lambda o: o.occupation_cluster)
    ]

    dim_locations = [
        {
            "location_key": idx,
            "province_code": meta[0],
            "province_th": prov_th,
            "province_en": meta[1],
            "region": meta[2],
            "is_south14": meta[3],
        }
        for idx, (prov_th, meta) in enumerate(sorted(PROVINCE_META.items(), key=lambda kv: kv[1][0]), start=1)
    ]

    return {
        "public_summary": public_summary,
        "skill_demand_weekly": skill_demand_weekly,
        "skill_cooccurrence": skill_cooccurrence,
        "occupation_skill_profile": occupation_skill_profile,
        "salary_stats": salary_stats,
        "posting_volume_daily": posting_volume_daily,
        "curriculum_coverage_ref": curriculum_coverage_ref,
        "pipeline_status": pipeline_status,
        "dq_summary": dq_summary,
        "top_links": top_links,
        "pending_aliases": pending_out,
        "dim_skills": dim_skills,
        "dim_occupations": dim_occupations,
        "dim_locations": dim_locations,
    }


def write_seed_marts(marts: dict[str, Any], out_path: Path | str) -> Path:
    """Write seed_marts.json safely (UTF-8, pretty JSON), preserving ML keys if already present."""
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    existing_ml: dict[str, Any] = {}
    if target.exists():
        try:
            prev = json.loads(target.read_text(encoding="utf-8"))
            for key in ("ml_leaderboard", "ml_feature_importance", "salary_prediction"):
                if key in prev and prev[key]:
                    existing_ml[key] = prev[key]
        except Exception:
            pass
    merged = dict(marts)
    for key in ("ml_leaderboard", "ml_feature_importance", "salary_prediction"):
        merged.setdefault(key, existing_ml.get(key, []))
    with open(target, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return target
