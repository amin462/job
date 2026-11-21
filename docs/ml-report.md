# รายงานการทดลองและประเมินผลโมเดล ML ประมาณเงินเดือน (ML Evaluation Report — T4.4 / T4.7)

> **Dataset Version:** `clean_postings_n102_a95df702` · **จำนวนแถวมีเงินเดือนที่ใช้เทรน:** 102 จากทั้งหมด 291 ประกาศ · **จำนวนบริษัท (Groups):** 67 บริษัท · **Champion:** `XGBoost`

## 1. การออกแบบการทดลองและความเป็นธรรมของโมเดล (Experimental Design & Fairness D6/D15)

- **ตัวแปรเป้าหมาย (Target):** `log(salary_mid)` เฉพาะประกาศที่ `has_salary == True` และ `salary_mid ∈ [5,000, 500,000]` บาท/เดือน (รายงานผลกลับเป็นบาทด้วย `exp(pred)`)
- **ตัวแปรต้น (Features):** `occupation_cluster`, `province_th`, `region`, `experience_band`, `education_level`, `employment_type_derived`, `seniority_level`, `industry`, `n_skills`, `education_rank`, `exp_years_mid`, และ multi-hot ทักษะยอดนิยม (Top 40 ทักษะ รวม 51 คอลัมน์)
- **การป้องกันอคติ (Fairness Guard D6):** **ไม่ใช้** `gender`, `mentions_gender`, `age`, `mentions_age`, `company`, `company_name`, และ `company_name_norm` เป็น feature ของโมเดลโดยเด็ดขาด
- **การแบ่งข้อมูลแบบ Nested Cross-Validation (D15):** Outer CV ใช้ `GroupKFold(n_splits=5)` แบ่งตาม `company_name_norm` (ทับซ้อนระหว่าง train/val = 0 บริษัทในทุก fold) · Inner Hyperparameter Tuning ใช้ `GroupKFold(n_splits=3)` เฉพาะภายใน outer train fold (`<= 6` trials/model/fold) ทำให้ outer validation fold ไม่รั่วไหลเข้าสู่การเลือก hyperparameter
- **การเสิร์ฟในระบบจริง (D19):** ใช้เฉพาะ **Champion ตัวเดียว** (`XGBoost`) ผ่าน FastAPI `services/ml-api` พร้อมตาราง fallback `mart.salary_prediction`

## 2. ตารางเปรียบเทียบผลโมเดล (Leaderboard: Mean ± SD across Outer Folds)

| อันดับ | โมเดล | R² (Mean ± SD) | RMSE บาท (Mean ± SD) | MAE บาท (Mean ± SD) | MAPE % (Mean ± SD) | Avg Fit+Tune (s) | สถานะ |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | `XGBoost` | 0.2577 ± 0.2659 | 9,083.5 ± 2,267.1 | 6,002.6 ± 796.0 | 25.78% ± 2.85% | 1.699 | **Champion** |
| 2 | `CatBoost` | 0.2710 ± 0.2402 | 9,102.2 ± 2,571.5 | 5,960.5 ± 1,190.6 | 25.36% ± 4.72% | 1.864 | Benchmark |
| 3 | `RandomForest` | 0.2756 ± 0.2005 | 9,136.4 ± 2,690.3 | 6,060.2 ± 1,152.7 | 25.02% ± 3.56% | 1.256 | Benchmark |
| 4 | `LightGBM` | 0.2402 ± 0.3310 | 9,257.1 ± 3,111.3 | 6,267.9 ± 1,661.5 | 27.54% ± 7.02% | 0.234 | Benchmark |
| 5 | `Ridge` | 0.1535 ± 0.4455 | 9,598.6 ± 2,804.8 | 6,247.6 ± 1,349.5 | 26.11% ± 3.51% | 0.038 | Benchmark |
| 6 | `Baseline` | -0.1472 ± 0.6381 | 10,834.8 ± 3,093.6 | 7,717.4 ± 1,824.2 | 32.02% ± 5.00% | 0.001 | Baseline |

- **ผลการเทียบกับ Baseline:** Champion `XGBoost` มี RMSE เฉลี่ย `9,083.51` บาท เทียบกับ Baseline `10,834.81` บาท (ลด RMSE ลง `16.2%` — **ดีกว่า Baseline**)
- **ช่วงความไม่แน่นอนของค่าคาด (`p25–p75` จาก Out-of-Fold Log Residuals):** `q25_offset = -0.1775`, `q75_offset = +0.2211` (`p25 = exp(ŷ + q25)`, `p50 = exp(ŷ)`, `p75 = exp(ŷ + q75)`)

## 3. เสถียรภาพราย Fold และยืนยันการไม่รั่วไหลข้ามบริษัท (Per-Fold Stability)

| Fold | Train Rows (Companies) | Val Rows (Companies) | Company Overlap | Champion RMSE (THB) | Champion MAE (THB) | Champion MAPE (%) | Baseline RMSE (THB) |
|---:|---|---|---:|---:|---:|---:|---:|
| 0 | 81 (53) | 21 (14) | 0 | 9,917.2 | 6,137.9 | 21.78% | 13,529.7 |
| 1 | 81 (53) | 21 (14) | 0 | 7,491.4 | 5,701.0 | 26.31% | 11,626.3 |
| 2 | 82 (54) | 20 (13) | 0 | 6,181.5 | 4,790.7 | 24.27% | 7,651.6 |
| 3 | 82 (54) | 20 (13) | 0 | 11,964.5 | 6,748.9 | 27.45% | 7,504.2 |
| 4 | 82 (54) | 20 (13) | 0 | 9,862.9 | 6,634.7 | 29.11% | 13,862.2 |

## 4. ความสำคัญของตัวแปร (Permutation Feature Importance — Top 15)

| อันดับ | Feature | Importance (Δ R²) | Std |
|---:|---|---:|---:|
| 1 | `exp_years_mid` | 0.4077 | 0.0843 |
| 2 | `education_level` | 0.1670 | 0.0372 |
| 3 | `skill__qc_qa_inspection` | 0.1078 | 0.0197 |
| 4 | `skill__chinese_mandarin` | 0.0296 | 0.0098 |
| 5 | `n_skills` | 0.0289 | 0.0122 |
| 6 | `education_rank` | 0.0257 | 0.0095 |
| 7 | `province_th` | 0.0168 | 0.0053 |
| 8 | `skill__service_mind` | 0.0109 | 0.0039 |
| 9 | `occupation_cluster` | 0.0100 | 0.0028 |
| 10 | `skill__inventory_stock_control` | 0.0090 | 0.0032 |
| 11 | `experience_band` | 0.0072 | 0.0033 |
| 12 | `industry` | 0.0036 | 0.0017 |
| 13 | `skill__microsoft_excel` | 0.0035 | 0.0010 |
| 14 | `skill__problem_solving_analytical_thinking` | 0.0024 | 0.0009 |
| 15 | `skill__payroll_benefits_administration` | 0.0012 | 0.0014 |

## 5. การวิเคราะห์ความคลาดเคลื่อนตามกลุ่มอาชีพและภูมิภาค (Error Analysis — T4.7)

### 5.1 รายกลุ่มอาชีพ (Occupation Cluster — Out-of-Fold)
| กลุ่มอาชีพ | n | ค่าเฉลี่ยจริง (บาท) | ค่าเฉลี่ยคาด (บาท) | RMSE (บาท) | MAE (บาท) | MAPE (%) |
|---|---:|---:|---:|---:|---:|---:|
| Sales & Business Development | 18 | 21,069 | 20,967 | 6,758.8 | 5,616.7 | 28.83% |
| Technician & Maintenance | 15 | 19,100 | 18,312 | 4,240.1 | 2,934.5 | 14.29% |
| Supply Chain, Logistics & Warehouse | 13 | 22,506 | 20,280 | 6,428.9 | 4,746.7 | 20.28% |
| Accounting & Finance | 10 | 24,300 | 24,346 | 8,322.4 | 7,379.2 | 36.08% |
| Admin, Coordination & Procurement | 8 | 18,500 | 19,986 | 4,585.2 | 4,167.5 | 23.00% |
| Manufacturing, Production & QA/QC | 8 | 27,445 | 24,929 | 14,805.4 | 9,644.1 | 43.04% |
| Engineering & Design | 7 | 30,429 | 26,512 | 12,198.0 | 6,529.5 | 15.07% |
| Customer Service & Call Center | 5 | 17,700 | 20,668 | 3,283.3 | 2,968.2 | 18.18% |
| Marketing & Digital Content | 5 | 23,400 | 22,806 | 5,193.8 | 4,120.6 | 16.79% |
| Safety, Environment & Sustainability | 3 | 22,500 | 25,399 | 5,519.3 | 4,370.3 | 22.70% |
| Software & IT | 3 | 49,167 | 28,080 | 28,219.4 | 21,087.0 | 37.68% |
| Food, Beverage & Culinary | 2 | 17,250 | 20,543 | 3,900.6 | 3,292.7 | 20.53% |
| Driving & Fleet Operations | 1 | 17,500 | 14,319 | 3,180.9 | 3,180.9 | 18.18% |
| Other / General | 1 | 10,400 | 16,917 | 6,517.2 | 6,517.2 | 62.67% |
| Translation & Languages | 1 | 29,500 | 18,689 | 10,810.6 | 10,810.6 | 36.65% |
| Human Resources | 1 | 25,000 | 42,550 | 17,549.5 | 17,549.5 | 70.20% |
| Management & Operations | 1 | 37,500 | 18,674 | 18,825.8 | 18,825.8 | 50.20% |

### 5.2 รายภูมิภาค (Region — Out-of-Fold)
| ภูมิภาค | n | ค่าเฉลี่ยจริง (บาท) | ค่าเฉลี่ยคาด (บาท) | RMSE (บาท) | MAE (บาท) | MAPE (%) |
|---|---:|---:|---:|---:|---:|---:|
| กลาง | 90 | 23,414 | 22,076 | 9,713.4 | 6,239.4 | 26.32% |
| ตะวันออก | 9 | 20,389 | 19,803 | 5,035.6 | 3,956.9 | 19.35% |
| ไม่ระบุ | 2 | 26,250 | 23,899 | 4,296.8 | 3,596.8 | 13.31% |
| อีสาน | 1 | 13,500 | 21,249 | 7,749.0 | 7,749.0 | 57.40% |

## 6. ข้อจำกัดและอคติในการเลือกตัวอย่าง (Limitations & Selection Bias)

1. **Selection Bias ของประกาศที่เปิดเผยเงินเดือน:** โมเดลเทรนเฉพาะประกาศที่มีตัวเลขเงินเดือนชัดเจนเท่านั้น ส่วนตำแหน่งระดับสูงหรือเฉพาะทางมักระบุว่า *"ตามโครงสร้างบริษัท / ตามตกลง"* ซึ่งถูกตัดออกจากชุดเทรน ทำให้ค่าคาดการณ์อาจเอนเอียงไปทางระดับปฏิบัติการหรือระดับต้น-กลาง
2. **เงินเดือนที่ประกาศ ≠ รายได้สุทธิจริง:** ตัวเลขเป้าหมาย `salary_mid` คำนวณจากค่ากึ่งกลางช่วงเงินเดือนฐาน (หรือขั้นต่ำกรณี *"ขึ้นไป"*) โดยไม่รวมค่าคอมมิชชั่น โบนัส หรือค่าล่วงเวลา
3. **ความครอบคลุมของข้อมูลรายกลุ่มย่อย:** กลุ่มอาชีพหรือจังหวัดที่มีจำนวนตัวอย่างน้อย (`n < 5`) มีความแปรปรวนสูง ระบบจึงแจ้งเตือน `out_of_domain` / `low_support_warning` และแสดงค่าเป็นช่วง `p25–p75` พร้อมข้อความกำกับว่า *"ประมาณการจากประกาศที่ระบุเงินเดือน ไม่ใช่เงินเดือนจริง"*
4. **การสุ่มแบบแบ่งชั้น vs การเทรน:** ตารางสถิติใน `mart.*` ถ่วงน้ำหนักด้วย `sample_weight` แต่โมเดล ML เทรนบนแถวประกาศจริงโดยไม่ถ่วงน้ำหนัก (PLAN §6) เพื่อสะท้อนความสัมพันธ์ระดับตำแหน่งงานจริง
