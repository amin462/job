# AGENTS.md — กติกาและคู่มือปฏิบัติงานสำหรับ AI Coding Agent

> ไฟล์นี้ใช้บังคับกับ AI Agent ทุกตัว (Gemini, Antigravity, Claude, Cursor, Codex) ที่เข้ามาทำงานในโปรเจกต์ `southbi` (**Skill Demand Intelligence / หัวข้อ E′**)

---

## 1. กติกาเหล็ก (ห้ามละเมิดโดยเด็ดขาด)

1. **ห้ามขยายขอบเขตเอง (No Scope Creep):**
   - ทำเฉพาะงานที่อยู่ใน [TASKS.md](TASKS.md) และ [PLAN.md](PLAN.md) (v4.2) เท่านั้น
   - **ตัดออกทั้งหมด (D3):** ระบบสมัครงาน, ใบสมัคร, pipeline สรรหา, สัมภาษณ์, บริษัทลงประกาศเอง, ระบบติดตามการเรียน, การนำเข้าข้อความ résumé (D18)
   - ถ้าจะเสนอเพิ่ม/ตัดงาน ต้องหยุดถามผู้ใช้และแจ้งผลกระทบต่อเวลาเป็นจำนวนวันก่อนเสมอ
2. **กติกาแหล่งข้อมูลและ ToS (D2, D4, D12):**
   - แหล่งหลักคือ **JobThai** (และ JobBKK เป็นแหล่งที่ 2 ในหมวด Could)
   - **ห้ามแตะต้องเด็ดขาด:** JobTopGun (ToS ห้าม scraping), JobsDB (robots.txt ห้าม), Indeed
   - **การแสดงผลบนเว็บ:** แสดงเฉพาะ **สถิติรวม (aggregate ที่ `n >= 5`) + ลิงก์ไปยังประกาศต้นฉบับ** ห้ามสร้างหน้าหรือ API ที่ส่งข้อความรายละเอียดประกาศ (`description`/`qualifications`) ออกไปสู่สาธารณะเด็ดขาด
   - **Polite Scraping:** ดึงทีละ 1 request (concurrency = 1), เว้นระยะ **≥ 5 วินาที** (+ jitter), ถ้าเจอ HTTP `403`, `429` หรือ CAPTCHA **ต้องหยุดทั้งรอบทันที** บันทึกสถานะลง `staging.scrape_run` ห้ามหลบเลี่ยง ห้ามหมุน IP ห้ามแก้ CAPTCHA
   - **ห้ามดึงข้อมูลจริงจำนวนมาก (T1.8)** จนกว่าผู้ใช้จะยืนยันเรื่องหนังสืออนุญาต (T0.3) ในระหว่างพัฒนาให้ใช้ไฟล์ตัวอย่างที่มีอยู่แล้วใน `spike/raw/` (131 ประกาศ) และ `spike/out/sample_jobs.csv`
3. **กติกา PDPA และความเป็นธรรมของ ML (D6, D12, D15):**
   - **ห้ามเก็บข้อมูลผู้ติดต่อ HR** (ชื่อ/เบอร์โทร/อีเมล/LINE) ตัดทิ้งตั้งแต่ขั้น parse ก่อนลง `staging`
   - **ห้ามใช้เพศ (`gender`), อายุ (`age`), และชื่อบริษัท (`company_name`) เป็น feature ของโมเดล ML เด็ดขาด** (ใช้ `company_key` เป็น `group` ใน `GroupKFold(5)` เท่านั้น) และต้องมี unit test ตรวจจับคอลัมน์ต้องห้ามใน `pipeline/tests/`
   - การจูน hyperparameter ใช้ **Nested CV** (`GroupKFold(3)` ชั้นในบนชุด train ของแต่ละ fold นอก) เพื่อไม่ให้ผลวัดบน fold นอกดีเกินจริง
   - ตอนทดลองเทียบ ≥ 5 โมเดล (Ridge, Random Forest, XGBoost, LightGBM, CatBoost + Baseline ค่ามัธยฐาน) แต่ **ในระบบจริงเสิร์ฟเฉพาะโมเดลที่ชนะ (Champion) ตัวเดียว** ผ่าน FastAPI `services/ml-api` (D19)
4. **กติกา AI / LLM (D7, D18):**
   - Gemini ใช้เป็น **ไอคอนแชทลอย** (`POST /api/chat`) ตอบคำถามจากข้อมูล `pageContext` ที่แสดงอยู่บนหน้านั้นเท่านั้น ห้ามแต่งตัวเลขใหม่
   - **ห้ามทำ Text-to-SQL**
   - **ห้ามใช้ LLM ดึงทักษะ จัดหมวดหมู่ เสนอ alias หรือติด label ชุดตรวจมือ 200 ประกาศเด็ดขาด** (การดึงทักษะใช้ dictionary + alias + PyThaiNLP `newmm`; การเสนอ alias ในคิว admin ใช้ `pg_trgm similarity`)
5. **กติกาความปลอดภัยและฐานข้อมูล (D10, D18):**
   - แยก schema ตั้งแต่ migration แรก: `staging`, `dw`, `mart`, `ml`, `public`
   - ปิด `staging`, `dw`, `ml` จาก `anon` และ `authenticated`; เปิดให้อ่านเฉพาะตาราง/view ใน `mart` ที่กำหนด (`mart.pipeline_status` และ `mart.dq_summary` ให้เฉพาะ admin อ่าน; หน้า Landing อ่าน `mart.public_summary`)
   - เปิด **RLS ทุกตารางใน `public`** (`app_*`) และใช้ policy แยก `insert`/`update` บน `app_profile` ที่บังคับ `role in ('student','institution')` เพื่อป้องกันผู้ใช้ตั้งตัวเองเป็น `admin`
   - ห้าม commit ไฟล์ใน `spike/raw/`, `data/raw/`, `design/*.jpg`, หรือ `.env*` ขึ้น git

---

## 2. สภาพแวดล้อมของเครื่องพัฒนา (ตรวจแล้ว)

- **OS:** Windows (PowerShell, working directory: `d:\project-next\southbi`)
- **Python:** เรียกผ่านคำสั่ง `py` (ติดตั้ง **Python 3.13.7** แล้ว — คำสั่ง `python` เฉยๆ อาจไม่อยู่ใน PATH ให้ใช้ `py -3` หรือสร้าง `.venv` ด้วย `py -m venv .venv` แล้วใช้ `.venv\Scripts\python.exe`)
  - เวลาสั่งรันสคริปต์ภาษาไทยบน Windows ให้ใส่ `-X utf8` เสมอ เช่น `py -I -X utf8 ...`
- **Node.js / npm:** มีแล้ว (`node` v26.1.0, `npm` 11.13.0)
- **Git:** มีแล้ว (`git` 2.52.0 — โฟลเดอร์นี้ยังไม่ได้รัน `git init` ซึ่งเป็นส่วนหนึ่งของงาน `T0.1`)
- **Docker:** มีแล้ว (`docker` 29.1.2)
- **Supabase CLI:** ยังไม่ได้ติดตั้งแบบ global (เรียกผ่าน `npx supabase ...` ได้เลย)

---

## 3. ขั้นตอนการทำงานของ Agent (Workflow Loop)

เมื่อได้รับคำสั่งให้ลุยงาน:

1. **อ่านสถานะล่าสุด:** เปิด [TASKS.md](TASKS.md) และ [docs/PROGRESS.md](docs/PROGRESS.md) เพื่อดูว่างานไหนเสร็จแล้ว (`[x]`) และงานไหนคือลำดับถัดไป
2. **แยกแยะงานที่ทำได้ทันที vs งานที่ต้องรอคน (`👤`):**
   - งานที่มีป้าย `👤` (เช่น `T0.2` สร้างโปรเจกต์ Supabase จริง, `T0.3` ส่งอีเมลจริง, `T1.8` รันเก็บข้อมูลหลายคืน, `T2.7` คนตรวจมือ 200 ประกาศ, `T8.3` เก็บแบบสอบถามจริง): **ให้ Agent ทำส่วนเตรียมการทั้งหมดให้เสร็จ 100%** (เช่น ร่างจดหมาย, เขียน SQL migration, เขียนสคริปต์, สร้างไฟล์แม่แบบ, ทดสอบกับข้อมูล 131 ประกาศที่มีใน `spike/out/sample_jobs.csv` หรือ SQLite/local Postgres/mock) แล้วบันทึกสิ่งที่ผู้ใช้ต้องกด/กรอกไว้ใน `docs/PROGRESS.md` **โดยไม่ต้องหยุดรอ** ให้ข้ามไปทำงานโค้ดข้อถัดไปที่ทำต่อได้ทันที
3. **ลงมือทำทีละ Task ตามเกณฑ์ DoD:**
   - อ้างอิงสเปกใน [ARCHITECTURE.md](ARCHITECTURE.md), [FRONTEND_SPEC.md](FRONTEND_SPEC.md), [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) ทุกครั้ง
   - เขียนโค้ด + รันเทสต์ (`pytest` หรือ `npm run build` / `vitest`) ให้ผ่านจริงตาม DoD
4. **อัปเดตเอกสารทุกครั้งที่จบ 1 Task:**
   - ติ๊ก `[x]` ใน [TASKS.md](TASKS.md) (หรือติ๊ก `[~]` ถ้ารอผู้ใช้ทำขั้นตอน `👤` สุดท้าย)
   - บันทึกสิ่งที่ทำ ไฟล์ที่สร้าง/แก้ไข และผลเทสต์ลงใน [docs/PROGRESS.md](docs/PROGRESS.md)
5. **การสื่อสารกับผู้ใช้:**
   - ตอบเป็น **ภาษาไทย** กระชับ ชัดเจน
   - อ้างอิงไฟล์และหัวข้อที่เกี่ยวข้องทุกครั้ง
