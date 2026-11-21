"""Rule-based skill extraction and pending-alias discovery (T2.4, T2.6).

CRITICAL RULES (PLAN D7, D18; AGENTS.md §1):
- Uses dictionary + alias matching + PyThaiNLP `newmm` tokenization ONLY.
- Pending alias queue uses character trigram similarity (`pg_trgm` style) ONLY.
- NEVER uses any LLM / AI model for skill extraction or alias suggestion.
"""
from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pythainlp.corpus import thai_stopwords
from pythainlp.tokenize import word_tokenize

from pipeline.etl.clean import normalize_thai_text

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SKILLS_CSV = REPO_ROOT / "taxonomy" / "skills.csv"
DEFAULT_ALIASES_CSV = REPO_ROOT / "taxonomy" / "aliases.csv"

_ASCII_WORD_RX = re.compile(r"^[A-Za-z0-9\s._/+-]+$")
_EN_TOKEN_RX = re.compile(r"[A-Za-z][A-Za-z0-9.+#/-]{1,30}")
_THAI_CHAR_RX = re.compile(r"[\u0e00-\u0e7f]")
_PURE_NUM_PUNCT_RX = re.compile(r"^[\d\W_]+$")

_DOMAIN_STOPWORDS: frozenset[str] = frozenset(
    {
        "บริษัท",
        "จำกัด",
        "มหาชน",
        "รับสมัคร",
        "พนักงาน",
        "เจ้าหน้าที่",
        "ตำแหน่ง",
        "หน้าที่",
        "ความรับผิดชอบ",
        "คุณสมบัติ",
        "สวัสดิการ",
        "เงินเดือน",
        "ทำงาน",
        "ปฏิบัติงาน",
        "วัน",
        "เดือน",
        "ปี",
        "บาท",
        "สาขา",
        "จังหวัด",
        "อำเภอ",
        "เขต",
        "ติดต่อ",
        "ด่วน",
        "เพศ",
        "อายุ",
        "วุฒิ",
        "วุฒิการศึกษา",
        "การศึกษา",
        "ปริญญาตรี",
        "ป.ตรี",
        "ปวส",
        "ปวช",
        "ม.6",
        "ม.3",
        "สามารถ",
        "ประสบการณ์",
        "พิจารณา",
        "พิจารณาเป็นพิเศษ",
        "อื่นๆ",
        "ฯลฯ",
        "ดูแล",
        "ตรวจสอบ",
        "จัดทำ",
        "สนับสนุน",
        "บริหาร",
        "จัดการ",
        "ดำเนินการ",
        "รายละเอียด",
        "เพิ่มเติม",
        "สมัคร",
        "สัมภาษณ์",
        "รายได้",
        "โบนัส",
        "ประกัน",
        "ประกันสังคม",
        "วันหยุด",
        "เวลา",
        "ล่วงเวลา",
        "ค่าคอมมิชชั่น",
        "คอมมิชชั่น",
        "เบี้ยขยัน",
        "ค่าเดินทาง",
        "ค่าอาหาร",
        "เครื่องแบบ",
        "ที่พัก",
        "รักษาพยาบาล",
        "พื้นที่",
        "ภาค",
        "ประเทศไทย",
        "กรุงเทพ",
        "กรุงเทพมหานคร",
        "ประจำ",
        "ทุก",
        "หลาย",
        "อัตรา",
        "ขึ้นไป",
        "อย่างน้อย",
        "ไม่จำกัด",
        "ยินดี",
        "จบใหม่",
        "นักศึกษา",
        "สินค้า",
        "ลูกค้า",
        "องค์กร",
        "มาตรฐาน",
        "ระบบ",
        "ข้อมูล",
        "งาน",
        "ด้าน",
        "สายงาน",
        "และ",
        "หรือ",
        "ใน",
        "ของ",
        "ที่",
        "ให้",
        "ได้",
        "มี",
        "เป็น",
        "การ",
        "ทาง",
        "ตาม",
        "ไม่",
        "ต้อง",
        "มาก",
        "ดี",
        "สูง",
        "พร้อม",
        "เริ่ม",
        "ผ่าน",
        "สำหรับ",
        "เกี่ยวกับ",
        "ต่าง",
        "ต่างๆ",
        "ภายใน",
        "ภายนอก",
        "ทั้ง",
        "กับ",
        "จาก",
        "ต่อ",
        "โดย",
        "เพื่อ",
        "แบบ",
        "ตามที่",
        "หาก",
        "ถ้า",
        "ผู้",
        "คน",
        "นี้",
        "นั้น",
        "และ/หรือ",
        "มีประสบการณ์",
        "ทักษะ",
        "การทำงาน",
        "มีความรู้",
        "เป็นพิเศษ",
        "รับมอบหมาย",
        "ยอดขาย",
        "ได้ดี",
        "เสาร์",
        "อาทิตย์",
        "สัปดาห์",
        "จันทร์",
        "ศุกร์",
        "หยุด",
        "บริการ",
        "รายงาน",
        "ยอด",
        "ร้าน",
        "สาขา",
        "ค่าคอม",
        "คอมมิชชั่น",
        "ค่าคอมมิชชัน",
        "เบี้ยเลี้ยง",
        "สัญญาจ้าง",
        "ประจำ",
        "และ",
        "ทำงานเป็น",
        "สามารถใช้",
        "เข้าเยี่ยม",
        "เป้าหมาย",
        "สอดคล้อง",
        "มาตรฐาน",
        "เรียบร้อย",
        "มีประสิทธิภาพ",
        "คล่องแคล่ว",
        "ใจรัก",
        "บุคลิก",
        "บุคลิกดี",
        "สุภาพ",
        "รับผิดชอบ",
        "ขยัน",
        "อดทน",
        "มนุษยสัมพันธ์",
        "and",
        "or",
        "the",
        "for",
        "with",
        "from",
        "that",
        "this",
        "have",
        "has",
        "will",
        "are",
        "is",
        "in",
        "on",
        "at",
        "to",
        "of",
        "by",
        "as",
        "an",
        "be",
        "all",
        "other",
        "others",
        "job",
        "work",
        "working",
        "company",
        "position",
        "responsibilities",
        "requirements",
        "qualifications",
        "experience",
        "years",
        "year",
        "degree",
        "bachelor",
        "good",
        "strong",
        "ability",
        "skills",
        "skill",
        "knowledge",
        "team",
        "including",
        "related",
        "field",
        "etc",
        "co",
        "ltd",
        "thailand",
        "full",
        "time",
        "male",
        "female",
        "age",
    }
)


@dataclass(frozen=True)
class SkillRecord:
    skill_key: int
    skill_canonical: str
    skill_slug: str
    skill_name_th: str
    skill_type: str
    skill_group: str
    onet_ref: str
    esco_ref: str


@dataclass(frozen=True)
class CompiledAlias:
    alias: str
    skill_canonical: str
    lang: str
    match_type: str
    pattern: re.Pattern[str] | None
    token_seq: tuple[str, ...] | None


def _needs_case_sensitive_regex(pattern_str: str) -> bool:
    """Detect single-letter uppercase token regexes (e.g. R or C) that must stay case-sensitive."""
    return bool(re.search(r"\)\s*[RC]\s*\(", pattern_str))


def _compile_alias(row: dict[str, str]) -> CompiledAlias:
    alias = row["alias"].strip()
    match_type = (row.get("match_type") or "exact").strip().lower()
    lang = (row.get("lang") or "en").strip().lower()
    skill_canonical = row["skill_canonical"].strip()

    if match_type == "regex":
        flags = 0 if _needs_case_sensitive_regex(alias) else re.I
        return CompiledAlias(alias, skill_canonical, lang, match_type, re.compile(alias, flags), None)

    if match_type == "word_boundary":
        escaped = re.sub(r"\\ ", r"\\s+", re.escape(alias))
        pat = re.compile(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])", re.I)
        return CompiledAlias(alias, skill_canonical, lang, match_type, pat, None)

    if match_type == "token":
        toks = tuple(t.lower() for t in word_tokenize(normalize_thai_text(alias), engine="newmm", keep_whitespace=False) if t.strip())
        return CompiledAlias(alias, skill_canonical, lang, match_type, None, toks)

    # match_type == "exact"
    if _ASCII_WORD_RX.match(alias) and not _THAI_CHAR_RX.search(alias):
        escaped = re.sub(r"\\ ", r"\\s+", re.escape(alias))
        pat = re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.I)
        return CompiledAlias(alias, skill_canonical, lang, match_type, pat, None)

    toks = tuple(t.lower() for t in word_tokenize(normalize_thai_text(alias), engine="newmm", keep_whitespace=False) if t.strip())
    escaped = re.escape(alias)
    pat = re.compile(escaped, re.I)
    return CompiledAlias(alias, skill_canonical, lang, match_type, pat, toks)


def trigram_set(text: str) -> set[str]:
    """Build Postgres pg_trgm-compatible character 3-gram set."""
    s = re.sub(r"\s+", " ", normalize_thai_text(text).lower()).strip()
    if not s:
        return set()
    padded = f"  {s} "
    return {padded[i : i + 3] for i in range(len(padded) - 2)}


def trigram_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity of 3-gram sets (matches pg_trgm similarity())."""
    ta = trigram_set(a)
    tb = trigram_set(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class SkillExtractor:
    """Dictionary + alias + PyThaiNLP `newmm` skill extractor."""

    def __init__(
        self,
        skills_csv: Path | str = DEFAULT_SKILLS_CSV,
        aliases_csv: Path | str = DEFAULT_ALIASES_CSV,
    ) -> None:
        self.skills_by_name: dict[str, SkillRecord] = {}
        self.skills_by_key: dict[int, SkillRecord] = {}
        with open(skills_csv, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rec = SkillRecord(
                    skill_key=int(row["skill_key"]),
                    skill_canonical=row["skill_canonical"].strip(),
                    skill_slug=row["skill_slug"].strip(),
                    skill_name_th=row["skill_name_th"].strip(),
                    skill_type=row["skill_type"].strip(),
                    skill_group=row["skill_group"].strip(),
                    onet_ref=(row.get("onet_ref") or "").strip(),
                    esco_ref=(row.get("esco_ref") or "").strip(),
                )
                self.skills_by_name[rec.skill_canonical] = rec
                self.skills_by_key[rec.skill_key] = rec

        self.aliases: list[CompiledAlias] = []
        self.approved_alias_strings: list[tuple[str, str]] = []
        with open(aliases_csv, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                status = (row.get("status") or "approved").strip().lower()
                if status != "approved":
                    continue
                canonical = row["skill_canonical"].strip()
                if canonical not in self.skills_by_name:
                    continue
                compiled = _compile_alias(row)
                self.aliases.append(compiled)
                if compiled.match_type != "regex":
                    self.approved_alias_strings.append((compiled.alias.lower(), canonical))

    def tokenize(self, text: str) -> list[str]:
        """Tokenize normalized Thai/mixed text with PyThaiNLP `newmm`."""
        norm = normalize_thai_text(text)
        if not norm:
            return []
        return [t for t in word_tokenize(norm, engine="newmm", keep_whitespace=False) if t.strip()]

    def extract_with_matches(self, text: str) -> dict[str, str]:
        """Return mapping `{skill_canonical: first_matched_alias}`."""
        norm = normalize_thai_text(text)
        if not norm:
            return {}
        tokens = [t.lower() for t in self.tokenize(norm)]
        token_set = set(tokens)
        token_bigrams = {(tokens[i], tokens[i + 1]) for i in range(len(tokens) - 1)}

        matched: dict[str, str] = {}
        for ca in self.aliases:
            if ca.skill_canonical in matched:
                continue
            hit = False
            if ca.match_type == "token" and ca.token_seq:
                if len(ca.token_seq) == 1:
                    hit = ca.token_seq[0] in token_set
                elif len(ca.token_seq) == 2:
                    hit = ca.token_seq in token_bigrams
                else:
                    n = len(ca.token_seq)
                    hit = any(tuple(tokens[i : i + n]) == ca.token_seq for i in range(len(tokens) - n + 1))
            else:
                if ca.pattern and ca.pattern.search(norm):
                    hit = True
                elif ca.token_seq and len(ca.token_seq) == 1 and ca.token_seq[0] in token_set:
                    hit = True

            if hit:
                matched[ca.skill_canonical] = ca.alias
        return matched

    def extract_skills(self, text: str) -> list[str]:
        """Return canonical skill names sorted by taxonomy skill_key."""
        matches = self.extract_with_matches(text)
        return sorted(matches.keys(), key=lambda name: self.skills_by_name[name].skill_key)

    def discover_pending_aliases(
        self,
        texts: Iterable[str],
        top_n: int = 100,
        min_freq: int = 2,
        min_similarity: float = 0.4,
    ) -> list[dict[str, object]]:
        """Discover top unmapped terms & propose candidates via pg_trgm similarity ONLY (no LLM)."""
        th_stops = set(thai_stopwords()) | _DOMAIN_STOPWORDS
        doc_freq: Counter[str] = Counter()

        for raw in texts:
            norm = normalize_thai_text(raw)
            if not norm:
                continue
            seen_in_doc: set[str] = set()

            # 1. PyThaiNLP newmm tokens (Thai + mixed unigrams)
            toks = [t.strip().lower() for t in self.tokenize(norm)]
            clean_toks: list[str] = []
            for tok in toks:
                if not tok or len(tok) < 2 or _PURE_NUM_PUNCT_RX.match(tok):
                    continue
                if tok in th_stops:
                    continue
                clean_toks.append(tok)
                if len(tok) >= 3:
                    seen_in_doc.add(tok)

            # 2. Thai adjacent bigrams
            for i in range(len(clean_toks) - 1):
                a, b = clean_toks[i], clean_toks[i + 1]
                if _THAI_CHAR_RX.search(a) and _THAI_CHAR_RX.search(b):
                    bg = f"{a}{b}"
                    if 4 <= len(bg) <= 24 and bg not in th_stops:
                        seen_in_doc.add(bg)

            # 3. English technical tokens & bigrams
            en_toks = [m.group(0).lower() for m in _EN_TOKEN_RX.finditer(norm)]
            en_clean = [t for t in en_toks if len(t) >= 2 and t not in th_stops and not _PURE_NUM_PUNCT_RX.match(t)]
            for t in en_clean:
                seen_in_doc.add(t)
            for i in range(len(en_clean) - 1):
                seen_in_doc.add(f"{en_clean[i]} {en_clean[i + 1]}")

            # Filter out terms that already map cleanly to an approved alias
            for cand in seen_in_doc:
                if not self.extract_with_matches(cand):
                    doc_freq[cand] += 1

        # Precompute trigram sets for approved aliases for fast similarity lookup
        alias_trigrams = [(alias, canonical, trigram_set(alias)) for alias, canonical in self.approved_alias_strings]

        results: list[dict[str, object]] = []
        # Keep top candidates meeting min_freq (fallback to freq >= 1 if corpus is very small)
        items = [(term, freq) for term, freq in doc_freq.most_common() if freq >= min_freq]
        if len(items) < top_n:
            items = doc_freq.most_common(top_n * 3)

        for term, freq in items:
            if len(results) >= top_n:
                break
            t_grams = trigram_set(term)
            best_sim = 0.0
            best_canonical = None
            best_alias = None
            if t_grams:
                for alias_str, canonical, a_grams in alias_trigrams:
                    if not a_grams:
                        continue
                    sim = len(t_grams & a_grams) / len(t_grams | a_grams)
                    if sim > best_sim:
                        best_sim = sim
                        best_canonical = canonical
                        best_alias = alias_str

            suggested_key = None
            suggested_canonical = None
            suggested_alias = None
            sim_out = round(best_sim, 3) if best_sim >= min_similarity else None
            if best_sim >= min_similarity and best_canonical:
                suggested_key = self.skills_by_name[best_canonical].skill_key
                suggested_canonical = best_canonical
                suggested_alias = best_alias

            results.append(
                {
                    "alias": term,
                    "freq": int(freq),
                    "status": "pending",
                    "suggested_skill_key": suggested_key,
                    "suggested_skill_canonical": suggested_canonical,
                    "suggested_matched_alias": suggested_alias,
                    "similarity_score": sim_out,
                }
            )

        results.sort(key=lambda r: (-int(r["freq"]), -(float(r["similarity_score"] or 0.0)), str(r["alias"])))
        return results[:top_n]
