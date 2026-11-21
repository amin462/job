"""Rule-based occupation cluster mapping from title and category (T2.5)."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from pipeline.etl.clean import normalize_thai_text

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OCCUPATIONS_CSV = REPO_ROOT / "taxonomy" / "occupations.csv"

_ASCII_RX = re.compile(r"^[A-Za-z0-9\s.&/+-]+$")
_TITLE_DECOR_RX = re.compile(
    r"(?i)(?:ด่วน\s*!+|รับด่วน\s*!*|\[[^\]]*\]|\(สัญญาจ้าง[^)]*\)|\(fixed\s*term[^)]*\)|@\S+)"
)


@dataclass(frozen=True)
class OccupationCluster:
    occupation_cluster: str
    occupation_slug: str
    occupation_name_th: str
    keywords_th: tuple[str, ...]
    keywords_en: tuple[str, ...]
    job_category_hints: tuple[str, ...]
    onet_ref: str


def normalize_job_title(title: str | None) -> tuple[str, str]:
    """Return `(job_title_norm, title_short)` without raw description text."""
    raw = normalize_thai_text(title)
    if not raw:
        return "unspecified", ""
    short = raw[:120].strip()
    cleaned = _TITLE_DECOR_RX.sub(" ", raw)
    cleaned = re.sub(r"[()\[\],/|]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return (cleaned[:80].strip() or short[:80].lower()), short


class OccupationMapper:
    """Deterministic keyword + category rule mapper for occupation clusters."""

    def __init__(self, occupations_csv: Path | str = DEFAULT_OCCUPATIONS_CSV) -> None:
        self.clusters: list[OccupationCluster] = []
        self._en_patterns: dict[str, list[tuple[str, re.Pattern[str]]]] = {}

        with open(occupations_csv, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                kw_th = tuple(k.strip() for k in (row.get("keywords_th") or "").split("|") if k.strip())
                kw_en = tuple(k.strip().lower() for k in (row.get("keywords_en") or "").split("|") if k.strip())
                hints = tuple(k.strip() for k in (row.get("job_category_hints") or "").split("|") if k.strip())
                occ = OccupationCluster(
                    occupation_cluster=row["occupation_cluster"].strip(),
                    occupation_slug=row["occupation_slug"].strip(),
                    occupation_name_th=row["occupation_name_th"].strip(),
                    keywords_th=kw_th,
                    keywords_en=kw_en,
                    job_category_hints=hints,
                    onet_ref=(row.get("onet_ref") or "").strip(),
                )
                self.clusters.append(occ)
                pats: list[tuple[str, re.Pattern[str]]] = []
                for kw in kw_en:
                    esc = re.sub(r"\\ ", r"\\s+", re.escape(kw))
                    pats.append((kw, re.compile(rf"(?<![A-Za-z0-9]){esc}(?![A-Za-z0-9])", re.I)))
                self._en_patterns[occ.occupation_cluster] = pats

    def map_posting(self, title: str | None, occupational_category: str | None = None) -> dict[str, str]:
        """Map job title + occupational_category to a canonical occupation cluster."""
        title_norm_text = normalize_thai_text(title)
        cat_norm_text = normalize_thai_text(occupational_category)
        job_title_norm, title_short = normalize_job_title(title)

        best_occ: OccupationCluster | None = None
        best_score = 0.0

        for occ in self.clusters:
            score = 0.0
            if cat_norm_text:
                for hint in occ.job_category_hints:
                    if cat_norm_text == hint:
                        score += 4.0
                        break
                    if hint in cat_norm_text or cat_norm_text in hint:
                        score += 2.5
                        break

            if title_norm_text:
                for kw in occ.keywords_th:
                    if kw in title_norm_text:
                        score += 3.0 + 0.05 * len(kw)
                for kw, pat in self._en_patterns[occ.occupation_cluster]:
                    if pat.search(title_norm_text):
                        score += 3.0 + 0.05 * len(kw)

            if score > best_score:
                best_score = score
                best_occ = occ

        if best_occ is None or best_score <= 0.0:
            return {
                "occupation_cluster": "Other / General",
                "occupation_slug": "other-general",
                "occupation_name_th": "อื่นๆ / ทั่วไป",
                "onet_ref": "",
                "job_title_norm": job_title_norm,
                "title_short": title_short,
                "mapped": False,
            }

        return {
            "occupation_cluster": best_occ.occupation_cluster,
            "occupation_slug": best_occ.occupation_slug,
            "occupation_name_th": best_occ.occupation_name_th,
            "onet_ref": best_occ.onet_ref,
            "job_title_norm": job_title_norm,
            "title_short": title_short,
            "mapped": True,
        }
