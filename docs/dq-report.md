# รายงานคุณภาพข้อมูล (Data Quality Report — T3.3 / T8.2)

> **แหล่งข้อมูล:** PostgreSQL Staging (staging.job_posting_raw + listing_seen) · **รายการที่อ่าน:** 291 (ล้มเหลว 0) · **ประกาศหลังหักซ้ำ (Unique Postings):** 291 ประกาศ

## 1. สรุปภาพรวม (Summary Metrics)

| ตัวชี้วัด | ค่า | เกณฑ์เป้าหมาย |
|---|---|---|
| จำนวนประกาศที่ไม่ซ้ำ (`fact_job_posting`) | 291 | — |
| ครอบคลุมจังหวัด | 15 จังหวัด | — |
| ระบุเงินเดือนตัวเลขถูกต้อง `[5,000–500,000]` | 102/291 (35.1%) | — |
| ดึงทักษะได้ `>= 1` ทักษะ | 287/291 (98.6%) | >= 90% |
| ค่าเฉลี่ยทักษะต่อประกาศ | 5.7 | — |
| จัดกลุ่ม Occupation Cluster ได้ | 289/291 (99.3%) | >= 85% |
| ดึงวุฒิการศึกษาได้ | 253/291 (86.9%) | >= 80% |
| ดึงประสบการณ์ทำงานได้ | 141/291 (48.5%) | รายงานตรงตามข้อมูล |
| ระบุเพศ / อายุ (ติดตามเพื่อ Fairness เท่านั้น, ห้ามเข้า ML) | 51.2% / 55.3% | 0% ใน ML features |

## 2. ผลการตรวจสอบคุณภาพข้อมูล 8 ด้าน (Data Quality Checks)

| ด้าน (Dimension) | Check | ตาราง | จำนวนตรวจ | ไม่ผ่าน | ผลลัพธ์ | รายละเอียด |
|---|---|---|---:|---:|:---:|---|
| Completeness | `Completeness: core_fields_complete` | `dw.fact_job_posting` | 291 | 2 | **PASS** | Core fields (title, province, category, company) complete: 289/291 (99.3%) |
| Completeness | `Completeness: numeric_salary_rate` | `dw.fact_job_posting` | 291 | 189 | **PASS** | Numeric salary available: 102/291 (35.1%) |
| Validity | `Validity: salary_bounds_and_order` | `dw.fact_job_posting` | 102 | 0 | **PASS** | Valid monthly THB [5000, 500000] & min<=max: 102/102; quarantined out-of-range=1 |
| Validity | `Validity: canonical_province_and_date` | `dw.dim_location` | 291 | 2 | **FAIL** | Canonical provinces=289/291, non-future date_posted=291/291 |
| Uniqueness | `Uniqueness: source_job_id_dedup` | `dw.fact_job_posting` | 291 | 0 | **PASS** | Duplicate (source, source_job_id)=0; identical content_hash across distinct IDs=0 |
| Consistency | `Consistency: occupation_cluster_mapping` | `dw.dim_occupation` | 291 | 2 | **PASS** | Mapped to occupation cluster: 289/291 (99.3%); companies consolidated 149 -> 149 |
| Freshness | `Freshness: active_and_recent_postings` | `dw.fact_job_posting` | 291 | 0 | **PASS** | Within 60d of reference (2026-11-19): 291/291; expired valid_through=0 |
| Taxonomy | `Taxonomy: skill_extraction_coverage` | `dw.fact_posting_skill` | 291 | 4 | **PASS** | Postings with >=1 skill: 287/291 (98.6%); pending unmapped candidates queued=100 |
| Compliance | `Compliance: pdpa_tos_and_ml_fairness` | `dw.fact_job_posting` | 45 | 0 | **PASS** | HR contact columns=[], PII value leaks=0, raw text leak=[], forbidden ML cols=[]; DQ-only mentions_gender=149/291 (51.2%), mentions_age=161/291 (55.3%) |
| Sampling | `Sampling: stratum_and_weight_conservation` | `dw.fact_job_posting` | 291 | 0 | **PASS** | Valid stratum+weight=291/291; checked 100 strata vs N_h; mismatches=0 |

## 3. การกระจายตามภูมิภาคและกลุ่มอาชีพ

### ภูมิภาค (Region)
| ภูมิภาค | จำนวนประกาศ |
|---|---:|
| กลาง | 232 |
| ตะวันออก | 50 |
| ไม่ระบุ | 6 |
| อีสาน | 2 |
| ตะวันตก | 1 |

### กลุ่มอาชีพ (Top 15 Occupation Clusters)
| กลุ่มอาชีพ | จำนวนประกาศ |
|---|---:|
| Technician & Maintenance | 51 |
| Sales & Business Development | 48 |
| Manufacturing, Production & QA/QC | 37 |
| Accounting & Finance | 34 |
| Supply Chain, Logistics & Warehouse | 25 |
| Engineering & Design | 18 |
| Admin, Coordination & Procurement | 17 |
| Marketing & Digital Content | 15 |
| Customer Service & Call Center | 12 |
| Safety, Environment & Sustainability | 8 |
| Driving & Fleet Operations | 6 |
| Human Resources | 5 |
| Food, Beverage & Culinary | 3 |
| Translation & Languages | 3 |
| Software & IT | 3 |

## 4. ทักษะยอดนิยมที่สกัดได้และคิว Alias Pending

### Top 15 Skills
| ทักษะ | จำนวนประกาศ |
|---|---:|
| Communication | 165 |
| Problem Solving & Analytical Thinking | 101 |
| Attention to Detail & Integrity | 97 |
| Sales & Closing | 73 |
| Mechanical & Maintenance (PM/CM) | 65 |
| English | 58 |
| Microsoft Office | 57 |
| Production Operations | 54 |
| Microsoft Excel | 51 |
| Accounting | 51 |
| Electrical Systems | 44 |
| Teamwork & Collaboration | 40 |
| Warehouse & Logistics | 38 |
| QC / QA Inspection | 35 |
| Payroll & Benefits Administration | 31 |

### ตัวอย่างคำใหม่ในคิว Alias Pending (Top 15 จากทั้งหมด 100 คำ — ใช้กฎ `pg_trgm similarity >= 0.4` ไม่ใช้ AI)
| คำที่พบ | ความถี่ (ประกาศ) | ทักษะที่กฎเสนอ | Alias ที่คล้ายที่สุด | Similarity |
|---|---:|---|---|---:|
| `เอกสาร` | 88 | Translation & Interpretation | แปลเอกสาร | 0.417 |
| `ติดตาม` | 84 | Credit Analysis & Debt Collection | ติดตามหนี้ | 0.500 |
| `ระดับ` | 81 | - | - | - |
| `วิเคราะห์` | 77 | Problem Solving & Analytical Thinking | วิเคราะห์ปัญหา | 0.562 |
| `ควบคุม` | 75 | Auditing & Internal Control | ควบคุมภายใน | 0.462 |
| `ทีม` | 75 | - | - | - |
| `เพศชาย` | 66 | - | - | - |
| `บันทึก` | 60 | - | - | - |
| `โปรแกรม` | 58 | Microsoft Word | โปรแกรม word | 0.615 |
| `ปวส.` | 57 | - | - | - |
| `รอบคอบ` | 57 | - | - | - |
| `คุณภาพ` | 55 | QC / QA Inspection | ควบคุมคุณภาพ | 0.429 |
| `ละเอียด` | 53 | Attention to Detail & Integrity | ละเอียดรอบคอบ | 0.467 |
| `office` | 52 | Microsoft Office | ms office | 0.545 |
| `หน่วยงาน` | 52 | - | - | - |
