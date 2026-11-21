# Prompt เปิด Claude session ใหม่ (อัปเดต 21 พ.ย. 2569 22:00)

> คัดลอกกล่องด้านล่างไปวางใน session ใหม่ของ Claude Code (โฟลเดอร์ D:\project-next\southbi) · ไม่มีคีย์/รหัสผ่านในนี้

---

```text
ทำงานต่อในโปรเจกต์ D:\project-next\southbi (หัวข้อ E′ Skill Demand Intelligence) ตอบเป็นภาษาไทย อธิบายแบบเข้าใจง่าย

## อ่านก่อน
AGENTS.md (กติกาบังคับ) → docs/PROGRESS.md (สถานะ + การตัดสินใจของผู้ใช้หัวข้อ 3 + changelog) → docs/data-dictionary.md → TASKS.md → HANDOFF_GEMINI.md (งานที่สั่ง Gemini รอบล่าสุด)

## สถานะ ณ 21 พ.ย. 2569 22:00
- GitHub: https://github.com/amin462/job (public) branch main, push แล้วถึง 0da09d1 · TASKS: [x] 46, [~] 18, [ ] 17
- เทสต์ล่าสุด: pytest 136 passed · vitest 34 passed · tsc ผ่าน · npm run build ผ่าน
- Supabase โปรเจกต์ smaaunonziebjvfyfuje (Tokyo) · คีย์อยู่ใน .env และ apps/web/.env.local · Python ต่อผ่าน Session pooler (host ตรง db.*.supabase.co เป็น IPv6 เครื่องนี้ต่อไม่ได้) · migrations 001–005 ลงแล้ว · ยังไม่มี 006
- การเก็บข้อมูล (T1.8) กำลังรัน: scraper/jobthai_harvester.py + scraper/jobbkk_harvester.py ในหน้าต่าง cmd ย่อไว้
  - 22:00: JobThai 16,956 id (ok 291, pending 16,663) กำลังสแกนหน้ารายการรอบใหม่ (281/3,555 มี N_h) แล้วจะดึง 291 เดิมซ้ำ ตามด้วย pending · JobBKK 9,996 id ยังไม่ได้ดึงรายละเอียด
  - คาดการณ์ (ถ้าเครื่องไม่ sleep): ได้ 5,000 ประกาศ ~อาทิตย์ 22 พ.ย. 12:00 · ครบ ~16,000 ~จันทร์ 23 พ.ย. 08:00
  - เครื่องหลุดสองครั้งเพราะ **ปิดฝาโน้ตบุ๊ก** (Windows log "Reason: Lid") และครั้งหนึ่งถูกปิด process ทั้งหมด → เปิดใหม่ด้วย scripts\start_harvesters.bat (ไม่เปิดซ้ำ) · ดูสถานะ: `powershell -ExecutionPolicy Bypass -File scripts\start_harvesters.ps1 -Status`
- การตัดสินใจของผู้ใช้: T0.3 ยืนยันแล้ว · delay ≥ 5 วินาที (jitter 0–1) · เจอ 403/429 พัก 60 นาทีแล้วลองใหม่ (ต่างจาก AGENTS.md ที่ให้หยุดทันที — ผู้ใช้เลือกเอง) · ใช้ scraper/ เป็นตัวเก็บ + pipeline/scraper/import_sqlite.py เป็นสะพานเข้า staging · ต้องเก็บทุก column ยกเว้นข้อมูลส่วนบุคคล (PDPA)
- Gemini อาจกำลังทำงานรอบที่ 2 ตาม HANDOFF_GEMINI.md อยู่ในโฟลเดอร์เดียวกัน (commit ได้ แต่ไม่ push) → ก่อนแก้ไฟล์ให้ดู `git status` / `git log` ก่อน อย่าแก้ไฟล์ที่ Gemini กำลังแก้ค้าง

## งานแรกของ session นี้
1. เช็ก harvester ด้วย start_harvesters.ps1 -Status ถ้าหยุดให้รัน start_harvesters.ps1 แล้วดูว่าทำไมหยุด (Get-WinEvent Kernel-Power 506/507 ดูเหตุผล sleep)
2. ดูว่า Gemini commit อะไรเพิ่ม → รันเทสต์ทั้งหมด (pytest, vitest, tsc, build) → ตรวจตามกติกา AGENTS.md (ไม่มีคีย์หลุด, ไม่มีข้อความประกาศใน repo public, เว็บไม่ส่ง description/qualifications, n ≥ 5, ไม่ใช้ LLM ติด label) → รายงานผู้ใช้แบบสั้น
3. ถามผู้ใช้ก่อน push ขึ้น GitHub ทุกครั้ง

## สิ่งที่ผู้ใช้ต้องทำเอง (เตือนถ้ายังไม่ทำ)
- ตั้ง Windows: Settings → System → Power → When I close the lid (plugged in) = Do nothing และเสียบสายชาร์จไว้
- Supabase Dashboard → Data API → Exposed schemas เพิ่ม `mart` แล้วรัน `.venv\Scripts\python.exe -X utf8 -m pipeline.check_permissions`
- ใส่ GEMINI_API_KEY ใน .env และ apps/web/.env.local
- deploy ml-api (Render Free หรือเครื่องมหาวิทยาลัย) ตาม docs/DEPLOY.md · ตอบ PLAN.md §11 (T0.4)
- คนตรวจมือ 200 ประกาศใน eval/skills_gold.csv (T2.7) และสุ่มตรวจวุฒิ/ประสบการณ์ 50 ประกาศ (T2.2)

## ข้อควรรู้
- เงินเดือนมีตัวเลขแค่ ~35% ของประกาศ (บริษัทไม่เปิดเผย แก้ไม่ได้) → แถวเทรนเงินเดือน ≈ 35% ของประกาศที่ดึงได้
- แต่ละชั้นสุ่ม (จังหวัด × ประเภทงาน) ได้แค่ ≤ 20 ประกาศล่าสุดจากหน้าแรก · N_h มาจาก "total" ในหน้ารายการ
- ตัวเลือกเพิ่มคุณภาพที่ยังไม่ได้ทำ (ต้องถามผู้ใช้ก่อน): ไล่หน้า 2..k ของชั้นใหญ่ตามสัดส่วน, JobBKK เป็นแหล่งที่ 2 + กันประกาศซ้ำข้ามเว็บ, feature คำในชื่อตำแหน่งสำหรับ ML, ขยาย taxonomy (T2.8)
- Python: .venv\Scripts\python.exe -X utf8 (รันโมดูลด้วย -m จาก root) · Git Bash แก้ไฟล์ .bat ด้วย sed จะทำให้ CRLF หาย ต้องแปลงกลับ
```
