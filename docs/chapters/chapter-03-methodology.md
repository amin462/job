# บทที่ 3: วิธีดำเนินงานโครงงาน

บทนี้อธิบายการออกแบบสถาปัตยกรรมระบบ โครงสร้างฐานข้อมูล การเก็บและทำความสะอาดข้อมูล อนุกรมวิธานทักษะ กระบวนการเรียนรู้ของเครื่อง ตลอดจนการออกแบบส่วนติดต่อผู้ใช้และระบบรักษาความปลอดภัยของโครงงาน **Skill Demand Intelligence (E′)** ตามสเปกสถาปัตยกรรมเวอร์ชัน `v4.2`

---

## 3.1 สถาปัตยกรรมระบบโดยรวม (System Architecture v4.2)

ระบบถูกออกแบบให้แยกภาระงานออกเป็น 4 ส่วนหลักเพื่อให้ทำงานร่วมกันอย่างปลอดภัยและใช้งานได้บนโครงสร้างพื้นฐานฟรีตลอดระยะเวลา 16 สัปดาห์ (Decision D9, D19):

```text
[1. Local / Lab PC: Python 3.13 Pipeline]
  ├─ Polite Scraper (Playwright + httpx, ≥5s/req, ตัด HR contact)
  ├─ ETL & Taxonomy (pandas + PyThaiNLP newmm + 8 DQ checks)
  └─ ML Benchmark (5 โมเดล + Baseline, Nested GroupKFold) ──► models/salary_champion.joblib
                                                                       │
        │ (เขียนข้อมูลผ่าน DATABASE_URL)                                │ (deploy โมเดลเดียว)
        ▼                                                              ▼
[2. Supabase: PostgreSQL + Auth + RLS]                     [3. Render Free / VM มหาวิทยาลัย]
  ├─ staging / dw / ml (ปิดจากเว็บ API)                      FastAPI: services/ml-api
  ├─ mart.* (Aggregate n>=5, เปิดอ่านแบบ read-only)          (/health, /predict, /predict/batch)
  └─ public.app_* (เปิด RLS ทุกตาราง)                                  ▲
        │                                                              │ (Proxy + 8s timeout
        │ (Server Components / RLS Client)                             │  + Fallback mart.salary_prediction)
        ▼                                                              │
[4. Vercel Hobby: Next.js App Router (apps/web)] ──────────────────────┘
  ├─ Liquid Glass UI + Apache ECharts + TanStack Table
  └─ POST /api/chat ──► Google Gemini API (เฉพาะ pageContext บนหน้านั้น)
```

### เหตุผลการเลือกเทคโนโลยี Deploy (D19)
- **Vercel + Supabase + Render Free (หรือเซิร์ฟเวอร์มหาวิทยาลัย):** แยกส่วนคำนวณ ML ให้อยู่ใน Python FastAPI (`services/ml-api`) โดยตรงเพื่อลดความเสี่ยงจากการแปลงโมเดลเป็น ONNX บน Serverless Function และหลีกเลี่ยงข้อจำกัดของ Railway Free ที่มีเครดิตจำกัดหลังพ้นช่วงทดลอง 30 วัน
- **การแก้ปัญหา Cold Start ของ Render Free:** หน้า `/salary` ยิงคำขอ pre-warm ไปยัง `/api/salary/estimate?warm=1` (`GET /health`) ทันทีที่เปิดหน้า ตั้ง `timeout` ฝั่ง Proxy ที่ 8 วินาทีพร้อมสลับไปใช้ตาราง `mart.salary_prediction` เป็น **Fallback** อัตโนมัติ และตั้ง `cron-job.org` ยิงปลุกทุก 14 นาทีในช่วงซ้อม/วันสอบ (และยิง Supabase ทุก 3 วันเพื่อป้องกันการ Pause)

---

## 3.2 การออกแบบระบบเก็บข้อมูลและการสุ่มแบบแบ่งชั้น (Polite Scraper & Sampling)

โมดูลเก็บข้อมูลอยู่ในโฟลเดอร์ `pipeline/scraper/` โดยมีองค์ประกอบหลักดังนี้:

1. **การรวมศูนย์การตั้งค่า (`config.py`):** กำหนดค่าคงที่ทั้งหมดไว้ในไฟล์เดียว ได้แก่ `MIN_DELAY_SEC = 5.0`, `USER_AGENT` ที่ระบุชื่อโครงงานและอีเมลติดต่อ, รหัส 77 จังหวัดของ JobThai + `"หลายจังหวัด"` + `"ต่างประเทศ"` (อ้างอิง `province_totals.csv`), ตัวกรองหมวดงานสำหรับจังหวัดขนาดใหญ่ (เช่น กรุงเทพฯ และชลบุรี เพื่อหลีกเลี่ยงเพดานการเลื่อนหน้ารายการ), และรายการแหล่งต้องห้าม `FORBIDDEN_SOURCES = {"jobtopgun", "jobsdb", "indeed"}` ซึ่งระบบจะปฏิเสธการทำงานทันทีหากถูกเรียกใช้
2. **Discovery รายจังหวัดและรายหมวด (`discovery.py`):** ใช้ Playwright เปิดหน้ารายการ `?province=XX` (และแบ่งตามหมวดงานในจังหวัดใหญ่) เพื่อรวบรวม `source_job_id` ทั้งหมดที่พบลงในตาราง `staging.listing_seen` พร้อมระบุ `stratum` และ `seen_date`
3. **การวางแผนสุ่มตัวอย่างแบบแบ่งชั้น (`quota.py` — D13):** คำนวณจำนวนที่ต้องเก็บต่อชั้นจังหวัด × หมวดจากสูตร:
   $$n_h = \min\Big(N_h,\; \max\big(5,\; \operatorname{round}(n_{\text{target}} \cdot \frac{N_h}{N_{\text{total}}})\big)\Big)$$
   พร้อมคำนวณ `sample_weight = N_h / n_h` และตรวจสอบความอนุรักษ์น้ำหนัก ($\sum_{i \in h} w_i = N_h$)
4. **การดึงหน้าประกาศแบบสุภาพ (`fetch.py`):** ใช้ `httpx` แบบ Concurrency = 1 หน่วงเวลาไม่น้อยกว่า 5.0 วินาที + ค่าสุ่ม jitter ข้ามไฟล์ HTML ที่มีอยู่บนดิสก์แล้ว (Resume) และ **หยุดการทำงานทั้งรอบทันที** พร้อมบันทึกสถานะ `stopped_403`, `stopped_429` หรือ `stopped_captcha` ลง `staging.scrape_run` หากพบสถานะจำกัดสิทธิ์หรือคำว่า `"captcha"` ในผลตอบกลับ
5. **การแยกโครงสร้างและตัด PII (`parse.py`):** สกัด `JobPosting` JSON-LD จากแท็ก `<script type="application/ld+json">` และ `self.__next_s` ลบคีย์ผู้ติดต่อ HR (`telephone`, `email`, `contactPoint`, `applicationContact`, `faxNumber`, `contact`) รวมถึงล้างรูปแบบเบอร์โทร อีเมล และ LINE ID ก่อนสร้าง `content_hash` (SHA-256) เพื่อโหลดเข้า `staging.job_posting_raw` (`load_staging.py`) แบบไม่ซ้ำ
6. **Re-discovery รายสัปดาห์ (`rediscover.py` — D14):** เปิดเฉพาะหน้ารายการทุกสัปดาห์โดยไม่โหลดหน้าประกาศเดิมซ้ำ เพื่ออัปเดต `last_seen_date_key` และคัดเฉพาะประกาศใหม่เข้าสู่คิวการดึง (ตั้งเวลาอัตโนมัติผ่าน `scripts/register_scheduled_task.ps1`)

---

## 3.3 การออกแบบฐานข้อมูล คลังข้อมูล และความปลอดภัย (Schema & RLS)

ไฟล์ SQL Migration ใน `supabase/migrations/` แบ่งโครงสร้างออกเป็น 5 ไฟล์หลักตามลำดับการพึ่งพา (`001` ถึง `005`):

### 3.3.1 การแยก Schema และสิทธิ์การเข้าถึง (Migration 001 & 004)
- สร้าง 4 schemas เพิ่มเติม (`staging`, `dw`, `mart`, `ml`) ร่วมกับ `public` และเปิดใช้งาน extension `pg_trgm`
- ใช้คำสั่ง `REVOKE ALL ON SCHEMA staging, dw, ml FROM anon, authenticated` เพื่อไม่ให้ฝั่งเว็บเรียกผ่าน PostgREST ได้โดยตรง
- เปิดสิทธิ์ `SELECT` เฉพาะตารางและ View ใน `mart` ที่ใช้สำหรับหน้าเว็บทั่วไป ส่วน `mart.pipeline_status` และ `mart.dq_summary` **ไม่เปิดสิทธิ์ให้ `anon` และ `authenticated`** แต่ให้ Admin เรียกผ่าน `SECURITY DEFINER` RPC ที่ตรวจ `public.is_admin()` เท่านั้น

### 3.3.2 โครงสร้างตารางคลังข้อมูล Star/Galaxy (Migration 002 & 003)
- **Dimensions (10 ตาราง):** `dw.dim_date` (ครอบคลุมปี 2025–2027), `dw.dim_source` (`jobthai`, `jobbkk`), `dw.dim_location` (77 จังหวัด + หลายจังหวัด + ต่างประเทศ พร้อม `region` และ `is_south14`), `dw.dim_company` (เก็บ `company_name_norm` เป็น Group สำหรับ CV), `dw.dim_occupation`, `dw.dim_skill`, `dw.skill_alias` (พร้อมดัชนี GIN `gin_trgm_ops`), `dw.dim_education`, `dw.dim_experience`, `dw.dim_employment_type`
- **Facts (3 ตาราง):**
  - `dw.fact_job_posting`: เก็บข้อมูลสรุปรายประกาศ (grain = 1 ประกาศล่าสุด) พร้อม `salary_min`, `salary_max`, `salary_mid`, `salary_open_max`, `salary_unit_orig`, `has_salary` (generated column), `first_seen_date_key`, `last_seen_date_key`, `sample_stratum`, `sample_weight`
  - `dw.fact_posting_skill`: ความสัมพันธ์ประกาศ × ทักษะ (`posting_key`, `skill_key`, `match_alias_id`)
  - `dw.fact_labor_monthly`: ตัวเลขสถิติแรงงานภาครัฐรายเดือนเพื่อแสดงบริบท
- **Marts (12 ออบเจ็กต์):** ครอบคลุม `skill_demand_weekly` (ถ่วงน้ำหนักด้วย `sample_weight` แยก active และ new), `skill_cooccurrence`, `occupation_skill_profile`, `salary_stats`, `posting_volume_daily`, `curriculum_coverage_ref`, `public_summary`, `pipeline_status`, `dq_summary`, `ml_leaderboard`, `salary_prediction`, และ `top_links` (สูงสุด 5 ลิงก์/กลุ่มอาชีพ/จังหวัด เฉพาะชื่อตำแหน่งสั้น แหล่ง และ URL โดยไม่มีเนื้อหาประกาศ) ทุกตารางสาธารณะบังคับการซ่อนสถิติเมื่อ `n_postings < 5`

### 3.3.3 ความปลอดภัยและ Row Level Security (Migration 005)
- เปิด `ENABLE ROW LEVEL SECURITY` บนทุกตาราง `public.app_*` (`app_profile`, `app_user_skill`, `app_curriculum`, `app_curriculum_skill`, `app_chat_log`, `app_alias_suggestion`)
- ป้องกันการยกระดับสิทธิ์ (Privilege Escalation) บน `app_profile` ด้วยการแยก Policy `profile_insert` และ `profile_update` โดยบังคับเงื่อนไข `WITH CHECK (user_id = auth.uid() AND role IN ('student', 'institution'))` และจัดการบัญชี `admin` ผ่าน `service_role` เท่านั้น

---

## 3.4 กระบวนการ ETL, อนุกรมวิธานทักษะ และคุณภาพข้อมูล

### 3.4.1 กฎการทำความสะอาดข้อมูล (`pipeline/etl/clean.py`)
1. **การแปลงเงินเดือนเป็นบาท/เดือน:**
   - ช่วงเงินเดือน (เช่น `"15,000-20,000"` หรือ `"15k-25k"`) → `mid = (min + max) / 2`
   - ระบุขั้นต่ำปลายเปิด (เช่น `"15,000 ขึ้นไป"`) → `min = 15,000`, `max = NULL`, `mid = min`, ติดธง `salary_open_max = True`
   - รายวัน → คูณ `26` (`salary_unit_orig = 'DAY'`) · รายชั่วโมง → คูณ `8 × 26` (`salary_unit_orig = 'HOUR'`)
   - `"ตามตกลง"` / `"ตามโครงสร้างบริษัท"` → `NULL`
   - ค่าหลังแปลงที่อยู่นอกช่วง `[5,000, 500,000]` บาท/เดือน → แปลงเป็น `NULL` และติดธง `salary_out_of_range = True`
2. **พื้นที่และชื่อบริษัท:** ลบคำนำหน้า `"จังหวัด"` จัดรูป 77 จังหวัดมาตรฐานพร้อมภาคและธงภาคใต้ 14 จังหวัด; ลบคำทั่วไปของชื่อบริษัท (`บริษัท`, `จำกัด`, `(มหาชน)`, `Co., Ltd.`) เพื่อสร้าง `company_name_norm`
3. **วุฒิการศึกษาและประสบการณ์:** ใช้ Regular Expression แยกวุฒิเป็น 5 ระดับ (`ไม่ระบุ`, `ม.3/ม.6`, `ปวช./ปวส.`, `ปริญญาตรี`, `ปริญญาโท+`) และแยกประสบการณ์เป็น 5 ระดับ (`ไม่ระบุ/ไม่จำเป็น`, `0 ปี / จบใหม่`, `1-2 ปี`, `3-5 ปี`, `5+ ปี`)

### 3.4.2 อนุกรมวิธานทักษะและการสกัดทักษะ (`taxonomy/` & `extract_skills.py`, `map_taxonomy.py`)
- สร้าง `taxonomy/skills.csv` (≥ 110 ทักษะมาตรฐาน ครอบคลุม `tool`, `technical`, `soft`, `language`, `licence` พร้อมรหัสอ้างอิง `onet_ref`, `esco_ref`), `taxonomy/aliases.csv` (≥ 250 คำพ้องไทย/อังกฤษ), และ `taxonomy/occupations.csv` (กลุ่มอาชีพหลัก)
- ทำการ normalize ข้อความ ตัดคำภาษาไทยด้วย **PyThaiNLP `newmm`** และจับคู่ alias โดยใช้ `word_boundary` / `regex` สำหรับคำสั้นกำกวม (เช่น `Word`, `R`, `SQL`, `ขาย`)
- **คิวเสนอ Alias ใหม่ (ไม่ใช้ AI):** นับความถี่คำที่ไม่ตรงในพจนานุกรม แล้วจับคู่กับ alias ที่มีอยู่ด้วย **Trigram Similarity ($\ge 0.4$)** เพื่อเสนอรายชื่อให้ Admin พิจารณาอนุมัติในหน้า `/admin/taxonomy`
- **การประเมินความแม่นยำด้วยคนจริง (`eval/`):** จัดทำคู่มือ `eval/labeling-guideline.md` สคริปต์สุ่มแบ่งชั้น `eval/prepare_gold_set.py` (200 ประกาศ โดยไม่เก็บเนื้อหาประกาศลง `eval/`) และ `eval/evaluate_skills.py` สำหรับคำนวณ Precision, Recall (ภายใน Taxonomy), F1 และ Cohen's Kappa

### 3.4.3 การตรวจสอบคุณภาพข้อมูล 8 ด้าน (`validate.py`)
ระบบตรวจสอบคุณภาพข้อมูลทั้ง 8 ด้าน (Completeness, Validity, Uniqueness, Consistency, Freshness, Taxonomy, Compliance, Sampling) ก่อนโหลดเข้า `dw` และบันทึกผลลง `staging.dq_result` โดยตรวจสอบเป็นพิเศษว่าไม่มีคอลัมน์ HR contact และไม่มี `gender`/`age` ในชุดข้อมูล ML

---

## 3.5 กระบวนการ Machine Learning และการให้บริการ Champion API

1. **การเตรียม Feature (`pipeline/ml/features.py`):**
   - ตัวแปรเข้า (Input Features): `occupation_cluster`, `province_th`, `region`, `experience_band`, `education_level`, `employment_type`, `industry`, `n_skills`, และ multi-hot encoding ของทักษะยอดนิยม Top-K
   - **ตัวแปรต้องห้าม:** มีชุดทดสอบ `pytest` ยืนยันว่าไม่มี `gender`, `age`, `mentions_gender`, `mentions_age` และ `company_name` อยู่ในชุด feature ของโมเดล
   - เป้าหมาย (Target): `log(salary_mid)` สำหรับประกาศที่มี `has_salary = True` (ไม่ถ่วง `sample_weight` ในการเทรน ML)
2. **การเปรียบเทียบโมเดลและ Nested CV (`benchmark.py`, `champion.py`):**
   - เปรียบเทียบ Baseline (ค่ามัธยฐานตาม `occupation_cluster × region`) ร่วมกับ **5 โมเดล** (Ridge, Random Forest, XGBoost, LightGBM, CatBoost)
   - ประเมินผลด้วย **`GroupKFold(5, group=company_key)`** ชั้นนอก และจูน Hyperparameter แบบ **Nested `GroupKFold(3)`** ชั้นใน (Randomized Search ≤ 20 รอบ) เพื่อให้ fold นอกไม่ถูกใช้คัดเลือก hyperparameter
   - เลือกโมเดล Champion จากค่า RMSE เฉลี่ยต่ำสุด (ต้องดีกว่า Baseline ชัดเจนและเสถียรข้าม fold) คำนวณ Residual Quantile สำหรับช่วง `p25–p75` และ Feature Importance แล้วบันทึกลง `ml.*`
3. **การ Export และให้บริการ (`export_model.py` & `services/ml-api`):**
   - บันทึกไฟล์ `models/salary_champion.joblib` (หรือไฟล์ native) คู่กับ `models/feature_spec.json`
   - พัฒนา FastAPI Service (`GET /health`, `POST /predict`, `POST /predict/batch` ที่ตรวจ Header `X-ML-Key`) เพื่อรับคำขอจาก Vercel Proxy `/api/salary/estimate` และคำนวณตาราง `mart.salary_prediction` ล่วงหน้าสำหรับเป็นระบบ Fallback

---

## 3.6 การออกแบบเว็บแอปพลิเคชัน UI Liquid Glass และแชท Gemini

1. **โครงสร้างหน้าจอ (`apps/web`):** ครอบคลุมหน้าสาธารณะ (`/`, `/market`, `/occupations/[slug]`, `/skills/[slug]`, `/salary`, `/ml-lab`, `/privacy`, `/about`), ส่วนนักศึกษา (`/me/skills`, `/me/gap`), ส่วนสถานศึกษา (`/institution/curricula`, `/institution/curricula/[id]`), ส่วนผู้ดูแล (`/admin/pipeline`, `/admin/quality`, `/admin/taxonomy`, `/admin/sources`), และหน้าเข้าสู่ระบบพร้อมปุ่มเดโม 4 Persona (`/login`)
2. **Design System (Liquid Glass & ECharts):** ใช้การ์ด `.glass` / `.glass-strong` ร่วมกับ `.chart-surface` พื้นทึบ 94% ใต้กราฟ ECharts ยึดสีตัวตน `#6C5CE7` (ฉัน/หลักสูตร), `#E0623F` (ตลาด), `#0E9AAE` (เปรียบเทียบ) พร้อมปุ่ม "ดูเป็นตาราง", `<ProvenanceBadge>` และโหมด `data-glass="off"`
3. **ผู้ช่วยแชท Gemini (`POST /api/chat`):** รวบรวมข้อมูลหน้าจอผ่าน `usePageContext()` ตัดขนาดไม่เกิน ~6,000 tokens (ไม่ส่งข้อความประกาศหรือ PII) ควบคุม Rate limit (ล็อกอิน 20 ข้อ/วัน, เยี่ยมชม 5 ข้อ/วัน/IP) บันทึกสถิติคำถามลง `app_chat_log` และทดสอบ Grounded Check ด้วยชุดคำถาม 30 ข้อ

---

## 3.7 แผนการทดสอบและประเมินผลระบบ

| ด้านการประเมิน | วิธีการและเครื่องมือ | เกณฑ์ความสำเร็จ |
|---|---|---|
| **หน่วยย่อย (Unit Tests)** | `pytest` สำหรับ Scraper, Salary Cleaner (30 รูปแบบ), Skill Extractor, ML Leakage Check | ผ่านทุก Test Case 100% |
| **คุณภาพข้อมูล (DQ)** | `validate.py` ตรวจ 8 ด้าน | ฟิลด์หลัก ≥ 95%, ซ้ำ < 2%, ทักษะ ≥ 1 อย่าง ≥ 90% |
| **ความแม่นยำทักษะ** | ตรวจมือ 200 ประกาศ + ซ้ำ 50 ประกาศ | Precision ≥ 85%, วัด Recall & Cohen's κ |
| **ฟังก์ชันและ E2E** | Test Case F1–F9 + Playwright 3 บทบาท | ผ่านครบทุก Flow หลัก |
| **ความปลอดภัย (RLS)** | ทดสอบ User A/B, Visitor, ยกระดับ Admin | บล็อกการเข้าถึงข้ามสิทธิ์และการแก้ role 100% |
| **แชท Gemini** | ทดสอบ 30 คำถาม (Grounded Check) | ตอบตรงตัวเลขบนหน้า/ปฏิเสธเหมาะสม |
| **ประสิทธิภาพและความพึงพอใจ** | Lighthouse Mobile + เวลาโหลด Mart + แบบสอบถาม Likert 5 ระดับ (≥ 30 คน) | โหลดหน้า Market < 3 วินาที, รายงาน $\bar{x}$ ± S.D. |
