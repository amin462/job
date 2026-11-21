# รายงานคุณภาพข้อมูล (Data Quality Report — T3.3 / T8.2)

> **แหล่งข้อมูล:** JobThai HTML Snapshot · **ไฟล์ที่อ่าน:** 131 ไฟล์ (ล้มเหลว 0) · **ประกาศหลังหักซ้ำ (Unique Postings):** 126 ประกาศ

## 1. สรุปภาพรวม (Summary Metrics)

| ตัวชี้วัด | ค่า | เกณฑ์เป้าหมาย |
|---|---|---|
| จำนวนประกาศที่ไม่ซ้ำ (`fact_job_posting`) | 126 | — |
| ครอบคลุมจังหวัด | 76 จังหวัด | — |
| ระบุเงินเดือนตัวเลขถูกต้อง `[5,000–500,000]` | 70/126 (55.6%) | — |
| ดึงทักษะได้ `>= 1` ทักษะ | 126/126 (100.0%) | >= 90% |
| ค่าเฉลี่ยทักษะต่อประกาศ | 5.6 | — |
| จัดกลุ่ม Occupation Cluster ได้ | 126/126 (100.0%) | >= 85% |
| ดึงวุฒิการศึกษาได้ | 108/126 (85.7%) | >= 80% |
| ดึงประสบการณ์ทำงานได้ | 46/126 (36.5%) | รายงานตรงตามข้อมูล |
| ระบุเพศ / อายุ (ติดตามเพื่อ Fairness เท่านั้น, ห้ามเข้า ML) | 33.3% / 58.7% | 0% ใน ML features |

## 2. ผลการตรวจสอบคุณภาพข้อมูล 8 ด้าน (Data Quality Checks)

| ด้าน (Dimension) | Check | ตาราง | จำนวนตรวจ | ไม่ผ่าน | ผลลัพธ์ | รายละเอียด |
|---|---|---|---:|---:|:---:|---|
| Completeness | `Completeness: core_fields_complete` | `dw.fact_job_posting` | 126 | 0 | **PASS** | Core fields (title, province, category, company) complete: 126/126 (100.0%) |
| Completeness | `Completeness: numeric_salary_rate` | `dw.fact_job_posting` | 126 | 56 | **PASS** | Numeric salary available: 70/126 (55.6%) |
| Validity | `Validity: salary_bounds_and_order` | `dw.fact_job_posting` | 70 | 0 | **PASS** | Valid monthly THB [5000, 500000] & min<=max: 70/70; quarantined out-of-range=1 |
| Validity | `Validity: canonical_province_and_date` | `dw.dim_location` | 126 | 0 | **PASS** | Canonical provinces=126/126, non-future date_posted=126/126 |
| Uniqueness | `Uniqueness: source_job_id_dedup` | `dw.fact_job_posting` | 126 | 0 | **PASS** | Duplicate (source, source_job_id)=0; identical content_hash across distinct IDs=0 |
| Consistency | `Consistency: occupation_cluster_mapping` | `dw.dim_occupation` | 126 | 0 | **PASS** | Mapped to occupation cluster: 126/126 (100.0%); companies consolidated 53 -> 53 |
| Freshness | `Freshness: active_and_recent_postings` | `dw.fact_job_posting` | 126 | 0 | **PASS** | Within 60d of reference (2026-11-18): 126/126; expired valid_through=0 |
| Taxonomy | `Taxonomy: skill_extraction_coverage` | `dw.fact_posting_skill` | 126 | 0 | **PASS** | Postings with >=1 skill: 126/126 (100.0%); pending unmapped candidates queued=100 |
| Compliance | `Compliance: pdpa_tos_and_ml_fairness` | `dw.fact_job_posting` | 45 | 0 | **PASS** | HR contact columns=[], PII value leaks=0, raw text leak=[], forbidden ML cols=[]; DQ-only mentions_gender=42/126 (33.3%), mentions_age=74/126 (58.7%) |
| Sampling | `Sampling: stratum_and_weight_conservation` | `dw.fact_job_posting` | 126 | 0 | **PASS** | Valid stratum+weight=126/126; checked 78 strata vs N_h; mismatches=0 |

## 3. การกระจายตามภูมิภาคและกลุ่มอาชีพ

### ภูมิภาค (Region)
| ภูมิภาค | จำนวนประกาศ |
|---|---:|
| ใต้ | 42 |
| กลาง | 39 |
| อีสาน | 20 |
| ตะวันออก | 9 |
| เหนือ | 9 |
| ตะวันตก | 5 |
| ไม่ระบุ | 2 |

### กลุ่มอาชีพ (Top 15 Occupation Clusters)
| กลุ่มอาชีพ | จำนวนประกาศ |
|---|---:|
| Sales & Business Development | 56 |
| Technician & Maintenance | 8 |
| Manufacturing, Production & QA/QC | 8 |
| Accounting & Finance | 7 |
| Marketing & Digital Content | 6 |
| Construction & Architecture | 6 |
| Supply Chain, Logistics & Warehouse | 5 |
| Management & Operations | 4 |
| Food, Beverage & Culinary | 4 |
| Human Resources | 4 |
| Admin, Coordination & Procurement | 4 |
| Customer Service & Call Center | 3 |
| Translation & Languages | 2 |
| Agriculture & Agro-Industry | 2 |
| Engineering & Design | 2 |

## 4. ทักษะยอดนิยมที่สกัดได้และคิว Alias Pending

### Top 15 Skills
| ทักษะ | จำนวนประกาศ |
|---|---:|
| Sales & Closing | 64 |
| Communication | 63 |
| Attention to Detail & Integrity | 38 |
| Service Mind | 36 |
| Problem Solving & Analytical Thinking | 32 |
| Customer Service | 28 |
| Payroll & Benefits Administration | 28 |
| Negotiation & Persuasion | 24 |
| English | 22 |
| Mechanical & Maintenance (PM/CM) | 16 |
| QC / QA Inspection | 16 |
| Electrical Systems | 14 |
| Inventory & Stock Control | 14 |
| Microsoft Excel | 14 |
| Microsoft Office | 14 |

### ตัวอย่างคำใหม่ในคิว Alias Pending (Top 15 จากทั้งหมด 100 คำ — ใช้กฎ `pg_trgm similarity >= 0.4` ไม่ใช้ AI)
| คำที่พบ | ความถี่ (ประกาศ) | ทักษะที่กฎเสนอ | Alias ที่คล้ายที่สุด | Similarity |
|---|---:|---|---|---:|
| `เดินทาง` | 33 | - | - | - |
| `รัก` | 32 | - | - | - |
| `ทีม` | 31 | - | - | - |
| `หน้า` | 31 | - | - | - |
| `ติดตาม` | 30 | Credit Analysis & Debt Collection | ติดตามหนี้ | 0.500 |
| `ไลน์` | 30 | - | - | - |
| `วิเคราะห์` | 29 | Problem Solving & Analytical Thinking | วิเคราะห์ปัญหา | 0.562 |
| `kpi` | 29 | - | - | - |
| `ปัญหา` | 29 | - | - | - |
| `เบื้องต้น` | 29 | - | - | - |
| `ทัศนคติ` | 28 | - | - | - |
| `ระดับ` | 28 | - | - | - |
| `target` | 27 | - | - | - |
| `ปวส.` | 27 | - | - | - |
| `รอบ` | 27 | - | - | - |
