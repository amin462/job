# ร่างอีเมลขออนุญาตเก็บข้อมูลเพื่อการศึกษาถึงทีมงาน JobThai (T0.3)

> **คำแนะนำสำหรับผู้จัดทำ:** สามารถเลือกส่งฉบับภาษาไทย (แนะนำสำหรับทีมงาน JobThai ในประเทศไทย) หรือแนบฉบับภาษาอังกฤษประกอบ โดยกรอกข้อมูลใน `[...]` ให้ครบถ้วน และบันทึกวันที่ส่ง/ผลตอบรับไว้ในหน้า `/admin/sources` และ `docs/PROGRESS.md`

---

## ฉบับที่ 1: ภาษาไทย (หลัก)

**ถึง:** ฝ่ายติดต่อประสานงาน / ทีมกฎหมายและดูแลระบบ บริษัท ทิงค์เน็ต จำกัด (JobThai.com)  
**หัวข้ออีเมล (Subject):** ขออนุญาตนำข้อมูลประกาศรับสมัครงานสาธารณะบน JobThai มาใช้วิเคราะห์เชิงสถิติสำหรับโครงงานนักศึกษา (เพื่อการศึกษาเท่านั้น)

เรียน ทีมงาน JobThai.com

ข้าพเจ้า `[ชื่อ-สกุล]` รหัสนักศึกษา `[รหัสนักศึกษา]` นักศึกษาชั้นปีที่ `[ชั้นปี]` สาขาวิชา `[สาขาวิชา/มหาวิทยาลัย]` กำลังดำเนินโครงงานปริญญานิพนธ์ระดับปริญญาตรี เรื่อง **"Skill Demand Intelligence: ระบบวิเคราะห์ความต้องการทักษะในตลาดแรงงานไทยจากประกาศงาน ด้วยคลังข้อมูลและการเรียนรู้ของเครื่อง"** ภายใต้การดูแลของอาจารย์ที่ปรึกษา `[ชื่ออาจารย์ที่ปรึกษา]`

โครงงานนี้มีวัตถุประสงค์เพื่อพัฒนาทักษะทางวิศวกรรมข้อมูลและการเรียนรู้ของเครื่อง โดยช่วยให้นักศึกษาและสถาบันการศึกษาเห็นภาพรวมความต้องการทักษะในตลาดแรงงานไทยและช่วงเงินเดือนที่เหมาะสม ข้าพเจ้าจึงใคร่ขออนุญาตเข้าถึงและจัดเก็บข้อมูลจาก **หน้าประกาศรับสมัครงานสาธารณะ** บนเว็บไซต์ JobThai.com เพื่อนำมาวิเคราะห์ในโครงงาน โดยมีมาตรการเคารพสิทธิ์และระบบของท่านอย่างเคร่งครัดดังนี้

1. **เพื่อการศึกษาเท่านั้น ไม่มีผลประโยชน์เชิงพาณิชย์:** ระบบนี้จัดทำเพื่อส่งอาจารย์ในรายวิชาโครงงานเท่านั้น ไม่มีการหารายได้ โฆษณา หรือจำหน่ายข้อมูลใดๆ
2. **การเข้าถึงแบบสุภาพ (Polite Access) ไม่กระทบการทำงานของเซิร์ฟเวอร์:**
   - เข้าถึงเฉพาะ URL สาธารณะที่ `robots.txt` อนุญาต ไม่เรียกใช้ API ภายในของระบบ
   - ส่งคำขอทีละ **1 request (Concurrency = 1)** และหน่วงเวลา **อย่างน้อย 5 วินาทีต่อ 1 request**
   - ใช้วิธีสุ่มตัวอย่างแบบแบ่งชั้น (Stratified Sampling) ประมาณ 5,000–10,000 ประกาศ ไม่ดาวน์โหลดทั้งเว็บไซต์ในคราวเดียว
   - ระบุตัวตนโครงงานและอีเมลติดต่อไว้ใน `User-Agent` อย่างชัดเจน และหากพบสถานะ HTTP 403/429 ระบบจะหยุดการทำงานทันที
3. **การคุ้มครองข้อมูลส่วนบุคคล (PDPA):** ข้าพเจ้าจะ **ไม่จัดเก็บ** ข้อมูลติดต่อของเจ้าหน้าที่ฝ่ายบุคคล (ชื่อผู้ติดต่อ เบอร์โทรศัพท์ อีเมล หรือ LINE ID) โดยระบบจะตัดข้อมูลส่วนนี้ทิ้งตั้งแต่ขั้นตอนประมวลผลเริ่มต้น
4. **การแสดงผลและให้เครดิตแก่ JobThai:**
   - เว็บแอปพลิเคชันของโครงงานจะ **ไม่แสดงข้อความรายละเอียดหรือคุณสมบัติของประกาศงานซ้ำ** โดยเด็ดขาด
   - จะแสดงเฉพาะ **ตัวเลขสถิติเชิงรวม (Aggregate)** เช่น สัดส่วนความต้องการทักษะและช่วงเงินเดือน (เมื่อจำนวนตัวอย่าง `n >= 5`) เท่านั้น
   - มีการระบุแหล่งที่มาและวาง **ลิงก์ตรงกลับไปยังหน้าประกาศต้นฉบับบนเว็บไซต์ JobThai** เพื่อส่งเสริมการเข้าชมกลับสู่เว็บไซต์ของท่าน

หากทาง JobThai มีข้อกำหนดเพิ่มเติม รูปแบบข้อมูลสาธารณะที่แนะนำ หรือไม่ประสงค์ให้ดำเนินการต่อ ข้าพเจ้ายินดีปฏิบัติตามและยุติการเก็บข้อมูลพร้อมลบข้อมูลทันทีที่ได้รับแจ้ง

จึงเรียนมาเพื่อโปรดพิจารณาอนุเคราะห์ และขอขอบพระคุณมา ณ โอกาสนี้

ขอแสดงความนับถือ

`[ชื่อ-สกุล]` (`[รหัสนักศึกษา]`)  
นักศึกษาสาขาวิชา `[สาขาวิชา/มหาวิทยาลัย]`  
อีเมล: `[อีเมลติดต่อ]` | โทรศัพท์: `[เบอร์โทรศัพท์นักศึกษา]`  
อาจารย์ที่ปรึกษา: `[ชื่ออาจารย์ที่ปรึกษา]` (`[อีเมลอาจารย์ที่ปรึกษา]`)

---

## ฉบับที่ 2: English Template (Optional / International Correspondence)

**To:** JobThai Support / Legal & Technical Team (THiNKNET Co., Ltd.)  
**Subject:** Academic Request: Read-Only Statistical Analysis of Public JobThai Postings for Undergraduate Capstone Project

Dear JobThai Team,

My name is `[ชื่อ-สกุล]` (Student ID: `[รหัสนักศึกษา]`), an undergraduate student in `[สาขาวิชา/มหาวิทยาลัย]`. Under the supervision of `[ชื่ออาจารย์ที่ปรึกษา]`, I am developing an academic capstone project titled **"Skill Demand Intelligence: A Data Warehouse and Machine Learning–Based System for Analyzing Skill Demand from Thai Job Postings."**

Our goal is strictly educational: to analyze aggregate skill requirements and salary ranges across Thailand so students and universities can better align curricula with labor market needs. I am writing to respectfully request permission to read and analyze a stratified sample (~5,000–10,000 postings) from JobThai's **publicly accessible job posting pages** under the following strict commitments:

1. **Non-Commercial & Academic Use Only:** The project is solely for coursework evaluation and has zero commercial purpose.
2. **Polite & Rate-Limited Access:**
   - Read-only access to public pages permitted by `robots.txt` only (no internal APIs).
   - Strict sequential access (**concurrency = 1**) with a minimum delay of **>= 5 seconds per request**.
   - Transparent `User-Agent` identifying the student project and contact email; immediate halt on any HTTP 403, 429, or CAPTCHA response.
3. **PDPA & Privacy Protection:** All HR contact details (contact names, phone numbers, email addresses, and LINE IDs) are stripped immediately during parsing and are never stored in our database.
4. **Aggregate-Only Display & Attribution Links:**
   - We **never republish or display full job descriptions or qualification texts** on our website or APIs.
   - Only statistical aggregates (with minimum group threshold `n >= 5`) are shown, accompanied by clear attribution to JobThai and direct links back to the original job pages on `jobthai.com`.

If there are specific guidelines we should follow, or if you prefer that we do not collect data from JobThai, we will fully respect your decision and immediately stop and remove any collected raw files upon request.

Thank you very much for your time and consideration.

Sincerely,

`[ชื่อ-สกุล]` (`[รหัสนักศึกษา]`)  
`[สาขาวิชา/มหาวิทยาลัย]`  
Email: `[อีเมลติดต่อ]` | Phone: `[เบอร์โทรศัพท์นักศึกษา]`  
Project Advisor: `[ชื่ออาจารย์ที่ปรึกษา]` (`[อีเมลอาจารย์ที่ปรึกษา]`)
