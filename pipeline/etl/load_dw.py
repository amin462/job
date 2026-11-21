"""Data Warehouse loader and stratified weight/date calculator (T3.4).

Supports both offline DW preparation (used to generate clean_postings.csv and
seed_marts.json) and idempotent PostgreSQL loading when DATABASE_URL is given.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from pipeline.etl.clean import PROVINCE_META, normalize_province
from pipeline.etl.extract_skills import SkillExtractor
from pipeline.etl.map_taxonomy import OccupationMapper

REPO_ROOT = Path(__file__).resolve().parents[2]
SPIKE_PROVINCE_TOTALS = REPO_ROOT / "spike" / "raw" / "jobthai" / "by_province" / "province_totals.csv"
# Fresh N_h per province / per province x jobtype cell from the JobThai harvester listing totals
# (written by `py -X utf8 -m pipeline.scraper.import_sqlite`); falls back to the spike file.
HARVEST_PROVINCE_TOTALS = REPO_ROOT / "data" / "processed" / "jobthai_province_totals.csv"
HARVEST_STRATA_CSV = REPO_ROOT / "data" / "processed" / "jobthai_strata.csv"
DEFAULT_PROVINCE_TOTALS = (
    HARVEST_PROVINCE_TOTALS if HARVEST_PROVINCE_TOTALS.exists() else SPIKE_PROVINCE_TOTALS
)


def _resolve_province_totals_csv(province_totals_csv: Path | str | None) -> Path:
    if province_totals_csv is not None:
        return Path(province_totals_csv)
    if HARVEST_PROVINCE_TOTALS.exists():
        return HARVEST_PROVINCE_TOTALS
    return SPIKE_PROVINCE_TOTALS


def load_province_population_maps(
    province_totals_csv: Path | str | None = None,
) -> tuple[dict[str, int], dict[str, int]]:
    """Load province population N_h keyed by (province_th, province_code)."""
    by_prov: dict[str, int] = {}
    by_code: dict[str, int] = {}
    path = _resolve_province_totals_csv(province_totals_csv)
    if not path.exists():
        return by_prov, by_code
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            prov = normalize_province(row.get("province"))["province_th"]
            code = str(row.get("code") or "").strip()
            if code.isdigit():
                code = code.zfill(2)
            try:
                total = int(float(row.get("total") or 0))
            except ValueError:
                total = 0
            by_prov[prov] = by_prov.get(prov, 0) + total
            if code:
                by_code[code] = by_code.get(code, 0) + total
    return by_prov, by_code


def load_province_population(province_totals_csv: Path | str = DEFAULT_PROVINCE_TOTALS) -> dict[str, int]:
    """Load reference stratum population N_h keyed by canonical province_th."""
    by_prov, _ = load_province_population_maps(province_totals_csv)
    return by_prov


def load_strata_population(strata_csv: Path | str | None = HARVEST_STRATA_CSV) -> dict[str, int]:
    """Load cell population N_h keyed by stratum string (`p=<prov>|c=<jobtype>`)."""
    pop: dict[str, int] = {}
    if strata_csv is None:
        return pop
    path = Path(strata_csv)
    if not path.exists():
        return pop
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            st = str(row.get("stratum") or "").strip()
            if not st:
                continue
            try:
                n_h = int(float(row.get("N_h") or 0))
            except ValueError:
                n_h = 0
            pop[st] = n_h
    return pop


def _unpack_seen_entry(entry: Any) -> tuple[str | None, str | None, str | None]:
    """Support (first, last), (first, last, stratum), or dict entry in listing_seen_history."""
    if isinstance(entry, dict):
        return (
            entry.get("first_seen"),
            entry.get("last_seen"),
            entry.get("stratum"),
        )
    if isinstance(entry, (tuple, list)):
        first_s = entry[0] if len(entry) >= 1 else None
        last_s = entry[1] if len(entry) >= 2 else None
        stratum = entry[2] if len(entry) >= 3 else None
        return first_s, last_s, stratum
    return None, None, None


def _extract_province_code_from_stratum(stratum: str) -> str | None:
    for part in stratum.split("|"):
        if part.startswith("p="):
            code = part[2:].strip()
            if code.isdigit():
                return code.zfill(2)
            return code or None
    return None


def date_to_key(date_str: str | None, fallback: str | None = None) -> int | None:
    """Convert YYYY-MM-DD string to integer YYYYMMDD date_key."""
    val = (date_str or fallback or "").strip()[:10]
    if not val:
        return None
    try:
        parsed = dt.date.fromisoformat(val)
        return int(parsed.strftime("%Y%m%d"))
    except ValueError:
        return None


def compute_weights_and_seen_dates(
    postings: list[dict[str, Any]],
    province_totals_csv: Path | str | None = None,
    listing_seen_history: dict[tuple[str, str], Any] | None = None,
    default_seen_date: str | None = None,
    strata_csv: Path | str | None = HARVEST_STRATA_CSV,
) -> dict[str, float]:
    """Assign sample_stratum, sample_weight (N_h / n_h), and first/last_seen date keys.

    Stratum resolution order per posting:
    1. `stratum` from `staging.listing_seen` (via `listing_seen_history` or `p["listing_stratum"]`).
    2. Fallback `p=<province_code>|c=all` when no listing_seen record exists.

    Population N_h resolution:
    - Cell stratum (`|c=` present and not `|c=all`, non-JobBKK): from `jobthai_strata.csv`.
    - Province-only stratum (no `|c=`, or `|c=all`): from `jobthai_province_totals.csv`
      (or spike `province_totals.csv` fallback).

    Returns `{stratum: N_h}` reference map for DQ sampling validation.
    """
    pop_by_prov, pop_by_code = load_province_population_maps(province_totals_csv)
    pop_by_stratum = load_strata_population(strata_csv)
    stratum_counts: dict[str, int] = {}
    stratum_pop: dict[str, float] = {}

    for p in postings:
        source = str(p.get("source") or "jobthai")
        job_id = str(p.get("source_job_id") or "")
        key = (source, job_id)
        seen_entry = listing_seen_history.get(key) if listing_seen_history else None
        first_seen, last_seen, seen_stratum = _unpack_seen_entry(seen_entry)

        raw_stratum = str(seen_stratum or p.get("listing_stratum") or p.get("sample_stratum") or "").strip()
        p_code = str(p.get("province_code") or "00")
        p_th = str(p.get("province_th") or "ไม่ระบุ")
        if raw_stratum and raw_stratum != "unknown":
            stratum = raw_stratum
        else:
            stratum = f"p={p_code}|c=all"

        p["sample_stratum"] = stratum
        stratum_counts[stratum] = stratum_counts.get(stratum, 0) + 1

        if stratum not in stratum_pop:
            if stratum.startswith("jobbkk|"):
                n_pop = 0.0
            elif "|c=" in stratum and not stratum.endswith("|c=all"):
                n_pop = float(pop_by_stratum.get(stratum, 0))
            else:
                st_code = _extract_province_code_from_stratum(stratum)
                if st_code and st_code in pop_by_code:
                    n_pop = float(pop_by_code[st_code])
                else:
                    n_pop = float(pop_by_prov.get(p_th, 0))
            stratum_pop[stratum] = n_pop

        p["_resolved_seen_pair"] = (first_seen, last_seen)

    for p in postings:
        stratum = str(p["sample_stratum"])
        n_h = stratum_counts.get(stratum, 1)
        n_pop = stratum_pop.get(stratum, 0.0)
        p["sample_weight"] = round(n_pop / n_h, 6) if n_pop > 0 and n_h > 0 else 1.0

        first_s, last_s = p.pop("_resolved_seen_pair", (None, None))
        if not first_s:
            fallback_d = str(p.get("date_posted") or default_seen_date or dt.date.today().isoformat())[:10]
            first_s = fallback_d
            last_s = str(default_seen_date or fallback_d)[:10]
        elif not last_s:
            last_s = first_s
        if last_s < first_s:
            last_s = first_s

        p["first_seen_date"] = str(first_s)[:10]
        p["last_seen_date"] = str(last_s)[:10]
        p["first_seen_date_key"] = date_to_key(p["first_seen_date"])
        p["last_seen_date_key"] = date_to_key(p["last_seen_date"])

    return {st: n_pop for st, n_pop in stratum_pop.items() if n_pop > 0}


def upsert_dw_to_postgres(
    database_url: str,
    postings: list[dict[str, Any]],
    dq_results: list[dict[str, Any]],
    pending_aliases: list[dict[str, Any]],
    extractor: SkillExtractor,
    mapper: OccupationMapper,
    scrape_run_meta: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Idempotently load taxonomy, staging metadata, DW dims/facts, and pending aliases."""
    import psycopg

    counts = {"postings_upserted": 0, "skills_upserted": 0, "aliases_upserted": 0, "dq_inserted": 0}
    run_meta = scrape_run_meta or {
        "source": "jobthai",
        "scope": "sample_etl_load",
        "status": "done",
        "n_discovered": len(postings),
        "n_fetched": len(postings),
        "n_failed": 0,
    }

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            # 1. Insert scrape_run row for audit trail
            cur.execute(
                """
                insert into staging.scrape_run (source, scope, status, finished_at, n_discovered, n_fetched, n_failed)
                values (%s, %s, %s, now(), %s, %s, %s)
                returning scrape_run_id
                """,
                (
                    run_meta["source"],
                    run_meta.get("scope"),
                    run_meta.get("status", "done"),
                    int(run_meta.get("n_discovered", len(postings))),
                    int(run_meta.get("n_fetched", len(postings))),
                    int(run_meta.get("n_failed", 0)),
                ),
            )
            scrape_run_id = cur.fetchone()[0]

            # 2. Upsert dim_skill & skill_alias
            skill_key_by_name: dict[str, int] = {}
            for rec in extractor.skills_by_key.values():
                cur.execute(
                    """
                    insert into dw.dim_skill (skill_canonical, skill_slug, skill_name_th, skill_type, skill_group, onet_ref, esco_ref)
                    values (%s, %s, %s, %s, %s, %s, %s)
                    on conflict (skill_canonical) do update set
                      skill_slug    = excluded.skill_slug,
                      skill_name_th = excluded.skill_name_th,
                      skill_type    = excluded.skill_type,
                      skill_group   = excluded.skill_group,
                      onet_ref      = excluded.onet_ref,
                      esco_ref      = excluded.esco_ref
                    returning skill_key
                    """,
                    (
                        rec.skill_canonical,
                        rec.skill_slug,
                        rec.skill_name_th,
                        rec.skill_type,
                        rec.skill_group,
                        rec.onet_ref,
                        rec.esco_ref,
                    ),
                )
                skill_key_by_name[rec.skill_canonical] = cur.fetchone()[0]
                counts["skills_upserted"] += 1

            alias_id_by_text: dict[str, int] = {}
            for ca in extractor.aliases:
                sk = skill_key_by_name[ca.skill_canonical]
                cur.execute(
                    """
                    insert into dw.skill_alias (skill_key, alias, lang, match_type, status)
                    values (%s, %s, %s, %s, 'approved')
                    on conflict (alias) do update set
                      skill_key  = excluded.skill_key,
                      lang       = excluded.lang,
                      match_type = excluded.match_type,
                      status     = 'approved'
                    returning alias_id
                    """,
                    (sk, ca.alias, ca.lang, ca.match_type),
                )
                alias_id_by_text[ca.alias] = cur.fetchone()[0]
                counts["aliases_upserted"] += 1

            # 3. Lookup static dimensions
            cur.execute("select source_name, source_key from dw.dim_source")
            source_map = dict(cur.fetchall())
            cur.execute("select level_th, education_key from dw.dim_education")
            edu_map = dict(cur.fetchall())
            cur.execute("select band_th, experience_key from dw.dim_experience")
            exp_map = dict(cur.fetchall())
            cur.execute("select type_th, employment_type_key from dw.dim_employment_type")
            emp_map = dict(cur.fetchall())

            # 4. Ensure dim_date covers posting dates
            for p in postings:
                for d_str in (p.get("date_posted"), p.get("valid_through"), p.get("first_seen_date"), p.get("last_seen_date")):
                    if not d_str:
                        continue
                    dk = date_to_key(d_str)
                    if dk is not None:
                        d_obj = dt.date.fromisoformat(d_str[:10])
                        iso_week = d_obj.isocalendar()
                        cur.execute(
                            """
                            insert into dw.dim_date (date_key, full_date, year, quarter, month, week, day_of_week, is_weekend)
                            values (%s, %s, %s, %s, %s, %s, %s, %s)
                            on conflict (date_key) do nothing
                            """,
                            (
                                dk,
                                d_obj,
                                d_obj.year,
                                (d_obj.month - 1) // 3 + 1,
                                d_obj.month,
                                iso_week.week,
                                d_obj.isoweekday(),
                                d_obj.isoweekday() in (6, 7),
                            ),
                        )

            # 5. Upsert dynamic dims and fact rows
            for p in postings:
                src_key = source_map.get(p.get("source", "jobthai"), source_map["jobthai"])
                prov_th = p.get("province_th") or "ไม่ระบุ"
                dist_th = p.get("district_th") or ""
                meta = PROVINCE_META.get(prov_th, ("00", "Unspecified", "ไม่ระบุ", False))
                cur.execute(
                    """
                    insert into dw.dim_location (province_code, province_th, province_en, district_th, region, is_south14)
                    values (%s, %s, %s, %s, %s, %s)
                    on conflict (province_th, district_th) do update set
                      province_code = excluded.province_code,
                      province_en   = excluded.province_en,
                      region        = excluded.region,
                      is_south14    = excluded.is_south14
                    returning location_key
                    """,
                    (meta[0], prov_th, meta[1], dist_th, meta[2], meta[3]),
                )
                loc_key = cur.fetchone()[0]

                cur.execute(
                    """
                    insert into dw.dim_company (company_name_norm, industry)
                    values (%s, %s)
                    on conflict (company_name_norm) do update set
                      industry = coalesce(excluded.industry, dw.dim_company.industry)
                    returning company_key
                    """,
                    (p["company_name_norm"], p.get("industry")),
                )
                comp_key = cur.fetchone()[0]

                cur.execute(
                    """
                    insert into dw.dim_occupation (occupation_cluster, occupation_slug, occupation_name_th, job_title_norm, onet_ref)
                    values (%s, %s, %s, %s, %s)
                    on conflict (occupation_cluster, job_title_norm) do update set
                      occupation_slug    = excluded.occupation_slug,
                      occupation_name_th = excluded.occupation_name_th,
                      onet_ref           = excluded.onet_ref
                    returning occupation_key
                    """,
                    (
                        p["occupation_cluster"],
                        p["occupation_slug"],
                        p["occupation_name_th"],
                        p["job_title_norm"],
                        p.get("onet_ref") or None,
                    ),
                )
                occ_key = cur.fetchone()[0]

                emp_type = p.get("employment_type") or "ไม่ระบุ"
                if emp_type not in emp_map:
                    cur.execute(
                        "insert into dw.dim_employment_type (type_th) values (%s) on conflict (type_th) do nothing",
                        (emp_type,),
                    )
                    cur.execute("select employment_type_key from dw.dim_employment_type where type_th = %s", (emp_type,))
                    emp_map[emp_type] = cur.fetchone()[0]

                cur.execute(
                    """
                    insert into dw.fact_job_posting (
                      source_key, source_job_id, source_url, title_short,
                      date_posted_key, valid_through_key, location_key, company_key, occupation_key,
                      education_key, experience_key, employment_type_key,
                      salary_min, salary_max, salary_mid, salary_open_max, salary_unit_orig,
                      n_skills, first_seen_date_key, last_seen_date_key,
                      sample_stratum, sample_weight, scrape_run_id
                    ) values (
                      %s, %s, %s, %s,
                      %s, %s, %s, %s, %s,
                      %s, %s, %s,
                      %s, %s, %s, %s, %s,
                      %s, %s, %s,
                      %s, %s, %s
                    )
                    on conflict (source_key, source_job_id) do update set
                      source_url          = excluded.source_url,
                      title_short         = excluded.title_short,
                      date_posted_key     = excluded.date_posted_key,
                      valid_through_key   = excluded.valid_through_key,
                      location_key        = excluded.location_key,
                      company_key         = excluded.company_key,
                      occupation_key      = excluded.occupation_key,
                      education_key       = excluded.education_key,
                      experience_key      = excluded.experience_key,
                      employment_type_key = excluded.employment_type_key,
                      salary_min          = excluded.salary_min,
                      salary_max          = excluded.salary_max,
                      salary_mid          = excluded.salary_mid,
                      salary_open_max     = excluded.salary_open_max,
                      salary_unit_orig    = excluded.salary_unit_orig,
                      n_skills            = excluded.n_skills,
                      first_seen_date_key = least(dw.fact_job_posting.first_seen_date_key, excluded.first_seen_date_key),
                      last_seen_date_key  = greatest(dw.fact_job_posting.last_seen_date_key, excluded.last_seen_date_key),
                      sample_stratum      = excluded.sample_stratum,
                      sample_weight       = excluded.sample_weight,
                      scrape_run_id       = excluded.scrape_run_id
                    returning posting_key
                    """,
                    (
                        src_key,
                        p["source_job_id"],
                        p["source_url"],
                        p["title_short"],
                        date_to_key(p.get("date_posted")),
                        date_to_key(p.get("valid_through")),
                        loc_key,
                        comp_key,
                        occ_key,
                        edu_map.get(p.get("education_level"), edu_map["ไม่ระบุ"]),
                        exp_map.get(p.get("experience_band"), exp_map["ไม่ระบุ/ไม่จำเป็น"]),
                        emp_map[emp_type],
                        p.get("salary_min"),
                        p.get("salary_max"),
                        p.get("salary_mid"),
                        bool(p.get("salary_open_max")),
                        p.get("salary_unit_orig"),
                        int(p.get("n_skills", 0)),
                        p.get("first_seen_date_key"),
                        p.get("last_seen_date_key"),
                        p.get("sample_stratum"),
                        float(p.get("sample_weight", 1.0)),
                        scrape_run_id,
                    ),
                )
                posting_key = cur.fetchone()[0]
                counts["postings_upserted"] += 1

                # Replace bridge skills idempotently for this posting
                cur.execute("delete from dw.fact_posting_skill where posting_key = %s", (posting_key,))
                for skill_name, alias_str in (p.get("matched_aliases") or {}).items():
                    sk = skill_key_by_name.get(skill_name)
                    if sk is None:
                        continue
                    aid = alias_id_by_text.get(alias_str)
                    cur.execute(
                        """
                        insert into dw.fact_posting_skill (posting_key, skill_key, match_alias_id)
                        values (%s, %s, %s)
                        on conflict (posting_key, skill_key) do nothing
                        """,
                        (posting_key, sk, aid),
                    )

            # 6. Insert DQ results
            for dq in dq_results:
                cur.execute(
                    """
                    insert into staging.dq_result (scrape_run_id, dimension, check_name, table_name, n_total, n_fail, pass, details)
                    values (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        scrape_run_id,
                        dq["dimension"],
                        dq["check_name"],
                        dq["table_name"],
                        int(dq["n_total"]),
                        int(dq["n_fail"]),
                        bool(dq["pass"]),
                        dq["details"],
                    ),
                )
                counts["dq_inserted"] += 1

            # 7. Sync pending alias suggestions without creating duplicates
            for item in pending_aliases:
                cur.execute(
                    "select id from public.app_alias_suggestion where alias = %s and status = 'pending' limit 1",
                    (item["alias"],),
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        "update public.app_alias_suggestion set freq = %s, skill_key = %s where id = %s",
                        (int(item["freq"]), item.get("suggested_skill_key"), existing[0]),
                    )
                else:
                    cur.execute(
                        """
                        insert into public.app_alias_suggestion (alias, skill_key, status, freq, sample_context)
                        values (%s, %s, 'pending', %s, %s)
                        """,
                        (item["alias"], item.get("suggested_skill_key"), int(item["freq"]), None),
                    )
        conn.commit()
    return counts
