# รายงานการทดลองและประเมินผลโมเดล ML ประมาณเงินเดือน (ML Evaluation Report — T4.4 / T4.7)

> **Dataset Version:** `clean_postings_n70_376eaa66` · **จำนวนแถวมีเงินเดือนที่ใช้เทรน:** 70 จากทั้งหมด 126 ประกาศ · **จำนวนบริษัท (Groups):** 31 บริษัท · **Champion:** `Ridge`

## 1. การออกแบบการทดลองและความเป็นธรรมของโมเดล (Experimental Design & Fairness D6/D15)

- **ตัวแปรเป้าหมาย (Target):** `log(salary_mid)` เฉพาะประกาศที่ `has_salary == True` และ `salary_mid ∈ [5,000, 500,000]` บาท/เดือน (รายงานผลกลับเป็นบาทด้วย `exp(pred)`)
- **ตัวแปรต้น (Features):** `occupation_cluster`, `province_th`, `region`, `experience_band`, `education_level`, `employment_type`, `industry`, `n_skills`, `education_rank`, `exp_years_mid`, และ multi-hot ทักษะยอดนิยม (Top 40 ทักษะ รวม 50 คอลัมน์)
- **การป้องกันอคติ (Fairness Guard D6):** **ไม่ใช้** `gender`, `mentions_gender`, `age`, `mentions_age`, `company`, `company_name`, และ `company_name_norm` เป็น feature ของโมเดลโดยเด็ดขาด
- **การแบ่งข้อมูลแบบ Nested Cross-Validation (D15):** Outer CV ใช้ `GroupKFold(n_splits=5)` แบ่งตาม `company_name_norm` (ทับซ้อนระหว่าง train/val = 0 บริษัทในทุก fold) · Inner Hyperparameter Tuning ใช้ `GroupKFold(n_splits=3)` เฉพาะภายใน outer train fold (`<= 6` trials/model/fold) ทำให้ outer validation fold ไม่รั่วไหลเข้าสู่การเลือก hyperparameter
- **การเสิร์ฟในระบบจริง (D19):** ใช้เฉพาะ **Champion ตัวเดียว** (`Ridge`) ผ่าน FastAPI `services/ml-api` พร้อมตาราง fallback `mart.salary_prediction`

## 2. ตารางเปรียบเทียบผลโมเดล (Leaderboard: Mean ± SD across Outer Folds)

| อันดับ | โมเดล | R² (Mean ± SD) | RMSE บาท (Mean ± SD) | MAE บาท (Mean ± SD) | MAPE % (Mean ± SD) | Avg Fit+Tune (s) | สถานะ |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | `Ridge` | -0.1584 ± 0.7644 | 7,333.9 ± 5,388.6 | 5,152.5 ± 3,273.7 | 21.30% ± 10.86% | 0.208 | **Champion** |
| 2 | `RandomForest` | -0.0556 ± 0.3234 | 7,597.5 ± 5,350.6 | 5,534.0 ± 3,314.5 | 22.68% ± 11.26% | 9.386 | Benchmark |
| 3 | `LightGBM` | -0.2521 ± 0.4183 | 8,008.4 ± 5,139.0 | 6,077.1 ± 3,797.7 | 25.64% ± 14.48% | 1.357 | Benchmark |
| 4 | `CatBoost` | -0.1198 ± 0.1699 | 8,237.2 ± 5,668.4 | 5,804.6 ± 3,570.9 | 23.28% ± 12.47% | 9.693 | Benchmark |
| 5 | `XGBoost` | -0.1921 ± 0.3127 | 8,558.1 ± 5,791.7 | 6,105.7 ± 3,894.3 | 24.92% ± 14.43% | 10.095 | Benchmark |
| 6 | `Baseline` | -9.2035 ± 19.2905 | 10,045.3 ± 4,236.5 | 6,987.5 ± 2,767.5 | 29.63% ± 9.84% | 0.004 | Baseline |

- **ผลการเทียบกับ Baseline:** Champion `Ridge` มี RMSE เฉลี่ย `7,333.95` บาท เทียบกับ Baseline `10,045.26` บาท (ลด RMSE ลง `27.0%` — **ดีกว่า Baseline**)
- **ช่วงความไม่แน่นอนของค่าคาด (`p25–p75` จาก Out-of-Fold Log Residuals):** `q25_offset = -0.1948`, `q75_offset = +0.0328` (`p25 = exp(ŷ + q25)`, `p50 = exp(ŷ)`, `p75 = exp(ŷ + q75)`)

## 3. เสถียรภาพราย Fold และยืนยันการไม่รั่วไหลข้ามบริษัท (Per-Fold Stability)

| Fold | Train Rows (Companies) | Val Rows (Companies) | Company Overlap | Champion RMSE (THB) | Champion MAE (THB) | Champion MAPE (%) | Baseline RMSE (THB) |
|---:|---|---|---:|---:|---:|---:|---:|
| 0 | 46 (30) | 24 (1) | 0 | 1,375.3 | 1,109.6 | 5.71% | 5,861.9 |
| 1 | 58 (24) | 12 (7) | 0 | 4,857.6 | 3,615.3 | 17.61% | 5,382.8 |
| 2 | 58 (24) | 12 (7) | 0 | 4,430.3 | 3,984.9 | 21.26% | 11,680.3 |
| 3 | 59 (23) | 11 (8) | 0 | 13,950.7 | 8,650.2 | 27.17% | 15,043.4 |
| 4 | 59 (23) | 11 (8) | 0 | 12,055.9 | 8,402.5 | 34.73% | 12,257.9 |

## 4. ความสำคัญของตัวแปร (Permutation Feature Importance — Top 15)

| อันดับ | Feature | Importance (Δ R²) | Std |
|---:|---|---:|---:|
| 1 | `exp_years_mid` | 0.2811 | 0.0494 |
| 2 | `skill__english` | 0.0550 | 0.0114 |
| 3 | `industry` | 0.0527 | 0.0107 |
| 4 | `education_level` | 0.0507 | 0.0177 |
| 5 | `province_th` | 0.0467 | 0.0125 |
| 6 | `occupation_cluster` | 0.0326 | 0.0070 |
| 7 | `skill__chinese_mandarin` | 0.0238 | 0.0057 |
| 8 | `region` | 0.0219 | 0.0120 |
| 9 | `skill__document_control_administration` | 0.0169 | 0.0056 |
| 10 | `skill__civil_construction_supervision` | 0.0167 | 0.0073 |
| 11 | `skill__inventory_stock_control` | 0.0163 | 0.0035 |
| 12 | `experience_band` | 0.0150 | 0.0067 |
| 13 | `skill__attention_to_detail_integrity` | 0.0130 | 0.0053 |
| 14 | `skill__customer_service` | 0.0130 | 0.0059 |
| 15 | `skill__teaching_coaching` | 0.0122 | 0.0052 |

## 5. การวิเคราะห์ความคลาดเคลื่อนตามกลุ่มอาชีพและภูมิภาค (Error Analysis — T4.7)

### 5.1 รายกลุ่มอาชีพ (Occupation Cluster — Out-of-Fold)
| กลุ่มอาชีพ | n | ค่าเฉลี่ยจริง (บาท) | ค่าเฉลี่ยคาด (บาท) | RMSE (บาท) | MAE (บาท) | MAPE (%) |
|---|---:|---:|---:|---:|---:|---:|
| Sales & Business Development | 41 | 20,268 | 19,166 | 3,350.1 | 2,334.4 | 11.20% |
| Food, Beverage & Culinary | 4 | 22,438 | 22,907 | 3,433.6 | 2,727.5 | 14.34% |
| Technician & Maintenance | 4 | 19,875 | 22,402 | 3,749.6 | 3,103.0 | 19.46% |
| Supply Chain, Logistics & Warehouse | 3 | 14,417 | 19,280 | 4,876.7 | 4,863.4 | 33.92% |
| Marketing & Digital Content | 3 | 22,167 | 20,352 | 7,009.9 | 6,123.4 | 28.38% |
| Construction & Architecture | 3 | 36,167 | 22,670 | 21,427.8 | 17,418.5 | 43.48% |
| Accounting & Finance | 2 | 22,750 | 23,309 | 1,902.7 | 1,818.6 | 7.88% |
| Customer Service & Call Center | 2 | 18,500 | 21,792 | 3,679.8 | 3,292.0 | 18.33% |
| Management & Operations | 2 | 17,500 | 21,849 | 4,349.8 | 4,349.4 | 24.91% |
| Manufacturing, Production & QA/QC | 2 | 15,500 | 20,436 | 5,488.2 | 4,935.6 | 34.41% |
| Hospitality, Tourism & Front Office | 1 | 17,000 | 19,331 | 2,330.5 | 2,330.5 | 13.71% |
| Agriculture & Agro-Industry | 1 | 12,000 | 20,046 | 8,045.7 | 8,045.7 | 67.05% |
| Translation & Languages | 1 | 47,500 | 19,620 | 27,880.1 | 27,880.1 | 58.69% |
| Admin, Coordination & Procurement | 1 | 55,000 | 20,881 | 34,118.7 | 34,118.7 | 62.03% |

### 5.2 รายภูมิภาค (Region — Out-of-Fold)
| ภูมิภาค | n | ค่าเฉลี่ยจริง (บาท) | ค่าเฉลี่ยคาด (บาท) | RMSE (บาท) | MAE (บาท) | MAPE (%) |
|---|---:|---:|---:|---:|---:|---:|
| กลาง | 22 | 19,318 | 20,013 | 4,405.2 | 3,772.4 | 21.38% |
| อีสาน | 18 | 18,778 | 18,684 | 2,925.8 | 2,193.8 | 12.60% |
| ใต้ | 13 | 27,750 | 23,038 | 14,181.5 | 8,204.0 | 23.16% |
| เหนือ | 8 | 18,625 | 19,143 | 2,407.3 | 1,801.2 | 9.96% |
| ตะวันออก | 5 | 25,800 | 20,446 | 13,174.7 | 8,453.4 | 27.71% |
| ตะวันตก | 3 | 20,583 | 18,506 | 2,244.3 | 2,077.0 | 9.93% |
| ไม่ระบุ | 1 | 35,000 | 21,627 | 13,373.1 | 13,373.1 | 38.21% |

## 6. ข้อจำกัดและอคติในการเลือกตัวอย่าง (Limitations & Selection Bias)

1. **Selection Bias ของประกาศที่เปิดเผยเงินเดือน:** โมเดลเทรนเฉพาะประกาศที่มีตัวเลขเงินเดือนชัดเจนเท่านั้น ส่วนตำแหน่งระดับสูงหรือเฉพาะทางมักระบุว่า *"ตามโครงสร้างบริษัท / ตามตกลง"* ซึ่งถูกตัดออกจากชุดเทรน ทำให้ค่าคาดการณ์อาจเอนเอียงไปทางระดับปฏิบัติการหรือระดับต้น-กลาง
2. **เงินเดือนที่ประกาศ ≠ รายได้สุทธิจริง:** ตัวเลขเป้าหมาย `salary_mid` คำนวณจากค่ากึ่งกลางช่วงเงินเดือนฐาน (หรือขั้นต่ำกรณี *"ขึ้นไป"*) โดยไม่รวมค่าคอมมิชชั่น โบนัส หรือค่าล่วงเวลา
3. **ความครอบคลุมของข้อมูลรายกลุ่มย่อย:** กลุ่มอาชีพหรือจังหวัดที่มีจำนวนตัวอย่างน้อย (`n < 5`) มีความแปรปรวนสูง ระบบจึงแจ้งเตือน `out_of_domain` / `low_support_warning` และแสดงค่าเป็นช่วง `p25–p75` พร้อมข้อความกำกับว่า *"ประมาณการจากประกาศที่ระบุเงินเดือน ไม่ใช่เงินเดือนจริง"*
4. **การสุ่มแบบแบ่งชั้น vs การเทรน:** ตารางสถิติใน `mart.*` ถ่วงน้ำหนักด้วย `sample_weight` แต่โมเดล ML เทรนบนแถวประกาศจริงโดยไม่ถ่วงน้ำหนัก (PLAN §6) เพื่อสะท้อนความสัมพันธ์ระดับตำแหน่งงานจริง
