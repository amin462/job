# Skill Demand Intelligence (E′)

**ระบบวิเคราะห์ความต้องการทักษะในตลาดแรงงานไทยจากประกาศงาน ด้วยคลังข้อมูลและการเรียนรู้ของเครื่อง**  
*A Data Warehouse and Machine Learning–Based System for Analyzing Skill Demand from Thai Job Postings*

โครงงานสาขาคอมพิวเตอร์ธุรกิจ (วิชาโครงงาน) — เน้นกระบวนการวิศวกรรมข้อมูล (Data Pipeline & Cleaning), ระบบจัดหมวดหมู่ทักษะไทย/อังกฤษ (Skill Taxonomy), คลังข้อมูล (Star/Galaxy Data Warehouse), การวัดผลโมเดลการเรียนรู้ของเครื่อง (ML Benchmark ≥ 5 โมเดล + Champion Serving) และแดชบอร์ดสไตล์ Liquid Glass สำหรับนักศึกษา สถานศึกษา และผู้ดูแลระบบ

---

## 1. สารบัญเอกสารหลัก

ดูแผนที่เอกสารทั้งหมดได้ที่ **[INDEX.md](INDEX.md)**
- **[PLAN.md](PLAN.md)** — บันทึกการตัดสินใจ (D1–D19) วัตถุประสงค์ ขอบเขต และแผน 16 สัปดาห์
- **[TASKS.md](TASKS.md)** — รายการงานย่อยราย Phase (Phase 0 → 9) พร้อมเกณฑ์ตรวจรับ (DoD)
- **[docs/PROGRESS.md](docs/PROGRESS.md)** — สถานะความคืบหน้าล่าสุด
- **[CONTEXT.md](CONTEXT.md)** — บริบทปัญหา ผู้ใช้ 3 กลุ่ม และกติกา ToS / PDPA / ความเป็นธรรมของโมเดล
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — สถาปัตยกรรมระบบ, SQL DDL (`staging`, `dw`, `mart`, `ml`, `public` + RLS)
- **[FRONTEND_SPEC.md](FRONTEND_SPEC.md)** — สเปกหน้าเว็บทุก route, flows, และการส่ง `pageContext` ให้แชท Gemini
- **[DESIGN_SYSTEM.md](DESIGN_SYSTEM.md)** — สไตล์ Liquid Glass, ชุดสีที่ตรวจ contrast แล้ว และ Apache ECharts
- **[docs/DEPLOY.md](docs/DEPLOY.md)** — คู่มือ Deploy ฟรีแบบ 2 ที่ + DB (Vercel + Supabase + Render Free / เซิร์ฟเวอร์มหาวิทยาลัย)
- **[AGENTS.md](AGENTS.md)** / **[GEMINI.md](GEMINI.md)** — กติกาและคู่มือปฏิบัติงานสำหรับ AI Agent

---

## 2. สถาปัตยกรรมและการ Deploy (ฟรี 100%)

```text
[JobThai JSON-LD] ──(Playwright + httpx, ≥5s/req, ตัด HR contact)──► [Python Pipeline (Local / เครื่องมหาวิทยาลัย)]
                                                                            │
                                                      clean → PyThaiNLP + alias taxonomy → DQ checks
                                                                            ▼
                                                           [Supabase PostgreSQL + Auth + RLS]
                                                            schemas: staging │ dw │ mart │ ml │ public
                                                                    │                    │
                                             อ่านเฉพาะ mart.* + app_* │                    │ train & GroupKFold(5)
                                                                    ▼                    ▼
                                                    [Next.js บน Vercel] ◄──proxy── [FastAPI ml-api (Champion)]
                                                             │                      (Render Free / มหาวิทยาลัย)
                                                             └── POST /api/chat (Gemini + pageContext)
```

---

## 3. โครงสร้างโฟลเดอร์

```text
southbi/
├─ apps/web/                 Next.js App Router (TypeScript, Tailwind v4, shadcn/ui, ECharts)
├─ pipeline/                 Python (scraper/, etl/, ml/, tests/)
├─ services/ml-api/          FastAPI เสิร์ฟโมเดลเงินเดือน Champion (/health, /predict, /predict/batch)
├─ taxonomy/                 skills.csv, aliases.csv, occupations.csv
├─ supabase/migrations/      SQL migrations 001–005 (schemas, staging, dw, mart, ml, app + RLS)
├─ eval/                     labeling-guideline.md, skills_gold.csv (ชุดตรวจมือ 200 ประกาศ)
├─ models/                   salary_champion.joblib + feature_spec.json
├─ spike/                    สคริปต์และผลวิเคราะห์ทดลองเบื้องต้น (n = 131 ประกาศ)
├─ docs/                     รายงาน spike, DEPLOY.md, PROGRESS.md, บทที่ 1–5, หนังสือขออนุญาต
└─ INDEX.md PLAN.md TASKS.md CONTEXT.md ARCHITECTURE.md FRONTEND_SPEC.md DESIGN_SYSTEM.md AGENTS.md
```

---

## 4. การตั้งค่าและรันระบบ (Quick Start)

### 4.1 เตรียม Environment Variables
คัดลอกไฟล์ `.env.example` ไปเป็น `.env` (สำหรับ Python) และ `apps/web/.env.local` (สำหรับ Next.js) แล้วใส่ค่าจริง:
```powershell
Copy-Item .env.example .env
```

### 4.2 สภาพแวดล้อม Python (Pipeline & ML)
บนเครื่อง Windows นี้ใช้คำสั่ง `py` (Python 3.13):
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r pipeline/requirements.txt
py -X utf8 -m pytest pipeline/tests
```

### 4.3 เว็บแอปพลิเคชัน (Next.js)
```powershell
cd apps/web
npm install
npx vitest run
npm run dev
```

### 4.4 บริการทำนายเงินเดือน (FastAPI Champion Service)
```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --app-dir services/ml-api --reload --port 8000
```
