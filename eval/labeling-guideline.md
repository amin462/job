# คู่มือการติดป้ายทักษะสำหรับชุดตรวจมือ (Skill Labeling Guideline — T2.7 / D16)

> **กติกาสำคัญ (PLAN D7, D16, D18):**
> - **ห้ามใช้ LLM / AI** ในการติดป้ายหรือช่วยตัดสินชุดข้อมูลนี้โดยเด็ดขาด ต้องดำเนินการโดยผู้ตรวจที่เป็นมนุษย์เท่านั้น
> - เพื่อปฏิบัติตาม ToS ของแหล่งข้อมูล (D4) ไฟล์ชุดตรวจ `eval/skills_gold_template.csv` และ `eval/skills_gold.csv` จะเก็บเฉพาะรหัสประกาศ (`source_job_id`), ลิงก์ต้นฉบับ (`source_url`), ชื่อตำแหน่งสั้น (`title_short`) และคอลัมน์ป้ายทักษะ — **ห้ามบันทึกข้อความรายละเอียดประกาศ (`description`/`qualifications`) ลงในไฟล์ชุดประเมิน** ให้ผู้ตรวจเปิดอ่านประกาศจากลิงก์ `source_url` หรือชุดข้อมูลภายในเครื่องขณะตรวจ

---

## 1. วัตถุประสงค์และขนาดตัวอย่าง

1. ใช้ประเมินความถูกต้อง (Precision, Recall, F1) ของตัวดึงทักษะแบบกฎและพจนานุกรม (`pipeline/etl/extract_skills.py`) แยกตามกลุ่มทักษะ (`skill_group`)
2. จำนวนตัวอย่างตรวจมือ: **200 ประกาศ** (สุ่มแบบแบ่งชั้นตาม `occupation_cluster`)
3. แบ่งงานระหว่างผู้ตรวจ 2 คน (หากทำตั้งแต่ 2 คนขึ้นไป):
   - ผู้ตรวจ A อย่างเดียว: 75 ประกาศ
   - ผู้ตรวจ B อย่างเดียว: 75 ประกาศ
   - **ชุดตรวจซ้ำร่วมกัน (Overlap Set): 50 ประกาศ** (ตรวจอิสระจากกัน ห้ามดูคำตอบอีกฝ่าย) เพื่อคำนวณค่าความสอดคล้อง **Cohen's kappa ($\kappa$)**

---

## 2. นิยามของ "ทักษะ" (Definition of a Skill)

ทักษะที่ต้องติดป้าย หมายถึง **ความสามารถ ความรู้ เครื่องมือ/ซอฟต์แวร์ ภาษา ใบอนุญาตวิชาชีพ หรือคุณลักษณะเชิงพฤติกรรม** ที่ประกาศระบุว่าผู้สมัครต้องมีหรือใช้ในการปฏิบัติงานจริง แบ่งเป็น 5 ประเภทตาม `taxonomy/skills.csv`:

| ประเภท (`skill_type`) | ตัวอย่างในประกาศไทย |
|---|---|
| `tool` | Microsoft Excel, Microsoft Word, PowerPoint, Power BI, AutoCAD, SolidWorks, SAP / ERP, Express Accounting, Photoshop, Canva |
| `technical` | SQL, Python, Accounting, Tax, Digital Marketing & Paid Ads, Warehouse & Logistics, QC / QA Inspection, Mechanical & Maintenance, Civil & Construction Supervision, Sales & Closing |
| `soft` | Communication, Teamwork & Collaboration, Leadership & Team Management, Problem Solving & Analytical Thinking, Negotiation & Persuasion, Service Mind |
| `language` | English, Chinese (Mandarin), Japanese, Korean, Translation & Interpretation |
| `licence` | Driving Licence (Car), Driving Licence (Motorcycle), Heavy Truck Licence (ท.2/บ.2), Engineering Licence (กว.), Safety Officer Licence (จป.), CPA / CPD Accounting Licence, Nursing / Medical Licence, TOEIC / IELTS Certificate |

---

## 3. กฎการรวมเข้าและตัดออก (Inclusion & Exclusion Rules)

### 3.1 รวมเข้า (Inclusion)
- ติดป้ายทุกทักษะที่ปรากฏชัดเจนใน **ชื่อตำแหน่ง**, **หน้าที่ความรับผิดชอบ**, หรือ **คุณสมบัติผู้สมัคร**
- หากชื่อตำแหน่งระบุบทบาท/เครื่องมือเชิงวิชาชีพโดยตรง (เช่น "ช่างเชื่อม" → `Welding & Metalwork`, "บาริสต้า" → `Food & Beverage Preparation`, "นักแปลภาษาจีน-ไทย" → `Chinese (Mandarin)` + `Translation & Interpretation`) ให้ติดป้ายทักษะนั้นด้วย
- ติดป้ายเฉพาะ **Canonical Skill** ที่มีอยู่ใน `taxonomy/skills.csv` ลงในคอลัมน์ `gold_skills_a` / `gold_skills_b` คั่นด้วยเครื่องหมาย `|` (pipe) เช่น `Microsoft Excel|Accounting|Tax`

### 3.2 ตัดออก (Exclusion)
1. **ห้ามติดป้ายสวัสดิการและสถานที่:** เช่น `"ค่ารักษาพยาบาล"`, `"ประกันสุขภาพ"`, `"ใกล้รถไฟฟ้า BTS/MRT"` ไม่ใช่ทักษะด้านการแพทย์ (`Nursing`) หรือไฟฟ้า (`Electrical Systems`)
2. **ห้ามติดป้ายข้อมูลส่วนบุคคล/การเลือกปฏิบัติ:** เพศ (`เพศชาย/หญิง`), อายุ (`22-35 ปี`), ส่วนสูง, ภูมิลำเนา
3. **ห้ามติดป้ายวุฒิการศึกษาและประสบการณ์:** เช่น `ปริญญาตรี`, `ปวส.`, `ประสบการณ์ 2 ปี` (แยกจัดเก็บไว้ในมิติ `dim_education` และ `dim_experience` แล้ว)
4. **ห้ามติดป้ายชื่อสินค้าหรืออุตสาหกรรมที่ไม่ใช่ทักษะปฏิบัติงาน:** เช่น พนักงานขายมือถือทั่วไปให้ติด `Sales & Closing` ไม่ติด `Mobile App Development`

---

## 4. กฎการแก้ความกำกวม (Ambiguity Resolution Rules)

| คำที่พบบ่อย | กฎการตัดสิน |
|---|---|
| **ขาย / Sales** | ติดป้าย `Sales & Closing` เฉพาะเมื่อหน้าที่หลักเกี่ยวข้องกับการเสนอขาย ปิดการขาย เชียร์ขาย หรือขายสินค้า/บริการ; **ไม่ติดป้าย** เมื่อคำว่า "ยอดขาย" ปรากฏในบริบทงานบัญชี/คลังสินค้า/QC (เช่น "สรุปรายงานยอดขาย", "ผลิตทันยอดขาย") |
| **Word** | ติดป้าย `Microsoft Word` เฉพาะเมื่อหมายถึงโปรแกรมพิมพ์เอกสาร หรือ MS Office; **ไม่ติดป้าย** เมื่อเป็นคำภาษาอังกฤษทั่วไป (เช่น `keyword`, `password`, `forward`, `in other words`) |
| **Express** | ติดป้าย `Express Accounting` เฉพาะบริบทโปรแกรมบัญชี Express; **ไม่ติดป้าย** เมื่อหมายถึงขนส่งด่วนหรือชื่อบริษัท |
| **R / C / Go** | ติดป้าย `R Programming`, `C Programming`, `Go (Golang)` เฉพาะเมื่อระบุเป็นภาษาโปรแกรมชัดเจน; **ไม่ติดป้าย** เมื่อพบเป็นคำย่อ/คำทั่วไป เช่น `HR`, `R&D`, `A/R`, `PC`, `QC`, `go to` |
| **SQL vs MySQL / PostgreSQL** | ติดป้ายเฉพาะเจาะจงตามที่ระบุ (เช่น ระบุ `PostgreSQL` ให้ติด `PostgreSQL`; ถ้าประกาศระบุคำว่า `SQL` แยกด้วยจึงติดทั้งคู่) |
| **Network** | ติดป้าย `Network / IT Support` เฉพาะเครือข่ายคอมพิวเตอร์/ไอที; **ไม่ติดป้าย** เมื่อหมายถึง "เครือข่ายลูกค้า/สายสัมพันธ์ธุรกิจ" ในงานขาย/KOL |
| **ใบขับขี่ ท.2 / บ.2** | ติดป้าย `Heavy Truck Licence (ท.2/บ.2)` เฉพาะเมื่อมีจุดหรือระบุใบอนุญาตขับขี่รถบรรทุกชัดเจน; **ไม่ติดป้าย** กรณีข้อความทั่วไปอย่าง "รับ 2 อัตรา" |

---

## 5. กฎการคำนวณ Recall และทักษะนอก Taxonomy (D16)

1. **Recall นับเฉพาะทักษะใน Taxonomy (`Recall within taxonomy`):**
   - เพื่อไม่ให้คะแนน Recall ถูกบิดเบือนจากทักษะที่อยู่นอกพจนานุกรมในเวอร์ชันปัจจุบัน ระบบจะคำนวณ:
     $$\text{Precision} = \frac{TP}{TP + FP}, \quad \text{Recall}_{\text{in-tax}} = \frac{TP}{TP + FN_{\text{in-tax}}}$$
2. **บันทึกทักษะนอก Taxonomy แยกต่างหาก (Out-of-Taxonomy / OOV Log):**
   - หากพบทักษะจริงในประกาศที่ **ยังไม่มีใน `taxonomy/skills.csv`** (เช่น `Power Apps`, `SAP B1`, `SolidEdge`) ให้พิมพ์ชื่อลงในคอลัมน์ `out_of_taxonomy_skills` คั่นด้วย `|`
   - สคริปต์ `eval/evaluate_skills.py` จะคำนวณ **OOV Rate** แยกต่างหาก เพื่อใช้เป็นข้อมูลขยาย Taxonomy รอบที่ 2 (`T2.8`)

---

## 6. ขั้นตอนการตรวจซ้ำ 50 ประกาศและคำนวณ Cohen's $\kappa$

1. รันสคริปต์สร้างชุดสุ่มแบ่งชั้น:
   ```powershell
   .\.venv\Scripts\python.exe -I -X utf8 eval/prepare_gold_set.py
   ```
2. ผู้ตรวจ A ติดป้ายในคอลัมน์ `gold_skills_a` สำหรับแถวที่ `annotator_group` เป็น `annotator_a` และ `overlap_50`
3. ผู้ตรวจ B ติดป้ายในคอลัมน์ `gold_skills_b` สำหรับแถวที่ `annotator_group` เป็น `annotator_b` และ `overlap_50` (ห้ามดูผลของ A ก่อน)
4. รันสคริปต์ประเมินผลเพื่อตรวจ Cohen's $\kappa$ และ Precision / Recall / F1 รายกลุ่มทักษะ:
   ```powershell
   .\.venv\Scripts\python.exe -I -X utf8 eval/evaluate_skills.py --gold eval/skills_gold.csv --pred data/processed/clean_postings.csv
   ```
5. เกณฑ์เป้าหมาย:
   - Cohen's $\kappa \ge 0.75$ (ความสอดคล้องระดับดีมากระหว่างผู้ตรวจ 2 คน)
   - Overall Precision $\ge 0.85$ และ Recall (within taxonomy) $\ge 0.80$
   - กรณีที่ผู้ตรวจทั้งสองเห็นต่างกันบนชุด `overlap_50` ให้ปรึกษาร่วมกัน (Adjudication) เพื่อสรุปป้ายที่ถูกต้องที่สุดลงในชุด `skills_gold.csv`
