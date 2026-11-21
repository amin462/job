# Prompt ส่งต่อให้ Gemini — รอบที่ 2 (21 พ.ย. 2569 22:00)

> **วิธีใช้:** คัดลอกข้อความในกล่องด้านล่างไปวางสั่ง Gemini ได้เลย · ไม่มีคีย์หรือรหัสผ่านใน prompt (อยู่ใน `.env` ที่ไม่อยู่ใน git) — **ห้ามวางคีย์ลงในแชท Gemini**
> รอบที่ 1 (ลง migrations, import, ETL, เว็บต่อ Supabase, demo personas, fixtures) เสร็จและตรวจแล้ว: pytest 136 · vitest 34 · tsc · build ผ่าน · push ถึง `0da09d1`

---

```text
คุณคือผู้ช่วยพัฒนาโครงงานจบ หัวข้อ E′ "Skill Demand Intelligence" ในโฟลเดอร์ D:\project-next\southbi (Windows, PowerShell) ตอบเป็นภาษาไทย กระชับ อ้างไฟล์ทุกครั้ง

## 1. อ่านก่อนเริ่ม
AGENTS.md → docs/PROGRESS.md (หัวข้อ 2–4 และ changelog 21 พ.ย. ทั้งหมด) → docs/data-dictionary.md (column ทั้งหมดของชุดข้อมูล) → TASKS.md

## 2. สถานะ
- git: branch main, push แล้วถึง 0da09d1 · **commit ได้ แต่ห้าม push** (ผู้ใช้จะสั่งเอง) · commit เฉพาะไฟล์ที่ตัวเองแก้ ห้าม `git add -A`
- Supabase: migrations 001–005 ลงแล้ว, staging/dw/mart มีข้อมูลจาก 291 ประกาศจริง, DATABASE_URL เป็น Session pooler (ห้ามเปลี่ยน)
- **การเก็บข้อมูลกำลังรัน** (scraper/jobthai_harvester.py, scraper/jobbkk_harvester.py ในหน้าต่าง cmd ของผู้ใช้):
  - **ห้ามปิด/รีสตาร์ท/แก้ harvester ห้ามสั่ง taskkill หรือ Stop-Process กับ python.exe / cmd.exe ใดๆ** (เคยถูกปิดหมดจนเสียข้อมูลหลายชั่วโมง)
  - ห้ามยิง request ไป jobthai.com / jobbkk.com เอง · อ่าน data/*.sqlite ได้อย่างเดียวผ่าน `py -X utf8 -m pipeline.scraper.import_sqlite`
  - ดูสถานะได้ด้วย `powershell -ExecutionPolicy Bypass -File scripts\start_harvesters.ps1 -Status`
- ชุดข้อมูลใหม่ (Claude, 0da09d1): harvester เก็บทุก field ยกเว้นข้อมูลส่วนบุคคลลง `payload.x_jobthai` · `pipeline/etl/enrich.py` สร้าง column ใหม่ (ENRICH_COLUMNS: seniority_level, employment_type_derived, accepts_fresh_grad, is_remote, shift_work, work_days_per_week, positions, salary_disclosure, benefit_* 14 ตัว, n_benefit_types, urgent, near_transit, in_industrial_estate, online_interview, days_listed) → clean_postings 66 column · ML ใช้ seniority_level + employment_type_derived แล้ว

## 3. งานรอบนี้ (ตามลำดับ จบแต่ละข้อ: รันเทสต์ → ติ๊ก TASKS.md → บันทึก docs/PROGRESS.md → commit)
1. **เก็บ column ใหม่ลง DW:** `supabase/migrations/006_fact_enrich_columns.sql` เพิ่มทุก column ใน ENRICH_COLUMNS ลง `dw.fact_job_posting` (nullable, ชนิดตาม docs/data-dictionary.md) · แก้ `pipeline/etl/load_dw.py` ให้ upsert ค่าเหล่านี้ · `npx supabase db push --db-url "$env:DATABASE_URL"` · รัน import_sqlite + run_pipeline ซ้ำ ตรวจว่ารันซ้ำแล้วจำนวนแถวไม่เปลี่ยน และค่าไม่เป็น NULL ทั้งคอลัมน์
2. **Mart จาก column ใหม่ (T3.5/T3.6 ส่วนขยาย):** สถิติรวมถ่วง sample_weight และซ่อน n < 5 — สัดส่วนรับจบใหม่, ระดับตำแหน่ง, สวัสดิการแต่ละอย่าง, จำนวนอัตรารวม (positions) ต่อ occupation_cluster และต่อจังหวัด/ภาค · grant select ให้ anon เฉพาะ mart ใหม่ที่เป็นสถิติรวม · เพิ่มเทสต์ตัวเลข mart = query ตรงจาก dw
3. **แสดงบนเว็บ:** หน้า Market (`/market`) และ Occupation (`/occupations/[slug]`) เพิ่มกราฟ/การ์ดจาก mart ข้อ 2 ตาม DESIGN_SYSTEM.md (ECharts, ปุ่มดูเป็นตาราง, ProvenanceBadge) และส่งตัวเลขเข้า pageContext ของแชท · หน้า Salary (`/salary`, T5.12) เพิ่มตัวเลือก "ระดับตำแหน่ง" (seniority_level) และ "ประเภทการจ้าง" (employment_type_derived) ส่งผ่าน `/api/salary/estimate` → ml-api (ค่าที่ไม่เลือก = "ไม่ระบุ" / "full_time") · vitest + build ต้องผ่าน
4. **T5.17:** ทุกหน้าใช้งานได้ที่ 375px, โหมดกระจกปิด (glass off) ใช้ได้, เทสต์ contrast ≥ 4.5:1 อัตโนมัติ 3 จุดของพื้น mesh
5. **T8.1:** ตาราง test case F1–F9 + Playwright E2E 3 role (นักศึกษา/สถานศึกษา/admin) ทดสอบกับ `npm run dev` บน localhost ด้วยบัญชีเดโมจาก .env (ห้ามพิมพ์รหัสออก log) → `docs/test-report.md`
6. **T8.4:** วัด Lighthouse มือถือ + เวลาโหลดหน้า Market < 3 วินาที บน localhost → บันทึกใน docs/test-report.md
7. **T0.5 (เตรียม):** สคริปต์ Task Scheduler ที่ `scripts/` ให้ผู้ใช้กดลงทะเบียนเอง (ห้ามลงทะเบียนเอง) สำหรับ (ก) เปิด `scripts\start_harvesters.ps1` ทุก 15 นาทีตอนเครื่องเปิด (ข) import_sqlite + run_pipeline วันละครั้ง · และวิธี ping Supabase กัน pause ใน docs/DEPLOY.md
8. **ถ้า JobThai มีประกาศ status ok ≥ 5,000 แล้ว** (เช็กด้วย sqlite แบบอ่านอย่างเดียว): import_sqlite → run_pipeline --from-staging → benchmark (nested GroupKFold) → export_model → อัปเดต docs/ml-report.md, docs/dq-report.md (T8.2) และเพิ่มการทดลอง ablation "มี/ไม่มี สวัสดิการ" ในรายงาน (ไม่ใส่สวัสดิการในโมเดลที่ให้บริการ) · ถ้ายังไม่ถึงให้ข้ามข้อนี้และบันทึกจำนวนปัจจุบันใน PROGRESS
9. งาน `[~]`/`[ ]` อื่นใน TASKS.md ที่ไม่ต้องรอคน ทำต่อตามลำดับพึ่งพาท้ายไฟล์ · งาน 👤 ให้เตรียมให้พร้อมแล้วเขียนสิ่งที่ผู้ใช้ต้องกดใน PROGRESS หัวข้อ 2

## 4. กติกาที่ห้ามพลาด
- ห้ามขยายขอบเขต (ไม่มีระบบสมัครงาน/สรรหา/บริษัทลงประกาศ/résumé) จะเพิ่มงานต้องถามผู้ใช้พร้อมบอกผลต่อเวลา
- เว็บ/API สาธารณะแสดงเฉพาะสถิติรวม n ≥ 5 + ลิงก์ต้นฉบับ ห้ามส่ง description / qualifications / company_detail / directions / ข้อมูลจาก x_jobthai.listing ออกไป
- ML ห้ามใช้ gender/age/company_name/salary_disclosure เป็น feature · GroupKFold(5) ตาม company + nested GroupKFold(3)
- ห้ามใช้ LLM ดึงทักษะ/จัดหมวด/เสนอ alias/ติด label · ห้าม Text-to-SQL · Gemini ใช้แค่แชทตอบจาก pageContext
- ห้าม commit data/, spike/raw/, spike/out/, design/*.jpg, .env* · ห้ามพิมพ์คีย์/รหัสผ่าน
- ติ๊ก [x] เฉพาะเมื่อรันพิสูจน์ DoD จริงแล้ว ไม่งั้นใช้ [~] พร้อมเหตุผล
```
