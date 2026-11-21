# PROGRESS.md — สมุดบันทึกความคืบหน้าโครงงาน (Skill Demand Intelligence / E′)

> ไฟล์นี้ให้ AI Agent อัปเดตทุกครั้งที่ทำงานแต่ละ Task ใน [TASKS.md](../TASKS.md) เสร็จ เพื่อให้ส่งต่องานข้ามเซสชันได้โดยไม่หลุดบริบท

---

## 1. สถานะภาพรวมปัจจุบัน

- **เวอร์ชันแผน:** `PLAN.md` v4.2 (ล็อกการตัดสินใจ D1–D19 ครบถ้วน)
- **Phase ปัจจุบัน:** กำลังเริ่ม **Phase 0 (Setup & ข้อตกลง)** ควบคู่กับ **T9.1 (ร่างบทที่ 1)** และ **Phase 1–3 (Migrations & Pipeline โครงหลัก)**
- **ข้อมูลที่มีอยู่แล้วในเครื่อง:**
  - `spike/out/sample_jobs.csv` (131 ประกาศจาก JobThai ที่ parse แล้ว)
  - `spike/raw/jobthai/sample` (29 ไฟล์) และ `spike/raw/jobthai/by_province` (111 ไฟล์)
  - สามารถใช้ชุดข้อมูล 131 ประกาศนี้เขียนและรัน unit tests ของ Phase 1–4 ได้ทันทีโดยไม่ต้องดึงข้อมูลจากเว็บเพิ่ม

---

## 2. รายการที่รอผู้ใช้ดำเนินการจริง (`👤` Human Actions)

> **กติกาสำหรับ AI Agent:** ห้ามหยุดรอรายการด้านล่าง ให้สร้างไฟล์ร่าง สคริปต์ SQL migrations โค้ด pipeline โค้ด `services/ml-api` และโค้ด `apps/web` ล่วงหน้าให้ครบ แล้วติ๊กงานส่วนโค้ดเดินหน้าต่อไปได้เลย

- [ ] **👤 T0.2:** สร้างโปรเจกต์บน Supabase แล้วนำ `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL` มาใส่ใน `.env` และ `apps/web/.env.local`
- [ ] **👤 T0.3:** ตรวจร่างหนังสือใน `docs/letters/` (เมื่อ Agent สร้างเสร็จ) กรอกชื่อมหาวิทยาลัย/อาจารย์/นักศึกษา แล้วส่งขออนุมัติอาจารย์ + ส่งอีเมลถึง JobThai
- [ ] **👤 T0.4:** ตอบคำถามใน `PLAN.md §11` (จำนวนผู้จัดทำ, วันสอบจริง, เกณฑ์จำนวนกลุ่มตัวอย่างแบบสอบถามของอาจารย์)
- [ ] **👤 T0.6:** สอบถามฝ่าย IT มหาวิทยาลัยว่ามี VM/เซิร์ฟเวอร์ที่เปิด HTTPS สาธารณะให้รัน `services/ml-api` หรือไม่ (ระหว่างรอ ให้ใช้ Render Free เป็นค่าเริ่มต้นตาม `docs/DEPLOY.md`)
- [ ] **👤 T1.8:** รันเก็บข้อมูลจริงหลายคืน (≥ 5,000 ประกาศ) หลังส่งหนังสือ T0.3 และทดสอบสคริปต์ T1.2–T1.7 ผ่านแล้ว · เตรียม `pipeline/scraper/run_long.py` สำหรับรันหลาย batch แบบสุภาพ; ยังไม่เริ่มจนกว่าจะครบเงื่อนไขอนุญาตและงานก่อนหน้า
- [ ] **👤 T2.7:** คนตรวจมือ 200 ประกาศตามคู่มือ `eval/labeling-guideline.md` ลงใน `eval/skills_gold.csv`
- [ ] **👤 T8.3:** เก็บแบบสอบถามความพึงพอใจ Likert 5 ระดับจากผู้ใช้จริงตามจำนวนที่อาจารย์กำหนด

---

## 3. บันทึกงานที่ทำเสร็จแล้ว (Changelog)

### 2026-11-18 — วางโครงเอกสารและสถาปัตยกรรม v4.2
- [x] ทดลองดึงข้อมูลเบื้องต้น (Data Spike n = 131) และสรุปผลใน [docs/data-spike-2026-11-18.md](data-spike-2026-11-18.md)
- [x] จัดทำเอกสารหลักครบทุกไฟล์: [PLAN.md](../PLAN.md), [TASKS.md](../TASKS.md), [CONTEXT.md](../CONTEXT.md), [ARCHITECTURE.md](../ARCHITECTURE.md), [FRONTEND_SPEC.md](../FRONTEND_SPEC.md), [DESIGN_SYSTEM.md](../DESIGN_SYSTEM.md)
- [x] ปรับปรุงแผนเป็น **v4.1 (D13–D18)**:
  - เพิ่มตาราง `staging.listing_seen`, คอลัมน์ `first_seen_date_key`, `last_seen_date_key`, `sample_stratum`, `sample_weight` ใน `dw.fact_job_posting`
  - เปลี่ยนตารางแนวโน้มเป็นรายสัปดาห์ `mart.skill_demand_weekly` (ถ่วงน้ำหนัก) และเพิ่ม `mart.public_summary` สำหรับหน้า Landing
  - แก้ไข RLS ของ `public.app_profile` แยก `insert`/`update` บังคับ `role in ('student','institution')` ป้องกันผู้ใช้ยกระดับสิทธิ์เป็น `admin`
  - ล็อกกติกาการแปลงเงินเดือน, การจูนโมเดลแบบ Nested `GroupKFold(3)`, คู่มือตรวจมือ 200 ประกาศ + Cohen's κ และการเสนอ alias ด้วย `pg_trgm` (ไม่ใช้ AI)
- [x] ปรับปรุงแผนเป็น **v4.2 (D19 — Deploy ฟรี 2 ที่ + DB)**:
  - ใช้ **Vercel** (`apps/web`) + **Supabase** (Postgres/Auth/RLS) + **Render Free หรือเซิร์ฟเวอร์มหาวิทยาลัย** สำหรับ FastAPI `services/ml-api` (เสิร์ฟโมเดล Champion โดยตรง ไม่ใช้ ONNX และไม่ใช้ Railway)
  - สร้างไฟล์นำทางและคู่มือครบชุด: [INDEX.md](../INDEX.md), [AGENTS.md](../AGENTS.md), [GEMINI.md](../GEMINI.md), [README.md](../README.md), [docs/DEPLOY.md](DEPLOY.md), [docs/PROGRESS.md](PROGRESS.md), [.env.example](../.env.example), [.gitignore](../.gitignore), [HANDOFF_GEMINI.md](../HANDOFF_GEMINI.md)

---

## 4. ลำดับงานถัดไปสำหรับ AI Agent (ทำต่อทันที)

1. **T0.1:** รัน `git init` และสร้างโครงสร้างโฟลเดอร์ (`apps/web`, `pipeline`, `services/ml-api`, `taxonomy`, `supabase/migrations`, `eval`, `models`, `docs/letters`, `docs/chapters`) + `pipeline/requirements.txt` + `.venv`
2. **T0.3 (ส่วนร่างเอกสาร) & T9.1:** สร้างร่างหนังสือขออนุมัติอาจารย์และอีเมลขออนุญาต JobThai ใน `docs/letters/` และเขียนร่างบทที่ 1 ฉบับสมบูรณ์ใน `docs/chapters/chapter-01-introduction.md`
3. **T1.1, T3.1, T3.2, T3.5, T3.6, T3.8, T6.1:** เขียนไฟล์ SQL Migrations `001` ถึง `005` ใน `supabase/migrations/` ให้ตรงตาม DDL ใน `ARCHITECTURE.md §3` ทุกตารางพร้อม seed 77 จังหวัด (`dim_location`) และ `dim_date`
4. **T1.2–T1.7:** พัฒนาโมดูล `pipeline/scraper/` (`config.py`, `parse.py`, `discovery.py`, `fetch.py`, `load_staging.py`, `quota.py`, `rediscover.py`) พร้อม `pytest` ทดสอบกับไฟล์ HTML ใน `spike/raw/jobthai/` (ตรวจว่าไม่มี HR contact และจำลอง 429 แล้วหยุดทันที)
5. **T2.1–T2.7 (ส่วนโค้ดและคู่มือ):** สร้าง `taxonomy/skills.csv` (≥ 100 ทักษะ), `aliases.csv`, `occupations.csv`, โมดูล `pipeline/etl/` (`clean.py`, `extract_skills.py`, `map_taxonomy.py`), คู่มือ `eval/labeling-guideline.md` และสคริปต์คำนวณ precision/recall/κ พร้อม unit tests ครอบคลุมรูปแบบเงินเดือนจริง 30 รูปแบบ
6. **T3.3, T3.4, T3.7:** พัฒนา `validate.py` (DQ 8 ด้าน), `load_dw.py`, `build_marts.py`, `run_pipeline.py`
7. **T4.0–T4.6:** สร้าง FastAPI `services/ml-api` (`/health`, `/predict`, `/predict/batch`, `Dockerfile`, `render.yaml`) และโมดูล `pipeline/ml/` (`features.py` พร้อมเทสต์กันคอลัมน์ `gender`/`age`/`company_name`, `benchmark.py` 5 โมเดล + baseline ด้วย Nested GroupKFold, `export_model.py`) แล้วรันทดสอบทั้งสายกับข้อมูลตัวอย่าง 131 ประกาศ
8. **Phase 5–8:** สร้างเว็บ Next.js `apps/web` ตาม `DESIGN_SYSTEM.md` และ `FRONTEND_SPEC.md` จนครบทุกหน้า + `/api/chat` + `/api/salary/estimate` + E2E/RLS tests
