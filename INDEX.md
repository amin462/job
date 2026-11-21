# INDEX.md — สารบัญเอกสารและแผนที่โปรเจกต์ (Skill Demand Intelligence / E′)

> **อัปเดตล่าสุด:** 18 พ.ย. 2569 (v4.2) · ใช้ไฟล์นี้เป็นจุดตั้งต้นสำหรับทั้งผู้พัฒนาและ AI Agent ทุกตัว

---

## 1. ลำดับการอ่านสำหรับ AI Agent / ผู้พัฒนาใหม่

1. **[AGENTS.md](AGENTS.md)** (หรือ **[GEMINI.md](GEMINI.md)**) — กติกาเหล็ก ข้อห้าม สภาพแวดล้อมเครื่อง และขั้นตอนการทำงานของ AI
2. **[PLAN.md](PLAN.md)** (v4.2) — บันทึกการตัดสินใจ D1–D19 ขอบเขต วัตถุประสงค์ และ Roadmap 16 สัปดาห์
3. **[TASKS.md](TASKS.md)** (v4.2) — รายการงานย่อยราย Phase (Phase 0 → 9) พร้อม checkbox, เกณฑ์ตรวจรับ (DoD) และป้ายงานที่ต้องใช้คนจริง (`👤`)
4. **[docs/PROGRESS.md](docs/PROGRESS.md)** — สมุดบันทึกความคืบหน้าล่าสุด งานที่ทำเสร็จแล้ว และงานถัดไป
5. **[ARCHITECTURE.md](ARCHITECTURE.md)** (v4.2) — สถาปัตยกรรมระบบ, SQL DDL (`staging`, `dw`, `mart`, `ml`, `public` + RLS), Scraper, ETL, ML pipeline, FastAPI `services/ml-api` และ `/api/chat`
6. **[CONTEXT.md](CONTEXT.md)** — โดเมน กติกา ToS / PDPA / ความเป็นธรรมของโมเดล และสเปกฟังก์ชัน F1–F9
7. **[FRONTEND_SPEC.md](FRONTEND_SPEC.md)** — สเปกทุกหน้า (route, inputs/outputs, ตาราง mart ที่อ่าน, กราฟ, สถานะ empty/loading/error, `pageContext` ของแชท Gemini)
8. **[DESIGN_SYSTEM.md](DESIGN_SYSTEM.md)** — สไตล์ Liquid Glass ("แก้วเฉพาะเปลือก กราฟและข้อความอยู่บนพื้นทึบ contrast ≥ 4.5:1"), สี `#6C5CE7` / `#E0623F` / `#0E9AAE`, Apache ECharts
9. **[docs/DEPLOY.md](docs/DEPLOY.md)** — สถาปัตยกรรมและการตั้งค่า Deploy ฟรี 2 ที่ + DB (Vercel + Supabase + Render Free / เซิร์ฟเวอร์มหาวิทยาลัย)

---

## 2. ตารางไฟล์ทั้งหมดในโปรเจกต์ (Source of Truth)

### เอกสารหลัก (Root)
| ไฟล์ | บทบาท | สถานะ |
|---|---|---|
| [README.md](README.md) | ภาพรวมโปรเจกต์ โครงสร้างโฟลเดอร์ และคำสั่งรันระบบ | ✅ พร้อมใช้ |
| [INDEX.md](INDEX.md) | สารบัญเอกสารและแผนที่โปรเจกต์ (ไฟล์นี้) | ✅ พร้อมใช้ |
| [AGENTS.md](AGENTS.md) | กติกาและขั้นตอนการทำงานสำหรับ AI Agent ทุกค่าย | ✅ พร้อมใช้ |
| [GEMINI.md](GEMINI.md) | ไฟล์คำสั่งหลักสำหรับ Gemini CLI / Antigravity | ✅ พร้อมใช้ |
| [PLAN.md](PLAN.md) | แผนแม่บท v4.2 (Decisions D1–D19, ขอบเขต, ML, การประเมินผล, Roadmap) | ✅ ล็อกแล้ว |
| [TASKS.md](TASKS.md) | งานย่อย Phase 0–9 แบบ checkbox พร้อม DoD และลำดับพึ่งพา | ✅ ล็อกแล้ว |
| [CONTEXT.md](CONTEXT.md) | บริบทโดเมน ผู้ใช้ 3 กลุ่ม กติกา ToS/PDPA/AI | ✅ ล็อกแล้ว |
| [ARCHITECTURE.md](ARCHITECTURE.md) | สถาปัตยกรรม + SQL DDL ครบทุก schema + RLS policies | ✅ ล็อกแล้ว |
| [FRONTEND_SPEC.md](FRONTEND_SPEC.md) | สเปกหน้าเว็บทุก route + User flows + `pageContext` | ✅ ล็อกแล้ว |
| [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) | Design tokens, Liquid Glass CSS, ECharts theme และการจับคู่กราฟ | ✅ ล็อกแล้ว |
| [HANDOFF_GEMINI.md](HANDOFF_GEMINI.md) | Prompt ฉบับเต็มสำหรับสั่งให้ Gemini ลุยงานต่ออัตโนมัติ | ✅ อัปเดต v4.2 |
| [.env.example](.env.example) | แม่แบบตัวแปรสภาพแวดล้อมทั้งหมด (Supabase, ML API, Gemini, Demo) | ✅ พร้อมใช้ |

### เอกสารย่อยและรายงาน (`docs/`)
| ไฟล์ | บทบาท | สถานะ |
|---|---|---|
| [docs/data-spike-2026-11-18.md](docs/data-spike-2026-11-18.md) | รายงานผลทดลองดึงข้อมูลจริง (n = 131 ประกาศจาก JobThai) | ✅ เสร็จสมบูรณ์ |
| [docs/DEPLOY.md](docs/DEPLOY.md) | คู่มือ Deploy ฟรี (Vercel + Supabase + Render Free / มหาวิทยาลัย) | ✅ พร้อมใช้ |
| [docs/PROGRESS.md](docs/PROGRESS.md) | บันทึกความคืบหน้ารายวัน/ราย Task และรายการที่รอผู้ใช้ | ✅ พร้อมใช้ |
| `docs/letters/` | ร่างหนังสือขออนุมัติอาจารย์และอีเมลขออนุญาต JobThai (T0.3) | ⏳ รอสร้างใน Phase 0 |
| `docs/chapters/` | ร่างเล่มโครงงาน บทที่ 1–5 (T9.1–T9.3) | ⏳ รอสร้าง (T9.1 ทำก่อนได้) |
| `docs/ml-report.md` | รายงานผลเปรียบเทียบโมเดล ML 5 ตัว + baseline (T4.4) | ⏳ รอสร้างใน Phase 4 |
| `docs/test-report.md` | รายงานผลทดสอบฟังก์ชัน F1–F9, RLS และแชท 30 ข้อ (T8.1) | ⏳ รอสร้างใน Phase 8 |
| `docs/archive/` | เอกสารหัวข้อเก่า (SouthBiz / PLAN v2–v3) — **เก็บอ้างอิงเท่านั้น ห้ามใช้** | 🗄️ Archive |

### โค้ดและข้อมูลทดลองที่มีอยู่แล้ว (`spike/`)
| ไฟล์ | บทบาท |
|---|---|
| [spike/scripts/parse_jobposting.py](spike/scripts/parse_jobposting.py) | แยก JSON-LD `JobPosting` จาก HTML ของ JobThai และตัดข้อมูลผู้ติดต่อ HR |
| [spike/scripts/fetch_sample.py](spike/scripts/fetch_sample.py) | ดึงหน้าประกาศแบบสุภาพ (ทีละ 1 request, เว้น ≥ 5 วินาที, หยุดเมื่อ 403/429/CAPTCHA) |
| [spike/scripts/analyze_sample.py](spike/scripts/analyze_sample.py) | วิเคราะห์ความครบของฟิลด์ เงินเดือน และดึงทักษะเบื้องต้นจาก dictionary |
| [spike/out/sample_jobs.csv](spike/out/sample_jobs.csv) | ข้อมูลตัวอย่างที่ parse แล้ว 131 ประกาศ (ใช้เขียนเทสต์ใน Phase 1–2 ได้ทันที) |
| `spike/raw/` | ไฟล์ HTML ดิบจากการทดลอง (อยู่ใน `.gitignore` ห้าม commit) |

### โฟลเดอร์ที่จะสร้างตาม `TASKS.md`
| โฟลเดอร์ | บทบาท | Phase |
|---|---|---|
| `supabase/migrations/` | SQL migrations 001–005 (schemas, staging, dw, mart, ml, app + RLS) | Phase 1, 3, 6 |
| `pipeline/scraper/` | `config.py`, `parse.py`, `discovery.py`, `fetch.py`, `load_staging.py`, `rediscover.py` | Phase 1 |
| `pipeline/etl/` | `clean.py`, `extract_skills.py`, `map_taxonomy.py`, `validate.py`, `load_dw.py`, `build_marts.py` | Phase 2–3 |
| `pipeline/ml/` | `features.py`, `benchmark.py`, `champion.py`, `export_model.py` | Phase 4 |
| `pipeline/tests/` | `pytest` unit tests สำหรับ parser, cleaner, skill extractor, leakage check | Phase 1–4 |
| `taxonomy/` | `skills.csv`, `aliases.csv`, `occupations.csv` | Phase 2 |
| `eval/` | `labeling-guideline.md`, `skills_gold.csv` (เฉพาะ id + ทักษะ, ไม่มีข้อความประกาศ) | Phase 2 |
| `services/ml-api/` | FastAPI เสิร์ฟโมเดล champion (`/health`, `/predict`, `/predict/batch`) บน Render/มหาวิทยาลัย | Phase 4 |
| `models/` | `salary_champion.joblib` + `feature_spec.json` | Phase 4 |
| `apps/web/` | Next.js App Router + Tailwind v4 + shadcn/ui + Apache ECharts + Gemini Chat | Phase 5–7 |
