# PROGRESS.md — สมุดบันทึกความคืบหน้าโครงงาน (Skill Demand Intelligence / E′)

> ไฟล์นี้ให้ AI Agent อัปเดตทุกครั้งที่ทำงานแต่ละ Task ใน [TASKS.md](../TASKS.md) เสร็จ เพื่อให้ส่งต่องานข้ามเซสชันได้โดยไม่หลุดบริบท
> สัญลักษณ์ใน TASKS.md: `[x]` เสร็จตาม DoD · `[~]` มีโค้ด/ร่างแล้ว แต่ DoD ยังขาดส่วนที่ต้องใช้ Supabase จริง ข้อมูลจริง หรือคน · `[ ]` ยังไม่ทำ

---

## 1. สถานะภาพรวมปัจจุบัน (21 พ.ย. 2569)

- **เวอร์ชันแผน:** `PLAN.md` v4.2 (D1–D19)
- **git:** commit แรก `753a33a` บน `master` (ยังไม่มี remote) — data/, spike/raw/, spike/out/, design/, .env* ไม่อยู่ใน git
- **TASKS.md:** `[x]` 30 ข้อ · `[~]` 34 ข้อ · `[ ]` 17 ข้อ (อัปเดตล่าสุด 21 พ.ย. หลังบันทึกผล ML benchmark และ `mart.salary_prediction` ลง Supabase Postgres จริง: `T4.2`, `T4.6`)
- **Supabase (T0.2):** โปรเจกต์ `smaaunonziebjvfyfuje` (Tokyo) · คีย์อยู่ใน `.env` และ `apps/web/.env.local` (ไม่อยู่ใน git) · Python ต่อผ่าน **Session pooler** ได้แล้ว (host ตรง `db.*.supabase.co` มีแต่ IPv6 เครื่องนี้ต่อไม่ได้) · **ลง migrations `001`–`005` แล้ว** (Postgres 17.12, schema `staging`/`dw`/`mart`/`ml`/`public`, `pg_trgm` v1.6, RLS ครบ 6 ตาราง `app_*`, seed `dim_location` 79 / `dim_date` 1,095)
- **GitHub:** `https://github.com/amin462/job` (public, ยังว่าง) — ยังไม่ได้ตั้ง remote/push รอผู้ใช้สั่ง
- **เทสต์ล่าสุด:** `pytest` scraper+import+skills+clean 90 passed (รวมเทสต์ N_h ใหม่ 4 ข้อ) · `test_ml.py` ผ่านเมื่อเช้า (ไม่ได้แก้ไฟล์ ML) · `vitest` 26/26 · `tsc --noEmit` ผ่าน · `npm run build` ผ่าน (26 route)
- **การเก็บข้อมูลจริง (T1.8) กำลังรัน:** ผู้ใช้ยืนยัน T0.3 แล้ว (21 พ.ย.) — harvester ทั้งสองตัวรันแบบหน้าต่าง cmd ย่อไว้ ด้วย delay ≥ 5 วินาที
  - JobThai (`data/jobthai.sqlite`): 16,130 job id · ดึงรายละเอียดแล้ว 291 · error 2 · ที่เหลือรอดึง (ประมาณ 27 ชม. หลังสแกนรายการรอบใหม่ ~6 ชม.)
  - JobBKK (`data/jobbkk.sqlite`): 7,542 job id (ยังสแกนกรุงเทพฯ ไม่ครบ) · ยังไม่ได้ดึงรายละเอียด
- **ข้อมูลตัวอย่างสำหรับพัฒนา:** `spike/out/sample_jobs.csv` (131 ประกาศ) + `spike/raw/jobthai/` (140 ไฟล์ HTML) — ไม่อยู่ใน git

---

## 2. รายการที่รอผู้ใช้ดำเนินการจริง (`👤` Human Actions)

> **กติกาสำหรับ AI Agent:** ห้ามหยุดรอรายการด้านล่าง ให้ทำส่วนโค้ด/ร่างให้ครบแล้วเดินงานถัดไป

- [~] **👤 T0.2 / T3.8:** สร้างโปรเจกต์ + ใส่คีย์ใน `.env` แล้ว (21 พ.ย.) · Python ต่อได้ · **ผลทดสอบ REST (21 พ.ย.):** REST ใช้ publishable key อ่าน `mart.public_summary` ได้ `HTTP 406 PGRST106` เพราะ `Exposed schemas` ยังมีแค่ `public, graphql_public` · **ผู้ใช้ต้องทำเพิ่ม:** Dashboard → Project Settings → Data API → Exposed schemas เพิ่ม `mart` (ห้ามเปิด `staging`, `dw`, `ml`) แล้วรัน `.venv\Scripts\python.exe -X utf8 -m pipeline.check_permissions` ซ้ำเพื่อปิด `T3.8` และหา Gemini API key ใส่ `GEMINI_API_KEY` ใน `.env` + `apps/web/.env.local`
- [x] **👤 T0.3:** ผู้ใช้ยืนยันหนังสืออนุญาตแล้ว (21 พ.ย. 2569)
- [ ] **👤 T0.4:** ตอบคำถามใน `PLAN.md §11` (จำนวนผู้จัดทำ, วันสอบจริง, เกณฑ์จำนวนกลุ่มตัวอย่างแบบสอบถาม)
- [ ] **👤 T0.6:** ถาม IT มหาวิทยาลัยเรื่อง VM/HTTPS สำหรับ `services/ml-api` (ระหว่างรอใช้ Render Free)
- [~] **👤 T1.8:** กำลังรัน harvester (ดูหัวข้อ 1) · เมื่อมีประกาศ ok เพิ่ม ให้รัน `py -X utf8 -m pipeline.scraper.import_sqlite` เพื่อนำเข้า staging
- [ ] **👤 T2.7:** คนตรวจมือ 200 ประกาศตาม `eval/labeling-guideline.md` ลงใน `eval/skills_gold.csv` (ห้ามใช้ LLM)
- [ ] **👤 T8.3:** เก็บแบบสอบถาม Likert 5 ระดับ (ร่างข้อคำถามอยู่ใน `docs/questionnaire.md`)

---

## 3. การตัดสินใจของผู้ใช้ที่ต้องรู้ (21 พ.ย. 2569)

1. **T0.3 ยืนยันแล้ว** → เก็บข้อมูลจริงจำนวนมากได้
2. **Delay ≥ 5 วินาที:** แก้ค่าเริ่มต้นและค่าขั้นต่ำใน `scraper/jobthai_harvester.py`, `scraper/jobbkk_harvester.py`, `scraper/run_jobthai.bat`, `scraper/run_jobbkk.bat` เป็น 5 วินาที (+ jitter 0–50%)
3. **การรับมือ 403/429/CAPTCHA ใน harvester คงไว้แบบเดิมตามที่ผู้ใช้เลือก:** พัก 60 นาทีแล้วลองใหม่ หยุดเมื่อโดน 3 ครั้งติด (exit code 2) — ⚠️ ต่างจาก AGENTS.md ข้อ 2 ที่ให้หยุดทั้งรอบทันที (`pipeline/scraper/fetch.py` ยังหยุดทันทีตามกฎ)
4. **ลำดับรัน harvester คงเดิม:** สแกนหน้ารายการทั้งหมดก่อน แล้วค่อยดึงรายละเอียด (ได้ first_seen/last_seen สดสำหรับ D14)
5. **รวม scraper เป็นชุดเดียว:** ใช้ `scraper/` (harvester ที่ทดสอบกับเว็บจริงแล้ว) เป็นตัวเก็บข้อมูล + `pipeline/scraper/import_sqlite.py` เป็นสะพานเข้า staging · `pipeline/scraper/run_long.py`, `harvest_batch.py`, `jobbkk_harvest.py` ไม่ใช้เก็บจริงแล้ว (เก็บไว้เป็นโค้ดอ้างอิงและเทสต์)

---

## 4. ข้อสังเกต/ความเสี่ยงที่พบ

- **N_h ของชั้นสุ่ม (T1.7) — แก้แล้ว 21 พ.ย.:** หน้ารายการ JobThai ฝัง JSON `{"data":{"total":N,"data":[...]}}` ไว้ ซึ่งบอกทั้ง N_h ของตัวกรองนั้น และ `province.id`/`jobType.id` ของแต่ละประกาศ harvester เก็บค่านี้แล้ว (ไม่ยิง request เพิ่ม) ตรวจกับข้อมูลจริงแล้ว: นนทบุรี × งานธุรการ N_h = 158 และ 20 ประกาศที่ได้มีชั้นตรงกันทั้งหมด · ค่าจะครบทุกชั้นหลัง harvester สแกนหน้ารายการรอบนี้เสร็จ (~6 ชม.) แล้วรัน `py -X utf8 -m pipeline.scraper.import_sqlite`
  - ข้อจำกัดที่เหลือ: แต่ละชั้นได้แค่ ≤ 20 ประกาศล่าสุด (หน้าแรก) ชั้นใหญ่ เช่น กรุงเทพฯ จึงถูกสุ่มน้อยกว่าสัดส่วน (น้ำหนักสูง ความแปรปรวนสูง) — ถ้าต้องการจัดสรรตามสัดส่วนจริงต้องไล่หน้า 2..k ของชั้นใหญ่ตาม `quota.py`
  - หน้ารายการที่ total = 0 ยังมีลิงก์ประกาศอื่น ~5 ลิงก์ (ประกาศแนะนำ) — id พวกนี้ไม่มีชั้นของตัวเองจนกว่าจะไปเจอในหน้าของชั้นจริง ห้ามนับเข้าชั้นของหน้าที่เจอ
- **clone แล้วรันเทสต์ไม่ครบ (T0.1):** เทสต์บางข้อใช้ `spike/raw/` และ `spike/out/` ซึ่งไม่อยู่ใน git (มีข้อความประกาศ) — ต้องคัดลอกไฟล์เองหรือทำ fixture ที่ตัดข้อความออก
- **JobBKK** เป็นงานระดับ Could (T1.9 / T8.6) แต่ harvester รันอยู่แล้ว
- งาน `[~]` ฝั่ง DB (migrations 001–005, grants, RLS, marts) **ยังไม่เคยรันกับ Postgres/Supabase จริง** — ต้องทดสอบ `npx supabase db reset` หลัง T0.2

---

## 5. บันทึกงานที่ทำเสร็จแล้ว (Changelog)

### 2026-11-21 (ค่ำ) — งานที่ 9 (ส่วนที่ 1): บันทึกผล ML Benchmark + `mart.salary_prediction` ลง Supabase Postgres จริง (T4.2, T4.6)
- ปรับปรุง [pipeline/ml/export_model.py](../pipeline/ml/export_model.py):
  - เพิ่ม `_load_dotenv()` ใน `main()` ให้โหลด `DATABASE_URL` จาก `.env` อัตโนมัติเหมือน `run_pipeline.py` / `import_sqlite.py`
  - ปรับ `upsert_ml_to_postgres` ให้ลบ `ml.experiment` ของ `(task, dataset_version)` เดิมก่อนบันทึกใหม่ (`on delete cascade`) เพื่อความ idempotent และเปลี่ยนการเขียน `ml.model_result`, `ml.feature_importance`, `mart.salary_prediction` เป็น batch `unnest(...)` ใน 1 roundtrip ต่อตาราง
  - แก้ `generate_ml_report_markdown` ให้อ่านรายชื่อ features จาก `feature_spec` จริงแทนข้อความตายตัว
- ปรับ [apps/web/src/components/views/MlLabView.tsx](../apps/web/src/components/views/MlLabView.tsx) ให้คัดกรองแสดงผลจาก `experiment_id` ล่าสุดเมื่อ Postgres มีหลาย experiment และแปลงค่า numeric อย่างปลอดภัย
- เพิ่ม unit test `test_upsert_ml_to_postgres_idempotent_batches` ใน [pipeline/tests/test_ml.py](../pipeline/tests/test_ml.py)
- รัน `.venv\Scripts\python.exe -X utf8 -m pipeline.ml.export_model --input data/processed/clean_postings.csv --models-dir data/processed/ml_models_preview --out-dir data/processed --report docs/ml-report.md --merge-seed` (รันซ้ำตรวจ idempotent 3 รอบ):
  - ชุดข้อมูลจริง 291 ประกาศ (`n_rows=102` มีเงินเดือน, `67` บริษัท, version `clean_postings_n102_a95df702`): Champion = `XGBoost` (`RMSE=9,083.5`, `MAE=6,002.6`, `MAPE=25.78%` เทียบ Baseline `10,834.8`, `beats_baseline=True`)
  - Postgres จริง: `ml.experiment = 1`, `ml.model_result = 36`, `ml.feature_importance = 25`, `mart.salary_prediction = 748`, `mart.ml_leaderboard = 36`, `mart.ml_feature_importance = 25` (ไม่เพิ่มแถวซ้ำ)
  - หมายเหตุเรื่องความเข้ากันได้: คง `models/salary_champion.joblib` (`n=70`) ไว้บน `HEAD` จนกว่างาน `enrich.py` + `features.py` (และ `COPY pipeline/etl/enrich.py` ใน [services/ml-api/Dockerfile](../services/ml-api/Dockerfile)) จะถูก commit พร้อมกัน หรือหลังเก็บข้อมูลครบเป้า `T1.8` แล้วค่อยรัน export ทับ `models/`
- ทดสอบ: `pytest pipeline/tests/test_ml.py -q` ได้ `15 passed` · `apps/web` `npx vitest run` ได้ `6 files, 28 passed` · `npx tsc --noEmit` ผ่าน → ปิด **`T4.2`**, **`T4.6`** เป็น `[x]`

### 2026-11-21 (ค่ำ) — งานที่ 8: Clean-Clone Fixtures & Skip Guards (T0.1)
- เพิ่ม synthetic fixtures ที่ตัดข้อความประกาศจริง (`description`/`qualifications`) และ PII ออกใน [pipeline/tests/fixtures/](../pipeline/tests/fixtures/) (`province_totals.csv`, `jobthai_listing_sample.html`, `jobthai_postings/job_900001..900021.html`, `jobbkk_job_sample.html`, `jobbkk_listing_sample.html`, `clean_postings_sample.csv`) และ [apps/web/src/__tests__/fixtures/seed_marts_sample.json](../apps/web/src/__tests__/fixtures/seed_marts_sample.json)
- อัปเดต [pipeline/tests/test_scraper.py](../pipeline/tests/test_scraper.py), [pipeline/tests/test_skills.py](../pipeline/tests/test_skills.py), และ [pipeline/tests/test_ml.py](../pipeline/tests/test_ml.py) ให้ใช้ `@pytest.mark.skipif` เมื่อไม่มี `spike/raw/` (4 เทสต์ข้ามเมื่อ clean clone) และใช้ synthetic fixtures แทนไฟล์ใน `spike/out/`/`data/`
- อัปเดต [apps/web/src/lib/data.ts](../apps/web/src/lib/data.ts) (`resolveSeedPath()`) ให้ Vitest fallback ไปใช้ `seed_marts_sample.json` เมื่อยังไม่มี `data/processed/seed_marts.json`, และแก้ไขคำสั่ง Quick Start ใน [README.md](../README.md) (`--app-dir services/ml-api`) ให้รันหลัง clone ได้จริง
- ทดสอบ:
  - จำลอง clean-clone (`git archive HEAD` + ไฟล์ Task 8 โดยไม่มี `spike/raw/`, `spike/out/`, `data/`, `.env*`): `pytest pipeline/tests -q -rs` ผ่าน `105 passed, 4 skipped` (และ working tree แบบไม่มีโฟลเดอร์ข้างต้น: `131 passed, 4 skipped`)
  - บนเครื่องหลัก: `.venv\Scripts\python.exe -X utf8 -m pytest pipeline/tests -q` ได้ `135 passed` และ `apps/web` `npx vitest run` ได้ `6 files, 28 passed`
- ปิด **`T0.1`** เป็น `[x]`

### 2026-11-21 (16:00) — โครงสร้างชุดข้อมูลครบ (A+B) + เร่งความเร็ว harvester · Claude
- **ผู้ใช้สั่ง:** เก็บทุก column ที่เว็บมี ตัดเฉพาะข้อมูลส่วนบุคคล (PDPA) และแปลงเป็น feature ให้ครบ — เอกสาร **[docs/data-dictionary.md](data-dictionary.md)** อธิบายทุก column (ที่มา, ครอบคลุม, ใช้ทำอะไร, ห้ามใช้อะไร)
- `scraper/jobthai_harvester.py` (รีสตาร์ทแล้ว 16:02):
  - หน้ารายการ: เก็บทั้ง record ของแต่ละประกาศ (`job.listing_meta`) + flag urgent / near_transit / industrial_estate / online_interview / district_id / salary_text_listing
  - หน้าประกาศ: อ่านทุก element `id="job-*"` (ไม่รวมการ์ดงานอื่น) → `positions`, `salary_text`, `update_at`, `company_detail`, `directions` (scrub เบอร์/อีเมล/LINE) เก็บใน `jsonld.x_jobthai`
  - ดึง 291 ประกาศเดิมซ้ำก่อน (ทุกแถวจะมี column เท่ากัน) ถ้าประกาศปิดไปแล้วเก็บข้อมูลเดิมไว้ + `x_jobthai.unavailable`
  - เติม province_id/jobtype_id จากชื่อในตัวประกาศเมื่อหน้ารายการไม่ได้ให้
  - ความเร็ว: jitter 0–1 วินาที (เดิม 0–2.5) delay ยัง ≥ 5 วินาที · รอบถัดไปข้ามหน้ารายการที่ว่าง (total = 0) ซึ่งสแกนไปแล้วไม่เกิน 3 วัน (~46% ของหน้ารายการว่าง)
- **ใหม่** `pipeline/etl/enrich.py` + `pipeline/tests/test_enrich.py` (22 เทสต์): seniority_level (ระบุได้ 87%), employment_type_derived, accepts_fresh_grad, is_remote, shift_work, work_days_per_week, positions, salary_disclosure, benefit_* 14 กลุ่ม + n_benefit_types, urgent, near_transit, in_industrial_estate, online_interview, days_listed — กฎคำค้นล้วน ไม่ใช้ LLM
- `pipeline/etl/run_pipeline.py`: ส่ง `payload` เข้า `enrich_fields()` → clean_postings 66 column (เดิม 36)
- `pipeline/ml/features.py`: feature ใหม่ `seniority_level`, `employment_type_derived` (แทน `employment_type` ที่เป็น FULL_TIME ทุกแถว) · หน้า Salary ส่งสองค่านี้ได้ (ไม่ส่ง = ไม่ระบุ/full_time) · โมเดลที่ export ไว้เดิมยังใช้ได้ (spec เดิมไม่มีสอง column นี้)
- เทสต์: `pytest pipeline/tests` 131 passed
- ⚠️ **ถึง Gemini:** ประมาณ 15:52 harvester ทั้งสองตัวถูกปิดพร้อมกัน (ไม่มี log) — **ห้ามสั่งปิด python.exe ทั้งหมด** (`taskkill /IM python.exe` ฯลฯ) ให้ปิดเฉพาะ PID ของตัวเองถ้าจำเป็น

### 2026-11-21 (เย็น) — งานที่ 7: สร้างและตรวจบัญชีเดโม 4 Persona ใน Supabase Auth (T6.2, T6.3)
- สร้างสคริปต์ `pipeline/seed_demo_personas.py`: ใช้ `SUPABASE_SECRET_KEY` สร้าง/อัปเดตผู้ใช้ทั้ง 4 บัญชี (`DEMO_*_EMAIL`/`DEMO_*_PASSWORD` จาก `.env`) แล้วเรียก `public.attach_demo_persona` และทดสอบ login ด้วย password + อ่าน `app_profile`/`app_user_skill`/`app_curriculum` ภายใต้ RLS (ห้ามพิมพ์อีเมล/รหัสผ่าน/คีย์)
- รัน `.venv\Scripts\python.exe -X utf8 -m pipeline.seed_demo_personas` 2 รอบติด (idempotent): `student_data (role=student, n_skills=4)`, `student_acc (role=student, n_skills=4)`, `institution (role=institution, n_curricula=1)`, `admin (role=admin)` ผ่านทั้งหมด
- ซิงก์ `DEMO_*` (8 ตัวแปร) เข้า `apps/web/.env.local` (ไม่อยู่ใน git) และให้ `apps/web/src/app/api/demo/route.ts` ล้าง cookie เดโมเก่าเมื่อ sign-in ผ่าน Supabase สำเร็จ · `vitest` `28/28`, `tsc --noEmit` ผ่าน → ปิด `T6.2`, `T6.3` เป็น `[x]`

### 2026-11-21 (เย็น) — งานที่ 6: เชื่อม Next.js `apps/web` กับ Supabase จริง + fallback และตัวกรองความปลอดภัย (T0.2, T5.4)
- ทดสอบเชื่อมจาก Node/Next.js ด้วย `apps/web/.env.local`: `get_dim_skills` (128), `get_dim_occupations` (18), `get_dim_locations` (80) อ่านจาก Supabase ได้จริง; ส่วน `mart.*` คืน `PGRST106` จนกว่าผู้ใช้จะกดเพิ่ม `mart` ใน Exposed schemas (fallback ไปยัง `data/processed/seed_marts.json` อัตโนมัติ)
- ปรับปรุง `apps/web/src/lib/supabase/config.ts`, `server.ts` (เพิ่ม `createSupabasePublicClient` แบบ cookie-less), `data.ts` (pagination `.range()` เกิน 1,000 แถว, runtime sanitizer ตัดฟิลด์ `description`/`qualifications`/HR PII และบังคับซ่อน `n < 5` ทุก mart ทั้งจาก Supabase และ fallback, ให้ `getAdminData` และ `getUserSkills` อ่านจาก Supabase ก่อน), `/api/salary/estimate`, `/api/user-state`, และเพิ่ม `app/loading.tsx` + `app/error.tsx`
- เพิ่มเทสต์ `apps/web/src/__tests__/data-supabase.test.ts` · ผลรัน: `vitest` `28/28 passed` (6 ไฟล์), `tsc --noEmit` ผ่าน, `npm run build` ผ่านครบ 26 route → ปิด `T5.4` เป็น `[x]` (คง `T0.2` เป็น `[~]` รอ `👤` Exposed schemas `mart` + `GEMINI_API_KEY`)

### 2026-11-21 (เย็น) — งานที่ 5: รันทั้งสายจาก staging ใน Postgres → DW → Marts (T2.3, T3.4, T3.5, T3.6, T3.7)
- เพิ่ม `load_raw_from_postgres` และ `--from-staging` ใน `pipeline/etl/run_pipeline.py` (อ่าน `staging.job_posting_raw` + `staging.listing_seen` จาก Postgres) และปรับ `upsert_dw_to_postgres` ใน `pipeline/etl/load_dw.py` ให้ upsert แบบ set-based `unnest(...)` และรีใช้ `scrape_run` + แทนที่ `dq_result` ของรอบเดิมอย่าง idempotent
- แก้ bug false positive ใน `_LINE_SCRUB_RX` (`pipeline/etl/clean.py`) ที่จับคำลงท้ายด้วย `line` (เช่น `airline call`) และเพิ่ม regression test ใน `pipeline/tests/test_clean.py`
- รัน `.venv\Scripts\python.exe -X utf8 -m pipeline.etl.run_pipeline --from-staging` 2 รอบติดกับข้อมูลจริง `291` ประกาศ:
  - ผลรัน: `skill_cov=98.6% (287/291)` · `occ_cov=99.3% (289/291)` · `with_salary=102 (35.1%)` · `Compliance PASS (PII leaks=0)` · `Sampling PASS (291/291, mismatches=0)` · `Validity: canonical_province_and_date` รายงานตามจริง `289/291` (2 ประกาศ WFH/ไม่มี `jobLocation`)
  - **Idempotency check:** จำนวนแถวทุกตาราง (`fact_job_posting=291`, `fact_posting_skill=1,647`, `dim_skill=128`, `skill_alias=568`, `dim_location=151`, `dim_company=149`, `dim_occupation=284`, `dq_result=10`, `scrape_run=7`, `app_alias_suggestion=101`) ไม่เปลี่ยนเลยหลังรันซ้ำ (`Diffs={}`)
  - **Mart vs DW check (T3.5):** ตรวจ `mart.public_summary`, `mart.occupation_skill_profile`, `mart.salary_stats`, และการซ่อน `n < 5` บนทุก view ใน `mart` (`skill_demand_weekly=714`, `skill_cooccurrence=460`, `occupation_skill_profile=448`, `salary_stats=205`, `posting_volume_daily=23`, `curriculum_coverage_ref=386`, `top_links=155`, `pipeline_status=7`, `dq_summary=10`) ตรงกับ query ตรงจาก `dw.*` ทุกค่า
- อัปเดต `docs/dq-report.md` (และ `data/processed/clean_postings.csv`, `seed_marts.json` ที่ไม่อยู่ใน git) · รัน `pytest` (`test_load_dw`, `test_import_sqlite`, `test_scraper`, `test_skills`, `test_clean`): `95 passed` · ปิด `T2.3`, `T3.4`, `T3.5`, `T3.6`, `T3.7` เป็น `[x]`

### 2026-11-21 (เย็น) — งานที่ 4: แบ่งชั้นจังหวัด × ประเภทงานและน้ำหนักสุ่ม (T1.7, T3.4)
- ปรับ `pipeline/etl/load_dw.py` (`compute_weights_and_seen_dates`, เพิ่ม `load_strata_population` และ `load_province_population_maps`):
  - ใช้ `sample_stratum` จาก `staging.listing_seen` (เช่น `p=<province>|c=<jobtype>`) หรือ fallback `p=<code>|c=all` เมื่อไม่มีประวัติ `listing_seen`
  - คำนวณ `sample_weight = N_h / n_h` โดยชั้นระดับ `p=XX|c=YY` ใช้ `N_h` จาก `data/processed/jobthai_strata.csv` และชั้นที่ยังไม่มี `|c=` (เช่น `p=XX`) ใช้ `N_h` ระดับจังหวัดจาก `jobthai_province_totals.csv` (หรือไฟล์ spike สำรอง); ถ้าชั้น `p=XX|c=YY` ยังไม่ถูกสแกน total ให้ fallback `1.0`
- เพิ่มเทสต์ `pipeline/tests/test_load_dw.py` ตรวจ `sample_stratum`, `first_seen`/`last_seen`, fallback ระดับจังหวัด, `Σw == N_h` ต่อชั้น, และ DQ Sampling check
- รัน `pytest` (`test_load_dw`, `test_import_sqlite`, `test_scraper`, `test_skills`, `test_clean`): `91 passed` · คง `T3.4` เป็น `[~]` เพื่อพิสูจน์รันซ้ำใน Postgres จริงในงานที่ 5

### 2026-11-21 (เย็น) — งานที่ 3: นำเข้าข้อมูลจริงเข้า Postgres staging (T1.5)
- ปรับ `pipeline/scraper/load_staging.py` (ใช้ Postgres `unnest(...)` แบบ 1 roundtrip/batch แทนการยิงทีละแถว ทำให้ import 25k+ rows เสร็จใน ~1–2 นาที พร้อมตรวจรูปแบบวันที่ก่อนลง) และให้ `pipeline/scraper/import_sqlite.py` โหลด `.env` อัตโนมัติเมื่อไม่ระบุ `--sqlite-path`
- รันเทสต์ `pytest pipeline/tests/test_import_sqlite.py pipeline/tests/test_scraper.py`: `36 passed`
- รัน `.venv\Scripts\python.exe -X utf8 -m pipeline.scraper.import_sqlite` เข้า Supabase Postgres จริง 2 รอบติด:
  - รอบแรก: JobThai `16,451` job ids (`291` ประกาศ ok, `0` parse_failed) + JobBKK `9,512` job ids (`0` ok) → `staging.scrape_run=6`, `staging.listing_seen=51,926`, `staging.job_posting_raw=291` (ตรวจ HR contact key ใน `payload` = `[]`)
  - รอบสอง (idempotency check): `staging.scrape_run` คงที่ `6`, `staging.job_posting_raw` คงที่ `291` (`inserted=0, duplicates=291`), `listing_seen` เพิ่มเฉพาะ ID ใหม่ที่ harvester เพิ่งเจอระหว่างรัน (`+26` แถว เป็น `51,952`)
- คง `T1.5` เป็น `[~]` เพราะ DoD ระบุโหลด `500` ประกาศ (ตอนนี้ harvester เพิ่งดึงรายละเอียดได้ `291` ประกาศ รอ harvester ดึงถึง `>= 500` แล้วรัน `import_sqlite` ซ้ำเพื่อปิด `[x]`)

### 2026-11-21 (เย็น) — งานที่ 2: ทดสอบสิทธิ์ REST และ RLS จริงบน Supabase (T3.8, T6.4)
- สร้างสคริปต์อัตโนมัติ `pipeline/check_permissions.py` และรันตรวจเทียบสิทธิ์จริงกับ Supabase (`37/37 passed`):
  - **Postgres privileges & `SET LOCAL ROLE anon`:** `anon`/`authenticated` ไม่มีสิทธิ์ `USAGE` บน `staging`/`dw`/`ml` และอ่าน `mart.pipeline_status`/`mart.dq_summary` ไม่ได้ (`42501`), แต่อ่าน `mart.public_summary` ได้
  - **REST (publishable key):** `staging.job_posting_raw`, `dw.fact_job_posting`, `ml.experiment`, `mart.pipeline_status`, `mart.dq_summary` ถูกปฏิเสธ (`HTTP 406`), `public.app_profile` ถูกปฏิเสธ (`HTTP 401`), `rpc/get_admin_pipeline_status` ถูกปฏิเสธ (`HTTP 401`), `rpc/get_dim_skills` อ่านได้ (`HTTP 200`), ส่วน `mart.public_summary` คืน `HTTP 406 PGRST106` เพราะยังไม่ได้เปิด `mart` ใน Dashboard → Data API → Exposed schemas (บันทึกไว้ในหัวข้อ 2 👤 เพื่อรอผู้ใช้กดเปิด จึงคง `T3.8` เป็น `[~]`)
  - **Live Auth + RLS (สร้าง user ทดสอบชั่วคราว 3 บัญชีด้วย secret key แล้วลบทิ้งทั้งหมดหลังจบ):** `handle_new_user` ตัด `role='admin'` จาก metadata เหลือ `student` · `PATCH`/`INSERT` เปลี่ยน `role='admin'` เองถูก RLS บล็อก (`HTTP 403`) · User B อ่าน `app_profile`/`app_user_skill` ของ User A ไม่ได้ (`[]`) · student เรียก admin RPC ถูกบล็อก (`403`) ขณะที่ admin เรียกได้ (`200`) → ปิด `T6.4` เป็น `[x]`

### 2026-11-21 (เย็น) — งานที่ 1: ลง migrations 001–005 บน Supabase จริง (T1.1, T3.1, T3.2, T6.1)
- รัน `npx supabase db push --yes --db-url "$env:DATABASE_URL"` ผ่าน Session pooler ลง PostgreSQL 17.12 สำเร็จทั้ง 5 ไฟล์ (`001`–`005`) โดยไม่ต้องแก้ SQL
- ตรวจด้วย `pipeline.check_db` และสคริปต์ Python: พบครบทั้ง 5 schemas (`staging`=4, `dw`=13, `mart`=13, `ml`=3, `public`=6), `pg_trgm` v1.6, `dim_location`=79 (`is_south14`=14), `dim_date`=1,095 (`2025-01-01`..`2027-12-31`), `dim_source`=`['jobthai','jobbkk']`, constraints/indexes ของ `fact_*` ครบ และเปิด RLS ครบทุกตาราง `app_*` (6/6)
- คง `T3.5`, `T3.6`, `T3.8` เป็น `[~]` ไว้รอตรวจสิทธิ์ REST (งานที่ 2) และตรวจตัวเลขตรงกับ `dw` หลังโหลดข้อมูลจริง (งานที่ 5)
- คืนรหัสงาน `**T#.#` ใน `TASKS.md` ที่ขาดหายจากการอัปเดตสถานะก่อนหน้าให้ครบทุกข้อ

### 2026-11-21 (บ่าย) — Supabase .env + N_h ของชั้นสุ่ม (T0.2, T1.7)
- `.env`, `apps/web/.env.local`: ใส่ URL/publishable/secret key ของ Supabase (ตั้งชื่อเดิม `NEXT_PUBLIC_SUPABASE_ANON_KEY`/`SUPABASE_SERVICE_ROLE_KEY` ให้ด้วยเพราะโค้ดเรียกชื่อนั้น) · `DATABASE_URL` = Session pooler `aws-1-ap-northeast-1` · สุ่ม `ML_API_KEY` และรหัสบัญชีเดโม 4 บัญชีไว้ใน `.env`
- `scraper/jobthai_harvester.py`: `parse_listing()` อ่าน total + province/jobType ของแต่ละประกาศจาก JSON ในหน้ารายการ (เก็บเฉพาะรหัส/ชื่อหมวด ไม่เก็บชื่อบริษัท) · เพิ่มคอลัมน์ `listing.total`, `job.province_id`, `job.jobtype_id`, ตาราง `ref` (อัปเกรด DB เดิมอัตโนมัติ ข้อมูลเดิมอยู่ครบ) · สแกนหน้ารายการที่ยังไม่มี total ก่อน · รีสตาร์ทแล้ว 15:33
- `pipeline/scraper/import_sqlite.py`: stratum ของแต่ละประกาศใช้ `p=<province_id>|c=<jobtype_id>` ของตัวมันเอง (ถ้ายังไม่รู้ใช้หน้าที่เจอ) · `export_jobthai_strata()` เขียน `data/processed/jobthai_strata.csv` (stratum, N_h, n_seen, n_fetched) และ `jobthai_province_totals.csv` (เขียนเมื่อทุกจังหวัดมี total แล้วเท่านั้น)
- `pipeline/etl/load_dw.py`: ใช้ `data/processed/jobthai_province_totals.csv` เป็น N_h ถ้ามีไฟล์ ไม่งั้นใช้ไฟล์ spike เดิม
- `pipeline/tests/test_import_sqlite.py`: +4 เทสต์ (parse_listing, อัปเกรด schema, stratum + export N_h, ไม่เขียน province totals ถ้ายังไม่ครบ)

### 2026-11-21 — ตรวจงาน Gemini, ปรับ harvester, commit แรก, ตัวนำเข้า SQLite
- ตรวจไฟล์ที่ Gemini สร้าง (18 พ.ย. 22:35 – 19 พ.ย. 00:33): migrations 001–005, `pipeline/scraper|etl|ml`, `services/ml-api`, `apps/web` (26 route), taxonomy (128 ทักษะ / 568 alias / 21 กลุ่มอาชีพ), `eval/`, บทที่ 1–5, จดหมาย, แบบสอบถาม, `docs/ml-report.md`, `docs/dq-report.md` — Gemini ไม่ได้ติ๊ก TASKS.md ไว้ จึงไล่ติ๊กใหม่ตาม DoD
- ปรับ delay ≥ 5 วินาทีใน harvester ทั้งสองตัว แล้วรีสตาร์ท (ความคืบหน้าอยู่ใน SQLite ไม่หาย)
- `.gitignore`: เพิ่ม `spike/out/` แบบชัดเจน (มี `description_preview`) → commit แรก `753a33a`
- **ใหม่** `pipeline/scraper/import_sqlite.py`: อ่าน `data/jobthai.sqlite` / `data/jobbkk.sqlite` แบบ read-only →
  `staging.listing_seen` (stratum `p=XX|c=YY` / `jobbkk|p=<จังหวัด>|c=ทั้งหมด`, วันที่เวลาไทย, แยก run `first_seen`/`last_seen`) และ JSON-LD ที่ status ok → `parse_jobposting_item` (ตัด HR contact + scrub PII) → `staging.job_posting_raw` (dedupe `content_hash`) · รันซ้ำไม่เพิ่มแถว
  - ผลกับข้อมูลจริง: JobThai 16,130 id → listing_seen, 291 ประกาศ → job_posting_raw (HR key 0, เบอร์โทร/อีเมลในข้อความ 0) · JobBKK 7,542 id → listing_seen · รันรอบสองได้ inserted 0
  - ปลายทางทดสอบ: `data/processed/staging_harvest.db` (ไม่อยู่ใน git)
- `pipeline/scraper/parse.py`: แยก `parse_jobposting_item()` ออกจาก `parse_html()` ให้ใช้กับ JSON-LD ได้โดยตรง
- `pipeline/scraper/load_staging.py`: เพิ่ม `find_scrape_run`, `get_or_create_scrape_run`, และ `insert_listing_seen(update_existing=True)`
- **ใหม่** `pipeline/tests/test_import_sqlite.py` (4 เทสต์: วันที่/stratum, PII, idempotent + last_seen เลื่อน, JobBKK URL)
- แก้ `apps/web/src/__tests__/ui-components.test.tsx`: เทสต์ OfficialLaborTrendCard ค้นข้อความที่ซ้ำ 2 จุด → ค้นป้าย "ไม่ใช่ประกาศงานล่าสุด" แทน

### 2026-11-18/19 — งานที่ Gemini ทำ (ตรวจแล้ว 21 พ.ย.)
- ร่างเอกสาร: `docs/letters/*`, `docs/chapters/chapter-01..05`, `docs/questionnaire.md`, `docs/presentation-outline.md`, `eval/labeling-guideline.md`
- DB: `supabase/migrations/001–005` (schemas, staging, dims + seed 77 จังหวัด, facts, marts + grants, `app_*` + RLS)
- Pipeline: `pipeline/scraper/*` (config, parse, discovery, fetch, load_staging, quota, rediscover, harvest_batch, jobbkk_harvest, run_long), `pipeline/etl/*` (clean, extract_skills, map_taxonomy, validate, load_dw, build_marts, run_pipeline), `pipeline/ml/*` (features, benchmark, champion, export_model) + ผลรันบนตัวอย่าง n = 126 (Champion `Ridge`, RMSE 7,334 บาท vs baseline 10,045)
- `services/ml-api` (FastAPI + Dockerfile + `render.yaml`), `models/salary_champion.joblib` + `feature_spec.json`
- `apps/web`: Next.js 16 + Tailwind v4 + ECharts ทุกหน้าใน FRONTEND_SPEC, `/api/chat`, `/api/salary/estimate`, `/api/demo`, อ่านข้อมูลจาก `data/processed/seed_marts.json` เมื่อยังไม่มี Supabase

### 2026-11-18 — วางโครงเอกสารและสถาปัตยกรรม v4.2
- Data Spike n = 131 ([docs/data-spike-2026-11-18.md](data-spike-2026-11-18.md)) และเอกสารหลักทั้งหมด (PLAN v4.1 → v4.2, D13–D19)

---

## 6. ลำดับงานถัดไปสำหรับ AI Agent

1. **ระหว่าง harvester รัน:**
   - เปลี่ยน `load_dw.py` ให้แบ่งชั้นแบบ จังหวัด × ประเภทงาน (ใช้ stratum จาก `listing_seen` + `jobthai_strata.csv`) แทนระดับจังหวัด
   - ทำ fixture ตัวอย่างที่ตัดข้อความประกาศออก เพื่อให้ clone แล้วรันเทสต์ได้ (ปิด T0.1)
   - ต่อ `run_pipeline.py` ให้อ่านจาก staging ที่ import_sqlite สร้าง แล้วรันทั้งสายกับ 291+ ประกาศจริง (T3.7)
2. **ตอนนี้ทำได้แล้ว (T0.2 มีคีย์):** `npx supabase db push --db-url "$DATABASE_URL"` ลง migrations 001–005 → ปิด T1.1, T3.1, T3.2, T3.5, T3.6, T3.8, T6.1, T6.4 → รัน import_sqlite เข้า Postgres
3. **หลังได้ ≥ 5,000 ประกาศ:** รัน ETL + benchmark ใหม่ด้วยข้อมูลจริง แล้วอัปเดต `docs/ml-report.md`, `docs/dq-report.md`

### งานต่อจากโครงสร้างชุดข้อมูลใหม่ (21 พ.ย. 16:00)
1. Migration `006_fact_enrich_columns.sql`: เพิ่ม column ของ `pipeline/etl/enrich.py` (`ENRICH_COLUMNS`) ใน `dw.fact_job_posting` (nullable) + ให้ `load_dw.upsert_dw_to_postgres` เขียนค่าเหล่านี้ → `npx supabase db push --db-url` → รัน pipeline ซ้ำ ตรวจรันซ้ำแล้วแถวไม่เปลี่ยน
2. Mart สถิติรวม (n ≥ 5) จาก column ใหม่: สัดส่วนรับจบใหม่, สวัสดิการ, ระดับตำแหน่ง, จำนวนอัตรา ต่อ occupation/จังหวัด — ใช้ในหน้า Market/Occupation (ถ่วง `sample_weight`)
3. หน้า Salary (`/salary`, T5.12): เพิ่มตัวเลือก ระดับตำแหน่ง (`seniority_level`) และประเภทการจ้าง (`employment_type_derived`) ส่งไป `/api/salary/estimate` → ml-api
4. หลังได้ข้อมูลจริง ≥ 5,000: benchmark ใหม่ (feature ใหม่อยู่ใน `CATEGORICAL_FEATURES` แล้ว) + ablation เทียบ "มี/ไม่มี สวัสดิการ" ในบทที่ 4
