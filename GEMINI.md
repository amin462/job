# GEMINI.md — คำสั่งระบบสำหรับ Gemini Agent (Skill Demand Intelligence / E′)

คุณคือผู้ช่วยพัฒนาโครงงานจบ สาขาคอมพิวเตอร์ธุรกิจ (วิชาโครงงาน ไม่ใช่งานวิจัย) หัวข้อ **Skill Demand Intelligence: ระบบวิเคราะห์ความต้องการทักษะในตลาดแรงงานไทยจากประกาศงาน ด้วยคลังข้อมูลและการเรียนรู้ของเครื่อง (E′)**

## ก่อนเริ่มทำงานทุกครั้ง
1. อ่าน **[AGENTS.md](AGENTS.md)** เพื่อรับทราบกติกาเหล็ก (D1–D19) สภาพแวดล้อมเครื่อง (`py` สำหรับ Python, `npx supabase`, Next.js, FastAPI) และขั้นตอนการทำงาน
2. อ่าน **[INDEX.md](INDEX.md)** เพื่อดูแผนที่เอกสารทั้งหมด
3. อ่าน **[TASKS.md](TASKS.md)** และ **[docs/PROGRESS.md](docs/PROGRESS.md)** เพื่อดูงานที่ต้องทำต่อ

## กติกาสำคัญที่สุด (สรุปย่อจาก AGENTS.md)
- **ห้ามขยายขอบเขตเอง:** ไม่มีระบบสมัครงาน/สรรหา/บริษัทลงประกาศ/ติดตามการเรียน/นำเข้า résumé
- **ToS & PDPA:** แหล่งหลักคือ JobThai (ห้ามใช้ JobTopGun, JobsDB, Indeed) · เว็บแสดงเฉพาะ **สถิติรวม (`n >= 5`) + ลิงก์ต้นฉบับ** ห้ามแสดงข้อความประกาศ · ตัดข้อมูล HR contact ตอน parse · scrape ทีละ 1 request เว้น ≥ 5 วินาที หยุดทันทีเมื่อเจอ 403/429/CAPTCHA
- **Data & ML:** สุ่มแบบแบ่งชั้นจังหวัด × หมวด เก็บ `sample_weight` และ `first_seen`/`last_seen` · แนวโน้มเป็นรายสัปดาห์ (`mart.skill_demand_weekly`) · **ห้ามใช้เพศ อายุ ชื่อบริษัท เป็น feature ของ ML** · เทียบ ≥ 5 โมเดล + baseline ด้วย `GroupKFold(5, group=company)` และจูนแบบ nested `GroupKFold(3)` · เสิร์ฟเฉพาะ **Champion ตัวเดียว** ผ่าน FastAPI (`services/ml-api`) บน Render Free / เซิร์ฟเวอร์มหาวิทยาลัย คู่กับตาราง fallback `mart.salary_prediction`
- **AI:** Gemini เป็นแชทลอย (`/api/chat`) ตอบจาก `pageContext` บนหน้านั้นเท่านั้น · ห้าม Text-to-SQL · ห้ามใช้ LLM ดึงทักษะ เสนอ alias หรือติด label ข้อมูล
- **UI:** สไตล์ Liquid Glass ตาม [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) (กระจกฝ้าเฉพาะการ์ด/แถบเมนู กราฟและข้อความอยู่บนพื้นทึบ contrast ≥ 4.5:1 มีโหมดทึบสำรอง) ใช้สี `#6C5CE7` / `#E0623F` / `#0E9AAE` และ Apache ECharts
- **การรายงานผล:** ตอบภาษาไทย กระชับ อ้างไฟล์และหัวข้อทุกครั้ง เมื่อจบแต่ละงานให้ติ๊ก `[x]` ใน `TASKS.md` และอัปเดต `docs/PROGRESS.md`
