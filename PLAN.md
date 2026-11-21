# PLAN.md — แผนโครงงาน (v4: Skill Demand Intelligence / E′)

> v4.2 · 18 พ.ย. 2569 (v4 + ปรับหลังรีวิว D13–D18 + deploy 2 ที่ D19) · แทนที่ v3 (เก็บไว้ที่ `docs/archive/PLAN-v3.md`) · เอกสารที่เกี่ยวข้อง: [CONTEXT.md](CONTEXT.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) · [FRONTEND_SPEC.md](FRONTEND_SPEC.md) · **[TASKS.md](TASKS.md)** (งานย่อยรายสัปดาห์) · [docs/data-spike-2026-11-18.md](docs/data-spike-2026-11-18.md)

---

## 1. บันทึกการตัดสินใจ (Decisions log)

| # | ตัดสินใจ | เหตุผล |
|---|---|---|
| D1 | เลือกหัวข้อ **E′ Skill Demand Intelligence (data-first)** | ข้อมูลหาได้จริง (spike), ตรงกับกรรมการสาย Data, ไม่ติดข้อจำกัดข้อมูลชายแดนใต้ |
| D2 | แหล่งหลัก **JobThai**, ภายหลัง JobBKK; **ห้าม** JobTopGun, JobsDB, Indeed | ToS/robots (ดู spike) |
| D3 | **ไม่มีระบบสมัครงาน/สรรหา/บริษัทลงประกาศ/ติดตามการเรียน** | ลดขอบเขตเหลือเท่าที่เสร็จใน 16 สัปดาห์ |
| D4 | เว็บแสดงเฉพาะ **aggregate + ลิงก์ต้นฉบับ** | ToS ห้ามเผยแพร่ซ้ำ |
| D5 | ML: เทียบ ≥ 5 โมเดลตอนทดสอบ แต่ **ระบบจริงใช้ champion ตัวเดียว** | โชว์ผลวัดผลโดยไม่เพิ่มภาระระบบ |
| D6 | **ห้ามใช้เพศ/อายุเป็น feature** | ความเป็นธรรม; ประกาศระบุเพศ 27%, อายุ 58% (ตัวอย่าง n = 131) |
| D7 | Gemini = ไอคอนแชทลอย ตอบจาก `pageContext`; ไม่ Text-to-SQL, ไม่ label ข้อมูล | ลดความเสี่ยง/ตรวจสอบได้ |
| D8 | Taxonomy ของโครงงานเอง (alias ไทย/อังกฤษ) อ้างอิง O*NET/ESCO | O*NET ตรงแค่ 5/21, ESCO ไม่มีไทย |
| D9 | Deploy ฟรี **2 ที่ + DB**: Next.js บน **Vercel** · **Supabase** (DB/Auth) · **ml-api (FastAPI) บน Render free หรือเซิร์ฟเวอร์มหาวิทยาลัย**; scraper/ETL รันบนเครื่องตัวเอง/มหาวิทยาลัย (ดู D19, [docs/DEPLOY.md](docs/DEPLOY.md)) | ฟรี |
| D10 | แยก schema `staging/dw/mart/ml` + RLS ทุกตาราง `public` ตั้งแต่ migration แรก | บทเรียนจากโครงการเดิม |
| D11 | UI สไตล์ **Liquid Glass** บนโครงภาพอ้างอิง, ECharts, มี fallback ทึบ | ดู DESIGN_SYSTEM.md |
| D12 | Scrape สุภาพ: 1 request, ≥ 5 วินาที, หยุดเมื่อ 403/429/CAPTCHA, ตัดข้อมูล HR | ToS/PDPA |
| D13 | สุ่มแบบแบ่งชั้นจังหวัด × หมวด **จัดสรรตามสัดส่วน + ขั้นต่ำชั้นละ 5** และเก็บ `sample_weight` ใน fact; สัดส่วนใน mart ถ่วงน้ำหนัก | กันตัวเลขระดับประเทศเอียง (ARCH §4) · +0.5 วัน |
| D14 | เก็บ `first_seen`/`last_seen` จาก re-discovery รายสัปดาห์; แนวโน้มเป็น **รายสัปดาห์** (`mart.skill_demand_weekly`) | ข้อมูลเป็น snapshot ประกาศที่เปิดอยู่ และมีช่วงเวลาแค่ ~3–4 เดือน · +0.5–1 วัน |
| D15 | ML tuning แบบ **nested** (GroupKFold ชั้นใน) | กันผลวัดดีเกินจริง · +0.5 วัน |
| D16 | ชุดตรวจมือ 200 ประกาศมี **คู่มือ label** + Cohen's κ (ถ้าทำ ≥ 2 คน); recall นับเฉพาะทักษะใน taxonomy | ผลวัดตรวจสอบได้ · +0.5 วัน |
| D17 | ~~ทดสอบ ONNX บน Vercel~~ → แทนด้วย D19 | — |
| D18 | ตัดฟีเจอร์ "นำเข้า résumé"; เทียบหลักสูตร/PDF = Should; คิว alias เสนอด้วยกฎ (`pg_trgm`) ไม่ใช้ AI; Landing อ่าน `mart.public_summary`; ผู้ใช้ตั้ง role admin เองไม่ได้ (RLS) | ให้ตรงข้อตกลง D3/D7 และแก้ช่องโหว่สิทธิ์ · 0 วัน |
| D19 | Champion เสิร์ฟผ่าน **FastAPI `services/ml-api`** บน **Render free** (ค่าเริ่มต้น) หรือ **เซิร์ฟเวอร์มหาวิทยาลัย** (ถ้าได้ HTTPS สาธารณะ); ไม่ export ONNX; fallback `mart.salary_prediction`; **ไม่ใช้ Railway** (ไม่ฟรีพอ 16 สัปดาห์) | ตัดความเสี่ยง ONNX บน Vercel, ใช้โมเดล Python ตรง · +1 วัน (ml-api) −1 วัน (ONNX) ≈ 0 |

---

## 2. นิยามโครงงาน

- **ชื่อไทย:** ระบบวิเคราะห์ความต้องการทักษะในตลาดแรงงานไทยจากประกาศงาน ด้วยคลังข้อมูลและการเรียนรู้ของเครื่อง
- **ชื่ออังกฤษ:** Skill Demand Intelligence: A Data Warehouse and Machine Learning–Based System for Analyzing Skill Demand from Thai Job Postings
- **วัตถุประสงค์**
  1. พัฒนากระบวนการเก็บ คลีน และจัดโครงสร้างประกาศงานทั่วประเทศ (scraper → staging → คลังข้อมูล Star/Galaxy) พร้อมตัวชี้วัดคุณภาพข้อมูล
  2. สร้าง taxonomy ทักษะภาษาไทย/อังกฤษและกระบวนการดึงทักษะจากข้อความประกาศ
  3. พัฒนาเว็บแอปแสดงความต้องการทักษะ เงินเดือน และ skill gap สำหรับนักศึกษา/ผู้จบใหม่ และรายงาน curriculum alignment สำหรับสถานศึกษา
  4. เปรียบเทียบโมเดล ML อย่างน้อย 5 โมเดลสำหรับประมาณเงินเดือน และนำโมเดลที่ดีที่สุดมาใช้ในระบบ
  5. ประเมินประสิทธิภาพของระบบและความพึงพอใจของผู้ใช้
- **ขอบเขต:** ประกาศงานทั่วประเทศจาก JobThai (ตัวอย่างหลักพัน–หมื่นประกาศ) · วิเคราะห์ทักษะ, เงินเดือน, ตำแหน่ง, พื้นที่, ประสบการณ์/วุฒิ · ผู้ใช้ 3 กลุ่ม (นักศึกษา, สถานศึกษา, admin)
- **นอกขอบเขต:** ระบบสมัคร/สรรหา, บริษัทลงประกาศ, แสดงเนื้อหาประกาศ, ทำนายตลาดอนาคต, ข้อมูลเชิงพาณิชย์

---

## 3. ผู้ใช้และหน้าจอ

(รายละเอียดอยู่ใน [FRONTEND_SPEC.md](FRONTEND_SPEC.md) · ทุกหน้ามีไอคอนแชท Gemini ลอยมุมขวาล่าง)

| กลุ่ม | หน้า | คำถามที่ตอบ |
|---|---|---|
| ทุกคน | **Market Explorer**, Occupation detail, Skill detail | ตลาดต้องการทักษะอะไร เปลี่ยนอย่างไร |
| ทุกคน | **Salary Explorer/Estimator** (champion) | เงินเดือนช่วงไหนสมเหตุสมผล |
| Student | **My Skills + Skill Gap** | ฉันขาดอะไร ตำแหน่งไหนตรงกับฉัน |
| Institution | **Curriculum Alignment** | หลักสูตรครอบคลุมทักษะตลาดแค่ไหน |
| ทุกคน | **ML Lab** | โมเดลไหนดีที่สุด เชื่อได้แค่ไหน |
| Admin | **Pipeline / Data Quality / Taxonomy review / Sources** | ข้อมูลสดและถูกต้องไหม |
| กรรมการ | Login + เดโมคลิกเดียว 4 persona | |

---

## 4. Data pipeline

```text
JobThai (listing ราย จังหวัด/หมวด, Playwright) → detail (JSON-LD) → data/raw (ดิสก์)
 → staging.job_posting_raw (ตัด HR contact)
 → clean/normalize (เงินเดือน, สถานที่, บริษัท, วุฒิ/ประสบการณ์, dedupe)
 → skill extraction (dictionary + alias + PyThaiNLP)
 → taxonomy mapping (alias→skill, title→occupation cluster)
 → validate (DQ checks)
 → dw (dim_*, fact_*) → mart (aggregate) → เว็บ / ML
```
| ขั้น | เครื่องมือ | ผลที่ต้องได้ |
|---|---|---|
| Discovery/Fetch | Playwright + httpx, 1 req/≥5 s | job id ต่อจังหวัด/หมวด, HTML ดิบบนดิสก์ |
| Parse | JSON-LD (`spike/scripts/parse_jobposting.py`) | ฟิลด์มาตรฐาน ไม่มีข้อมูล HR |
| Clean | pandas | เงินเดือนเป็นบาท/เดือน, จังหวัดมาตรฐาน, dedupe |
| Skill extraction | dictionary + alias, PyThaiNLP `newmm` | `fact_posting_skill` |
| Taxonomy | CSV + คิว alias ที่ admin อนุมัติ | 100–200 ทักษะ, ครอบคลุม ≥ 90% ของประกาศ |
| Validate | SQL/Python checks | `dq_result`, รายงาน |
| DW/Marts | SQL migrations, materialized views | ตารางที่หน้าเว็บอ่าน |
ขนาดที่คาด: ตัวอย่าง 5,000–10,000 ประกาศ (ที่ ~600/ชม. = 8–17 ชม. กระจายหลายคืน) ถ้าเงินเดือนเป็นตัวเลข ~56% จะมีแถว ML ราว 2,800–5,600 แถว · ข้อมูลทั้งหมดอยู่ในโควตา Supabase 500 MB เมื่อไม่เก็บ HTML ดิบ
**การสุ่ม (D13):** discovery เก็บ id ทุกตัวลง `staging.listing_seen` → จัดสรรตามสัดส่วนจังหวัด × หมวด (ขั้นต่ำชั้นละ 5) → `sample_weight = N_ชั้น / n_ชั้น` · **re-discovery รายสัปดาห์ (D14)** เปิดเฉพาะหน้ารายการ เพื่ออัปเดต `last_seen` และหาประกาศใหม่

---

## 5. Data Warehouse (Star / Galaxy)

DDL เต็มอยู่ใน [ARCHITECTURE.md §3](ARCHITECTURE.md)
- **Dimensions:** `dim_date`, `dim_job_title/occupation`, `dim_skill` (+ `skill_alias`), `dim_company`, `dim_location`, `dim_education`, `dim_experience`, `dim_employment_type`, `dim_source`
- **Facts:** `fact_job_posting` (grain 1 ประกาศ; มี `first_seen`/`last_seen`, `sample_weight`), `fact_posting_skill` (grain ประกาศ × ทักษะ), `fact_labor_monthly` (optional, ตัวเลขภาครัฐรายเดือน)
- **Marts (aggregate):** `skill_demand_weekly`, `skill_cooccurrence`, `occupation_skill_profile`, `salary_stats`, `posting_volume_daily`, `curriculum_coverage_ref`, `public_summary`, `pipeline_status`, `dq_summary`, `ml_leaderboard`, `salary_prediction`, `top_links`
- **App tables (RLS):** `app_profile`, `app_user_skill`, `app_curriculum`, `app_curriculum_skill`, `app_chat_log`, `app_alias_suggestion`
- **ML:** `ml.experiment`, `ml.model_result`, `ml.feature_importance`

---

## 6. Machine Learning

**งานหลัก: ประมาณเงินเดือน (Regression)** — target = log(เงินเดือนกลางช่วงต่อเดือน) เฉพาะประกาศที่ระบุตัวเลข

| รายการ | รายละเอียด |
|---|---|
| Features | กลุ่มอาชีพ, จังหวัด/ภาค, band ประสบการณ์, วุฒิ, ประเภทการจ้าง, อุตสาหกรรม, จำนวนทักษะ, multi-hot ทักษะ top-K — **ไม่มีเพศ/อายุ/ชื่อบริษัท** |
| โมเดล | Baseline (มัธยฐาน occupation × ภาค), Ridge, Random Forest, XGBoost, LightGBM, CatBoost |
| การวัดผล | 5-fold **GroupKFold (group = บริษัท)**, R², RMSE, MAE, MAPE (ค่าเฉลี่ย ± SD), เวลาเทรน · tuning แบบ **nested** (random search ≤ 20 รอบ, GroupKFold(3) ชั้นใน) · ML ใช้แถวจริงไม่ถ่วง `sample_weight` |
| เลือก champion | RMSE เฉลี่ยต่ำสุด ต้องดีกว่า baseline ชัดเจนและเสถียรข้าม fold |
| ใช้ในระบบจริง | champion ตัวเดียว: FastAPI `services/ml-api` (Render free/เซิร์ฟเวอร์มหาวิทยาลัย) ผ่าน proxy `/api/salary/estimate` + คำนวณล่วงหน้าลง `mart.salary_prediction` (fallback); โมเดลอื่นแสดงเฉพาะ ML Lab |
| การอธิบาย | feature importance (permutation/SHAP ของ champion) แสดงเป็นช่วงค่าคาด p25–p75 |
| ข้อจำกัดที่ต้องเขียน | selection bias ของประกาศที่ระบุเงินเดือน, เงินเดือนประกาศ ≠ เงินเดือนจริง, ตัวอย่างไม่ใช่ census |

**งานรอง (Should): จัดกลุ่มตำแหน่งเป็น occupation cluster** ด้วยกฎ + (ถ้ามีเวลา) TF-IDF + clustering ไว้ตรวจความสอดคล้อง ไม่ใช่ฟังก์ชันหลัก

**แชท Gemini:** `POST /api/chat {question, pageContext}` ตอบจากข้อมูลบนหน้าเท่านั้น (ดู ARCHITECTURE §8)

---

## 7. คุณภาพข้อมูล (Data quality metrics)

Completeness, Validity, Uniqueness, Consistency, Freshness, Taxonomy coverage/precision, Compliance — รายละเอียด check ใน ARCHITECTURE §7 · เป้าหมายเริ่มต้น: ฟิลด์หลัก ≥ 95% ครบ, ซ้ำ < 2%, ประกาศมีทักษะ ≥ 1 ≥ 90%, precision ทักษะ (ตรวจมือ 200 ประกาศ) ≥ 85%

---

## 8. การทดสอบและประเมินผล (รูปแบบโครงงาน)

| หัวข้อ | วิธี | ผลที่เสนอในเล่ม |
|---|---|---|
| ฟังก์ชันระบบ | ตาราง test case ทุก use case (F1–F9) + E2E flow หลัก 3 role | ผ่าน/ไม่ผ่าน, บั๊กที่แก้ |
| คุณภาพข้อมูล | ผล DQ ต่อรอบ + จำนวนประกาศ/จังหวัด/หมวด | ตาราง + กราฟ |
| ดึงทักษะ | ตรวจมือ **200 ประกาศ** (สุ่มแบ่งชั้นหมวด) ตาม **คู่มือ label** (`eval/labeling-guideline.md`): precision / recall ต่อกลุ่มทักษะ (recall นับเฉพาะทักษะที่อยู่ใน taxonomy + รายงานทักษะนอก taxonomy แยก) · ถ้า ≥ 2 คน ตรวจซ้ำ 50 ประกาศหา Cohen's κ | ตาราง + ตัวอย่างข้อผิดพลาด + κ |
| ML | Leaderboard 5 โมเดล + baseline, ผลราย fold, feature importance | ตาราง + กราฟ |
| แชท | ชุดคำถาม 30 ข้อ (3 ข้อต่อหน้า) ตรวจว่าตอบตรงกับตัวเลขบนหน้า ไม่แต่งตัวเลข (grounded check) | % ตอบถูกต้อง/ปฏิเสธเหมาะสม |
| ความปลอดภัย | ทดสอบ RLS: ผู้ใช้ A อ่านข้อมูล B ไม่ได้, visitor เข้า admin ไม่ได้ | ตารางผล |
| ความพึงพอใจ | แบบสอบถาม **Likert 5 ระดับ** (ความถูกต้อง ใช้งานง่าย ประโยชน์ การออกแบบ) หา x̄, S.D. จากผู้ทดลองใช้ตามจำนวนที่อาจารย์กำหนด (เสนอ ≥ 30 คน: นักศึกษา + อาจารย์) | ตาราง x̄ ± S.D. |

---

## 9. Roadmap 16 สัปดาห์ (ปรับตามวันสอบจริง · แตกเป็นงานย่อยใน [TASKS.md](TASKS.md))

> v4.1 เพิ่มงานรวม ~2.5–3 วัน (D13–D17) กระจายอยู่ใน Phase 1–4 โดยใช้ buffer สัปดาห์ 13 · ยังไม่ตัดงานใด รอคำตอบ §11 (จำนวนคน/วันสอบ)

| สัปดาห์ | งาน | ผลที่ต้องได้ |
|---|---|---|
| 1–2 | ตั้ง repo, Supabase, migration แรก (schemas + RLS), scraper รายจังหวัดต้นแบบ, ขอหนังสืออนุญาต, taxonomy ชุดแรก | scrape ได้ 500 ประกาศเข้า staging, ทักษะ 100 รายการ |
| 3–5 | เก็บข้อมูลหลัก (หลายคืน), clean, extract skills, DW, marts, DQ | ข้อมูล 5,000+ ประกาศ + รายงานคุณภาพข้อมูล |
| 5–7 | เว็บ: shell + Liquid Glass tokens, auth/RLS/เดโม, Market Explorer, Skill/Occupation detail | เดโมหน้าตลาดทักษะ |
| 7–9 | My Skills, Skill Gap, Curriculum Alignment | flow นักศึกษา + สถานศึกษาใช้ได้ |
| 9–11 | ML benchmark 5 โมเดล, champion + ml-api (FastAPI), Salary Estimator, ML Lab | ตารางเทียบโมเดล + หน้า Salary |
| 11–12 | แชท Gemini ลอยทุกหน้า, Admin (pipeline/quality/taxonomy) | ครบทุกหน้า |
| 13 | ตรวจมือ 200 ประกาศ, ปรับ taxonomy, JobBKK (ถ้ามีเวลา), ปรับ UI/มือถือ | precision ทักษะ, UI ผ่าน checklist |
| 14–15 | ทดสอบทุกด้าน, แบบสอบถาม, แก้ไข | รายงานผลทดสอบ |
| 16 | เล่ม, สไลด์, วิดีโอสำรอง, ซ้อมนำเสนอ | พร้อมสอบ |

---

## 10. ความเสี่ยงและทางแก้

| ความเสี่ยง | ทางแก้ |
|---|---|
| JobThai ไม่อนุญาต/บล็อก (403/429/CAPTCHA) | หยุดทันที ไม่หลบเลี่ยง; เก็บ snapshot ให้ได้ก่อนสัปดาห์ 5; ขอหนังสืออนุญาตตั้งแต่สัปดาห์ 1; ใช้ JobBKK/ข้อมูลที่เก็บแล้วเป็นสำรอง · **กติกาตัดสิน:** ปฏิเสธ → หยุดเก็บ ใช้ข้อมูลที่มีตามความเห็นอาจารย์ (ลบถ้าถูกขอ) · ไม่ตอบภายในสัปดาห์ 3 → อาจารย์ตัดสินเป็นลายลักษณ์อักษร (CONTEXT §5.1) |
| ml-api หลับ (Render free หลัง 15 นาที, cold start ~1 นาที) / เซิร์ฟเวอร์มหาวิทยาลัยล่ม | ปลุกด้วย `GET /health` ตอนเปิดหน้า Salary, ping cron-job.org ทุก 14 นาทีช่วงเดโม/วันสอบ, timeout 8 วินาที → fallback `mart.salary_prediction` พร้อมป้าย |
| หน้าเว็บ/ JSON-LD เปลี่ยน | parse จาก JSON-LD, selector อยู่ไฟล์เดียว, เก็บ HTML ดิบเพื่อ re-parse |
| ToS ห้ามเผยแพร่ซ้ำ | aggregate + ลิงก์เท่านั้น, ไม่ commit ข้อมูลดิบ, หนังสืออนุมัติอาจารย์ |
| ข้อมูลเงินเดือนน้อย/เอียง | รายงาน selection bias, ใช้ GroupKFold, แสดงช่วงไม่ใช่ค่าเดียว, ซ่อนเมื่อ n < 5 |
| Taxonomy ไม่ครอบคลุม/ precision ต่ำ | คิว alias + admin อนุมัติ, วัดผลด้วยตรวจมือ, เริ่มจากทักษะที่ชัด |
| ประสิทธิภาพ glass/ECharts บนมือถือ | ลด blur, ไม่ซ้อนแก้ว, lazy-load กราฟ, สลับเป็นทึบได้ |
| Supabase หลับ / Gemini quota หมดวันสอบ | ping อัตโนมัติ, คำตอบเดโมสำรอง, วิดีโอสำรอง |
| PDPA | ไม่เก็บข้อมูล HR, ผู้ใช้ลบข้อมูลตนเองได้, privacy notice |
| ขอบเขตบวม | ยึดหมวด Must ใน TASKS.md; เพิ่มงานต้องถามและแจ้งผลต่อเวลา |

---

## 11. คำถามที่ต้องยืนยัน
1. **ทำกี่คน** และแบ่งบทบาท (data/pipeline, ML, frontend, เอกสาร)
2. **วันสอบ/ส่งโครงงานจริง** เพื่อปรับ roadmap
3. **เกณฑ์อาจารย์ที่ปรึกษา:** จำนวนผู้ตอบแบบสอบถามขั้นต่ำ, ต้องมีผู้เชี่ยวชาญประเมินไหม, รูปแบบเล่ม
4. อาจารย์ช่วยออกหนังสืออนุมัติ/ติดต่อ JobThai ได้หรือไม่
5. จะใช้ภาษาใดเป็นหลักบนหน้าเว็บ (ค่าเริ่มต้นเสนอ: ไทย + สลับ EN)
