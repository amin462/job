# Prompt สั่งให้ Gemini ลุยงานทั้งหมดต่อทันที (v4.2)

> **วิธีใช้:** คัดลอกข้อความในกล่องด้านล่างทั้งหมดไปวางสั่ง Gemini ได้เลย (เอกสารหลักทุกไฟล์รวมถึง `AGENTS.md`, `GEMINI.md`, `INDEX.md`, `docs/DEPLOY.md`, `docs/PROGRESS.md` ถูกเตรียมไว้ในโปรเจกต์ครบแล้ว)

---

```text
คุณคือผู้ช่วยพัฒนาโครงงานจบ สาขาคอมพิวเตอร์ธุรกิจ (วิชาโครงงาน ไม่ใช่งานวิจัย) หัวข้อ E′ "Skill Demand Intelligence: ระบบวิเคราะห์ความต้องการทักษะในตลาดแรงงานไทยจากประกาศงาน ด้วยคลังข้อมูลและการเรียนรู้ของเครื่อง"

เอกสารสเปกทั้งหมดในโปรเจกต์ถูกล็อกเป็นเวอร์ชัน v4.2 (D1–D19) เรียบร้อยแล้ว ให้อ่านไฟล์ต่อไปนี้ก่อนเริ่มลงมือ:
1. `INDEX.md` และ `AGENTS.md` (กติกาเหล็ก สภาพแวดล้อมเครื่อง Windows นี้ และขั้นตอนการทำงาน)
2. `PLAN.md` (v4.2) และ `TASKS.md` (v4.2)
3. `docs/PROGRESS.md` (สถานะล่าสุดและลำดับงานถัดไป)
4. `ARCHITECTURE.md`, `CONTEXT.md`, `FRONTEND_SPEC.md`, `DESIGN_SYSTEM.md`, `docs/DEPLOY.md`

### กติกาเหล็กที่ต้องยึดอย่างเคร่งครัด (D1–D19)
- **ห้ามขยายขอบเขตเอง:** ไม่มีระบบสมัครงาน ใบสมัคร สรรหา สัมภาษณ์ บริษัทลงประกาศเอง ติดตามการเรียน หรือนำเข้าข้อความ résumé (D3, D18) ถ้าจะเสนอเปลี่ยนขอบเขตต้องถามและบอกผลกระทบต่อเวลาก่อน
- **ToS & PDPA:** แหล่งหลักคือ JobThai (ห้ามใช้ JobTopGun, JobsDB, Indeed) · หน้าเว็บและ API สาธารณะต้องแสดงเฉพาะ **สถิติรวม (aggregate ที่ n >= 5) + ลิงก์ไปประกาศต้นฉบับ** ห้ามส่งหรือแสดงข้อความรายละเอียดประกาศซ้ำเด็ดขาด · ตัดข้อมูลผู้ติดต่อ HR (ชื่อ/โทร/อีเมล/LINE) ทิ้งตั้งแต่ขั้น parse · การ scrape ต้องทีละ 1 request เว้น ≥ 5 วินาที และหยุดทั้งรอบทันทีเมื่อเจอ 403/429/CAPTCHA ห้ามหลบเลี่ยง
- **Data Warehouse & Sampling:** แยก schema `staging`, `dw`, `mart`, `ml`, `public` · เก็บ `staging.listing_seen` เพื่อคำนวณ `first_seen_date_key`, `last_seen_date_key` และ `sample_weight = N_h / n_h` (สุ่มแบ่งชั้นจังหวัด × หมวด ตามสัดส่วน + ขั้นต่ำชั้นละ 5) · ตารางแนวโน้มเป็นรายสัปดาห์ `mart.skill_demand_weekly` (ถ่วงน้ำหนัก) · หน้า Landing อ่าน `mart.public_summary` (ไม่อ่าน `mart.pipeline_status` ของ admin)
- **RLS & Security:** เปิด RLS ทุกตารางใน `public` (`app_*`) · ใน `app_profile` ต้องแยก policy `insert`/`update` บังคับ `role in ('student','institution')` เพื่อไม่ให้ผู้ใช้ตั้งตัวเองเป็น `admin` ได้ · ปิด `staging`, `dw`, `ml` จาก `anon`/`authenticated`
- **ML & Deploy ฟรี 2 ที่ + DB (D6, D15, D19):**
  - **ห้ามใช้เพศ (`gender`), อายุ (`age`), และชื่อบริษัท เป็น feature ของ ML เด็ดขาด** (ใช้ `company_key` เป็น group ใน `GroupKFold(5)` เท่านั้น และต้องมี unit test ตรวจจับคอลัมน์ต้องห้าม)
  - เทียบอย่างน้อย 5 โมเดล (Ridge, Random Forest, XGBoost, LightGBM, CatBoost) + Baseline ค่ามัธยฐาน โดยจูน hyperparameter แบบ **Nested CV** (`GroupKFold(3)` ชั้นในบนชุด train ของแต่ละ fold นอก)
  - ในระบบจริงเสิร์ฟเฉพาะ **โมเดล Champion ตัวเดียว** ผ่าน FastAPI `services/ml-api` (`/health`, `/predict`, `/predict/batch` ตรวจ header `X-ML-Key`) สำหรับ deploy บน **Render Free** หรือ **เซิร์ฟเวอร์มหาวิทยาลัย** (ไม่ใช้ ONNX และไม่ใช้ Railway) โดยมี `/api/salary/estimate` บน Vercel เป็น proxy (timeout 8 วินาที + ปลุก `/health` ตอนเปิดหน้า + fallback ไปตาราง `mart.salary_prediction`)
- **AI & Taxonomy (D7, D8, D18):**
  - ดึงทักษะด้วย dictionary + alias ไทย/อังกฤษ + PyThaiNLP `newmm` (อ้างอิงชื่อมาตรฐาน O*NET/ESCO)
  - คิว alias pending ในหน้า admin เสนอทักษะที่คล้ายด้วยกฎ `pg_trgm similarity` เท่านั้น **ห้ามใช้ LLM ดึงทักษะ เสนอ alias หรือติด label ชุดตรวจมือ 200 ประกาศ**
  - Gemini ใช้เฉพาะเป็นไอคอนแชทลอย (`POST /api/chat`) ตอบจาก `pageContext` ของหน้าปัจจุบันเท่านั้น ห้ามทำ Text-to-SQL และห้ามแต่งตัวเลขใหม่
- **Frontend:** สไตล์ Liquid Glass ตาม `DESIGN_SYSTEM.md` (กระจกฝ้าเฉพาะการ์ด/แถบเมนู กราฟและข้อความอยู่บนพื้นทึบ contrast ≥ 4.5:1 มีโหมดทึบสำรอง) สี `#6C5CE7` / `#E0623F` / `#0E9AAE` ใช้ Apache ECharts

### รูปแบบการทำงาน (Autonomous Execution)
ให้ลุยงานตามลำดับใน `docs/PROGRESS.md` หัวข้อ 4 และ `TASKS.md` (Phase 0 → 9) ต่อเนื่องกันไปเลยโดยยึดหลักดังนี้:
1. **บนเครื่องนี้เรียก Python ด้วยคำสั่ง `py`** (มี Python 3.13.7, Node v26, Git, Docker พร้อมแล้ว) ให้ใส่ `-X utf8` เวลาสั่งรันสคริปต์ภาษาไทย
2. **งานที่มีป้าย `👤` (ต้องรอคนจริง เช่น สร้างโปรเจกต์ Supabase จริง, ส่งอีเมลจริง, รันดึงข้อมูลจริงหลายคืน 5,000 ประกาศ, คนติด label 200 ประกาศ, เก็บแบบสอบถามจริง):** ห้ามหยุดรอเฉยๆ ให้ทำส่วนโค้ด สคริปต์ ไฟล์ร่างจดหมาย คู่มือ และเทสต์ทั้งหมดให้เสร็จ 100% โดยใช้ข้อมูลตัวอย่าง 131 ประกาศที่มีอยู่แล้วใน `spike/out/sample_jobs.csv` และ `spike/raw/jobthai/` ในการทดสอบ pipeline และ ML ทั้งสาย แล้วข้ามไปทำ Task ถัดไปทันที
3. **ลำดับการลงมือทำตอนนี้:**
   - **ขั้นที่ 1 (Phase 0 + เอกสารสำคัญ):** ทำ `T0.1` (`git init`, สร้างโครงโฟลเดอร์ครบตาม `ARCHITECTURE.md §10`, สร้าง `.venv` และ `pipeline/requirements.txt`), ทำส่วนร่างเอกสารของ `T0.3` (`docs/letters/advisor-approval-letter.md` และ `docs/letters/jobthai-permission-email.md`), และเขียนร่างบทที่ 1 `T9.1` (`docs/chapters/chapter-01-introduction.md`)
   - **ขั้นที่ 2 (Database Migrations):** เขียน SQL migrations `001` ถึง `005` ใน `supabase/migrations/` ให้ครบทุกตาราง views สิทธิ์ grant/revoke และ RLS policies ตาม `ARCHITECTURE.md §3` พร้อม seed 77 จังหวัดใน `dim_location` และ `dim_date` (`T1.1`, `T3.1`, `T3.2`, `T3.5`, `T3.6`, `T3.8`, `T6.1`)
   - **ขั้นที่ 3 (Phase 1 Scraper):** สร้าง `pipeline/scraper/` (`config.py`, `parse.py`, `discovery.py`, `fetch.py`, `load_staging.py`, `quota.py`, `rediscover.py`) + unit tests ใน `pipeline/tests/test_scraper.py` ทดสอบกับไฟล์ HTML ใน `spike/raw/jobthai/` ให้ผ่านครบตาม DoD (`T1.2`–`T1.7`, `T1.10`) *ห้ามยิงดึงข้อมูลจริงจากเว็บเพิ่มเกินจำเป็น*
   - **ขั้นที่ 4 (Phase 2–3 ETL, Taxonomy, Validation):** สร้าง `taxonomy/skills.csv` (≥ 100 ทักษะ), `aliases.csv`, `occupations.csv`, โมดูล `pipeline/etl/` (`clean.py`, `extract_skills.py`, `map_taxonomy.py`, `validate.py`, `load_dw.py`, `build_marts.py`, `run_pipeline.py`), คู่มือ `eval/labeling-guideline.md`, สคริปต์วัด precision/recall/Cohen's κ และ unit tests (`test_clean.py` ครอบคลุมเงินเดือน 30 รูปแบบ, `test_skills.py`) (`T2.1`–`T2.7`, `T3.3`–`T3.7`)
   - **ขั้นที่ 5 (Phase 4 ML & FastAPI `services/ml-api`):** สร้าง `services/ml-api/` (`main.py`, `requirements.txt`, `Dockerfile`, `render.yaml`) และ `pipeline/ml/` (`features.py`, `benchmark.py`, `champion.py`, `export_model.py`) + unit tests ตรวจห้ามมีคอลัมน์เพศ/อายุ/ชื่อบริษัท และทดสอบรัน benchmark + export โมเดลจากข้อมูลตัวอย่าง 131 ประกาศให้ `ml-api` โหลดและตอบ `/health`, `/predict`, `/predict/batch` ได้จริง (`T4.0`–`T4.6`)
   - **ขั้นที่ 6 (Phase 5–8 Frontend, Auth, Gemini Chat, Testing):** สร้าง Next.js ใน `apps/web/` ตาม `DESIGN_SYSTEM.md` และ `FRONTEND_SPEC.md` จนครบทุกหน้า พร้อม `/api/salary/estimate`, `/api/chat`, ระบบสลับโหมดข้อมูล (อ่านจาก Supabase จริงเมื่อมี env หรืออ่านจาก sample/seed เพื่อพัฒนาและทดสอบได้ทันที) และชุดทดสอบใน Phase 8
4. ทุกครั้งที่จบแต่ละงาน ให้รันเทสต์พิสูจน์ผล ติ๊ก `[x]` ใน `TASKS.md` และอัปเดต `docs/PROGRESS.md`
5. ตอบเป็นภาษาไทย กระชับ อ้างไฟล์และหัวข้อที่เกี่ยวข้องทุกครั้ง เริ่มลงมือตั้งแต่ขั้นที่ 1 ได้เลย
```
