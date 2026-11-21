# TASKS.md — แผนงานย่อยรายสัปดาห์ (ตาม PLAN v4 หัวข้อ 9)

> สัญลักษณ์: `[ ]` ยังไม่ทำ · `[x]` เสร็จตาม DoD · `[~]` มีโค้ด/ร่างแล้ว แต่ DoD ยังขาดส่วนที่ต้องใช้ Supabase จริง ข้อมูลจริง หรือคน (ดู docs/PROGRESS.md) · แต่ละงาน ≈ 0.5–2 วัน · **DoD** = เกณฑ์ว่าเสร็จ · **รอ** = งานที่ต้องเสร็จก่อน · ระดับ **M**ust / **S**hould / **C**ould
> ขอบเขตห้ามบวกเอง: เพิ่ม/ตัดงานต้องถามและแจ้งผลต่อเวลา · อ้างอิง: [PLAN.md](PLAN.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [FRONTEND_SPEC.md](FRONTEND_SPEC.md) · [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md)
> v4.1 (18 พ.ย. 2569): ปรับตาม PLAN D13–D18 — งานที่แก้/เพิ่มมีป้าย ⟨v4.1⟩ รวม ~2.5–3 วัน · v4.2: deploy 2 ที่ (D19) ป้าย ⟨v4.2⟩ ≈ 0 วันสุทธิ
> **วิธีทำงานของ agent:** ดู [AGENTS.md](AGENTS.md) · ทำเสร็จแล้วติ๊ก `[x]` + บันทึกใน [docs/PROGRESS.md](docs/PROGRESS.md) · งานที่ต้องใช้คนจริง (ติด label gold set, แบบสอบถาม, ส่งหนังสือ, สร้างบัญชี) มีป้าย 👤

---

## Phase 0 — Setup และข้อตกลง (สัปดาห์ 1)
- [~] **T0.1 (M)** `git init` + ตั้ง repo (`apps/web`, `pipeline`, `services/ml-api`, `taxonomy`, `supabase/migrations`, `eval`, `models`, `docs`) + `.gitignore` (มีแล้ว) + README (มีแล้ว) · DoD: clone แล้วรันตามคำสั่งได้
- [~] **T0.2 (M)** 👤 สร้างโปรเจกต์ Supabase + เก็บ key ใน `.env.local` (ไม่ commit; agent เตรียม `.env.example` และสคริปต์ทดสอบเชื่อมต่อรอไว้) · DoD: ต่อฐานข้อมูลจาก Python และ Next.js ได้
- [x] **T0.3 (M)** 👤 ขอหนังสืออนุมัติจากอาจารย์ + ร่างอีเมลขออนุญาต JobThai (agent ร่างเอกสารใน `docs/letters/` ให้ครบ ผู้ใช้ส่งจริง) · DoD: ส่งแล้ว เก็บสำเนา
- [ ] **T0.4 (M)** 👤 ยืนยันคำถามเปิด (จำนวนคน, วันสอบ, เกณฑ์อาจารย์) แล้วปรับ roadmap · DoD: PLAN §11 ถูกตอบ
- [ ] **T0.5 (S)** ตั้ง Task Scheduler (re-discovery รายสัปดาห์) + ping Supabase ด้วย cron-job.org (กัน pause 7 วัน) · รอ T0.2
- [ ] **T0.6 (M)** 👤 ⟨v4.2⟩ ถาม IT มหาวิทยาลัย: มีเครื่อง/VM ให้รัน Python (scraper + ml-api) พร้อม HTTPS สาธารณะไหม → บันทึกคำตอบใน `docs/DEPLOY.md` (ค่าเริ่มต้นใช้ Render free ไปก่อนได้ทันที) · DoD: เลือก host ml-api ได้ (มหาวิทยาลัย / Render)

## Phase 1 — Scraper (สัปดาห์ 1–2, เก็บจริงสัปดาห์ 3–5)
- [x] **T1.1 (M)** Migration 001: schemas `staging/dw/mart/ml` + `scrape_run`, `listing_seen` ⟨v4.1⟩, `job_posting_raw`, `dq_result` (ARCH §3.1–3.2) · DoD: `supabase db reset` ผ่าน · รอ T0.2
- [x] **T1.2 (M)** รีแฟกเตอร์ `parse_jobposting.py` → `pipeline/scraper/parse.py` + unit test กับ HTML ตัวอย่าง 20 ไฟล์ · DoD: parse ครบ ไม่มีฟิลด์ HR contact
- [~] **T1.3 (M)** `discovery.py`: Playwright เปิด `?province=XX` เลื่อนหน้าเก็บ job id → บันทึกทุก id ลง `listing_seen` พร้อม stratum ⟨v4.1⟩ · DoD: ได้ id ≥ 90% ของ total จังหวัดเล็ก 3 จังหวัด
- [x] **T1.4 (M)** `fetch.py`: 1 req, ≥ 5 s, jitter, resume, หยุดเมื่อ 403/429/CAPTCHA + บันทึกสถานะ · DoD: test จำลอง 429 แล้วหยุดจริง
- [~] **T1.5 (M)** `load_staging.py`: parse → `job_posting_raw` (dedupe ด้วย `content_hash`) · DoD: โหลด 500 ประกาศ ซ้ำแล้วไม่เพิ่มแถว
- [~] **T1.6 (M)** discovery รายหมวดสำหรับกรุงเทพฯ/ชลบุรี (จังหวัดที่มีประกาศเกินเพดานหน้า) · รอ T1.3
- [x] **T1.7 (M)** วางแผนสุ่มแบบแบ่งชั้น (จังหวัด × หมวด) **จัดสรรตามสัดส่วน + ขั้นต่ำชั้นละ 5** → ตาราง quota + `sample_weight = N_h / n_h` ⟨v4.1, D13⟩ · DoD: สคริปต์แสดงจำนวนที่ต้องดึงต่อชั้น และ Σ น้ำหนักต่อชั้น = N_h
- [~] **T1.8 (M)** รันเก็บจริงหลายคืน → เป้า ≥ 5,000 ประกาศ · DoD: `scrape_run` ทุกรอบสถานะชัด, ไม่ถูก block · รอ T1.4–T1.7, T0.3
- [ ] **T1.10 (M)** ⟨v4.1, D14⟩ `rediscover.py` รายสัปดาห์: เปิดเฉพาะหน้ารายการ (ไม่โหลดหน้าประกาศซ้ำ) → อัปเดต `listing_seen` + ดึงเฉพาะประกาศใหม่ตาม quota · DoD: รัน 2 สัปดาห์ติด ได้ `last_seen` เปลี่ยนจริง · รอ T1.8 · 0.5–1 วัน
- [~] **T1.9 (C)** JobBKK scraper (Playwright) · รอ Phase 3 เสร็จ

## Phase 2 — ETL และ Taxonomy (สัปดาห์ 2–5)
- [x] **T2.1 (M)** `clean.py`: เงินเดือนตามกฎ ARCH §5.1 (ช่วง → กลางช่วง, "ขึ้นไป" → mid = min + ธง, วัน × 26, ชม. × 8 × 26, "ตามตกลง" → NULL, นอก 5,000–500,000 → NULL) ⟨v4.1⟩, จังหวัด/อำเภอ, ชื่อบริษัท normalize · DoD: test ครอบ 30 รูปแบบเงินเดือนจริง
- [~] **T2.2 (M)** วุฒิ/ประสบการณ์ regex → band · DoD: ตรวจมือ 50 ประกาศ ≥ 90% ถูก
- [x] **T2.3 (M)** taxonomy v0: `skills.csv` 100 ทักษะ + `aliases.csv` ไทย/อังกฤษ (เริ่มจาก dictionary ใน `analyze_sample.py`) · DoD: โหลดเข้า `dim_skill`/`skill_alias`
- [x] **T2.4 (M)** `extract_skills.py`: normalize + PyThaiNLP `newmm` + จับ alias (word boundary EN, token TH) · DoD: ประกาศมีทักษะ ≥ 1 ≥ 90%
- [x] **T2.5 (M)** `occupations.csv` + `map_taxonomy.py` (title → occupation cluster, 15–25 cluster) · DoD: ครอบคลุม ≥ 85% ของประกาศ
- [x] **T2.6 (M)** คิว alias pending: นับคำถี่ที่ไม่ map → ไฟล์/ตาราง `app_alias_suggestion`/ staging พร้อมทักษะที่เสนอด้วย `pg_trgm similarity` (ไม่ใช้ AI) ⟨v4.1⟩ · DoD: รายงาน top 100 คำ
- [~] **T2.7 (M)** 👤 เขียน `eval/labeling-guideline.md` (นิยามทักษะ, กรณีกำกวม, recall นับเฉพาะทักษะใน taxonomy) ⟨v4.1, D16⟩ → **คนตรวจมือ 200 ประกาศ** (ชุดอ้างอิง `eval/skills_gold.csv` — ห้ามใช้ LLM ติด label; agent เตรียมไฟล์ประกาศตัวอย่าง + สคริปต์คำนวณ precision/recall + Cohen's κ จาก 50 ประกาศที่ตรวจซ้ำ ถ้าทำ ≥ 2 คน) · DoD: ตารางต่อกลุ่มทักษะ · รอ T2.4
- [ ] **T2.8 (S)** ขยาย taxonomy เป็น 150–200 ทักษะรอบ 2 จากคิว alias · รอ T2.6, T2.7
- [ ] **T2.9 (S)** ผูก `onet_ref`/`esco_ref` ให้ทักษะที่มี

## Phase 3 — Data Warehouse, Marts, DQ (สัปดาห์ 3–6)
- [x] **T3.1 (M)** Migration 002: dims (ARCH §3.3) + seed `dim_date`, `dim_location` (77 จังหวัด + ภาค + is_south14) · รอ T1.1
- [x] **T3.2 (M)** Migration 003: `fact_job_posting`, `fact_posting_skill` + index · DoD: constraint ผ่าน
- [x] **T3.3 (M)** `validate.py`: DQ checks 8 ด้าน (รวม Sampling ⟨v4.1⟩) → `dq_result` + เกณฑ์ผ่าน · DoD: รันแล้วได้ตารางผล
- [x] **T3.4 (M)** `load_dw.py` idempotent (upsert) + คำนวณ `first_seen`/`last_seen` จาก `listing_seen` และใส่ `sample_stratum`/`sample_weight` ⟨v4.1⟩ · DoD: รันซ้ำแล้วจำนวนแถวไม่เปลี่ยน · รอ T2.x, T3.2
- [x] **T3.5 (M)** Migration 004: marts `skill_demand_weekly` (ถ่วงน้ำหนัก, active/ใหม่) ⟨v4.1⟩, `occupation_skill_profile`, `salary_stats`, `posting_volume_daily`, `top_links`, `public_summary` ⟨v4.1⟩ (ซ่อน n < 5) · DoD: ตรวจตัวเลขตรงกับ query ตรงจาก dw
- [x] **T3.6 (M)** marts `skill_cooccurrence`, `curriculum_coverage_ref`, `pipeline_status`, `dq_summary` (2 ตัวหลัง admin เท่านั้น ไม่ grant anon)
- [x] **T3.7 (M)** `build_marts.py` + สคริปต์ปลายทางรวม `run_pipeline.py` (extract→…→marts) · DoD: คำสั่งเดียวรันได้ทั้งสาย
- [~] **T3.8 (M)** สิทธิ์: ปิด `staging/dw/ml` จาก API, grant select เฉพาะ `mart.*` ที่จำเป็น · DoD: ทดสอบด้วย anon key แล้วอ่าน dw ไม่ได้
- [ ] **T3.9 (S)** `fact_labor_monthly` + การ์ดบริบทภาครัฐ

## Phase 4 — ML benchmark และ Champion (สัปดาห์ 9–11; เตรียม feature ตั้งแต่สัปดาห์ 6)
- [~] **T4.0 (M)** ⟨v4.2, D19⟩ โครง `services/ml-api` (FastAPI: `/health`, `/predict`, `/predict/batch`, ตรวจ header `X-ML-Key`) ด้วยโมเดลจำลอง → deploy บน **Render free** (หรือเซิร์ฟเวอร์มหาวิทยาลัยถ้าได้ HTTPS) · DoD: เรียกจาก Vercel preview ได้, วัด cold start จริงบันทึกใน `docs/DEPLOY.md` · 0.5–1 วัน
- [x] **T4.1 (M)** `features.py`: สร้างตาราง feature (ไม่มีเพศ/อายุ/ชื่อบริษัท) + test กัน leak · DoD: test ยืนยันคอลัมน์ต้องห้ามไม่อยู่ · รอ T3.4
- [~] **T4.2 (M)** Baseline + Ridge + RandomForest ใน `benchmark.py` ด้วย GroupKFold(5, group=company) · DoD: ผลบันทึก `ml.model_result`
- [x] **T4.3 (M)** XGBoost, LightGBM, CatBoost + tuning แบบ **nested** (random search ≤ 20 รอบ ด้วย GroupKFold(3) ชั้นในบน train ของแต่ละ fold) ⟨v4.1, D15⟩ · DoD: ครบ 5 โมเดล + baseline, ผลราย fold, fold นอกไม่ถูกใช้เลือก hyperparameter
- [x] **T4.4 (M)** เลือก champion + feature importance + residual quantile → ช่วงค่าคาด · DoD: รายงาน `docs/ml-report.md`
- [x] **T4.5 (M)** ⟨v4.2⟩ `export_model.py`: บันทึก champion (`models/salary_champion.joblib` หรือไฟล์ native) + `feature_spec.json` → ml-api โหลดจริง; test ค่าคาดจาก API = Python ±1e-6 · DoD: test ผ่าน · รอ T4.0, T4.4
- [~] **T4.6 (M)** `mart.salary_prediction` + `mart.ml_leaderboard` view
- [x] **T4.7 (S)** วิเคราะห์ error ตามกลุ่มอาชีพ/ภาค + เขียนข้อจำกัด (selection bias)
- [ ] **T4.8 (C)** SHAP beeswarm ของ champion

## Phase 5 — Frontend (สัปดาห์ 5–12; สไตล์ตาม DESIGN_SYSTEM.md)
### 5A โครงและระบบ
- [~] **T5.1 (M)** scaffold Next.js + Tailwind v4 + shadcn + `globals.css` (tokens + glass + fallback) · DoD: หน้า style guide แสดงการ์ดแก้ว/ทึบ
- [~] **T5.2 (M)** ธีม ECharts `skillbi` + `ChartSurface` + ปุ่ม "ดูเป็นตาราง" + `ProvenanceBadge` · DoD: กราฟตัวอย่าง 3 แบบผ่าน contrast
- [~] **T5.3 (M)** `AppShell` (sidebar/bottom tab, Context Bar), i18n TH/EN, middleware ตาม role
- [~] **T5.4 (M)** Supabase client ฝั่ง server + helper อ่าน `mart.*` + สถานะ loading/empty/error มาตรฐาน
### 5B หน้า (ดู FRONTEND_SPEC §3)
- [~] **T5.5 (M)** Landing `/` (KPI จาก `mart.public_summary` ⟨v4.1⟩ + calendar + top skills) · รอ T3.5
- [~] **T5.6 (M)** Market Explorer `/market` (ranked bars, Sankey, small multiples, volume + slider)
- [~] **T5.7 (M)** Skill detail `/skills/[slug]` (trend + co-occurrence + เงินเดือนเทียบ)
- [~] **T5.8 (M)** Occupation detail `/occupations/[slug]` + `SourceLink`
- [~] **T5.9 (M)** My Skills `/me/skills` + `SkillChipPicker` (ค้นด้วย alias ไทย/อังกฤษ) · รอ T6.2
- [~] **T5.10 (M)** Skill Gap `/me/gap` (radar, coverage, ทักษะที่ขาด, ตำแหน่งที่ตรง)
- [~] **T5.11 (M)** Curriculum list + detail + Alignment report (coverage meter, gaps, over-coverage) + CSV import/export · รอ T6.2
- [~] **T5.12 (M)** Salary page `/salary` + `/api/salary/estimate` (proxy → ml-api, timeout 8 วินาที, ปลุก `/health` ตอนเปิดหน้า) + fallback `mart.salary_prediction`/median พร้อมป้าย ⟨v4.2⟩ · รอ T4.5
- [~] **T5.13 (M)** ML Lab `/ml-lab` · รอ T4.6
- [~] **T5.14 (M)** Admin pipeline / quality / taxonomy queue / sources · รอ T3.6
- [~] **T5.15 (M)** Settings / Privacy / About + ลบข้อมูลตนเอง
- [ ] **T5.16 (S)** Curriculum PDF export, เทียบ 2 หลักสูตร
- [ ] **T5.17 (M)** ปรับมือถือ (375px) ทุกหน้า + glass off mode + ตรวจ contrast อัตโนมัติ 3 จุดของ mesh

## Phase 6 — Auth, RLS และเดโม (สัปดาห์ 5–8)
- [x] **T6.1 (M)** Migration 005: ตาราง `app_*` + RLS + `is_admin()` (ARCH §3.6) + กันผู้ใช้ตั้ง role admin เอง (policy แยก insert/update ที่ with check role ∈ student/institution) ⟨v4.1⟩ · DoD: เปิด RLS ทุกตาราง
- [~] **T6.2 (M)** Supabase Auth (email/password) + trigger สร้าง `app_profile` + onboarding · รอ T6.1
- [~] **T6.3 (M)** seed persona 4 บัญชี + หลักสูตรตัวอย่าง + ปุ่มเดโมคลิกเดียว (server action) · DoD: เข้าได้ภายใน 1 คลิก
- [x] **T6.4 (M)** ชุดทดสอบ RLS (user A/B, visitor, admin, **ผู้ใช้พยายามแก้ role เป็น admin** ⟨v4.1⟩, anon อ่าน `pipeline_status` ไม่ได้) อัตโนมัติ · DoD: ผลทุกกรณีตรงตามคาด

## Phase 7 — แชท Gemini (สัปดาห์ 11–12)
- [~] **T7.1 (M)** `usePageContext()` + ตัวตัดขนาด pageContext (≤ ~6,000 token) · DoD: ทุกหน้า Must ลงทะเบียน
- [~] **T7.2 (M)** `/api/chat` (system prompt, rate limit, log ลง `app_chat_log`) · DoD: ปฏิเสธเมื่อไม่มีข้อมูลในหน้า
- [~] **T7.3 (M)** `ChatFab`/`ChatPanel` + คำถามแนะนำต่อหน้า + disclaimer
- [~] **T7.4 (M)** ชุดคำถาม 30 ข้อ + สคริปต์ตรวจ grounded (ตัวเลขในคำตอบต้องมีใน pageContext) · DoD: รายงานผล
- [ ] **T7.5 (S)** คำตอบสำรองสำหรับคำถามเดโมเมื่อ quota หมด

## Phase 8 — ทดสอบและประเมินผล (สัปดาห์ 13–15)
- [ ] **T8.1 (M)** ตาราง test case F1–F9 + ทดสอบ E2E 3 role (Playwright) · DoD: ผลบันทึก `docs/test-report.md`
- [~] **T8.2 (M)** รายงานคุณภาพข้อมูลสุดท้าย (DQ + จำนวนประกาศต่อจังหวัด/หมวด)
- [~] **T8.3 (M)** 👤 ออกแบบแบบสอบถาม Likert 5 ระดับ (agent ร่างข้อคำถามใน `docs/questionnaire.md`) + ขออนุมัติอาจารย์ + เก็บข้อมูลจริง (จำนวนตามอาจารย์กำหนด) · DoD: ตาราง x̄, S.D.
- [ ] **T8.4 (M)** ทดสอบประสิทธิภาพ: Lighthouse มือถือ, เวลาโหลด mart หน้า Market < 3 วินาที
- [ ] **T8.5 (M)** แก้บั๊ก/ข้อเสนอแนะจากแบบสอบถาม
- [ ] **T8.6 (S)** JobBKK รอบเก็บเสริมถ้าข้อมูล JobThai ไม่พอ

## Phase 9 — เล่มและสอบ (สัปดาห์ 14–16)
- [~] **T9.1 (M)** บทที่ 1 (ที่มา วัตถุประสงค์ ขอบเขต ประโยชน์) ส่งอาจารย์ตั้งแต่สัปดาห์ 1–2
- [~] **T9.2 (M)** บทที่ 2–3 (ทฤษฎี/วิธีการ: DW, ETL, NLP dictionary, ML, ToS/PDPA)
- [~] **T9.3 (M)** บทที่ 4–5 (ผลการดำเนินงาน/ผลทดสอบ/สรุป ข้อจำกัด)
- [~] **T9.4 (M)** สไลด์ + วิดีโอเดโมสำรอง + ซ้อมนำเสนอ 2 รอบ
- [ ] **T9.5 (M)** deploy production ตาม [docs/DEPLOY.md](docs/DEPLOY.md): Vercel + Supabase + ml-api (Render/มหาวิทยาลัย) + ping cron-job.org + ตรวจ env/สิทธิ์ + ปิด debug ⟨v4.2⟩ · DoD: เปิดจากอุปกรณ์อื่นได้, Salary ตอบจาก ml-api, คีย์ไม่ปนใน repo
- [ ] **T9.6 (M)** Freeze ข้อมูล/โมเดลก่อนสอบ 1 สัปดาห์

---

## ลำดับพึ่งพา (สรุป)
`T0.2 → T1.1 → T1.3–T1.5 → T1.8 (เก็บข้อมูล) → T2.x → T3.x → (T4.x ∥ T5.5–T5.8) → T5.9–T5.14 → T7.x → T8.x → T9.x`
ข้อควรระวังคอขวด: **T0.3 (หนังสืออนุญาต)** และ **T1.8 (เก็บข้อมูลหลายคืน)** ควรเริ่มเร็วที่สุด; **T6.1–T6.2** ต้องเสร็จก่อนหน้านักศึกษา/สถานศึกษา
