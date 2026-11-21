# PROGRESS.md — สมุดบันทึกความคืบหน้าโครงงาน (Skill Demand Intelligence / E′)

> ไฟล์นี้ให้ AI Agent อัปเดตทุกครั้งที่ทำงานแต่ละ Task ใน [TASKS.md](../TASKS.md) เสร็จ เพื่อให้ส่งต่องานข้ามเซสชันได้โดยไม่หลุดบริบท
> สัญลักษณ์ใน TASKS.md: `[x]` เสร็จตาม DoD · `[~]` มีโค้ด/ร่างแล้ว แต่ DoD ยังขาดส่วนที่ต้องใช้ Supabase จริง ข้อมูลจริง หรือคน · `[ ]` ยังไม่ทำ

---

## 1. สถานะภาพรวมปัจจุบัน (21 พ.ย. 2569)

- **เวอร์ชันแผน:** `PLAN.md` v4.2 (D1–D19)
- **git:** commit แรก `753a33a` บน `master` (ยังไม่มี remote) — data/, spike/raw/, spike/out/, design/, .env* ไม่อยู่ใน git
- **TASKS.md:** `[x]` 19 ข้อ · `[~]` 45 ข้อ · `[ ]` 17 ข้อ (อัปเดตล่าสุด 21 พ.ย. หลังทดสอบสิทธิ์/RLS งานที่ 2)
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
