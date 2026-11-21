# DEPLOY.md — คู่มือและสถาปัตยกรรม Deploy ฟรี (2 ที่ + Database)

> อ้างอิง: [PLAN.md (D9, D19)](../PLAN.md) · [ARCHITECTURE.md §1, §6](../ARCHITECTURE.md) · [TASKS.md (T0.5, T0.6, T4.0, T9.5)](../TASKS.md)

---

## 1. สรุปการเลือกใช้บริการฟรี (ทำไมใช้คู่ไหน และทำไมตัด Railway)

โครงงานนี้แยกส่วนการทำงานออกเป็น **4 ส่วน** เพื่อให้ใช้แผนฟรีได้ตลอดอายุโครงงาน 16 สัปดาห์โดยไม่ติดเพดานทรัพยากร:

| ส่วนของระบบ | บริการที่เลือก | ทำไมถึงเลือก / ข้อจำกัดสำคัญ |
|---|---|---|
| **1. Frontend + BFF API** (`apps/web`) | **Vercel (Hobby — ฟรี)** | รองรับ Next.js App Router โดยตรง, HTTPS อัตโนมัติ, deploy จาก GitHub ทันที · มี `/api/chat` (เรียก Gemini) และ `/api/salary/estimate` (เป็น proxy เรียก `ml-api` พร้อม fallback) |
| **2. Database + Auth + RLS** (`supabase/migrations`) | **Supabase (Free Tier)** | ได้ PostgreSQL 500 MB + Auth + Row Level Security ครบ · **ข้อระวัง:** โปรเจกต์ฟรีจะ pause ถ้าไม่มีการใช้งาน 7 วัน → แก้ด้วยการตั้ง `cron-job.org` ยิง ping ทุก 3 วัน และ **ไม่เก็บ HTML ดิบใน DB** (5,000–10,000 ประกาศที่คลีนแล้วใช้พื้นที่ < 80 MB) |
| **3. ML Champion API** (`services/ml-api`) | **ทางเลือก A (แนะนำถ้ามี):** เซิร์ฟเวอร์/VM ของมหาวิทยาลัย<br>**ทางเลือก B (ฟรีสาธารณะ):** **Render (Free Web Service)** | เสิร์ฟ FastAPI ที่โหลดโมเดลที่ชนะ (`salary_champion.joblib` / CatBoost / LightGBM) ด้วย Python โดยตรง ไม่ต้องแปลงเป็น ONNX และไม่ต้องยัดไลบรารี ML ลงใน Vercel Serverless Function |
| **4. Scraper + ETL + ML Training** (`pipeline/`) | **เครื่องพัฒนา (Local PC) หรือเครื่องแล็บมหาวิทยาลัย** | การดึงข้อมูลใช้ Playwright + เว้น ≥ 5 วินาที/request (ใช้เวลาหลายชั่วโมง) และเก็บไฟล์ HTML ดิบบนดิสก์ จึง **ห้ามรันบน Vercel หรือ Render** ให้รันบนเครื่องตัวเอง/มหาวิทยาลัยแล้วอัปเดตผลเข้า Supabase ผ่าน `DATABASE_URL` |

### ทำไมไม่แนะนำ Railway สำหรับโครงงาน 16 สัปดาห์?
- **Railway:** ให้เครดิตทดลอง (Trial) \$5 แค่ **30 วันแรก** หลังจากนั้นแผน Free เหลือเครดิตเพียง **\$1/เดือน** (RAM จำกัด 0.5 GB และไม่มี cron) ซึ่งถ้าเปิด FastAPI ทิ้งไว้จะหมดโควตากลางเดือนและบริการจะดับก่อนวันสอบ
- **Render (Free Web Service):** ให้ **750 ชั่วโมง/เดือน** (1 เดือนมี 744 ชั่วโมง = รัน 1 service ได้เต็มเดือนฟรีตลอด) ข้อจำกัดเดียวคือ **ถ้าไม่มี request เข้ามา 15 นาที บริการจะหลับ (spin down)** และใช้เวลาปลุก (cold start) ประมาณ 50–60 วินาที ซึ่งเราแก้ได้ด้วยเทคนิคในหัวข้อที่ 3
- **หมายเหตุเรื่องฐานข้อมูลบน Render:** **ห้ามใช้ Render Free PostgreSQL** เพราะฐานข้อมูลฟรีของ Render จะหมดอายุและถูกลบใน 30 วัน ให้เก็บข้อมูลทั้งหมดไว้ที่ **Supabase** ที่เดียว

---

## 2. เปรียบเทียบที่ตั้งของ `services/ml-api`: มหาวิทยาลัย vs Render Free

ในงาน **T0.6** ให้สอบถามอาจารย์หรือฝ่าย IT ของมหาวิทยาลัยตามเช็กลิสต์นี้:

| เกณฑ์พิจารณา | เซิร์ฟเวอร์/VM มหาวิทยาลัย | Render Free Web Service |
|---|---|---|
| เปิดตลอด 24 ชม. ไม่หลับ (No Cold Start) | ✅ เปิดตลอด (ถ้าไม่ปิดเครื่อง) | ⚠️ หลับหลังไม่มีทราฟฟิก 15 นาที (ปลุก ~50–60 วินาที) |
| เรียกจาก Vercel ผ่านอินเทอร์เน็ตได้ไหม | ❓ ต้องมี Public IP/Domain + **HTTPS** (หรือเปิดพอร์ตให้ตั้ง Cloudflare Tunnel ได้) | ✅ มี HTTPS URL (`https://xxx.onrender.com`) ให้ทันที |
| รัน Scraper/ETL รายสัปดาห์ในตัวได้ไหม | ✅ ตั้ง `cron` บนเครื่องเดียวกันได้เลย | ❌ ไม่ได้ (RAM 512 MB ไม่พอ Playwright และไม่มีดิสก์ถาวร) |
| **ข้อสรุปการเลือก** | **ใช้เป็นตัวหลัก** ถ้า IT มหาวิทยาลัยเปิด HTTPS สาธารณะหรืออนุญาต Cloudflare Tunnel | **ใช้เป็นค่าเริ่มต้นทันที** ถ้ามหาวิทยาลัยให้ใช้ได้เฉพาะในวง LAN/VPN |

> **สามารถใช้ทั้ง 2 ที่คู่กันได้:** รัน Scraper/ETL บนเครื่องมหาวิทยาลัยหรือเครื่องตัวเอง (เพราะต้องออกเน็ตไปดึง JobThai และเขียนลง Supabase เท่านั้น ไม่ต้องเปิดพอร์ตรับขาเข้า) แล้วเอาเฉพาะ `services/ml-api` ขึ้น Render Free ให้ Vercel เรียกใช้งาน

---

## 3. การออกแบบ `services/ml-api` และวิธีแก้ Cold Start บน Render Free

เพื่อให้ผู้ใช้หน้า `/salary` ไม่ต้องคอย 60 วินาทีเวลา Render หลับ ระบบออกแบบป้องกันไว้ **3 ชั้น**:

1. **Pre-warm ตอนเปิดหน้า `/salary`:**
   - ทันทีที่ผู้ใช้เปิดหน้า `/salary` เบราว์เซอร์จะยิง `GET /api/salary/estimate?warm=1` แบบเบื้องหลังเพื่อส่ง `GET /health` ไปปลุก `ml-api` ล่วงหน้าในขณะที่ผู้ใช้กำลังเลือกตัวกรองและทักษะ
2. **Timeout 8 วินาที + Fallback อัตโนมัติ (`mart.salary_prediction`):**
   - เมื่อผู้ใช้กดปุ่มคำนวณ Route `/api/salary/estimate` บน Vercel จะเรียก `POST ${ML_API_URL}/predict` พร้อม header `X-ML-Key: ${ML_API_KEY}` และตั้ง timeout ไว้ 8 วินาที
   - ถ้า `ml-api` ตอบทัน → แสดงช่วงเงินเดือน p25–p75 จากโมเดล Champion สด พร้อมป้าย *"คำนวณสดจากโมเดล Champion"*
   - ถ้า `ml-api` กำลังตื่นหรือล่ม (timeout/5xx) → ดึงค่าที่คำนวณล่วงหน้าจากตาราง `mart.salary_prediction` (หรือค่ามัธยฐานจาก `mart.salary_stats`) มาแสดงทันทีพร้อมป้าย *"ค่าประมาณที่คำนวณล่วงหน้า (บริการโมเดลกำลังเริ่มต้น)"* หน้าเว็บจึงไม่มีวันพังในห้องสอบ
3. **Keep-Awake ช่วงซ้อมและวันสอบ:**
   - ตั้ง `cron-job.org` (ฟรี) ให้ยิง `GET https://<your-ml-api>.onrender.com/health` ทุก **14 นาที** ในช่วงสัปดาห์ที่ตรวจรับและวันสอบ (750 ชั่วโมง/เดือนของ Render เพียงพอสำหรับการเปิดค้าง 1 บริการตลอดทั้งเดือน)

### Endpoints ของ `services/ml-api`
- `GET /health` → `{"status": "ok", "model": "<champion_name>", "dataset_version": "..."}` (ไม่ล็อก key เพื่อให้ cron-job.org เรียกได้)
- `POST /predict` (ตรวจ header `X-ML-Key`) → รับ feature 1 ชุด คืน `{"p25": ..., "p50": ..., "p75": ..., "model_name": ...}`
- `POST /predict/batch` (ตรวจ header `X-ML-Key`) → รับรายการชุด feature (ใช้คำนวณการ์ด *"ทักษะที่ถ้าเพิ่มแล้วเงินเดือนที่คาดเพิ่มขึ้น"* ในครั้งเดียว ไม่ต้องวนยิงทีละทักษะ)

---

## 4. รายการ Environment Variables แยกตามสถานที่ Deploy

### 4.1 บน Vercel (`apps/web`)
| ตัวแปร | คำอธิบาย |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | URL ของโปรเจกต์ Supabase |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Anon key (ใช้คู่กับ RLS และอ่านเฉพาะ `mart.*` ที่เปิดสิทธิ์) |
| `SUPABASE_SERVICE_ROLE_KEY` | ใช้เฉพาะใน Server Action สำหรับล็อกอินเดโม 4 persona และงานหลังบ้าน |
| `ML_API_URL` | URL ของ FastAPI บน Render หรือเซิร์ฟเวอร์มหาวิทยาลัย |
| `ML_API_KEY` | รหัสลับที่ใช้ส่งใน header `X-ML-Key` ระหว่าง Vercel กับ `ml-api` |
| `GEMINI_API_KEY` | API key ของ Google Gemini สำหรับ `/api/chat` |
| `GEMINI_MODEL` | ค่าเริ่มต้น `gemini-2.5-flash` |
| `DEMO_*_EMAIL` / `DEMO_*_PASSWORD` | บัญชีเดโม 4 บทบาทสำหรับปุ่มเข้าใช้คลิกเดียว |

### 4.2 บน Render Free หรือเซิร์ฟเวอร์มหาวิทยาลัย (`services/ml-api`)
| ตัวแปร | คำอธิบาย |
|---|---|
| `ML_API_KEY` | รหัสลับตรงกับฝั่ง Vercel |
| `MODEL_PATH` | ค่าเริ่มต้น `models/salary_champion.joblib` |
| `FEATURE_SPEC_PATH` | ค่าเริ่มต้น `models/feature_spec.json` |

### 4.3 บนเครื่องที่รัน Pipeline (`pipeline/.env`)
| ตัวแปร | คำอธิบาย |
|---|---|
| `DATABASE_URL` | Connection string ของ Supabase Postgres (ใช้โหลด `staging` → `dw` → `mart` → `ml`) |
| `SCRAPER_USER_AGENT` | ข้อความระบุตัวตนโครงงานและอีเมลติดต่อ |
| `SCRAPER_MIN_DELAY_SEC` | `5.0` (ห้ามตั้งต่ำกว่า 5 วินาที) |

---

## 5. บันทึกผลการตัดสินใจเลือก Host (อัปเดตเมื่อทำ T0.6 และ T4.0)

- **สถานะปัจจุบัน:** ใช้ **Vercel (Web) + Supabase (DB/Auth) + Render Free (`services/ml-api`)** เป็นค่าเริ่มต้น และรัน `pipeline/` บนเครื่องพัฒนา
- **ผลสอบถาม IT มหาวิทยาลัย (T0.6):** *(รอผู้ใช้บันทึก)*
- **ผลทดสอบ Cold Start บน Render (T4.0):** *(รอ Agent/ผู้ใช้บันทึกเมื่อ deploy โครง `services/ml-api`)*
