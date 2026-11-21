# PLAN.md — ผลตรวจสเปก วิเคราะห์ความเป็นไปได้ และแผนพัฒนา SouthBiz Pulse BI (ข้อเสนอ v2)

> **สถานะ:** ร่าง v2 ปรับตามคำตอบรอบที่ 2 · **วันที่:** 18 พ.ย. 2569 (2026-11-18)
> **ขอบเขต:** ตรวจ [CONTEXT.md](CONTEXT.md), [ARCHITECTURE.md](ARCHITECTURE.md) และภาพอ้างอิงใน `design/`
> **เอกสารคู่กัน:** [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) ว่าด้วยภาษาภาพ สี และการจับคู่กราฟจากภาพ design กับฟีเจอร์จริง
>
> เอกสารนี้ยังไม่ได้แก้ CONTEXT.md/ARCHITECTURE.md เมื่อตอบคำถามที่เหลือในหัวข้อ 15 แล้ว จะนำข้อที่ตกลงไปปรับเป็น v2 ทั้งสองไฟล์

---

## 0. สรุปย่อ

### 0.1 บันทึกการตัดสินใจ (รอบที่ 2)

| เรื่อง | ตัดสินใจแล้ว | ผลต่อแผน |
|---|---|---|
| แหล่งข้อมูล | **Scraping** (อาจารย์ที่ปรึกษาแนะนำ) | Scraping เป็นแหล่งหลัก + API เปิด (FX/อากาศ/วันหยุด/ท่องเที่ยว) + ข้อมูลที่เจ้าของร้านกรอก ต้องมี governance (หัวข้อ 5.3) |
| ประเภทงาน | **โครงงาน** ไม่ใช่งานวิจัย ไม่ต้องลงพื้นที่ | ตัดการสำรวจภาคสนาม, QR survey, gold set 2 คน/κ ออก เปลี่ยนเป็นการทดสอบระบบ + ประเมินความพึงพอใจ (หัวข้อ 10) |
| อุตสาหกรรม | **ครบทุกธุรกิจตั้งแต่เริ่ม** | ใช้สถาปัตยกรรม **Industry Pack** (ตั้งค่าด้วย config ไม่ต้องเขียนโค้ดแยกอุตสาหกรรม) (หัวข้อ 4.0) |
| พื้นที่นำร่อง | **สงขลา ยะลา ปัตตานี นราธิวาส** | บริบทชายแดนใต้ (หัวข้อ 4.1) เปลี่ยนคู่แข่งข้ามแดนเป็นกลันตัน/เคดาห์/เประ/ปีนัง ตัดภูเก็ตกับฝั่งอันดามันออก |
| Python | **Deploy แยกที่อื่นได้** | เพิ่ม **Python ML Service** (FastAPI) แก้ปัญหา ONNX/CatBoost ได้ทั้งหมด และคำนวณ SHAP สดได้ (หัวข้อ 6.7) |
| Embedding model | **ไม่ใช้** | จับคู่ชื่อสินค้าด้วย dictionary + `pg_trgm` + Gemini batch + cache (หัวข้อ 5.7) |

### 0.2 เรื่องที่ยังต้องแก้ก่อนเริ่มเขียนโค้ด

| # | เรื่อง | ทำไมสำคัญ |
|---|---|---|
| 1 | **ช่องโหว่ Supabase:** ตาราง `dim_*`/`fact_*`/`stg_*`/`ml_*` อยู่ใน `public` และไม่เปิด RLS ทำให้ใครที่มี anon key ก็ **เขียนหรือลบข้อมูลผ่าน REST API ได้** | ต้องแยก schema ตั้งแต่ migration แรก (หัวข้อ 6.1) |
| 2 | **ความเสถียรของ scraper:** โดน block, หน้าเว็บเปลี่ยนโครงสร้าง, job ยาวเกินลิมิต 6 ชั่วโมงของ GitHub-hosted runner | ต้องออกแบบให้ resume ได้, incremental และหยุดเมื่อโดน block (หัวข้อ 5.2) |
| 3 | **Quota ของ LLM:** รีวิวหลักแสนรายการ ใช้ Gemini free tier ติด label ทั้งหมดไม่ทัน | ใช้แนวทาง teacher–student หรือ paid tier (หัวข้อ 5.6) |
| 4 | **ข้อมูลราคาไม่หนาแน่นเท่ากันทุกอุตสาหกรรม:** F&B มีเมนูบนแอปเดลิเวอรี แต่ร้านตัดผม อู่ หรือร้านเสื้อผ้าแทบไม่มีราคาออนไลน์ | ทุกอุตสาหกรรมต้องใช้ "ชั้นข้อมูลร่วม" ได้ครบ ส่วนโมดูลราคาเปิดตามความพร้อมของข้อมูล (หัวข้อ 4.0) |

### 0.3 การเปลี่ยนแปลงหลักที่เสนอ
1. **Industry Pack:** อุตสาหกรรมทั้งหมดถูกนิยามในตาราง config (หมวด, หน่วยราคา, aspect, แกน radar, คำค้นสำหรับ scrape, เกณฑ์เปิด ML)
2. **Scraping pipeline 6 ขั้น:** discovery แบบ grid → detail → reviews (incremental) → เมนู/ราคา → entity resolution → staging พร้อม governance
3. แยก schema `staging / dw / mart / app / ml / ops` และใช้ RLS ทุกตารางที่ API มองเห็น
4. แยก `fact_customer_reviews` เป็น `fact_review` กับ `fact_review_aspect` เพื่อแก้การนับซ้ำ (fan-trap)
5. ใส่ conformed keys (`geo_key`, `category_key`, `brand_key`) ลงในทุก fact ให้เป็น Galaxy Schema จริง
6. เพิ่ม `dim_data_source`, `fact_fx_daily`, `fact_weather_daily`, `fact_tourism_monthly`, ตาราง mapping และชั้น `mart.*`
7. เพิ่ม dbt-core เป็นชั้น transform พร้อม test และ lineage docs
8. **Python ML Service:** โมเดลทุกตัว (รวม CatBoost) เสิร์ฟตรงจาก Python, SHAP รายรายการ, student model สำหรับ sentiment
9. ML: GroupKFold ตามแบรนด์ + baseline + โมเดลแยกตาม sector (benchmark 6 โมเดลบน F&B และ Hospitality)
10. What-If แบบซื่อตรง: กำไรคำนวณแบบ deterministic, ML ให้ช่วงราคายุติธรรม, demand เป็นสมมติฐานที่ผู้ใช้เลือก
11. Copilot แบบ Hybrid: ใช้ intent template ก่อน ถ้าไม่ตรงค่อยให้ LLM เขียน SQL ตรวจด้วย AST และรันใน `READ ONLY` transaction
12. บริบทชายแดนใต้: ละหมาดวันศุกร์, รอมฎอน/ฮารีรายอ, ตราฮาลาลรับรอง, มลายูที่เขียนด้วยอักษรไทยหรือยาวี, ด่านชายแดน, วันหยุดศุกร์–เสาร์ของกลันตัน/เคดาห์

---

## 1. จุดแข็งที่ควรเก็บไว้

- **โจทย์ชัดและเป็นท้องถิ่นจริง:** ชายแดนใต้มีตัวแปรที่ระบบ BI ทั่วไปไม่มี (ฮาลาล, ลูกค้ามาเลเซีย, ละหมาดวันศุกร์, รอมฎอน, มรสุม)
- **แยก public market data กับต้นทุนส่วนตัว (COGS/GP)** ออกจากกันชัดเจนด้วย RLS ถูกหลักทั้ง multi-tenant และ privacy
- **"No LLM arithmetic":** ตัวเลขมาจาก SQL หรือโมเดลเท่านั้น และมี Data Lineage badge เป็นจุดแข็งที่ใช้ตอบกรรมการได้ดีมาก
- **Dual matching mode (standardized item กับ attribute band)** รองรับการขยายเป็นทุกอุตสาหกรรมได้อยู่แล้ว
- **ML Inspector Lab** เปิดให้กรรมการเห็นผลทุกโมเดล ไม่ใช่โชว์เฉพาะโมเดลที่ชนะ
- **Stack ฟรีทั้งหมด** และคิดเรื่อง Supabase pause กับ cold start ไว้แล้ว

---

## 2. ปัญหาที่พบในสเปกเดิม (เรียงตามความรุนแรง)

ระดับ: 🔴 Critical = ต้องแก้ก่อนเริ่ม · 🟠 High = ต้องแก้ก่อนเฟสที่เกี่ยวข้อง · 🟡 Medium = แก้ระหว่างทาง · ⚪ Low = ปรับปรุง · ✅ = แก้แล้วจากการตัดสินใจรอบ 2

| ID | ระดับ | ปัญหา | อยู่ที่ | แนวทางแก้ |
|---|---|---|---|---|
| C1 | 🟠 | Scraping: อาจารย์อนุมัติแล้ว แต่ยังต้องมี governance (rate, PII, opt-out) และ pipeline ที่ทนต่อการโดน block หรือหน้าเว็บเปลี่ยน | ARCH 1.1, 1.2 | หัวข้อ 5.2–5.3 |
| C2 | 🔴 | ตาราง warehouse/staging/ml อยู่ใน `public` และไม่มี RLS ทำให้ anon ทำ `INSERT/UPDATE/DELETE` ผ่าน PostgREST ได้ (Supabase grant สิทธิ์ให้ `anon`/`authenticated` ใน `public` เป็นค่าเริ่มต้น) | ARCH 2.3–2.4 | แยก schema และไม่ expose `dw/staging/ml/ops` (6.1) |
| C3 | 🟠 | ครบทุกอุตสาหกรรมตั้งแต่แรก: ถ้าเขียนโค้ดแยกต่ออุตสาหกรรมจะทำไม่ทัน และข้อมูลราคาบางอุตสาหกรรมบางมาก | CONTEXT 3, 6 | Industry Pack + data-readiness gating (4.0) |
| H1 | 🟠 | What-If "driven by champion ML model" แต่โมเดลทำนาย **ราคา** ไม่ได้ทำนาย **ยอดขาย** ระบบไม่มีข้อมูลยอดขายจึงประมาณ demand/elasticity ไม่ได้ | CONTEXT 6, ARCH 4 | แยกเป็น 3 ชั้น (7.5) |
| H2 | 🟠 | `fact_customer_reviews` มี grain = review × aspect แต่เก็บ `star_rating` และ `clean_review_text` ซ้ำทุก aspect ทำให้ `COUNT(*)`/`AVG(star_rating)` ผิด (fan-trap ภายใน fact) | ARCH 2.3 | แยก `fact_review` กับ `fact_review_aspect` (6.3) |
| H3 | 🟠 | Copilot ถูก revoke จากตาราง `app_*` ทั้งหมด จึงตอบคำถามสำคัญที่สุดอย่าง "margin **ของฉัน** เทียบตลาด" ไม่ได้ อีกทั้งรูปแบบ "restricted function + SET LOCAL" มีกับดัก (`SET ROLE` ใช้ใน SECURITY DEFINER ไม่ได้, `statement_timeout` ที่ตั้งในฟังก์ชันไม่มีผลกับ statement ที่กำลังรัน) | ARCH 5 | ใช้ login role เฉพาะ + `BEGIN READ ONLY` + inject CTE `my_skus` (8) |
| H4 | 🟠 | Gemini free tier: Google อาจนำ prompt ไปใช้พัฒนาผลิตภัณฑ์ ถ้าส่ง COGS/GP ส่วนตัวเข้าไปจะขัดกับคำสัญญาเรื่อง Cost Confidentiality และ quota รายวันไม่พอสำหรับรีวิวหลักแสน | ARCH 1.1, CONTEXT 7 | ส่งเฉพาะข้อมูล public, consent toggle, teacher–student (5.6, 9) |
| H5 | ✅ | `onnxruntime-node` ใหญ่เกินสำหรับ Vercel และ CatBoost export ONNX ไม่รองรับ categorical feature | ARCH 4.2 | **แก้แล้ว:** เสิร์ฟจาก Python ML Service (6.7, 7.6) |
| H6 | 🟠 | ML leakage: (ก) `price_positioning` ได้มาจากราคาเอง (ข) สาขาของ chain มีราคาเท่ากัน ถ้า group ตาม `outlet_key` จะรั่วข้าม fold (ค) "Stratified" ใช้กับ regression ไม่ได้ตรงๆ | ARCH 4.1 | GroupKFold ตาม `brand_key` และตัด feature ที่รั่ว (7.3) |
| N1 | 🟠 | ร้านเดียวกันอยู่ในหลายแหล่ง (Google Maps, Grab, LINE MAN) ชื่อสะกดต่างกัน ต้องเชื่อมให้เป็น outlet เดียว (entity resolution) ไม่มีในสเปกเดิม | — | 5.2 ขั้น [5] |
| N2 | 🟡 | ภาษามลายูปาตานีมักเขียนด้วย **อักษรไทย** หรือ **ยาวี** ทำให้ตัวตรวจภาษาทั่วไปคิดว่าเป็นภาษาไทย | CONTEXT 2.2 | ให้ LLM ระบุทั้ง `language` และ `script` (4.1) |
| N3 | 🟡 | ความหนาแน่นร้านและรีวิวในยะลา/ปัตตานี/นราธิวาสต่ำกว่าหาดใหญ่มาก รัศมี 1–5 กม. ในอำเภอเล็กอาจมีคู่แข่ง 0–2 ร้าน | CONTEXT 3.2 | เพิ่มรัศมี 10 กม. + เทียบระดับอำเภอ + กติกากลุ่มเล็ก |
| M1 | 🟡 | สูตร Popularity Index มีปัญหา operator precedence: `× (S/5)` คูณเฉพาะเทอมหลัง ไม่ได้คูณทั้งก้อน, ใช้ค่าเฉลี่ยดาวดิบ (ร้าน 2 รีวิว 5 ดาวชนะ), และ "top 5%" ในกลุ่ม < 20 ร้านจะได้ 0 ร้าน | ARCH 3.2 | วงเล็บ + Bayesian rating + กติกากลุ่มเล็ก (4.2) |
| M2 | 🟡 | Fact อ้างแค่ `outlet_key` ส่วน geo/category/brand อยู่ใน outlet จึงเป็น **snowflake** ไม่ใช่ galaxy ที่มี conformed dimension ตรงๆ | ARCH 2.3 | ใส่ conformed keys ลง fact (6.3) |
| M3 | 🟡 | `dim_brand.market_tier` มี `local_leader` ซึ่งเป็นสถานะแบบ dynamic รายเดือน และ `cross_border` ขึ้นกับว่า **ผู้ใช้** อยู่ประเทศไหน | ARCH 2.3 | แยก `brand_scale` (คงที่) ออกจาก tier ที่คำนวณตอน query |
| M4 | 🟡 | `fact_product_pricing.std_item_key NOT NULL` แต่ Mode B (แฟชั่น) ไม่มี standard item | ARCH 2.3 | ให้ NULL ได้ + `price_band_tier` + CHECK |
| M5 | 🟡 | ไม่มีตารางอัตราแลกเปลี่ยนรายวัน, ไม่มีตารางสภาพอากาศ, และ `dim_date` ขาดรอมฎอน ฮารีรายอ ตรุษจีน วันหยุดโรงเรียนมาเลเซีย | ARCH 2.3 | 6.2 |
| M6 | 🟡 | ยังไม่ normalize หน่วย (16 oz กับ 22 oz) และไม่แยกช่องทาง (ราคาบนแอปเดลิเวอรีมัก markup จากหน้าร้าน) ถ้าปนกัน peer price จะเพี้ยน | ARCH 2.3 | `unit_qty`, `unit_measure`, `channel` |
| M7 | 🟡 | ค่า "monthly velocity" ต้องมี snapshot ย้อนหลัง แต่เพิ่งเริ่มเก็บ | ARCH 3.2 | Backfill จากวันที่ของรีวิวที่ scrape มา (ได้ย้อนหลังหลายปี) |
| M8 | 🟡 | GitHub ปิด scheduled workflow อัตโนมัติถ้า repo ไม่มี activity 60 วัน ทำให้ keep-alive ตายเงียบ | ARCH 1.1 | ใช้ uptime monitor ภายนอก (UptimeRobot/cron-job.org) ping แทน |
| M9 | 🟡 | ยังไม่ได้นิยาม: 5 แกนของ radar, 4 KPI, เกณฑ์แบ่ง quadrant, และ task `review_priority_classification` | CONTEXT 5–6, ARCH 2.4 | นิยามใน 4.2 และเปลี่ยน task ที่สองเป็น sentiment student model (7.7) |
| M10 | 🟡 | Palette ใน ARCH 6.1 ไม่ตรงกับภาพ design และ `tabular-nums` บน KPI ขนาดใหญ่ทำให้ตัวเลขดูห่าง | ARCH 6.1 | ดู DESIGN_SYSTEM.md |
| L1 | ⚪ | "Next.js 14+" กับ `gemini-2.5-flash` ถูก hardcode แต่รุ่นเปลี่ยนเร็ว | ARCH 1.1 | ใช้ Next.js stable ล่าสุด, ตั้ง `GEMINI_MODEL` ผ่าน env, ทำ LLM provider abstraction |
| L2 | ⚪ | มี role `admin` แต่ใน repo tree ไม่มีหน้า admin (scraper monitor, mapping review queue) | ARCH 6.2 | เพิ่ม `/admin/*` |
| L3 | ⚪ | Demo guest ใช้บัญชีเดียวกัน กรรมการหลายคนแก้ข้อมูลทับกัน | CONTEXT 4.1 | Anonymous sign-in + clone tenant |
| L4 | ⚪ | ถ้าวางแผนแจ้งเตือนผ่าน LINE Notify: บริการนี้ปิดไปแล้วตั้งแต่ 31 มี.ค. 2025 | — | ใช้ LINE Messaging API (OA) |

**H1: What-If ที่ซื่อตรงต่อข้อมูล** ระบบรู้ราคาและต้นทุน แต่ไม่รู้ว่าถ้าขึ้นราคา 5 บาทแล้วยอดขายจะลดเท่าไร ถ้าพูดว่า "โมเดลทำนายกำไรหลังปรับราคา" กรรมการจะถามว่า "เทรนจากยอดขายอะไร" จึงต้องแยกเป็น 3 ชั้นตามหัวข้อ 7.5

---

## 3. ความเป็นไปได้ราย module

| Module | ความยากเทคนิค | ความเสี่ยงด้านข้อมูล | ภาระงาน (คน-สัปดาห์) | ข้อสรุป |
|---|---|---|---|---|
| Auth + Onboarding 3 ขั้น + Demo login | ต่ำ | ต่ำ | 1.5 | ✅ |
| Industry Pack (taxonomy + std items + aspects ทุกอุตสาหกรรม) | ต่ำ–กลาง | ต่ำ | 1.5 | ✅ ใช้ Gemini ช่วยร่าง แล้วตรวจเอง |
| Scraper Google Maps (discovery/detail/reviews) 4 จังหวัด | **สูง** | กลาง (block/หน้าเว็บเปลี่ยน) | 3 | ✅ งานหนักที่สุดของเฟสแรก |
| Scraper เมนู/ราคา (Grab, LINE MAN, ราคาห้องพัก) | สูง | กลาง | 2 | ✅ F&B + Hospitality |
| Scraper ราคาบริการ/ค้าปลีก (Shopee/FB/รูปป้ายราคา) | สูง | **สูง** | 2+ | ⚠️ Could: ใช้ข้อมูลที่เจ้าของร้านกรอก + Vision แทน |
| Entity resolution ข้ามแหล่ง | กลาง | กลาง | 1 | ✅ |
| Data Warehouse (Galaxy) + dbt + DQ tests | กลาง | กลาง | 3 | ✅ แกนหลัก |
| ETL: FX/อากาศ/วันหยุด/ท่องเที่ยว | ต่ำ | ต่ำ | 1 | ✅ |
| จับคู่ canonical item (ไม่ใช้ embedding) | กลาง | กลาง | 1.5 | ✅ |
| Store Economics + 4-Quadrant + Break-even | ต่ำ | ต่ำ | 1.5 | ✅ deterministic |
| Geospatial Radar (MapLibre + PostGIS) | กลาง | ต่ำ | 2 | ✅ |
| Location Opportunity Score (Huff) | กลาง | กลาง | 1.5 | ⭐ Should |
| Aspect sentiment หลายภาษา (teacher–student) | กลาง | ต่ำ (มีรีวิวจาก scrape) | 2 | ✅ |
| Python ML Service (FastAPI) | กลาง | ต่ำ | 1 | ✅ |
| ML 6 โมเดล + baseline + SHAP | กลาง | ต่ำ–กลาง | 2.5 | ✅ |
| Copilot Text-to-SQL + guardrail + ชุดทดสอบ | สูง | ต่ำ | 3 | ✅ |
| เทียบข้ามแดน (กลันตัน/เคดาห์/ปีนัง) | กลาง | กลาง | 1.5 | ⭐ Should (scrape แบบเดียวกัน) |
| Weekly Pulse ผ่าน LINE OA | ต่ำ | ต่ำ | 1 | ⭐ Should |

**สรุปภาระงาน:** ถ้าทำครบ Must + Should ประมาณ 35–40 คน-สัปดาห์ ทีม 2–3 คนใช้เวลาประมาณ 16–20 สัปดาห์ ถ้าทำคนเดียวต้องตัด Should เกือบทั้งหมด (คำถาม Q1 ในหัวข้อ 15)

---

## 4. ข้อเสนอปรับและเพิ่มแนวคิด

### 4.0 Industry Pack: ครบทุกธุรกิจตั้งแต่เริ่ม โดยไม่ต้องเขียนโค้ดแยก

**หลักคิด:** แยกระบบเป็น 2 ชั้น
- **ชั้นข้อมูลร่วม (Universal Layer)** ได้จาก Google Maps ครบทุกอุตสาหกรรม: ตำแหน่ง, หมวด, เรตติ้ง, จำนวนรีวิว, เนื้อหารีวิว, เวลาเปิด, attributes ทำให้ **Overview, Radar, Reviews, Copilot ใช้ได้กับทุกธุรกิจตั้งแต่วันแรก**
- **ชั้นราคา (Pricing Layer)** ความลึกต่างกันตามอุตสาหกรรม ระบบแสดงระดับความพร้อมให้ผู้ใช้เห็นตรงๆ

| Sector | ตัวอย่าง sub-category | หน่วยราคา | Mode | แหล่งราคา | ความหนาแน่นราคา | ML ราคา |
|---|---|---|---|---|---|---|
| **F&B** | คาเฟ่, ร้านน้ำชา/โรตี, อาหารตามสั่ง/ข้าวแกง, ข้าวยำ/นาซิดาแฆ, ก๋วยเตี๋ยว, ติ่มซำ, ไก่ทอด, ซีฟู้ด, เบเกอรี่/ของหวาน | แก้ว / จาน / ชิ้น | A | Grab, LINE MAN, รูปเมนูบน Google Maps (Vision) | สูง | ✅ benchmark 6 โมเดล |
| **Hospitality** | โรงแรม, รีสอร์ต, โฮมสเตย์/เกสต์เฮาส์ | คืน (ห้องมาตรฐาน 2 คน) | A | ราคาที่แสดงบน Google Maps / OTA | กลาง | ✅ benchmark 6 โมเดล |
| **Personal Services** | ร้านตัดผมชาย, ซาลอน, สปา/นวด, ทำเล็บ, ร้านซักรีด | ครั้ง / กก. | A | เจ้าของร้านกรอก, รูปป้ายราคา (Vision), บางร้านมีบน Google Maps | ต่ำ | ⏳ เปิดเมื่อข้อมูล ≥ เกณฑ์ |
| **Auto Services** | อู่ซ่อมรถยนต์/มอเตอร์ไซค์, คาร์แคร์ | ครั้ง | A | เจ้าของร้านกรอก, รูปป้ายราคา | ต่ำ | ⏳ |
| **Retail & Fashion** | เสื้อผ้า/มุสลิมะห์/ฮิญาบ, ของฝาก/OTOP, มินิมาร์ท, ร้านมือถือ | ชิ้น (price band) | B | เจ้าของร้านกรอก, (Could) Shopee/Lazada ของร้านในพื้นที่ | ต่ำ–กลาง | ⏳ |

**Config ที่ทำให้เพิ่มอุตสาหกรรมได้โดยไม่แก้โค้ด** (ขยาย `dim_category`):
```sql
CREATE TABLE dw.dim_category (
  category_key SERIAL PRIMARY KEY,
  industry_sector TEXT NOT NULL,          -- 'F&B','Hospitality','Personal Services','Auto Services','Retail & Fashion'
  sub_category TEXT NOT NULL,             -- 'Cafe','Roti & Tea Shop','Barbershop', ...
  sub_category_th TEXT NOT NULL,          -- 'คาเฟ่','ร้านน้ำชา/โรตี','ร้านตัดผมชาย', ...
  service_model TEXT NOT NULL,            -- 'dine_in','grab_and_go','appointment_service','retail_floor','nightly_stay'
  matching_mode TEXT NOT NULL CHECK (matching_mode IN ('standardized_item','attribute_band')),
  price_unit TEXT NOT NULL,               -- 'cup','dish','session','night','piece'
  price_unit_th TEXT NOT NULL,            -- 'แก้ว','จาน','ครั้ง','คืน','ชิ้น'
  source_place_types TEXT[] NOT NULL,     -- หมวดของ Google Maps ที่ map เข้าหมวดนี้
  search_keywords TEXT[] NOT NULL,        -- คำค้นที่ scraper ใช้ (ไทย/มลายู/อังกฤษ)
  radar_axes JSONB NOT NULL,              -- ป้ายชื่อ 5 แกนตามอุตสาหกรรม
  default_aspects JSONB NOT NULL,         -- aspect ที่ใช้ติด label รีวิว
  min_rows_for_ml INT NOT NULL DEFAULT 500,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE (industry_sector, sub_category, service_model)
);
```
UI อ่านป้ายทั้งหมดจาก config เช่น ชื่อแกน radar, ชื่อ aspect, หน่วย ("฿/แก้ว", "฿/ครั้ง", "฿/คืน") **ทุกการ์ดด้านราคาแสดงป้าย readiness:** "ข้อมูลพร้อม (n = 84 ร้าน)" / "ข้อมูลน้อย ใช้สถิติ peer แทน ML" / "ยังไม่มีข้อมูลราคา ให้เพิ่ม SKU ของคุณเพื่อเริ่มเทียบ"

### 4.1 บริบทชายแดนใต้ (สงขลา ยะลา ปัตตานี นราธิวาส)

| ปัจจัย | รายละเอียด | เก็บที่ไหน |
|---|---|---|
| **มรสุมตะวันออกเฉียงเหนือ** | สงขลา ปัตตานี นราธิวาสอยู่ฝั่งอ่าวไทยทั้งหมด ส่วนยะลาไม่ติดทะเล (inland) แต่ฝนหนักช่วงเดียวกัน (ราว พ.ย.–ม.ค.) มีน้ำท่วมซ้ำในบางพื้นที่ เช่น หาดใหญ่ (2543, 2553) และลุ่มน้ำโก-ลก แนวคิด "สองฝั่งมรสุม" เดิมเปลี่ยนเป็น "ฤดูมรสุมเทียบนอกฤดู" + ปริมาณฝนจริงรายวัน | `fact_weather_daily`, `coast_type` (`gulf` / `inland`) |
| **ฮาลาลเป็นค่าปกติ** | ในยะลา ปัตตานี นราธิวาส ร้านส่วนใหญ่ฮาลาลอยู่แล้ว จุดแยกความแตกต่างจึงเป็น **"มีตราฮาลาลรับรอง"** (สำนักงานคณะกรรมการอิสลามประจำจังหวัด) เทียบกับประกาศเอง ส่วนร้านที่ไม่ฮาลาล (เช่น ร้านจีนในเบตง/หาดใหญ่) เป็น niche ของตัวเอง | `dynamic_attributes`: `halal_certified`, `halal_self_declared`, `non_halal` |
| **ละหมาดวันศุกร์** | หลายร้านปิดช่วงเที่ยงวันศุกร์ เวลาเปิดจึงต้องรองรับ **หลายช่วงต่อวัน** | `operating_hours` เป็น JSONB รายวัน เช่น `{"fri": [["07:00","12:00"],["14:00","20:00"]]}` |
| **รอมฎอน / ฮารีรายอ** | ช่วงรอมฎอนร้านอาหารกลางวันเงียบหรือปิด แต่ช่วงค่ำพีกและมีตลาดรอมฎอน ส่วนช่วงฮารีรายอคนกลับบ้านและคนมาเลเซียข้ามแดนมาก | `dim_date.is_ramadan`, `is_hari_raya_aidilfitri`, `is_hari_raya_haji` |
| **ภาษาในรีวิว** | ไทย, มลายูมาตรฐาน (มาเลเซีย), **มลายูปาตานีที่เขียนด้วยอักษรไทยหรือยาวี (อักษรอาหรับ)**, อังกฤษ, จีน (เบตง/หาดใหญ่ และนักท่องเที่ยวจีนมาเลเซีย) | `fact_review.reviewer_language` + `script` (`thai`/`latin`/`jawi`/`han`) |
| **ด่านชายแดน** | สะเดา/ปาดังเบซาร์ (เคดาห์/เปอร์ลิส), เบตง (เประ), สุไหงโก-ลก/ตากใบ (กลันตัน) เป็นทางเข้าของลูกค้ามาเลเซีย | `area_character = 'border_town'`, feature `distance_to_border_km` |
| **วันหยุดสุดสัปดาห์รายรัฐ** | กลันตัน (และเคดาห์ตามประกาศล่าสุด) หยุดศุกร์–เสาร์ ทำให้คนจากรัฐเหล่านี้ข้ามมาวันศุกร์ ส่วนเประ ปีนัง เปอร์ลิสหยุดเสาร์–อาทิตย์ (ตรวจประกาศล่าสุดก่อนใช้) | `dim_date.is_weekend_my_fri_sat_states` |
| **คู่แข่งข้ามแดน** | Kota Bharu, Rantau Panjang (กลันตัน), Alor Setar, Changlun (เคดาห์), Pengkalan Hulu (เประ), George Town (ปีนัง ใช้เทียบหาดใหญ่) | tier `cross_border` |
| **ย่านมหาวิทยาลัย** | ม.อ. หาดใหญ่, ม.อ. ปัตตานี, มรภ.ยะลา, ม.นราธิวาสราชนครินทร์: คาเฟ่และร้านอาหารราคานักศึกษากระจุกตัว | `area_character = 'university_area'` |
| **แหล่งท่องเที่ยว** | หาดใหญ่ (ศูนย์กลางการค้า), เบตง (นักท่องเที่ยวไทยและมาเลเซีย), สงขลาเมืองเก่า, มัสยิดกลางปัตตานี | feature ความหนาแน่น POI ท่องเที่ยว |
| **เวลาเปิดช่วงกลางคืน** | จำนวนร้านที่เปิดดึกต่างกันมากระหว่างอำเภอ ทั้งจากพฤติกรรมผู้บริโภคและสถานการณ์ในพื้นที่ ทำให้ Operating-Hour Gap Detector มีค่ามาก | `mart.hourly_coverage` |
| **ความหนาแน่นข้อมูล** | อำเภอเล็กมีร้านและรีวิวน้อย | รัศมี 1/3/5/**10** กม. + เทียบระดับอำเภอ + กติกากลุ่มเล็ก |
| **เมนูท้องถิ่น (canonical items)** | ข้าวยำ/นาซิกราบู, นาซิดาแฆ, โรตี/มะตะบะ, ชาชัก, กาแฟโบราณ (โกปี๊), ไก่กอและ, ซาเต๊ะ, ไก่ทอดหาดใหญ่, ติ่มซำ, ไก่เบตง, ข้าวมันไก่ | seed `dim_standard_item` |
| **GP + VAT** | แพลตฟอร์มเดลิเวอรีคิด VAT 7% บนค่า GP ทำให้ GP 30% จริงๆ คือ ~32.1% | `effective_gp = gp × 1.07` (toggle ได้) |
| **ร้านร่วมจ่ายโปรโมชัน** | โปรส่วนลดที่ร้านร่วมจ่ายบนแอปกิน margin โดยไม่รู้ตัว | `channel_promo_cofund_pct` ใน SKU |
| **PPP เทียบข้ามประเทศ** | ราคาที่แปลงตาม FX แล้ว "แพงกว่า" ไม่ได้แปลว่าคนฝั่งนั้นรู้สึกแพง | แสดงทั้งราคาตาม FX และตาม PPP (World Bank) |
| **สถิติท่องเที่ยวรายจังหวัด** | proxy ของ demand (กระทรวงการท่องเที่ยวฯ, data.go.th) | `fact_tourism_monthly` |

### 4.2 นิยาม Business Logic ที่ยังขาด (ต้องเขียนลง CONTEXT v2)

**(ก) Popularity Index (แก้สูตร)**
```text
S_bayes   = (C × m + n × S̄) / (C + n)          # m = ค่าเฉลี่ยดาวของหมวดในจังหวัด, C = 20 (prior strength)
PI        = [0.60 × ln(1 + N_cum) + 0.40 × ln(1 + N_new_30d)] × (S_bayes / 5)
Leader    = ร้าน independent ที่ percentile_rank(PI) ≥ 0.95 ในกลุ่ม (จังหวัด × หมวด) และ N_cum ≥ 30
กลุ่มเล็ก  = ถ้ากลุ่มมี < 20 ร้าน ให้ top-1 (เมื่อกลุ่มมี ≥ 5 ร้าน), ถ้า < 5 ร้าน ไม่มี leader
```
N_new_30d คำนวณจากวันที่ของรีวิวที่ scrape มา ทำให้ backfill ย้อนหลังได้ทันที (แก้ M7) ส่วนน้ำหนัก 0.6/0.4 ให้ทดลองเทียบ 0.5/0.5 และ 0.7/0.3 แล้วรายงานว่าอันดับเปลี่ยนมากน้อยแค่ไหน

**(ข) 4 KPI Cards (ทุกใบต้องมี "ทำอะไรต่อ")**
| KPI | สูตร | ตัวอย่าง next action |
|---|---|---|
| Market Health Score (0–100) | ค่าเฉลี่ยถ่วงน้ำหนักของ 5 แกน (percentile เทียบ peer) | "ตามหลังผู้นำด้านความเร็วคิว 18 คะแนน ดูรีวิวที่เกี่ยวข้อง" |
| Price Position Index | median ของ Price Gap% เฉพาะ hero items เทียบ **median** ของ peer (แสดง n) | "ชาชักของคุณถูกกว่าตลาด 12% (n = 14) ขึ้นได้ 5 บาท" |
| Net Margin after GP (portfolio) | Σ(qty × CM) / Σ(qty × P) แยก walk-in กับ delivery | "มี 3 SKU เป็น Margin Bleeders บนแอป" |
| Sentiment Gap vs Leader | ส่วนต่าง sentiment ของ aspect ที่แย่ที่สุดเทียบ leader | "ลูกค้ามาเลเซียบ่นเรื่องไม่รับ DuitNow 9 ครั้งใน 90 วัน" |

ถ้าอุตสาหกรรมนั้นยังไม่มีข้อมูลราคา KPI ที่ 2–3 จะเปลี่ยนเป็น "เพิ่ม SKU เพื่อเปิดการเทียบราคา" แทน

**(ค) 5 แกน Capability Radar** (percentile 0–100 เทียบ peer, ชื่อแกนมาจาก `dim_category.radar_axes`)
1. **คุณภาพสินค้า/บริการ:** sentiment ของ aspect หลัก (รสชาติ / ฝีมือช่าง / ความสะอาดห้อง / คุณภาพผ้า)
2. **ความคุ้มค่า:** sentiment ด้าน `price_value` + ตำแหน่งราคาเทียบช่วงราคายุติธรรม (ถ้ามี)
3. **โมเมนตัมความนิยม:** percentile ของ Popularity Index
4. **ความสะดวกเข้าถึง:** คะแนนจาก JSONB (ชั่วโมงเปิด, ที่จอดรถ, QR/DuitNow, เดลิเวอรี, ตราฮาลาล)
5. **ประสบการณ์บริการ:** sentiment ด้าน `service`, `queue_speed`, `ambience`

**(ง) 4-Quadrant: มี 2 มุมมอง**
- **Market Lens:** X = Price Gap% เทียบ median ของ peer (เส้นแบ่งที่ 0 มีแถบ ±5% เป็นโซน "เท่าตลาด"), Y = Net Margin% (เส้นแบ่ง = target margin ที่ผู้ใช้ตั้ง)
  - ถูกกว่าตลาด + margin สูง → 💎 **Hidden Margin Gems** (ขึ้นราคาได้)
  - แพงกว่าตลาด + margin สูง → ⭐ **Hero Stars** (premium ที่ขายได้ ต้องเฝ้า sentiment ด้านความคุ้มค่า)
  - ถูกกว่าตลาด + margin ต่ำ → 🧲 **Traffic Pullers** (ตัวดึงลูกค้า ต้องถามตัวเองว่าตั้งใจหรือไม่)
  - แพงกว่าตลาด + margin ต่ำ → 🩸 **Margin Bleeders** (ต้นทุนมีปัญหา แก้ด่วน)
- **Internal Lens:** Menu Engineering ของ Kasavana & Smith (1982) X = สัดส่วนยอดขาย (เกณฑ์ 70% ของ 1/n), Y = Contribution Margin เทียบค่าเฉลี่ยถ่วงน้ำหนัก ได้ Stars / Plowhorses / Puzzles / Dogs ใช้ได้แม้อุตสาหกรรมนั้นยังไม่มีราคาตลาด เพราะใช้แค่ข้อมูลของร้านเอง

**(จ) สูตรเศรษฐศาสตร์ร้านค้า**
```text
CM_walkin        = P_walkin − C_cogs − C_pack_takeaway(ถ้ามี)
CM_delivery      = P_delivery × (1 − GP_eff/100) − C_cogs − C_pack − Promo_cofund
GP_eff           = GP × 1.07                         (ถ้าแพลตฟอร์มคิด VAT บน GP)
Price Gap%       = (P_my − median(P_peer)) / median(P_peer) × 100   # ใช้ median และราคาต่อหน่วยมาตรฐาน
Break-even/เดือน = Fixed_cost / Σ(share_i × CM_i)     # หน่วยต่อเดือน → ÷ วันเปิดร้าน = หน่วยต่อวัน
```
**กติกาความซื่อตรง:** ทุกตัวเลขเชิงเปรียบเทียบต้องแสดง **n** (จำนวนร้านที่ใช้เทียบ) ถ้า n < 3 ให้ซ่อนค่าและแสดง "ข้อมูลไม่พอ" แทน

### 4.3 ฟีเจอร์ใหม่ที่แนะนำ (เรียงตามความคุ้มค่า)

1. ⭐ **Location Opportunity Score สำหรับ New Investor** ใช้ Huff Gravity Model (Huff, 1963):
   `P_ij = (A_j^α / D_ij^β) / Σ_k (A_k^α / D_ik^β)` คำนวณบน hex grid รอบหมุด (`ST_HexagonGrid` ของ PostGIS) โดย demand proxy มาจากความหนาแน่นของ POI (โรงเรียน มหาวิทยาลัย สำนักงาน ที่พัก แหล่งท่องเที่ยว ด่านชายแดน) ได้ "ส่วนแบ่งตลาดที่คาดว่าจะได้" ที่อธิบายได้
2. ⭐ **เทียบหลายทำเล (Multi-pin Compare):** investor ปักได้ 2–4 หมุดแล้วเทียบ score cards ข้างกัน (ตารางใหม่ `app_candidate_locations`)
3. ⭐ **Proactive Insight Engine ที่ใช้ rule เป็นหลัก:** SQL rules สร้างข้อสังเกต เช่น "มีคู่แข่งใหม่ใน 1 กม. ภายใน 30 วัน", "sentiment ด้านคิวลด > 0.2 เทียบ 90 วันก่อน (n ≥ 10)", "อีก 14 วันเข้ารอมฎอน ปีที่แล้วรีวิวช่วงค่ำเพิ่ม 40%" แล้วให้ LLM **เรียบเรียงภาษาเท่านั้น** จากตัวเลขที่ได้ พร้อม lineage SQL
4. **Weekly Pulse ผ่าน LINE OA** (Messaging API): เจ้าของร้านไทยอยู่บน LINE เป็นหลัก ส่งสรุปสัปดาห์ละ 1 ข้อความ (ระวัง quota ฟรีของ OA)
5. **Saved Scenarios:** บันทึกผล What-If แล้วติดตามผลหลังเปลี่ยนราคาจริง (`app_scenarios`, `app_sku_price_history`)
6. **Data Coverage Map:** แสดงพื้นที่และอุตสาหกรรมที่มีข้อมูลพอ
7. **Thai-first i18n:** UI ภาษาไทยเป็นค่าเริ่มต้น สลับ EN ได้ (และ Malay ได้ในอนาคต) ด้วย `next-intl`
8. **Mobile-first / PWA:** ภาพ design เป็น card แนวตั้งซึ่งเหมาะกับมือถือ และเจ้าของร้านเปิดดูจากมือถือเป็นหลัก

### 4.4 หลักการ UX
- **ทุกหน้าจอตอบคำถามเดียวให้ชัด** เช่น Overview = "ร้านฉันอยู่ตรงไหน และควรทำอะไรสัปดาห์นี้"
- **Progressive disclosure:** หน้าแรกแสดงคำแนะนำ ตัวเลขละเอียดอยู่ในลิ้นชักหรือแท็บ
- **Freshness + Provenance badge ทุกการ์ด:** "อัปเดต 3 วันก่อน · แหล่ง: Google Maps + LINE MAN · n = 14"
- **Empty/low-data states** ออกแบบตั้งแต่แรก โดยเฉพาะอุตสาหกรรมที่ข้อมูลราคาบาง

---

## 5. กลยุทธ์ข้อมูล v2 (Scraping-first)

### 5.1 แหล่งข้อมูล

| ชั้นข้อมูล | แหล่ง | วิธี | ความถี่ |
|---|---|---|---|
| ร้านค้า, เรตติ้ง, จำนวนรีวิว, เวลาเปิด, attributes (ทุกอุตสาหกรรม) | **Google Maps** | Playwright scraper | discovery รายเดือน, detail รายสัปดาห์ |
| เนื้อหารีวิว | **Google Maps** | Playwright, incremental (หยุดเมื่อเจอรีวิวที่มีแล้ว) | รายสัปดาห์ |
| เมนูและราคา F&B | **Grab Food, LINE MAN** | Playwright / JSON ของหน้าเว็บ | ราย 2 สัปดาห์ |
| ราคาห้องพัก | ราคาที่แสดงบน Google Maps / OTA | Playwright | รายสัปดาห์ (บันทึกพร้อมวันที่เข้าพักที่ใช้ค้น) |
| เมนูจากรูปภาพ (ร้านที่ไม่มีบนแอป) | รูปเมนู/ป้ายราคาบน Google Maps → **Gemini Vision** | batch, ไม่เก็บรูป | ตามต้องการ |
| ราคาบริการ/ค้าปลีก | **เจ้าของร้านกรอก** (CSV / Vision / Quick-add) + (Could) Shopee/Lazada | ในแอป | ต่อเนื่อง |
| ข้ามแดน (กลันตัน/เคดาห์/เประ/ปีนัง) | Google Maps MY + GrabFood MY | scraper เดียวกัน | รายเดือน |
| ขอบเขตจังหวัด/อำเภอ, POI เสริม | OpenStreetMap (Overpass), ข้อมูลขอบเขตปกครอง | ETL | ครั้งเดียว + รายไตรมาส |
| อัตราแลกเปลี่ยน | ธปท. API (ต้องลงทะเบียน) หรือ Frankfurter (อัตรา ECB) | ETL | รายวัน |
| สภาพอากาศ | Open-Meteo (historical + forecast) | ETL | รายวัน |
| วันหยุดไทย/มาเลเซีย, รอมฎอน | ประกาศทางการ → seed CSV ที่ดูแลเอง | seed | รายปี |
| สถิติท่องเที่ยวรายจังหวัด | กระทรวงการท่องเที่ยวฯ / data.go.th | ETL | รายเดือน |
| ข้อมูล demo / load test | **Synthetic** (ติดป้ายชัดเจน) | `etl/synthetic/` | ครั้งเดียว |

**กติกา synthetic data:** ทุกแถวต้องมี `is_synthetic = TRUE` และ `source_key`, UI แสดงป้าย "ข้อมูลจำลอง" และห้ามนำไปประเมินโมเดล

### 5.2 Scraping Pipeline 6 ขั้น

```text
[1] Discovery   แบ่งพื้นที่เป็น grid (ในเมือง 1–2 กม., นอกเมือง 5 กม.) × คำค้นจาก dim_category.search_keywords
                → รายชื่อสถานที่ (dedupe ด้วย place id)
                หมายเหตุ: หน้าผลการค้นหาแสดงได้จำกัดต่อครั้ง จึงต้องใช้ grid ย่อยแทนการค้นทั้งจังหวัด
[2] Detail      เรตติ้ง, จำนวนรีวิว, เวลาเปิดรายวัน (หลายช่วงได้), attributes, ระดับราคา, หมวด, พิกัด
[3] Reviews     เรียงใหม่สุด → หยุดเมื่อเจอ review_hash ที่มีแล้ว (incremental)
                cap ต่อร้าน (เช่น 24 เดือนล่าสุดหรือ ≤ 200 รีวิว) → ลบ PII ใน memory ก่อนเขียน staging
[4] Menus       Grab / LINE MAN (F&B), ราคาห้อง (Hospitality), รูปเมนู → Vision
[5] Entity      เชื่อมร้านเดียวกันข้ามแหล่ง: ชื่อ (pg_trgm ≥ 0.5) + ระยะ ≤ 150 ม. + เบอร์โทรร้านตรงกัน
    Resolution  → คะแนนรวม ถ้าต่ำกว่าเกณฑ์เข้าคิวให้ admin ตรวจ → dw.map_outlet_source
[6] Load        staging → dbt build → warehouse → refresh marts → ops.scrape_run_log
```

**ความทนทานของ scraper**
- **Checkpoint/resume:** เก็บสถานะทุกขั้นในตาราง `ops.scrape_queue` ถ้าล้มกลางทางให้รันต่อจากจุดเดิม
- **แยก job เล็ก:** ทีละอำเภอ × หมวด เพื่อไม่ชนลิมิต 6 ชั่วโมงต่อ job ของ GitHub-hosted runner
- **ที่รัน:** แนะนำให้รันบนเครื่องตัวเองผ่าน **GitHub self-hosted runner** (ฟรี, ไม่มีลิมิตเวลาต่อ job, รัน browser ได้เต็มที่, ดู log ได้ง่าย) หรือบน VM ตามหัวข้อ 6.7
- **Selector แยกไฟล์:** เก็บ CSS/XPath selector ไว้ใน config เดียว เมื่อหน้าเว็บเปลี่ยนแก้ที่เดียว และมี smoke test ที่รันกับร้านตัวอย่าง 5 ร้านก่อนทุกรอบ
- **ตรวจคุณภาพทุกรอบ:** จำนวนร้านต่ออำเภอไม่ควรลดลงเกิน 20% จากรอบก่อน ถ้าลดให้หยุดและแจ้งเตือน (กันกรณี selector พังแล้วเขียนข้อมูลว่างทับ)

### 5.3 Governance ของ Scraping (ใส่ในเล่มบทที่ 3)
- **หนังสืออนุมัติจากอาจารย์ที่ปรึกษา** แนบภาคผนวก ระบุวัตถุประสงค์ "เพื่อการศึกษา ไม่เผยแพร่ข้อมูลดิบ ไม่ใช้เชิงพาณิชย์"
- **Polite scraping:** concurrency 1–2, หน่วงเวลาหลายวินาทีต่อหน้า, รันนอกช่วงเวลาเร่งด่วน **ถ้าเจอ CAPTCHA หรือโดน block ให้หยุดและลดอัตรา ห้ามใช้ proxy หมุน IP หรือระบบแก้ CAPTCHA อัตโนมัติ**
- **เก็บเท่าที่จำเป็น:** ไม่เก็บชื่อผู้รีวิว รูปโปรไฟล์ ลิงก์โปรไฟล์ ตัดข้อความรีวิวที่ 1,000 ตัวอักษร ลบเบอร์โทร/LINE ID ในเนื้อหารีวิว
- **Business opt-out:** หน้า "ขอนำร้านออกจากระบบ" สำหรับเจ้าของร้านที่ไม่ต้องการให้แสดง
- **Provenance:** ทุกแถวมี `source_key` และ `scraped_at` เพื่อให้ตรวจย้อนกลับได้

### 5.4 ความหนาแน่นข้อมูลที่คาดว่าจะได้ (ตรวจจริงหลัง discovery รอบแรก)
| จังหวัด | ลักษณะ | ร้าน/รีวิว |
|---|---|---|
| สงขลา (หาดใหญ่, เมืองสงขลา, สะเดา) | ศูนย์กลางเศรษฐกิจ + ท่องเที่ยว + ชายแดน | สูง |
| ยะลา (เมืองยะลา, เบตง) | เบตงเป็นแหล่งท่องเที่ยวที่รีวิวหนาแน่น ส่วนอำเภออื่นบาง | กลาง |
| ปัตตานี (เมืองปัตตานี, ย่าน ม.อ.) | ร้านท้องถิ่นและย่านนักศึกษา | ต่ำ–กลาง |
| นราธิวาส (เมือง, สุไหงโก-ลก, ตากใบ) | ชายแดนกลันตัน | ต่ำ–กลาง |

### 5.5 ประมาณปริมาณข้อมูลเทียบ Supabase Free (500 MB)
| ตาราง | แถวโดยประมาณ | ขนาดโดยประมาณ |
|---|---|---|
| outlets (ทุกอุตสาหกรรม 4 จังหวัด + ข้ามแดน) | 10,000–20,000 | ~15 MB |
| reviews (cap ต่อร้าน, 24 เดือน) | 150,000–250,000 | ~100 MB (ภาษาไทยใช้ 3 ไบต์ต่ออักษรใน UTF-8) |
| review aspects | 300,000–500,000 | ~30 MB |
| pricing (F&B + ห้องพัก) | 100,000–150,000 | ~25 MB |
| dim_date, FX, weather, tourism | ~50,000 | ~10 MB |
| indexes (GIN/GiST/trgm) | — | ~100–150 MB |
| **รวม** | | **~300–330 MB** |

**กันเกินโควตา:** ไม่เก็บ HTML ดิบใน Postgres (เก็บเป็นไฟล์ Parquet บนเครื่องหรือ Python host ถ้าต้องการ), ตัดข้อความรีวิว, เก็บรีวิวแค่ 24 เดือน และตั้ง alert เมื่อฐานข้อมูลเกิน 400 MB

### 5.6 การติด label รีวิวเมื่อมีหลักแสนรายการ
Gemini free tier ประมวลได้หลักพันรีวิวต่อวัน (ตรวจ quota ปัจจุบันก่อนเริ่ม) ถ้าจะทำ 200k รีวิวต้องใช้หลายเดือน มี 2 ทาง:

| ทาง | วิธี | ข้อดี | ข้อเสีย |
|---|---|---|---|
| **A. Teacher–Student** ⭐ | ให้ Gemini ติด label ตัวอย่าง 5,000–10,000 รีวิว (สุ่มแบบกระจายตามอุตสาหกรรม × ภาษา) → เทรนโมเดลเล็ก (TF-IDF แบบ char n-gram + Logistic Regression ต่อ aspect) บน Python service → ใช้โมเดลเล็กติด label ที่เหลือทั้งหมด | ฟรี, เร็ว, ได้ ML component เพิ่มอีกชิ้นให้รายงาน | ความแม่นต่ำกว่า Gemini เล็กน้อย ต้องรายงานส่วนต่าง |
| B. Paid tier | ใช้ Gemini Batch แบบจ่ายเงินกับทุกรีวิว | แม่นที่สุด, ง่าย | มีค่าใช้จ่าย (คำนวณจากราคาปัจจุบัน) ขัดกับเป้า $0 |

ไม่ว่าทางไหน ให้ cache ด้วย `review_hash` (ไม่ประมวลซ้ำ) และทำ checkpoint เมื่อชน quota

### 5.7 การจับคู่ชื่อสินค้า (ไม่ใช้ Embedding)

**ทำไมยังต้องจับคู่ ทั้งที่ scrape มาแล้วเข้า SQL ได้เลย:** ชื่อสินค้าที่ scrape มาแต่ละร้านเขียนไม่เหมือนกัน
| ร้าน | ชื่อที่ scrape ได้ | ราคา |
|---|---|---|
| A | อเมริกาโน่เย็น | 45 |
| B | Iced Americano | 50 |
| C | กาแฟดำเย็น | 35 |
| D | อเมริกาโน่ (ปั่น) 22oz | 55 |

ถ้า `GROUP BY raw_item_name` จะได้ 4 กลุ่ม กลุ่มละ 1 ร้าน ทำให้หา median ของตลาดไม่ได้ คำนวณ Price Gap ไม่ได้ และ ML ไม่รู้ว่าแถวไหนคือสินค้าชนิดเดียวกัน ต้องแปลงให้ A, B, C เป็น "อเมริกาโน่เย็น 16 oz" ก่อน (D เป็นคนละรายการเพราะปั่นและไซซ์ใหญ่)

**วิธีที่เสนอ (4 ชั้น ไม่ต้องใช้ embedding model):**
1. **Dictionary:** ตาราง `dw.map_item_synonym` เช่น `อเมริกาโน่`, `americano`, `กาแฟดำ` → Americano และคำบอกคุณลักษณะ `เย็น/ร้อน/ปั่น`, `16oz/22oz/แก้วใหญ่`
2. **`pg_trgm`:** จับคำสะกดผิดหรือคล้ายกัน (`อเมริกาโน`, `อเมริกาโน่ๆ`) เทียบเฉพาะ std items ในหมวดเดียวกัน
3. **Gemini batch:** ชื่อที่เหลือส่งทีละ 50 ชื่อพร้อมรายการ std items ของหมวดนั้น (≤ 60 รายการ) ให้คืน JSON `{raw, std_item_key | null, temperature, size, confidence}`
4. **Cache + คิวตรวจ:** เก็บผลใน `dw.map_raw_item` ต่อ **ชื่อที่ไม่ซ้ำ** (150k แถวราคาอาจมีชื่อไม่ซ้ำแค่ ~20k) ถ้า confidence ต่ำเข้าคิวให้ admin ตรวจ รอบต่อไปไม่ต้องเรียก LLM ซ้ำ

`pg_trgm` อย่างเดียวจับ "กาแฟดำเย็น" กับ "Iced Americano" ไม่ได้ เพราะไม่มีตัวอักษรร่วมกัน งานด้าน "ความหมาย" นี้ให้ Gemini ทำ ซึ่งใช้อยู่แล้วในระบบ จึงไม่ต้องเพิ่ม embedding model
**เสริมสำหรับ ML:** ใส่ชื่อดิบเป็น text feature ของ CatBoost ได้อีกทาง (โมเดลเรียนรู้คำอย่าง "ปั่น", "ใหญ่", "พรีเมียม") ใช้เป็นอีกการทดลองใน ML Lab

---

## 6. สถาปัตยกรรม v2

### 6.1 แบ่ง Schema (แก้ C2)

```text
public   (PostgREST expose)  → app_* ทุกตาราง เปิด RLS + RPC functions ที่ UI เรียก
mart     (expose, read-only) → materialized views ที่หน้า dashboard ใช้ GRANT SELECT ให้ authenticated เท่านั้น
dw       (ไม่ expose)         → dim_* / fact_* / map_* เขียนได้เฉพาะ ETL
staging  (ไม่ expose)         → stg_* ข้อมูลดิบหลังลบ PII
ml       (ไม่ expose)         → model registry, experiments, predictions; อ่านผ่าน mart view
ops      (ไม่ expose)         → scrape_queue, scrape_run_log, etl_run_log, dq_results, llm_usage_log
```
Role:
- `bi_readonly_login` (LOGIN, member of `bi_readonly_exec`): `USAGE` บน `mart` + `SELECT` เฉพาะ view ที่อนุญาต ใช้โดย Copilot ฝั่ง server เท่านั้น
- `etl_writer`: เขียน `staging`, `dw`, `ops` ใช้โดย scraper, ETL และ dbt
- `ml_service`: อ่าน `dw`/`mart`, เขียน `ml.*` และ label ใน `dw.fact_review_aspect` ใช้โดย Python ML Service
- Connection string ทั้งหมดอยู่ใน server/secrets เท่านั้น ไม่มีวันอยู่ใน Next.js client bundle

### 6.2 รายการตารางที่เปลี่ยนหรือเพิ่ม

| สถานะ | ตาราง | เหตุผล |
|---|---|---|
| ✏️ | `dw.dim_category` | Industry Pack config (4.0) |
| 🆕 | `dw.dim_data_source` | provenance ของแต่ละแหล่ง scrape/API |
| 🆕 | `dw.dim_aspect` | aspect ต่ออุตสาหกรรม + ป้ายไทย/อังกฤษ/มลายู |
| ✏️ | `dw.dim_brand` | ตัด `local_leader` ออก, เปลี่ยนเป็น `brand_scale` ∈ (independent, regional_chain, national_chain, global_chain) + `origin_country`; tier คำนวณตอน query |
| ✏️ | `dw.dim_business_outlet` | `operating_hours` แบบหลายช่วงต่อวัน, attributes ฮาลาลแบบใหม่, `distance_to_border_km`; (Could) SCD Type 2 |
| ✏️ | `dw.dim_geography` | `coast_type` เหลือ `gulf`/`inland`/`foreign`, `area_character` + `border_town`, `university_area` |
| ✏️ | `dw.dim_date` | + `is_ramadan`, `is_hari_raya_aidilfitri`, `is_hari_raya_haji`, `is_cny_period`, `is_songkran`, `is_my_school_holiday`, `is_weekend_my_fri_sat_states`, `holiday_name_th` |
| ✏️ | `dw.dim_standard_item` | + `unit_qty`, `unit_measure`, seed เมนูท้องถิ่น |
| 🆕 | `dw.map_outlet_source` | entity resolution: outlet ↔ id ในแต่ละแหล่ง + คะแนน |
| 🆕 | `dw.map_item_synonym`, `dw.map_raw_item` | การจับคู่ชื่อสินค้า (5.7) |
| ✏️ | `dw.fact_product_pricing` | + conformed keys, `channel`, `source_key`, `is_synthetic`, หน่วยมาตรฐาน, `std_item_key` NULL ได้ |
| 🔁 | `dw.fact_customer_reviews` → `dw.fact_review` + `dw.fact_review_aspect` | แก้ fan-trap + เพิ่ม `script` |
| ✏️ | `dw.fact_market_snapshot` | grain = เดือน (สิ้นเดือน), + `pi_rank_pct`, `group_size` |
| 🆕 | `dw.fact_fx_daily`, `dw.fact_weather_daily`, `dw.fact_tourism_monthly` | ข้อมูลอ้างอิง |
| 🆕 | `mart.peer_price_stats`, `mart.outlet_scorecard_monthly`, `mart.aspect_sentiment_monthly`, `mart.hourly_coverage`, `mart.data_readiness` | semantic layer + readiness ต่อ (หมวด × พื้นที่) |
| 🆕 | `app_candidate_locations`, `app_scenarios`, `app_sku_price_history`, `app_alert_rules` | ฟีเจอร์ใหม่ |
| ✏️ | `app_user_sku_portfolio` | + `channel_promo_cofund_pct`, `gp_includes_vat` |
| 🆕 | `ml.model_registry`, `ml.cv_fold_results`, `ml.prediction_cache` | เก็บผลราย fold + champion ต่อ sector |
| 🆕 | `ops.scrape_queue`, `ops.scrape_run_log`, `ops.etl_run_log`, `ops.dq_results`, `ops.llm_usage_log` | resume + observability + หน้า admin |

### 6.3 DDL ส่วนที่สำคัญ (ตัวอย่าง)

```sql
-- Provenance
CREATE TABLE dw.dim_data_source (
  source_key SMALLSERIAL PRIMARY KEY,
  source_name TEXT UNIQUE NOT NULL,           -- 'google_maps','grab_food','line_man','owner_input','synthetic_v1'
  collection_method TEXT NOT NULL
    CHECK (collection_method IN ('web_scrape','open_data_api','official_api','owner_submitted','synthetic')),
  notes TEXT
);

-- Pricing fact v2: มี conformed keys + channel + หน่วยมาตรฐาน + รองรับ Mode B
CREATE TABLE dw.fact_product_pricing (
  pricing_fact_id BIGSERIAL PRIMARY KEY,
  outlet_key   INT NOT NULL REFERENCES dw.dim_business_outlet(outlet_key),
  brand_key    INT NOT NULL REFERENCES dw.dim_brand(brand_key),
  category_key INT NOT NULL REFERENCES dw.dim_category(category_key),
  geo_key      INT NOT NULL REFERENCES dw.dim_geography(geo_key),
  std_item_key INT REFERENCES dw.dim_standard_item(std_item_key),      -- NULL ได้สำหรับ Mode B
  price_band_tier TEXT CHECK (price_band_tier IN ('entry','core','premium')),
  recorded_date_key DATE NOT NULL REFERENCES dw.dim_date(date_key),
  source_key SMALLINT NOT NULL REFERENCES dw.dim_data_source(source_key),
  channel TEXT NOT NULL DEFAULT 'walk_in' CHECK (channel IN ('walk_in','delivery','ota')),
  raw_item_name TEXT NOT NULL,
  currency_code CHAR(3) NOT NULL,
  original_price NUMERIC(12,2) NOT NULL CHECK (original_price >= 0),
  fx_rate_to_thb NUMERIC(12,6) NOT NULL,
  price_thb NUMERIC(12,2) NOT NULL CHECK (price_thb >= 0),
  unit_qty NUMERIC(10,2), unit_measure TEXT,                           -- 16 'oz', 1 'session', 1 'night'
  price_thb_per_std_unit NUMERIC(12,4),
  item_attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_synthetic BOOLEAN NOT NULL DEFAULT FALSE,
  CHECK (std_item_key IS NOT NULL OR price_band_tier IS NOT NULL)
);

-- Review fact แยก grain (แก้ fan-trap)
CREATE TABLE dw.fact_review (                                -- grain: 1 แถว = 1 รีวิว
  review_key BIGSERIAL PRIMARY KEY,
  outlet_key INT NOT NULL, brand_key INT NOT NULL, category_key INT NOT NULL, geo_key INT NOT NULL,
  review_date_key DATE NOT NULL REFERENCES dw.dim_date(date_key),
  source_key SMALLINT NOT NULL REFERENCES dw.dim_data_source(source_key),
  star_rating SMALLINT NOT NULL CHECK (star_rating BETWEEN 1 AND 5),
  reviewer_language CHAR(2) NOT NULL CHECK (reviewer_language IN ('th','ms','en','zh','other')),
  script TEXT CHECK (script IN ('thai','latin','jawi','han','other')),   -- มลายูอักษรไทย = ms + thai
  customer_segment TEXT CHECK (customer_segment IN ('local_resident','domestic_tourist','foreign_tourist','unknown')),
  overall_sentiment NUMERIC(4,2) CHECK (overall_sentiment BETWEEN -1 AND 1),
  clean_review_text TEXT NOT NULL,                           -- ลบ PII แล้ว, ≤ 1,000 ตัวอักษร
  review_hash TEXT UNIQUE NOT NULL,
  is_synthetic BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE dw.fact_review_aspect (                         -- grain: 1 แถว = 1 รีวิว × 1 aspect
  review_key BIGINT NOT NULL REFERENCES dw.fact_review(review_key) ON DELETE CASCADE,
  aspect_key SMALLINT NOT NULL REFERENCES dw.dim_aspect(aspect_key),
  sentiment_score NUMERIC(4,2) NOT NULL CHECK (sentiment_score BETWEEN -1 AND 1),
  evidence_span TEXT,                                        -- วลีที่ใช้เป็นหลักฐาน (explainability)
  label_source TEXT NOT NULL CHECK (label_source IN ('llm_teacher','student_model','manual','synthetic')),
  label_model_version TEXT,
  PRIMARY KEY (review_key, aspect_key)
);

-- การจับคู่ชื่อสินค้า (5.7)
CREATE TABLE dw.map_raw_item (
  raw_name_normalized TEXT NOT NULL,
  category_key INT NOT NULL REFERENCES dw.dim_category(category_key),
  std_item_key INT REFERENCES dw.dim_standard_item(std_item_key),     -- NULL = ไม่ตรงกับรายการมาตรฐาน
  attributes JSONB NOT NULL DEFAULT '{}'::jsonb,                      -- {"temperature":"iced","size_oz":16}
  match_method TEXT NOT NULL CHECK (match_method IN ('dictionary','trigram','llm','manual')),
  confidence NUMERIC(3,2),
  reviewed_by_admin BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (raw_name_normalized, category_key)
);

-- Entity resolution ข้ามแหล่ง
CREATE TABLE dw.map_outlet_source (
  outlet_key INT NOT NULL REFERENCES dw.dim_business_outlet(outlet_key),
  source_key SMALLINT NOT NULL REFERENCES dw.dim_data_source(source_key),
  source_entity_id TEXT NOT NULL,
  match_score NUMERIC(3,2) NOT NULL,
  match_method TEXT NOT NULL CHECK (match_method IN ('exact_id','name_distance','phone','manual')),
  PRIMARY KEY (source_key, source_entity_id)
);

CREATE TABLE dw.fact_fx_daily (
  date_key DATE NOT NULL REFERENCES dw.dim_date(date_key),
  currency_code CHAR(3) NOT NULL,
  rate_to_thb NUMERIC(14,6) NOT NULL,
  source_key SMALLINT NOT NULL REFERENCES dw.dim_data_source(source_key),
  PRIMARY KEY (date_key, currency_code)
);

CREATE TABLE dw.fact_weather_daily (
  geo_key INT NOT NULL REFERENCES dw.dim_geography(geo_key),
  date_key DATE NOT NULL REFERENCES dw.dim_date(date_key),
  precipitation_mm NUMERIC(6,2), temp_max_c NUMERIC(4,1),
  is_heavy_rain BOOLEAN GENERATED ALWAYS AS (precipitation_mm >= 35.1) STORED,  -- เกณฑ์ฝนหนักของกรมอุตุฯ
  PRIMARY KEY (geo_key, date_key)
);

-- Mart ตัวอย่าง: สถิติราคาของ peer (หน้า dashboard และ Copilot อ่านจากชั้นนี้)
CREATE MATERIALIZED VIEW mart.peer_price_stats AS
SELECT std_item_key, geo_key, category_key, brand_key, channel,
       date_trunc('month', recorded_date_key)::date AS month,
       COUNT(DISTINCT outlet_key)                                      AS n_outlets,
       percentile_cont(0.25) WITHIN GROUP (ORDER BY price_thb_per_std_unit) AS p25,
       percentile_cont(0.50) WITHIN GROUP (ORDER BY price_thb_per_std_unit) AS median,
       percentile_cont(0.75) WITHIN GROUP (ORDER BY price_thb_per_std_unit) AS p75,
       MIN(price_thb_per_std_unit) AS min_price, MAX(price_thb_per_std_unit) AS max_price
FROM dw.fact_product_pricing
WHERE std_item_key IS NOT NULL AND NOT is_synthetic
GROUP BY 1,2,3,4,5,6;
```

ตรวจ RLS ใน CI:
```sql
-- ห้ามมีตารางใน public ที่ไม่เปิด RLS: CI fail ถ้า query นี้คืนแถว
SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity;
```

### 6.4 ชั้น Transform: dbt-core (แนะนำ)
- `dbt/models/staging/` ทำความสะอาด, ตั้งชื่อ, แปลงชนิดข้อมูลจาก `staging.stg_*`
- `dbt/models/intermediate/` เชื่อมกับ `map_raw_item`/`map_outlet_source`, แปลง FX, normalize หน่วย
- `dbt/models/dw/` dim/fact (incremental models)
- `dbt/models/mart/` materialized views
- **dbt tests:** `unique`, `not_null`, `relationships`, `accepted_values` และ custom test เช่น "ราคาต่อหน่วยต้องอยู่ใน 3×IQR", "ทุก outlet ต้องอยู่ในขอบเขตจังหวัด (ST_Within)"
- **dbt docs** สร้าง lineage graph อัตโนมัติ เอาไปใส่ในเล่มบทที่ 3 ได้
- แบ่งหน้าที่: scraper/Python ทำ **E + L** (ดึง, ลบ PII, ติด label, จับคู่) ส่วน dbt ทำ **T**

### 6.5 ตารางเวลา Pipeline
| Job | ที่รัน | เวลา | งาน |
|---|---|---|---|
| `scrape_discovery` | self-hosted runner / VM | เดือนละครั้ง | grid discovery ทุกหมวด 4 จังหวัด + ข้ามแดน |
| `scrape_weekly` | self-hosted runner / VM | ทุกคืนวันเสาร์ | detail + reviews แบบ incremental ทีละอำเภอ |
| `scrape_menus` | self-hosted runner / VM | ราย 2 สัปดาห์ | Grab / LINE MAN / ราคาห้องพัก |
| `daily_reference` | GitHub Actions | ทุกวัน 06:00 | FX, อากาศ |
| `enrich_and_build` | GitHub Actions → Python service | หลัง scrape เสร็จ | ลบ PII → ติด label → จับคู่สินค้า → `dbt build` → refresh marts → คำนวณ leader |
| `monthly_snapshot` | GitHub Actions | วันที่ 1 | snapshot ตลาด + สถิติท่องเที่ยว |
| `ml_retrain` | สั่งรันเอง / Python host | หลังข้อมูลราคารอบใหม่ | train + log + อัปเดต champion |
| keep-alive | UptimeRobot / cron-job.org | ทุก 5–30 นาที | ping Next.js health (ซึ่ง query Supabase) + Python service ไม่ขึ้นกับกติกา 60 วันของ GitHub |
| `ci` | GitHub Actions | ทุก PR | lint, typecheck, Vitest, pytest, `dbt build` บน Supabase local, ตรวจ RLS, guardrail tests |

### 6.6 รูปแบบการเข้าถึงข้อมูลฝั่ง Frontend
- **Server Components** อ่าน `mart.*` ผ่าน Supabase client ที่ผูก session ผู้ใช้
- **ข้อมูลส่วนตัว** อ่าน `public.app_*` ภายใต้ RLS
- **การคำนวณที่ผสม public กับ private** (เช่น gap ราคาของฉันเทียบตลาด) ทำใน RPC แบบ `SECURITY INVOKER` เพื่อให้ RLS ยังมีผล
- **ML:** Next.js server route เรียก Python ML Service แบบ server-to-server พร้อม API key (ผู้ใช้ไม่เห็น endpoint)

### 6.7 Deployment Topology (Python แยก host)

```text
                        ┌──────────────────────────────┐
  ผู้ใช้ ── HTTPS ──────▶│ Vercel: Next.js (UI + API)   │
                        └──────┬───────────────┬───────┘
                               │ supabase-js    │ server-to-server + API key
                               ▼               ▼
        ┌────────────────────────────┐   ┌─────────────────────────────────────┐
        │ Supabase: Postgres+PostGIS │◀──│ Python ML Service (FastAPI)         │
        │ + Auth + RLS               │   │  /predict/fair-price (+ SHAP)       │
        └────────────▲───────────────┘   │  /label/reviews  (student model)    │
                     │                   │  /match/items    (dict+trgm+LLM)    │
                     │                   │  /vision/menu    (Gemini Vision)    │
                     │                   └─────────────────────────────────────┘
        ┌────────────┴───────────────┐
        │ Scraper Worker (Playwright) │  ← GitHub self-hosted runner บนเครื่องตัวเอง หรือ VM
        └────────────────────────────┘
  GitHub Actions (hosted): CI, dbt build, FX/อากาศ, trigger งาน
  UptimeRobot / cron-job.org: keep-alive ทั้ง Supabase (ผ่าน Next.js health) และ Python service
```

**ตัวเลือก host สำหรับ Python (เงื่อนไข free tier เปลี่ยนบ่อย ตรวจก่อนใช้):**
| Host | ข้อดี | ข้อจำกัด |
|---|---|---|
| **Hugging Face Spaces (Docker, CPU ฟรี)** ⭐ | ไม่ต้องใช้บัตร, RAM พอสำหรับ ML, deploy จาก Git | sleep เมื่อไม่มี traffic ระยะหนึ่ง (แก้ด้วย keep-alive), ตั้ง Space เป็น private |
| Google Cloud Run | free tier ต่อเดือนเยอะ, cold start ไม่กี่วินาที | ต้องผูก billing account (บัตร) |
| Render (free web service) | deploy ง่าย | sleep เร็ว, cold start นาน ไม่เหมาะกับเดโมสด |
| Oracle Cloud Always Free VM | รัน 24 ชม. ได้ทั้ง scraper + API + cron ในเครื่องเดียว | สมัครยาก/ต้องใช้บัตร, ต้องดูแลเซิร์ฟเวอร์เอง |

---

## 7. Machine Learning v2

### 7.1 นิยามโจทย์
- **Task หลัก:** Fair Market Price Estimation ทำนาย `log(price_thb_per_std_unit)` จากคุณลักษณะของร้าน ทำเล และสินค้า
- **โมเดลแยกตาม sector:** benchmark 6 โมเดลบน **F&B** และ **Hospitality** (ข้อมูลราคาหนาแน่นพอ) ส่วน sector อื่นเปิดใช้อัตโนมัติเมื่อข้อมูลถึง `min_rows_for_ml` ระหว่างนั้นใช้สถิติ peer (median/IQR) แทน
- **การใช้งาน:** (ก) ช่วงราคายุติธรรมของ SKU ผู้ใช้ (ข) ราคาเปิดตัวแนะนำสำหรับ investor (ค) ตรวจจับรายการที่ราคาผิดปกติ
- **Task รอง (แทน `review_priority_classification`):** sentiment student model (7.7)
- **Pipeline:** SQL view `ml.v_training_pricing` → pandas → train → บันทึกผลลง `ml.*` → เก็บไฟล์โมเดล → Python service โหลด champion ตรงนี้คือ "scrape → SQL → train" ที่ถามมา โดยมีขั้นทำความสะอาดและจับคู่สินค้าคั่นก่อนเข้า SQL

### 7.2 Features
| กลุ่ม | Feature |
|---|---|
| สินค้า | `std_item_key`/sub_category, `unit_qty`, attributes (เย็น/ร้อน/ปั่น), channel, (ทดลอง) ชื่อดิบเป็น text feature |
| ร้าน | `brand_scale`, `S_bayes`, log(จำนวนรีวิว), ตราฮาลาลรับรอง, parking, wifi, aircon, QR/DuitNow, ชั่วโมงเปิดรวม, เปิดดึก, ปิดละหมาดวันศุกร์ |
| ทำเล | จังหวัด, `area_character`, ระยะถึงด่านชายแดน, ระยะถึงย่านมหาวิทยาลัย, ความหนาแน่น POI 500 ม., จำนวนคู่แข่งหมวดเดียวกันใน 1 กม., ประเทศ |
| เวลา | เดือน/ฤดูกาล (มรสุม, รอมฎอน) |
| **ห้ามใช้ (leakage)** | `price_positioning` (ได้มาจากราคา), median ราคา peer ที่รวมแถวตัวเอง (ถ้าจะใช้ต้องคำนวณแบบ leave-one-brand-out ภายใน fold) |

### 7.3 Validation Protocol
- **GroupKFold (k = 5) โดย group = `brand_key`** (ร้านอิสระ = 1 brand ต่อ 1 ร้านอยู่แล้ว) กันสาขาของ chain ที่ราคาเท่ากันรั่วข้าม fold
- **Baseline (บังคับ):** median ราคาของ std_item ในจังหวัด (คำนวณภายใน fold) ทุกโมเดลต้องชนะ baseline นี้ ถ้าไม่ชนะต้องรายงานตรงๆ
- **Tuning:** ให้ทุกโมเดลได้งบ tuning เท่ากัน (เช่น Optuna 30–50 trials) เพื่อเทียบอย่างยุติธรรม
- **Metrics:** R², RMSE, MAE, MAPE (คำนวณหลังแปลงกลับจาก log) + ค่าเฉลี่ย ± S.D. ข้าม fold
- **(ทางเลือก)** Friedman test เทียบ 6 โมเดลข้าม fold ถ้าอาจารย์ต้องการความลึกทางสถิติ

### 7.4 Explainability
- SHAP `TreeExplainer` สำหรับ RF/XGB/LGBM/CatBoost, ค่าสัมประสิทธิ์สำหรับ Ridge, Permutation Importance สำหรับ SVR
- **SHAP รายรายการคำนวณสดได้** บน Python service (เช่น "ราคายุติธรรมสูงขึ้น 6 บาทเพราะอยู่ใกล้ด่านสะเดา")
- ทำ **Model Card** ใน `ml/MODEL_CARD.md` ระบุข้อมูลที่ใช้ การใช้งานที่เหมาะสม และข้อจำกัด

### 7.5 What-If Simulator แบบซื่อตรง (แก้ H1)
| ชั้น | สิ่งที่แสดง | ที่มา |
|---|---|---|
| 1. เศรษฐศาสตร์ร้าน | CM, net profit หลัง GP, break-even ตามราคาที่เลื่อน | deterministic (`lib/economics`) |
| 2. ตำแหน่งตลาด | ราคาที่เลื่อนอยู่ใน **ช่วงราคายุติธรรม** หรือไม่ (โซน: ถูกกว่าตลาด / ยุติธรรม / เสี่ยงแพง) | ML (quantile หรือ conformal interval) |
| 3. Demand (ทางเลือก) | กำไรต่อเดือนภายใต้ elasticity ที่ **ผู้ใช้เลือก** (ไม่ค่อยไวต่อราคา −0.5 / ปกติ −1.0 / ไวมาก −1.5) | สมมติฐาน ติดป้าย "Scenario" ชัดเจน |

**ทำไม slider ไม่ต้องเรียก API ทุกครั้งที่ลาก:** ราคายุติธรรมขึ้นกับคุณลักษณะของร้านและสินค้า ไม่ขึ้นกับราคาที่ผู้ใช้ตั้ง จึงเรียก Python service **ครั้งเดียวต่อ SKU** ได้ช่วงราคา แล้ว slider คำนวณทุกอย่างฝั่ง browser ทันที

### 7.6 Deployment (แก้ H5)
- โมเดลทุกตัวเสิร์ฟจาก **Python ML Service** ด้วย library ต้นฉบับ (CatBoost ใช้ categorical ได้ตามปกติ ไม่ต้องแปลง ONNX)
- **Fallback:** `ml.prediction_cache` เก็บผลทำนายของทุก std item × พื้นที่ไว้ล่วงหน้า ถ้า Python service ล่มหรือกำลัง cold start หน้าเว็บยังแสดงผลได้
- ไฟล์โมเดลเก็บใน Supabase Storage หรือ Hugging Face Hub (private) พร้อมเลขเวอร์ชันใน `ml.model_registry`

### 7.7 Sentiment Student Model (Task รอง)
1. Gemini (teacher) ติด label ตัวอย่าง 5,000–10,000 รีวิว
2. เทรน student: TF-IDF แบบ char n-gram (เหมาะกับภาษาไทยที่ไม่เว้นวรรค และมลายูหลายอักษร) + Logistic Regression ต่อ aspect
3. วัดผล: macro-F1 ของ student เทียบ teacher บนชุด held-out และสุ่ม 150–200 รีวิวมาตรวจเองเพื่อดูความถูกต้องของ teacher
4. ใช้ student ติด label รีวิวที่เหลือทั้งหมด แล้วแสดงผลใน ML Lab คู่กับโมเดลราคา

---

## 8. Conversational BI Copilot v2

### 8.1 Pipeline แบบ Hybrid
```text
คำถาม → [1] Intent Router (เทียบกับ template ~20 แบบ ด้วย keyword + LLM classify)
          ├─ ตรง template → SQL แบบ parameterized ที่เขียนไว้แล้ว (ปลอดภัย 100%, เร็ว, ใช้เดโมได้แน่นอน)
          └─ ไม่ตรง → [2] LLM สร้าง SQL จาก semantic layer (mart views + COMMENT ON COLUMN + ตัวอย่างคำถาม-SQL)
                     → [3] Guardrail: AST parse (ใช้ parser ของ PostgreSQL เช่น libpg-query/pgsql-parser)
                         - อนุญาตเฉพาะ SelectStmt เดียว
                         - relation ต้องอยู่ใน allowlist (mart.* + CTE my_skus)
                         - function ต้องอยู่ใน allowlist (ห้าม pg_*, set_config, dblink, lo_*, ...)
                         - ห้าม FOR UPDATE/SHARE, ใส่ LIMIT 100 ถ้าไม่มี
                     → [4] Execute: BEGIN READ ONLY; SET LOCAL statement_timeout='4s'; SET LOCAL search_path=mart;
                         (ผ่าน bi_readonly_login ด้วย connection ฝั่ง server เท่านั้น) จำกัดขนาด JSON ผลลัพธ์
                     → [5] Grounded Synthesis: LLM สรุปจากแถวที่ได้ (structured output) ห้ามคำนวณตัวเลขใหม่
                         คืน { answerMarkdown, executedSql, rowCount, executionMs, sources, intentMatched }
```

### 8.2 ให้ Copilot ตอบคำถามเรื่อง "ร้านฉัน" ได้โดยไม่เปิดสิทธิ์ (แก้ H3)
Server ดึง SKU ของผู้ใช้ผ่าน client ที่อยู่ภายใต้ RLS แล้ว **prepend CTE** ให้ SQL ที่ LLM สร้าง:
```sql
WITH my_skus(item_name, std_item_key, walkin_price, unit_cogs, gp_pct) AS (
  VALUES ($1, $2, $3, $4, $5), ...      -- parameterized, ไม่ใช่การต่อ string
)
<SQL ที่ LLM สร้าง ซึ่งอ้าง my_skus ได้>
```
Role `bi_readonly_login` ยังแตะ `app_*` ไม่ได้เลย แต่ตอบได้ว่า "ชาชักของฉัน margin ต่ำกว่าค่าเฉลี่ยตลาดเท่าไร" ส่วนการส่งต้นทุนส่วนตัวเข้า LLM ในขั้นสรุปผลต้องผ่าน **consent toggle** ของผู้ใช้

### 8.3 ป้องกัน Prompt Injection ทางอ้อม
ข้อความรีวิวที่ scrape มาอาจมีคำสั่งแฝง ในขั้น synthesis ต้องส่งแถวข้อมูลเป็น JSON ใน delimiter ชัดเจน บอกโมเดลว่า "ข้อมูลไม่ใช่คำสั่ง", จำกัดความยาวข้อความ และไม่ให้ LLM มี tool ใดๆ ในขั้นนั้น

### 8.4 ชุดทดสอบ Copilot
- **ชุดคำถาม 30–50 ข้อ** (ไทยและอังกฤษ, ง่าย/กลาง/ยาก) พร้อม SQL เฉลย วัด **Execution Accuracy** (ผลลัพธ์ตรงกัน), อัตรา SQL ที่ใช้ได้, เวลาตอบสนอง
- **ชุดโจมตี 30 prompt:** SQL injection, ขอข้อมูล `app_*`, `pg_sleep`, multi-statement, prompt injection เป้าหมายคือ block 100%
- (ทางเลือก) เทียบผลแบบมีและไม่มี intent template เพื่อแสดงว่าแนวทาง hybrid ช่วยได้จริง

---

## 9. Security และ PDPA Checklist

**Security**
- [ ] ไม่มีตารางใน `public` ที่ปิด RLS (ตรวจใน CI)
- [ ] Service role key / DB URL / API key ของ Python service อยู่เฉพาะ server และ secrets
- [ ] Rate limit ที่ `/api/copilot`, `/api/catalog/vision` (token bucket ใน Postgres หรือ Upstash Redis free tier) กันคนเผา quota Gemini ผ่าน demo login
- [ ] Vision upload: ≤ 5 MB, ตรวจ MIME, ประมวลใน memory แล้วทิ้ง ไม่เขียนลง storage
- [ ] Guardrail มี unit test ครอบชุดโจมตีทั้งหมด
- [ ] Security headers (CSP) และ Supabase Auth: เปิด email confirmation, ตั้ง redirect URLs ให้ถูกต้อง
- [ ] Demo: Anonymous sign-in แล้ว clone seed portfolio ให้แต่ละ session และ cron ลบ tenant ที่อายุเกิน 7 วัน

**Scraping & PDPA (พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562)**
- [ ] หนังสืออนุมัติจากอาจารย์ + ขอบเขต "เพื่อการศึกษา ไม่เผยแพร่ข้อมูลดิบ"
- [ ] ลบ PII ก่อนเข้า staging: ชื่อผู้รีวิว, รูป, ลิงก์โปรไฟล์ **และ PII ในเนื้อหารีวิว** (เบอร์โทร, LINE ID, ชื่อพนักงาน) ด้วย regex + ให้ LLM redact
- [ ] หน้า business opt-out
- [ ] Privacy Notice + consent ตอนสมัคร, consent แยกสำหรับ "ให้ AI อ่านต้นทุนของฉัน"
- [ ] สิทธิ์ลบบัญชี (cascade ลบข้อมูลทั้งหมด) และ export ข้อมูลของตัวเอง
- [ ] เปิดเผยว่าข้อมูลถูกส่งไปประมวลผลโดยผู้ให้บริการ LLM ต่างประเทศ และใน free tier อาจถูกใช้พัฒนาผลิตภัณฑ์
- [ ] Retention: รีวิว 24 เดือน, chat logs 90 วัน, ข้อมูล demo 7 วัน

---

## 10. แผนการทดสอบและประเมินผล (รูปแบบโครงงาน)

| หัวข้อ | วิธี | เกณฑ์ตั้งต้น |
|---|---|---|
| การทดสอบฟังก์ชัน | Black-box test case ทุก use case (ตารางในบทที่ 4) + E2E ด้วย Playwright บน flow หลัก (login → onboarding → 5 views → copilot) | test case สำคัญผ่าน 100% |
| Scraper | จำนวนร้าน/รีวิวต่อจังหวัดและอุตสาหกรรม, อัตราสำเร็จต่อรอบ, เวลาต่อรอบ | รายงานผล |
| คุณภาพข้อมูล | dbt tests + completeness, duplicate rate | ผ่าน ≥ 95% |
| Entity resolution / จับคู่สินค้า | สุ่ม 200 คู่มาตรวจเอง → accuracy | ≥ 90% |
| Sentiment | teacher เทียบที่ตรวจเอง 150–200 รีวิว, student เทียบ teacher (macro-F1) | F1 ≥ 0.75 |
| ML ราคา | 6 โมเดล + baseline, GroupKFold 5 fold, R²/RMSE/MAE/MAPE, SHAP | ชนะ baseline |
| Copilot | Execution Accuracy บนชุดคำถาม + block rate บนชุดโจมตี | EX ≥ 70%, block 100% |
| ประสิทธิภาพ | Lighthouse, เวลาตอบสนองของ RPC และ Python service | LCP < 2.5 s |
| ความพึงพอใจ | แบบสอบถาม Likert 5 ระดับ (ค่าเฉลี่ย x̄, S.D.) จากผู้ทดลองใช้ (จำนวนและกลุ่มตามที่อาจารย์กำหนด เช่น ~30 คน) | x̄ ≥ 3.51 (ระดับมาก) |
| ประเมินโดยผู้เชี่ยวชาญ (ถ้าหลักสูตรกำหนด) | ผู้เชี่ยวชาญ 3–5 ท่าน ประเมินด้านฟังก์ชัน ความถูกต้อง การใช้งาน ความปลอดภัย | x̄ ≥ 3.51 |

---

## 11. ขอบเขตงาน (MoSCoW)

| Must (ต้องมีวันสอบ) | Should | Could | Won't (รุ่นนี้) |
|---|---|---|---|
| Industry Pack ครบ 5 sector + ชั้นข้อมูลร่วมใช้ได้ทุกอุตสาหกรรม | ราคาห้องพัก (Hospitality) + ML sector ที่ 2 | ราคาบริการ/ค้าปลีกจาก Shopee/Lazada/FB | ดึงราคา OTA แบบ real-time |
| Scraper Google Maps 4 จังหวัด (ร้าน + รีวิว) + governance | เทียบข้ามแดน (กลันตัน/เคดาห์/เประ/ปีนัง) + PPP | SCD Type 2 | พยากรณ์ demand จริง (ไม่มีข้อมูลยอดขาย) |
| Scraper เมนู F&B (Grab/LINE MAN) + entity resolution + จับคู่สินค้า | Location Opportunity Score (Huff) | ภาษาจีน (zh) ใน UI | ระบบชำระเงินหรือ subscription |
| Warehouse v2 + dbt + DQ tests | Vision ดึงเมนูจากรูป | PWA + offline | Native mobile app |
| Onboarding 3 ขั้น + demo login แยก tenant | Weekly Pulse ผ่าน LINE OA | Isochrone แทนวงกลมรัศมี | |
| Overview, Radar, Pricing, Reviews, ML Lab | Sentiment student model | Dark mode | |
| Store economics + 2 lens quadrant + break-even | สลับสกุลเงิน + บริบทฤดูกาล | Multi-pin compare | |
| Python ML Service + ML 6 โมเดล (F&B) + baseline + SHAP | Saved scenarios | Admin mapping review UI เต็มรูปแบบ | |
| Copilot hybrid + guardrail + ชุดทดสอบ | | | |
| RLS + PDPA + scraping governance | | | |

---

## 12. Roadmap (สมมติ 20 สัปดาห์ เริ่ม 23 พ.ย. 2569 ปรับตามกำหนดสอบจริง)

| Phase | สัปดาห์ | งานหลัก | Deliverable / Definition of Done |
|---|---|---|---|
| **0. Foundation** | 1–2 | ตอบคำถามที่เหลือ, อัปเดต CONTEXT/ARCH v2, ตั้ง repo + CI, Supabase local + migrations v2, **Industry Pack taxonomy + std items + aspects**, design tokens, wireframe | `supabase db reset` ผ่าน, CI เขียว, RLS check ผ่าน, taxonomy ครบ 5 sector |
| **1. Scraping & Data Foundation** | 2–6 | Scraper discovery/detail/reviews (เริ่มสงขลา แล้วขยาย 3 จังหวัด), checkpoint/resume, PII strip, ETL อ้างอิง (FX/อากาศ/วันหยุด/ท่องเที่ยว), dbt staging→dw | ร้านครบ 4 จังหวัด, รีวิวรอบแรก, dbt tests ≥ 95% ผ่าน |
| **2. App Core (ชั้นข้อมูลร่วม)** | 4–9 | Auth + anonymous demo, onboarding, workspace shell + context bar, **Overview + Radar ใช้ได้ทุกอุตสาหกรรม** | เดโม end-to-end ได้ 4 persona (คาเฟ่หาดใหญ่, ร้านอาหารฮาลาลปัตตานี, ร้านตัดผมยะลา, โรงแรมเบตง) |
| **3. Pricing & Reviews** | 6–11 | Scraper เมนู + entity resolution + จับคู่สินค้า, Pricing view + economics + quadrant, ติด label รีวิว (teacher → student), Reviews view, Proactive insights | Pricing ใช้ได้กับ F&B, Reviews ใช้ได้ทุกอุตสาหกรรม |
| **4. ML** | 9–13 | Python ML Service, features, 6 โมเดล + baseline, GroupKFold, tuning, SHAP, ML Lab, What-If, (Should) ราคาห้องพัก + ML Hospitality | leaderboard + model card + API ทำงานพร้อม fallback cache |
| **5. Copilot** | 12–15 | semantic layer, intent templates, guardrail + tests, ชุดคำถาม/ชุดโจมตี, drawer UI | EX ≥ 70%, block 100%, Data Lineage UI |
| **6. Testing & Hardening** | 15–17 | test case + E2E, แบบประเมินความพึงพอใจ, performance, security review, Should ที่เหลือ | รายงานผลทดสอบ + ผลประเมิน |
| **7. เล่ม & สอบ** | 17–20 | เขียนเล่ม, Defense Mode, วิดีโอสำรอง, ซ้อมนำเสนอ | เล่มฉบับสมบูรณ์ + สไลด์ + demo script |

**Defense Mode (กันเดโมพังวันสอบ):** pre-warm Supabase และ Python service ก่อนสอบ 30 นาที, cache คำตอบของคำถามเดโมที่เตรียมไว้ (ใช้เมื่อ Gemini ล่มหรือ quota หมด), ใช้ `ml.prediction_cache` เมื่อ Python service ไม่ตอบ, วิดีโอบันทึกเดโมเต็ม flow เป็นแผนสำรองสุดท้าย

---

## 13. โครงสร้าง Repository v2

```text
southbiz-pulse-bi/
├── CONTEXT.md · ARCHITECTURE.md · PLAN.md · DESIGN_SYSTEM.md
├── docs/
│   ├── adr/                          # Architecture Decision Records (0001-scraping-governance.md, ...)
│   ├── data-dictionary.md            # สร้างจาก dbt docs
│   └── scraping-governance.md
├── .github/workflows/                # ci, daily_reference, enrich_and_build, monthly_snapshot, scrape_* (self-hosted)
├── supabase/
│   ├── migrations/                   # 001_schemas_roles · 002_dw_dims · 003_dw_facts_maps · 004_app_rls · 005_ml_ops · 006_rpc
│   ├── seed/                         # industry_pack.sql, std_items_*.csv, holidays_th_my.csv, demo personas
│   └── tests/                        # pgTAP: RLS + สิทธิ์ของ role
├── scraper/                          # Playwright (E + L)
│   ├── sources/ (google_maps/, grab/, lineman/, lodging/)
│   ├── selectors.yaml                # selector ทั้งหมดอยู่ที่เดียว
│   ├── queue.py · pii_scrub.py · entity_resolution.py
│   └── tests/ (smoke tests กับร้านตัวอย่าง)
├── etl/                              # API อ้างอิง: fx.py, weather.py, tourism.py, holidays.py, synthetic/
├── dbt/                              # T: staging → intermediate → dw → mart + tests
├── ml/                               # training (รันบนเครื่อง/Colab/CI)
│   ├── features.py · train_benchmark.py · sentiment_student.py · MODEL_CARD.md
├── services/ml-api/                  # Python ML Service (FastAPI + Dockerfile)
│   ├── app/ (predict.py, label.py, match.py, vision.py)
│   └── tests/
├── copilot-eval/                     # questions.yaml · adversarial.yaml · run_eval.ts
└── src/
    ├── app/
    │   ├── (auth)/login/ · onboarding/
    │   ├── workspace/ (overview, radar, pricing, reviews, ml-lab, location)
    │   ├── admin/ (scrapers, mapping-queue, entity-queue, data-quality)
    │   └── api/ (copilot/query, catalog/vision, insights, health)
    ├── components/ (charts/, cards/, map/, tables/)
    ├── lib/
    │   ├── economics/                # pure functions + Vitest
    │   ├── sql-guardrail/            # AST validator + attack tests
    │   ├── industry-pack/            # อ่าน config + ป้ายตามอุตสาหกรรม
    │   ├── llm/                      # provider abstraction (ตั้ง model ผ่าน env)
    │   ├── ml-client.ts              # เรียก Python service + fallback cache
    │   └── supabase/
    └── i18n/ (th.json, en.json)
```

---

## 14. Mapping เข้าสู่รูปเล่มโครงงาน (5 บท)

| บท | เนื้อหาจากโปรเจกต์ |
|---|---|
| 1 บทนำ | ที่มาและความสำคัญ (SME ชายแดนใต้), วัตถุประสงค์, ขอบเขต (4 จังหวัด, 5 sector), ประโยชน์ที่คาดว่าจะได้รับ, แผนการดำเนินงาน (Gantt จากหัวข้อ 12) |
| 2 ทฤษฎีและเทคโนโลยีที่เกี่ยวข้อง | Data Warehouse / Galaxy schema (Kimball), Web scraping, BI & Decision Support, Menu Engineering, Huff model, Aspect-based sentiment, ML regression (6 อัลกอริทึม), SHAP, Text-to-SQL, PostGIS, PDPA + **ระบบที่คล้ายกัน** (เช่น Google Business Profile insights, Wongnai/LINE MAN Merchant, Grab Merchant) เทียบจุดต่าง |
| 3 การวิเคราะห์และออกแบบระบบ | Use case, Activity/DFD, สถาปัตยกรรม + deployment topology, Galaxy schema/ERD, scraping pipeline + governance, dbt lineage, ML pipeline, การออกแบบ UI (DESIGN_SYSTEM) |
| 4 ผลการพัฒนาและการทดสอบ | หน้าจอระบบ, ผลการทดสอบฟังก์ชัน, สถิติข้อมูลที่เก็บได้, ผล DQ, ผล ML (leaderboard + SHAP), ผล Copilot, ผลประเมินความพึงพอใจ |
| 5 สรุปและข้อเสนอแนะ | สรุปผล, ปัญหาและอุปสรรค (เช่น scraper โดน block, ข้อมูลราคาบางในบางอุตสาหกรรม), ข้อเสนอแนะ (เชื่อม POS เพื่อทำ demand model) |

---

## 15. คำถามที่ยังต้องตัดสินใจ

| # | คำถาม | ค่าที่แนะนำ (⭐) ถ้ายังไม่ตอบจะใช้ค่านี้ |
|---|---|---|
| Q1 | ทีมกี่คน และวันสอบ/ส่งเล่มเมื่อไร | ใช้ roadmap 20 สัปดาห์ตามหัวข้อ 12 |
| Q4 | Chart library | ⭐ Apache ECharts (ครอบคลุมกราฟใน design ทุกแบบ) แทน Recharts |
| Q5 | ชั้น Transform | ⭐ เพิ่ม dbt-core |
| Q8 | Host ของ Python ML Service | ⭐ Hugging Face Spaces (Docker) + keep-alive / ทางเลือก Cloud Run หรือ Oracle VM |
| Q9 | การติด label รีวิว | ⭐ Teacher–student (ฟรี) / ทางเลือก Gemini paid tier |
| Q10 | ที่รัน scraper | ⭐ GitHub self-hosted runner บนเครื่องตัวเอง / ทางเลือก VM |
| Q11 | ขอบเขตข้ามแดน | ⭐ กลันตัน + เคดาห์ + ปีนัง (เประเฉพาะคู่เทียบของเบตง) |
| Q7 | อาจารย์เน้น DE หรือ DS มากกว่ากัน | ปรับน้ำหนักระหว่าง dbt/warehouse กับ ML/การทดสอบ |

**ตัดสินใจแล้ว:** Q2 = Scraping (อาจารย์แนะนำ) · Q3 = ครบทุกธุรกิจ (Industry Pack) · Q6 = ไม่ลงพื้นที่ · พื้นที่นำร่อง = สงขลา ยะลา ปัตตานี นราธิวาส · Python deploy แยก · ไม่ใช้ embedding
