# Data Dictionary — ชุดข้อมูลประกาศงาน (E′ Skill Demand Intelligence)

> ปรับปรุง 21 พ.ย. 2569 · ตัวเลข "ครอบคลุม" วัดจากประกาศจริง JobThai n = 291 (ดึง 19 พ.ย.) ถ้าไม่ได้ระบุเป็นอย่างอื่น
> หลัก: **เก็บทุก field ที่เว็บแสดง ยกเว้นข้อมูลส่วนบุคคล (PDPA)** · เว็บสาธารณะแสดงเฉพาะสถิติรวม n ≥ 5 + ลิงก์ต้นฉบับ (AGENTS.md ข้อ 2)

## 1. ชั้นข้อมูล (data lineage)

| ชั้น | ที่เก็บ | สร้างโดย | เนื้อหา |
|---|---|---|---|
| L0 ดิบ | `data/jobthai.sqlite` (`job`, `listing`, `ref`, `meta` = สถานะรอบเก็บ) | `scraper/jobthai_harvester.py` | JSON-LD ของประกาศ (ตัด HR contact) + `x_jobthai` (ข้อมูลหน้ารายการ + หน้าประกาศ), N_h ต่อหน้ารายการ |
| L1 staging | `staging.listing_seen`, `staging.job_posting_raw` (Supabase) | `pipeline/scraper/import_sqlite.py` | ทุก id ที่เห็น + วันที่เห็น + ชั้นสุ่ม · ประกาศที่ parse แล้ว + `payload` (JSON-LD สะอาด) |
| L2 clean / DW | `data/processed/clean_postings.csv`, `dw.fact_job_posting`, `dw.fact_posting_skill` | `pipeline/etl/run_pipeline.py` (+ `enrich.py`) | 66 column ต่อประกาศ (หัวข้อ 3) |
| L3 mart | `mart.*` | `pipeline/etl/build_marts.py` | สถิติรวม n ≥ 5 สำหรับเว็บ |
| N_h | `data/processed/jobthai_strata.csv`, `jobthai_province_totals.csv` | `import_sqlite.py` | จำนวนประกาศทั้งหมดต่อชั้น (จังหวัด × ประเภทงาน) |

## 2. สิ่งที่ตัดทิ้งตาม PDPA (ไม่เก็บตั้งแต่ L0)

| ข้อมูล | วิธีตัด |
|---|---|
| `telephone`, `email`, `contactPoint`, `applicationContact` (JSON-LD) | ลบ key ตอน harvest (`PII_KEYS`) และตอน parse อีกชั้น (`HR_CONTACT_KEYS` + fax/contact/LINE) |
| ชื่อผู้ติดต่อ, เบอร์โทร, อีเมล, LINE ID ที่อยู่ในข้อความ | แทนด้วย `[phone]`, `[email]`, `[line]` (`scrub_text` ใน harvester, `scrub_pii` ใน parse) |
| ส่วน "ติดต่อ/สมัครงาน" ของหน้าประกาศ | ไม่อ่านเลย (อ่านเฉพาะ element `id="job-*"` ที่เป็นรายละเอียดงาน) |
| HTML ดิบ | ไม่เก็บ |

ข้อมูลระดับบริษัท (ชื่อบริษัท, โลโก้, เว็บไซต์) ไม่ใช่ข้อมูลส่วนบุคคล จึงเก็บไว้ แต่ **ห้ามใช้ชื่อบริษัทเป็น feature ของ ML** (ใช้เป็น group ของ GroupKFold เท่านั้น — D6)

## 3. Column ของชุดข้อมูลหลัก (L2: clean_postings / fact)

ความหมายของคอลัมน์ "ใช้":  **A** = วิเคราะห์/สถิติรวม · **ML** = feature ของโมเดลเงินเดือน · **T** = target · **G** = group ของ CV · **DQ** = ตรวจคุณภาพเท่านั้น · **W** = น้ำหนักสุ่ม

### 3.1 ตัวระบุและที่มา
| column | ที่มา | ครอบคลุม | ใช้ |
|---|---|---|---|
| `source`, `source_job_id`, `source_url` | harvester | 100% | A (ลิงก์ต้นฉบับ) |
| `content_hash` | SHA-256 ของเนื้อหา | 100% | dedupe |
| `first_seen_date_key`, `last_seen_date_key` | `listing_seen` | 100% | A (แนวโน้มรายสัปดาห์, D14) |
| `days_listed` ⟨ใหม่⟩ | last − first seen + 1 | 100% (ค่าจริงหลังเก็บหลายรอบ) | A (ตำแหน่งที่หาคนยาก) |

### 3.2 ตำแหน่งงานและหมวด
| column | ที่มา | ครอบคลุม | ใช้ |
|---|---|---|---|
| `title_short`, `job_title_norm` | JSON-LD `title` | 100% | A |
| `occupational_category` | JSON-LD (= ประเภทงาน JobThai 42 หมวด) | 100% | A, ชั้นสุ่ม |
| `occupation_cluster`, `occupation_slug` | `map_taxonomy.py` (21 กลุ่ม) | 100% | A, **ML** |
| `industry` | JSON-LD | 100% | A, **ML** |
| `seniority_level` ⟨ใหม่⟩ | กฎคำในชื่อตำแหน่ง: intern / junior / staff / officer / senior / supervisor / manager / director / ไม่ระบุ | ระบุได้ 87% | A, **ML** |
| `seniority_rank` ⟨ใหม่⟩ | ลำดับ 0–6 ของข้างบน | 87% | A |
| `employment_type` | JSON-LD | 100% แต่ **เป็น FULL_TIME ทุกแถว** | ไม่ใช้ (ไม่มีข้อมูล) |
| `employment_type_derived` ⟨ใหม่⟩ | คำในชื่อ/ข้อความ: full_time / contract / part_time / internship / freelance | 100% (contract 2%) | A, **ML** |

### 3.3 พื้นที่
| column | ที่มา | ครอบคลุม | ใช้ |
|---|---|---|---|
| `province_code`, `province_th`, `province_en`, `region`, `is_south14` | JSON-LD `addressRegion` + ตาราง 77 จังหวัด | 99% | A, **ML** (`province_th`, `region`) |
| `district_th` | JSON-LD `addressLocality` | 96% | A |
| `near_transit` ⟨ใหม่⟩ | หน้ารายการ (ใกล้ BTS/MRT) | เฉพาะประกาศที่เห็นในหน้ารายการตั้งแต่ 21 พ.ย. | A |
| `in_industrial_estate` ⟨ใหม่⟩ | หน้ารายการ (นิคมอุตสาหกรรม) | 〃 (~6% เป็นจริง) | A |
| `is_remote` ⟨ใหม่⟩ | `jobLocationType`/คำว่า WFH, remote, hybrid | 100% (จริง 3%) | A |

### 3.4 เงินเดือน
| column | ที่มา | ครอบคลุม | ใช้ |
|---|---|---|---|
| `salary_min`, `salary_max`, `salary_mid`, `salary_open_max`, `salary_unit_orig`, `salary_out_of_range`, `has_salary` | JSON-LD `baseSalary` + กฎ ARCH §5.1 | **มีตัวเลข 35%** (กทม. 50%, จังหวัดอุตสาหกรรม 18–26%) | **T** (`salary_mid`), A |
| `salary_disclosure` ⟨ใหม่⟩ | ข้อความเงินเดือนบนหน้าประกาศ: numeric / company_structure / negotiable / by_experience / other | 100% หลังดึงซ้ำ | A เท่านั้น (ห้ามเป็น feature — บอกเป้าหมายเอง) |

> เงินเดือนที่ไม่มีตัวเลข **ไม่มีอยู่ในเว็บจริง** (ตรวจแล้ว: หน้าเว็บก็เขียนแค่ "ตามโครงสร้างบริษัท/ตามตกลง") จึงเพิ่มไม่ได้ — ทางเพิ่มแถวเทรนคือเก็บประกาศให้มากขึ้น

### 3.5 คุณสมบัติ
| column | ที่มา | ครอบคลุม | ใช้ |
|---|---|---|---|
| `education_level` | regex ใน qualifications | ~100% (รวม "ไม่ระบุ") | A, **ML** |
| `experience_band` | regex | ~100% (63% "ไม่ระบุ") | A, **ML** |
| `accepts_fresh_grad` ⟨ใหม่⟩ | คำว่า จบใหม่ / ไม่มีประสบการณ์ก็ได้ / fresh grad | 100% (จริง 11%) | A (สำคัญกับนักศึกษา) |
| `n_skills`, `skills` (+ `dw.fact_posting_skill`) | dictionary + alias + PyThaiNLP `newmm` (ไม่ใช้ LLM) | ≥ 1 ทักษะ ~100% | A, **ML** (multi-hot 40 ทักษะ) |

### 3.6 สภาพการทำงานและสวัสดิการ ⟨ใหม่ทั้งหมด⟩
| column | ที่มา | ครอบคลุม | ใช้ |
|---|---|---|---|
| `positions`, `positions_many` | หน้าประกาศ "อัตรา" (`job-number-of-position`) | ตัวเลข ~84%, "หลายอัตรา" ~5% | A (นับความต้องการตามจำนวนคน) |
| `work_days_per_week` | "จันทร์–ศุกร์/เสาร์", "5/6 วันต่อสัปดาห์" | ระบุ 18% | A |
| `shift_work` | "เข้ากะ/กะดึก/shift" | 100% (จริง 10%) | A |
| `urgent`, `online_interview` | หน้ารายการ (รับสมัครด่วน, สัมภาษณ์ออนไลน์) | เฉพาะที่เห็นในหน้ารายการ | A |
| `n_benefit_types` | จำนวนกลุ่มสวัสดิการที่พบ (มัธยฐาน 5) | 94% มีข้อความสวัสดิการ | A |
| `benefit_bonus` | โบนัส | 80% | A |
| `benefit_social_security` | ประกันสังคม | 64% | A |
| `benefit_health_insurance` | ประกันสุขภาพ/ชีวิต/อุบัติเหตุ | 55% | A |
| `benefit_provident_fund` | กองทุนสำรองเลี้ยงชีพ | 42% | A |
| `benefit_transport` | รถรับส่ง/ค่าเดินทาง/ค่าน้ำมัน | 28% | A |
| `benefit_overtime` | ค่าล่วงเวลา | 14% | A |
| `benefit_commission`, `benefit_housing`, `benefit_meal`, `benefit_annual_leave`, `benefit_annual_checkup`, `benefit_training`, `benefit_uniform`, `benefit_salary_raise` | คำในสวัสดิการ | 9–40% | A |

> สวัสดิการ/ด่วน/จำนวนอัตรา **ไม่ใส่ใน ML ตัวที่ให้บริการ** เพราะผู้ใช้หน้า Salary ไม่รู้ค่าพวกนี้ตอนทำนาย (ใส่แล้วค่าตอนใช้จริงจะเป็นค่าเดา) — ใช้ทดลองแบบ ablation ในบทที่ 4 ได้

### 3.7 การสุ่มและคุณภาพ
| column | ที่มา | ใช้ |
|---|---|---|
| `sample_stratum` | `p=<จังหวัด>\|c=<ประเภทงาน>` จากหน้ารายการ | W |
| `sample_weight` | N_h / n_h (N_h จาก `"total"` ของหน้ารายการ) | W (mart ถ่วงน้ำหนัก, ML ไม่ถ่วง) |
| `company_name_norm` | ชื่อบริษัท normalize | **G** เท่านั้น |
| `mentions_gender`, `mentions_age` | regex | **DQ เท่านั้น** ห้ามเป็น feature (D6) |

## 4. ข้อมูลดิบที่เก็บไว้เพิ่ม (L0/L1 `payload.x_jobthai`) — ยังไม่แตกเป็น column
| key | ความหมาย |
|---|---|
| `listing` | ทุก field ที่หน้ารายการแสดง: jobTitle, companyName, companyLogo, province, district, region, industrial, transitStations, disabledPerson, isTopCompany, workLocation, salary, urgent, tags, updatedAt, jobType |
| `salary_text`, `salary_text_listing` | ข้อความเงินเดือนบนหน้าประกาศ / หน้ารายการ |
| `positions_text` | ข้อความ "อัตรา" ดิบ |
| `update_at` | วันที่อัปเดตประกาศ (พ.ศ.) |
| `company_detail` | ข้อความ "เกี่ยวกับบริษัท" (scrub PII แล้ว) |
| `directions` | การเดินทาง (scrub PII แล้ว) |
| `disabled_person` | การรับผู้พิการ ตามที่หน้ารายการระบุ |
| `unavailable` | ดึงซ้ำไม่ได้แล้ว (ประกาศปิด) — ข้อมูลเดิมยังอยู่ |

## 5. ข้อจำกัดที่ต้องเขียนในเล่ม
- เงินเดือนมีตัวเลขแค่ ~35% → โมเดลเงินเดือนเรียนจากเฉพาะบริษัทที่เปิดเผยเงินเดือน (selection bias)
- แต่ละชั้นได้แค่ ≤ 20 ประกาศล่าสุด (หน้าแรกของหน้ารายการ) → ชั้นใหญ่น้ำหนักสูง
- ข้อมูลจากหน้ารายการ (urgent, near_transit, ...) มีเฉพาะประกาศที่ปรากฏในหน้ารายการตั้งแต่ 21 พ.ย. 2569 ประกาศเก่ากว่านั้นเป็นค่าว่าง (ไม่ทราบ) ไม่ใช่ "ไม่ใช่"
- ระดับตำแหน่ง ประเภทการจ้าง สวัสดิการ เป็นกฎคำค้น (ไม่ใช่ AI) อาจพลาดคำที่เขียนแปลก — ตรวจมือรวมกับชุด 200 ประกาศ (T2.7)
