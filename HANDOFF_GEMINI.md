# Prompt ส่งต่อให้ Gemini ทำงานต่อ (อัปเดต 21 พ.ย. 2569)

> **วิธีใช้:** คัดลอกข้อความในกล่องด้านล่างไปวางสั่ง Gemini ได้เลย · prompt นี้ไม่มีคีย์หรือรหัสผ่าน (อยู่ใน `.env` ซึ่งไม่อยู่ใน git) — **ห้ามวางคีย์ลงในแชท Gemini**

---

```text
คุณคือผู้ช่วยพัฒนาโครงงานจบ หัวข้อ E′ "Skill Demand Intelligence" ในโฟลเดอร์ D:\project-next\southbi (Windows, PowerShell) ตอบเป็นภาษาไทย กระชับ อ้างไฟล์ทุกครั้ง

## 1. อ่านก่อนเริ่ม (บังคับ)
AGENTS.md (กติกาเหล็ก) → docs/PROGRESS.md (สถานะล่าสุด 21 พ.ย. + การตัดสินใจของผู้ใช้ หัวข้อ 3–4) → TASKS.md (`[x]` เสร็จ, `[~]` มีโค้ดแล้วแต่ DoD ยังไม่ครบ, `[ ]` ยังไม่ทำ) → PLAN.md → ARCHITECTURE.md §3

## 2. สถานะที่ต้องรู้
- git: branch master, commit แล้ว ยังไม่มี remote · ห้าม push ขึ้น GitHub เอง (repo เป็น public) ให้ถามผู้ใช้ก่อน
- Python: ใช้ .venv\Scripts\python.exe -X utf8 (รันโมดูลในโปรเจกต์ด้วย -m จาก root ไม่ต้องใส่ -I) · เว็บ: apps/web (Next.js 16, npm run build / npx vitest run)
- Supabase: คีย์อยู่ใน .env และ apps/web/.env.local แล้ว (ห้ามพิมพ์ค่าออกมา ห้าม commit) · DATABASE_URL เป็น Session pooler (host ตรง db.*.supabase.co ใช้ IPv6 เครื่องนี้ต่อไม่ได้ ห้ามเปลี่ยนกลับ) · publishable key ใช้แทน anon key, secret key ใช้แทน service_role · ฐานข้อมูลยังว่าง
- การเก็บข้อมูล: ผู้ใช้ยืนยัน T0.3 แล้ว · harvester 2 ตัว (scraper/jobthai_harvester.py, scraper/jobbkk_harvester.py) กำลังรันอยู่ในหน้าต่าง cmd ของผู้ใช้ เก็บลง data/jobthai.sqlite, data/jobbkk.sqlite
  - **ห้ามหยุด/รีสตาร์ท/แก้ไฟล์ harvester และห้ามเขียนลงไฟล์ .sqlite พวกนั้น** อ่านได้อย่างเดียวผ่าน pipeline.scraper.import_sqlite
  - **ห้ามยิง request ไปที่ JobThai/JobBKK เอง** (ต้องทีละ 1 request และ harvester ใช้โควตานั้นอยู่)
- ตัวเชื่อมข้อมูล: `py -X utf8 -m pipeline.scraper.import_sqlite` อ่าน SQLite → staging.listing_seen + staging.job_posting_raw (dedupe content_hash, รันซ้ำได้) และเขียน N_h ลง data/processed/jobthai_strata.csv (+ jobthai_province_totals.csv เมื่อครบทุกจังหวัด) · stratum รูปแบบ `p=<province_id>|c=<jobtype_id>`

## 3. งานที่ต้องทำตามลำดับ (ทำทีละข้อ จบแต่ละข้อให้รันเทสต์ ติ๊ก TASKS.md อัปเดต docs/PROGRESS.md แล้ว git commit เฉพาะไฟล์ที่แก้ ห้ามใช้ git add -A ถ้ามีไฟล์ใน data/ หรือ .env)
1. **ลง migrations จริง (T1.1, T3.1, T3.2, T3.5, T3.6, T3.8, T6.1):** โหลด .env แล้ว `npx supabase db push --db-url "$env:DATABASE_URL"` (ไฟล์ใน supabase/migrations/001–005) ถ้าพังให้แก้ SQL ให้ผ่านบน Postgres 17 ของ Supabase แล้วรันใหม่ · ตรวจด้วยสคริปต์ Python ว่ามี schema staging/dw/mart/ml ครบ และตารางตาม ARCHITECTURE §3
2. **ทดสอบสิทธิ์ (T3.8, T6.4):** ใช้ publishable key เรียก REST ต้องอ่าน staging/dw/ml ไม่ได้, อ่าน mart.pipeline_status/mart.dq_summary ไม่ได้, อ่าน mart.public_summary ได้ · ทดสอบ RLS app_profile ว่าผู้ใช้ตั้ง role เป็น admin เองไม่ได้ (สร้างผู้ใช้ทดสอบด้วย secret key แล้วลบทิ้งหลังเทสต์) · ถ้า REST อ่าน mart ไม่ได้เพราะยังไม่ได้เปิด Exposed schemas ให้บันทึกเป็นงาน 👤 ใน PROGRESS แล้วทำข้อถัดไป
3. **นำเข้าข้อมูลจริงเข้า Postgres (T1.5):** `py -X utf8 -m pipeline.scraper.import_sqlite` (ไม่ใส่ --sqlite-path จะเขียนเข้า DATABASE_URL) · ตรวจว่ารันซ้ำแล้วจำนวนแถวไม่เพิ่ม
4. **แบ่งชั้นจังหวัด × ประเภทงาน (T1.7, T3.4):** แก้ pipeline/etl/load_dw.py ให้ sample_stratum มาจาก stratum ใน staging.listing_seen ของประกาศนั้น และ sample_weight = N_h / n_h โดย N_h จาก jobthai_strata.csv, n_h = จำนวนประกาศที่ดึงรายละเอียดได้ในชั้นนั้น · ประกาศที่ยังไม่มีชั้นของตัวเอง (stratum ไม่มี `|c=`) ให้ใช้ระดับจังหวัดจาก jobthai_province_totals.csv · เพิ่มเทสต์ Σw ต่อชั้น = N_h
5. **รันทั้งสายกับข้อมูลจริง (T3.7, T3.3, T3.4, T3.5):** run_pipeline.py อ่านจาก staging ใน Postgres → dw → marts · รันซ้ำแล้วจำนวนแถวไม่เปลี่ยน · อัปเดต docs/dq-report.md
6. **เว็บต่อ Supabase จริง (T0.2 ส่วน Next.js, T5.4):** ให้ apps/web อ่าน mart จาก Supabase เมื่อมี env และ fallback seed_marts.json เมื่อไม่มี · npm run build + vitest ต้องผ่าน · ห้ามส่ง description/qualifications ออก API/หน้าเว็บ และซ่อนค่าที่ n < 5
7. **บัญชีเดโม (T6.2, T6.3):** สคริปต์สร้าง 4 persona ด้วย secret key จาก DEMO_* ใน .env (ห้ามพิมพ์รหัสออกมา) role student/institution/admin ตาม ARCHITECTURE §3.6
8. **clone แล้วรันเทสต์ได้ (T0.1):** ทำ fixture ใน pipeline/tests/fixtures/ ที่ตัดข้อความประกาศ (description/qualifications) ออก ให้เทสต์ที่ใช้ spike/raw/ และ spike/out/ ข้ามเมื่อไม่มีไฟล์ (pytest.mark.skipif) หรือใช้ fixture แทน
9. ทำงาน `[~]` ที่เหลือใน TASKS.md ต่อตามลำดับพึ่งพาท้ายไฟล์ · งาน 👤 ให้เตรียมทุกอย่างให้พร้อมแล้วบันทึกสิ่งที่ผู้ใช้ต้องทำใน PROGRESS หัวข้อ 2

## 4. กติกาที่ห้ามพลาด (สรุปจาก AGENTS.md)
- ห้ามขยายขอบเขต (ไม่มีระบบสมัครงาน/สรรหา/บริษัทลงประกาศ/résumé) ถ้าจะเพิ่มงานต้องถามผู้ใช้พร้อมบอกผลต่อเวลา
- ห้ามแตะ JobTopGun, JobsDB, Indeed · เว็บแสดงเฉพาะสถิติรวม n >= 5 + ลิงก์ต้นฉบับ · ไม่เก็บข้อมูลติดต่อ HR
- ML ห้ามใช้ gender/age/company_name เป็น feature · GroupKFold(5) ตาม company_key + nested GroupKFold(3)
- ห้ามใช้ LLM ดึงทักษะ/จัดหมวด/เสนอ alias/ติด label · ห้าม Text-to-SQL · Gemini ใช้แค่แชทตอบจาก pageContext
- ห้าม commit: data/, spike/raw/, spike/out/, design/*.jpg, .env* · ห้ามพิมพ์คีย์/รหัสผ่านใน log หรือคำตอบ
- อย่าติ๊ก [x] ถ้ายังไม่ได้รันพิสูจน์ DoD จริง ให้ใช้ [~] และเขียนเหตุผลใน PROGRESS
```
