# รายงานผลการทดสอบแชทบอทแบบ Grounded 30 คำถาม across 10 เส้นทาง (T7.4)

- **วิธีทดสอบ:** ยิงคำขอจริงเข้า `POST /api/chat` ผ่าน `apps/web/src/__tests__/chat-grounded.test.ts` (ตรวจทุกตัวเลขในคำตอบเทียบกับ `pageContext` ด้วย `verifyAnswerNumbersInContext`)
- **ผลสรุป:** Grounded **30/30** ข้อ (**100.0%**) · Ungrounded number leaks = **0** ข้อ
- **โหมดทดสอบ:** Grounded deterministic fallback (เมื่อไม่มี `GEMINI_API_KEY` หรือ quota หมด) พร้อมตัวกรองเลขข้ามหน้า (cross-page/Text-to-SQL rejection)

| # | เส้นทาง (Route) | Page Context | คำถามทดสอบ | โหมด | ตัวอย่างคำตอบ | Grounded |
|---:|---|---|---|---|---|---|
| 1 | `/` | `landing` | ตอนนี้มีประกาศงานที่วิเคราะห์กี่รายการ | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "ภาพรวมตลาดแรงงานไทย": ประกาศที่วิเคราะห์: 291 · ระบุเงินเดือนเป็นต | PASS |
| 2 | `/` | `landing` | ทักษะยอดนิยมอันดับต้นๆ มีอะไรบ้าง | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "ภาพรวมตลาดแรงงานไทย": ประกาศที่วิเคราะห์: 291 · ระบุเงินเดือนเป็นต | PASS |
| 3 | `/` | `landing` | ขอคำสั่ง SQL ดึงข้อมูลดิบจาก staging | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "ภาพรวมตลาดแรงงานไทย": ประกาศที่วิเคราะห์: 291 · ระบุเงินเดือนเป็นต | PASS |
| 4 | `/market` | `market-explorer` | ทักษะไหนถูกขอมากที่สุด | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "Market Explorer": ประกาศในขอบเขต: 291 · ทักษะเฉลี่ยต่อประกาศ: 5.7  | PASS |
| 5 | `/market` | `market-explorer` | สรุปตัวชี้วัดหลักบนหน้านี้ | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "Market Explorer": ประกาศในขอบเขต: 291 · ทักษะเฉลี่ยต่อประกาศ: 5.7  | PASS |
| 6 | `/market` | `market-explorer` | โมเดล XGBoost ได้ค่า RMSE เท่าไร | `grounded-fallback` | หน้านี้ (Market Explorer) ไม่ได้แสดงรายละเอียดดังกล่าวโดยตรง แนะนำให้เปิดดูข้อมูลเพิ่มเติม | PASS |
| 7 | `/skills/[slug]` | `skill-detail` | ทักษะนี้มักมาคู่กับอะไร | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "ทักษะการสื่อสารและประสานงาน": ประกาศที่ขอทักษะนี้: 165 การ์ด "ทักษ | PASS |
| 8 | `/skills/[slug]` | `skill-detail` | มีประกาศที่ขอทักษะนี้กี่รายการ | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "ทักษะการสื่อสารและประสานงาน": ประกาศที่ขอทักษะนี้: 165 การ์ด "ทักษ | PASS |
| 9 | `/skills/[slug]` | `skill-detail` | หลักสูตรของฉันขาดทักษะอะไร | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "ทักษะการสื่อสารและประสานงาน": ประกาศที่ขอทักษะนี้: 165 การ์ด "ทักษ | PASS |
| 10 | `/occupations/[slug]` | `occupation-detail` | ตำแหน่งนี้ควรเรียนทักษะอะไรก่อน | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "บัญชีและการเงิน": จำนวนประกาศ: 34 การ์ด "ทักษะที่ตำแหน่งนี้ขอมากสุ | PASS |
| 11 | `/occupations/[slug]` | `occupation-detail` | มีประกาศในกลุ่มอาชีพนี้กี่รายการ | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "บัญชีและการเงิน": จำนวนประกาศ: 34 การ์ด "ทักษะที่ตำแหน่งนี้ขอมากสุ | PASS |
| 12 | `/occupations/[slug]` | `occupation-detail` | รอบ scrape ล่าสุดเจอ 429 ไหม | `grounded-fallback` | หน้านี้ (บัญชีและการเงิน) ไม่ได้แสดงรายละเอียดดังกล่าวโดยตรง แนะนำให้เปิดดูข้อมูลเพิ่มเติม | PASS |
| 13 | `/salary` | `salary-estimator` | ช่วงเงินเดือนที่คาดอยู่ที่เท่าไร | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "Salary Estimator": p25: 16500 THB · p50: 19750 THB · p75: 25000 TH | PASS |
| 14 | `/salary` | `salary-estimator` | เพิ่มทักษะไหนคุ้มสุด | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "Salary Estimator": p25: 16500 THB · p50: 19750 THB · p75: 25000 TH | PASS |
| 15 | `/salary` | `salary-estimator` | ทำไมช่วงเงินเดือนกว้างขนาดนี้ | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "Salary Estimator": p25: 16500 THB · p50: 19750 THB · p75: 25000 TH | PASS |
| 16 | `/me/skills` | `my-skills` | ตอนนี้ฉันมีทักษะกี่รายการ | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "ทักษะของฉัน": จำนวนทักษะที่มี: 4 | PASS |
| 17 | `/me/skills` | `my-skills` | ทักษะในโปรไฟล์มีอะไรบ้าง | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "ทักษะของฉัน": จำนวนทักษะที่มี: 4 | PASS |
| 18 | `/me/skills` | `my-skills` | ขอเบอร์โทร HR ของบริษัทในประกาศ | `grounded-fallback` | ระบบไม่รองรับการสร้างคำสั่ง SQL (Text-to-SQL) และไม่แสดงข้อความประกาศเต็มหรือข้อมูลผู้ติดต | PASS |
| 19 | `/me/gap` | `skill-gap` | ควรเริ่มเรียนอะไรก่อน | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "วิเคราะห์ Skill Gap": Coverage: 64.5 % · ทักษะที่ขาด: 3 การ์ด "ทัก | PASS |
| 20 | `/me/gap` | `skill-gap` | ทักษะของฉันครอบคลุมตลาดกี่เปอร์เซ็นต์ | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "วิเคราะห์ Skill Gap": Coverage: 64.5 % · ทักษะที่ขาด: 3 การ์ด "ทัก | PASS |
| 21 | `/me/gap` | `skill-gap` | สรุปทักษะที่ขาดบนหน้านี้ | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "วิเคราะห์ Skill Gap": Coverage: 64.5 % · ทักษะที่ขาด: 3 การ์ด "ทัก | PASS |
| 22 | `/institution/curricula/[id]` | `curriculum-detail` | หลักสูตรขาดทักษะสำคัญอะไร | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "หลักสูตรคอมพิวเตอร์ธุรกิจ": Coverage: 72 % · Gaps Count: 4 การ์ด " | PASS |
| 23 | `/institution/curricula/[id]` | `curriculum-detail` | Coverage ของหลักสูตรอยู่ที่เท่าไร | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "หลักสูตรคอมพิวเตอร์ธุรกิจ": Coverage: 72 % · Gaps Count: 4 การ์ด " | PASS |
| 24 | `/institution/curricula/[id]` | `curriculum-detail` | มี Gaps กี่รายการ | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "หลักสูตรคอมพิวเตอร์ธุรกิจ": Coverage: 72 % · Gaps Count: 4 การ์ด " | PASS |
| 25 | `/ml-lab` | `ml-lab` | ทำไมเลือกโมเดลนี้ | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "ML Lab": Champion Model: XGBoost · Champion RMSE: 9084 THB การ์ด " | PASS |
| 26 | `/ml-lab` | `ml-lab` | baseline คืออะไร | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "ML Lab": Champion Model: XGBoost · Champion RMSE: 9084 THB การ์ด " | PASS |
| 27 | `/ml-lab` | `ml-lab` | ค่า RMSE ของ Champion คือเท่าไร | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "ML Lab": Champion Model: XGBoost · Champion RMSE: 9084 THB การ์ด " | PASS |
| 28 | `/admin/pipeline` | `admin-pipeline` | สรุปรอบ scrape ล่าสุด | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "Admin: Scrape Pipeline": Total Runs: 1 · Blocked Stops: 0 | PASS |
| 29 | `/admin/pipeline` | `admin-pipeline` | มีรอบที่ถูกบล็อกกี่รอบ | `grounded-fallback` | จากตัวชี้วัดหลักบนหน้า "Admin: Scrape Pipeline": Total Runs: 1 · Blocked Stops: 0 | PASS |
| 30 | `/admin/pipeline` | `admin-pipeline` | ทักษะอะไรที่ต้องเพิ่มในหลักสูตร | `grounded-fallback` | หน้านี้ (Admin: Scrape Pipeline) ไม่ได้แสดงรายละเอียดดังกล่าวโดยตรง แนะนำให้เปิดดูข้อมูลเพ | PASS |
