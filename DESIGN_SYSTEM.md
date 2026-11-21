# DESIGN_SYSTEM.md — Liquid Glass Dashboard สำหรับ Skill Demand Intelligence (v4)

> **สถานะ:** ร่างข้อเสนอ · ใช้คู่กับ [FRONTEND_SPEC.md](FRONTEND_SPEC.md) · ฉบับ SouthBiz เก่าอยู่ที่ `docs/archive/DESIGN_SYSTEM-southbiz.md`
> **ภาพอ้างอิง:** `design/stock-vector-modern-financial-dashboard-...jpg` (mood reference เท่านั้น)
> ⚠️ ภาพเป็นตัวอย่าง Shutterstock ติดลายน้ำ: ห้าม commit/deploy ไฟล์ภาพ (`design/*.jpg` อยู่ใน `.gitignore`) และห้ามลอกแบบ 1:1

---

## 1. DNA จากภาพอ้างอิง + สไตล์ Liquid Glass

| องค์ประกอบ | จากภาพอ้างอิง | เพิ่มแบบ Liquid Glass |
|---|---|---|
| Layout | การ์ดมนแนวตั้งเป็นกริด (bento 12 คอลัมน์) | การ์ดโปร่งแสงเบลอพื้นหลัง |
| สี | ขาว + **ม่วง `#6C5CE7`** + **คอรัล `#E0623F`** + teal `#0E9AAE` | พื้นหลังเป็น mesh gradient ม่วง/พีช/ฟ้าอ่อนที่สว่างและนุ่ม |
| การ์ด | มุม ~20px, ไม่มีเงาหนัก, หัวข้อซ้าย + ไอคอนขวา | ขอบใน 1px สีขาวโปร่ง + แสงสะท้อนบางที่ขอบบน |
| ตัวเลขใหญ่ | Hero figure 36–40px | เหมือนเดิม วางบนพื้นการ์ดที่ทึบพอ |
| Gradient card | การ์ดม่วง→พีช | ใช้กับ **AI card / Champion model card** เท่านั้น |

### หลักการ "แก้วเฉพาะเปลือก ไม่ใช่ข้อมูล"
1. **Glass ใช้กับ chrome และการ์ดเท่านั้น** (sidebar, top bar, card, แชท, modal) — **กราฟ ตาราง และข้อความอยู่บนพื้นที่ทึบพอ** (`--surface-chart` ≈ ขาว 94%) เพื่อให้ contrast ไม่ขึ้นกับสีพื้นหลังที่ไหลอยู่ข้างหลัง
2. ข้อความ ≥ 4.5:1 (WCAG AA) ตรวจกับ "สีเลวร้ายที่สุดของ mesh" ไม่ใช่สีเฉลี่ย; ข้อความใหญ่/ไอคอน ≥ 3:1
3. ซ้อนแก้วได้ **ไม่เกิน 2 ชั้น** (page → card; ใน card ใช้พื้นทึบ/ tint ไม่ใช่ blur ซ้ำ)
4. ไม่ใช้แก้วกับพื้นที่อ่านข้อความยาว/ตารางหนาแน่น — ใช้ `surface-solid`
5. มี fallback ที่ดูดี (หัวข้อ 4) — ผู้ใช้ที่ปิดความโปร่งใสหรืออุปกรณ์อ่อนต้องได้การ์ดทึบสไตล์เดียวกัน

---

## 2. กฎการสร้างกราฟ (คงเดิมจาก dataviz method)

- **ห้าม dual-axis** — ถ้าสองหน่วยให้แยกกราฟหรือ index เป็น 100
- **สีผูกกับตัวตน ไม่ผูกอันดับ:** "ฉัน/หลักสูตรของฉัน" = ม่วงเสมอ, "ตลาด/benchmark" = คอรัลเสมอ, "ค่าที่สาม/ภูมิภาคเทียบ" = teal, ค่าบริบทเป็นเทา
- ≥ 2 series ต้องมี legend; ≤ 4 series ให้ direct label เฉพาะจุดสำคัญ (ปลายเส้น/ค่าสูงสุด) ไม่ติดตัวเลขทุกจุด
- เส้น 2px, ปลายแท่งมน 4px, ช่องว่าง 2px ระหว่างชิ้นที่ซ้อนกัน, gridline เป็น hairline ทึบ
- **ทุกกราฟมี tooltip + ปุ่ม "ดูเป็นตาราง"** และ keyboard focus แสดงผลเหมือน hover; มี `aria-label` สรุปใจความ
- ตัวกรองอยู่แถวเดียวด้านบน (Global Context Bar); ในการ์ดมีได้แค่ชิปสลับมุมมองของการ์ดนั้น
- refetch คงภาพเดิมที่ opacity ลดลง ไม่ใช้ skeleton กะพริบ
- ข้อความใช้สีหมึก (`--ink-*`) ไม่ใช้สีของ series
- ซ่อนค่าที่ **n < 5** (แสดง "ข้อมูลน้อยเกินไป") ทุกกราฟ

### ปรับกราฟของภาพให้อ่านค่าได้จริง
| กราฟในภาพ | ปัญหา | ใช้แทน |
|---|---|---|
| Rose / Pie | เทียบชิ้นใกล้กันไม่ได้ | **Ranked horizontal bars** |
| Concentric radial | ความยาววงไม่เท่ากัน | **Meter list** (ชื่อ + แถบ + ตัวเลข) |
| Mirrored stream | แอบเป็น dual-axis | **Area เดียว** + range slider |
| Wavy lines | smoothing สร้างจุดยอดปลอม | เส้นตรง/monotone เบา + small multiples |
| Candlestick | open/close ไม่มีความหมาย | **Range/box plot** (p25–p75, whisker, จุด = ค่าของฉัน) |
| Segmented gauge | ใช้ได้ (ค่าเดียวเทียบเพดาน) | Gauge/meter สำหรับ coverage 0–100 |

---

## 3. Design Tokens (Tailwind v4 / shadcn compatible)

### 3.1 สีตัวตน (ผ่าน `validate_palette.js --mode light` แล้วบนพื้น `#fcfcfb`)

| Token | Hex | ความหมายใน E′ |
|---|---|---|
| `--series-me` | `#6C5CE7` | ทักษะของฉัน / หลักสูตรของฉัน / จังหวัดที่เลือก |
| `--series-market` | `#E0623F` | ความต้องการของตลาด / benchmark ประเทศ |
| `--series-compare` | `#0E9AAE` | ค่าเปรียบเทียบที่สาม (ภูมิภาค/ช่วงเวลาก่อนหน้า) |
| `--series-context` | `#B4B3C6` | บริบท/ค่าที่ลดความเด่น (เทา ไม่นับเป็น categorical) |

CVD ΔE ต่ำสุด 15.9 (protan), normal-vision 27.3, contrast ≥ 3:1 ทั้ง 3 สี · Dark mode ยังไม่ validate (Could)

### 3.2 `globals.css`

```css
@import "tailwindcss";

:root {
  /* ===== Page background: mesh gradient อ่อน ===== */
  --page-base: #F4F3FA;
  --page-mesh:
    radial-gradient(900px 600px at 8% 0%,   #E4DEFF 0%, transparent 60%),
    radial-gradient(800px 560px at 95% 8%,  #FFE3D8 0%, transparent 62%),
    radial-gradient(900px 700px at 70% 100%, #D8F0F5 0%, transparent 60%);

  /* ===== Ink ===== */
  --ink-primary:   #1B1A2E;   /* บนพื้นขาว ≈ 16:1 */
  --ink-secondary: #4A4963;   /* ≈ 8:1 */
  --ink-muted:     #6B6A82;   /* ≈ 5.1:1 บนขาว ใช้กับข้อความเล็กได้ */

  /* ===== Surfaces ===== */
  --surface-solid:  #FFFFFF;
  --surface-chart:  rgb(255 255 255 / 0.94);  /* พื้นใต้กราฟ/ตาราง */
  --surface-sunken: #F7F7FB;
  --border-hairline: #E8E8F0;

  /* ===== Glass ===== */
  --glass-bg:        rgb(255 255 255 / 0.62);
  --glass-bg-strong: rgb(255 255 255 / 0.78);   /* sidebar, modal, แชท */
  --glass-border:    rgb(255 255 255 / 0.70);   /* ขอบใน 1px */
  --glass-edge:      rgb(108 92 231 / 0.10);    /* ขอบนอกบางๆ ให้การ์ดไม่จมบนพื้นสว่าง */
  --glass-highlight: linear-gradient(180deg, rgb(255 255 255 / 0.75), rgb(255 255 255 / 0) 38%);
  --glass-blur:      18px;
  --glass-saturate:  1.4;
  --glass-shadow:    0 1px 0 rgb(255 255 255 / 0.6) inset, 0 8px 28px rgb(48 36 120 / 0.08);

  /* ===== Identity (categorical) ===== */
  --series-me:      #6C5CE7;
  --series-market:  #E0623F;
  --series-compare: #0E9AAE;
  --series-context: #B4B3C6;
  --tint-me:     #ECE9FC;
  --tint-market: #FBE4DC;

  /* ===== Sequential (ม่วงเดียว) / Diverging ===== */
  --seq-1: #F1EFFD; --seq-2: #D9D3FA; --seq-3: #B7ACF4; --seq-4: #9384EE;
  --seq-5: #6C5CE7; --seq-6: #4B3DBF; --seq-7: #2F2680;
  --div-neg: #E8590C; --div-mid: #E4E4EC; --div-pos: #1971C2;

  /* ===== Status (ต้องมีไอคอน + ข้อความ) ===== */
  --status-good: #138A4B; --status-warning: #8A5A00; --status-critical: #C92A2A;

  /* ===== AI ===== */
  --ai-gradient: linear-gradient(135deg, #6C5CE7 0%, #A77BE8 55%, #F0A58C 100%);
  --on-ai: #FFFFFF;          /* ข้อความบน gradient ใช้ตัวหนา ≥ 16px และมี scrim ด้านล่าง */

  /* ===== Shape / spacing ===== */
  --radius-card: 20px; --radius-control: 12px; --radius-chip: 999px;
  --space-card: 20px;  --gap-grid: 16px;
  --focus-ring: 0 0 0 3px rgb(108 92 231 / 0.45);

  /* ===== Motion ===== */
  --ease-out: cubic-bezier(.2,.8,.2,1);
  --dur-fast: 140ms; --dur-base: 240ms;
}

@theme inline {
  --color-page: var(--page-base);
  --color-ink: var(--ink-primary);
  --color-ink-2: var(--ink-secondary);
  --color-ink-3: var(--ink-muted);
  --color-me: var(--series-me);
  --color-market: var(--series-market);
  --color-compare: var(--series-compare);
  --color-context: var(--series-context);
  --radius-card: 20px;
  --radius-control: 12px;
  --font-sans: "Inter", "IBM Plex Sans Thai", system-ui, sans-serif;
}

/* shadcn mapping */
:root {
  --background: var(--page-base);
  --foreground: var(--ink-primary);
  --card: var(--surface-solid);
  --card-foreground: var(--ink-primary);
  --primary: var(--series-me);
  --primary-foreground: #fff;
  --muted: var(--surface-sunken);
  --muted-foreground: var(--ink-muted);
  --border: var(--border-hairline);
  --ring: var(--series-me);
  --radius: 12px;
}

body {
  background-color: var(--page-base);
  background-image: var(--page-mesh);
  background-attachment: fixed;
  color: var(--ink-primary);
  font-family: var(--font-sans);
}

/* ===== Glass utility ===== */
.glass {
  position: relative;
  background: var(--glass-bg);
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
          backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  border: 1px solid var(--glass-border);
  outline: 1px solid var(--glass-edge); outline-offset: -1px;
  border-radius: var(--radius-card);
  box-shadow: var(--glass-shadow);
}
.glass::before {               /* แสงสะท้อนบาง ๆ ที่ขอบบน */
  content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none;
  background: var(--glass-highlight);
}
.glass-strong { background: var(--glass-bg-strong); }
.chart-surface {               /* ที่วางกราฟ/ตาราง: ทึบพอให้ contrast ไม่ผันผวน */
  background: var(--surface-chart); border-radius: calc(var(--radius-card) - 6px);
  padding: 12px;
}
.ai-card { background: var(--ai-gradient); color: var(--on-ai); border-radius: var(--radius-card); }

/* ===== Fallbacks ===== */
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .glass, .glass-strong { background: #FFFFFF; }
}
@media (prefers-reduced-transparency: reduce) {
  .glass, .glass-strong { background: #FFFFFF; -webkit-backdrop-filter: none; backdrop-filter: none; }
  .glass::before { display: none; }
  body { background-image: none; }
}
@media (prefers-contrast: more) {
  .glass, .glass-strong { background: #FFFFFF; backdrop-filter: none; border-color: #1B1A2E; }
}
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
/* อุปกรณ์อ่อน/มือถือ: ลดเบลอ และจำกัดจำนวนชั้นเบลอ */
@media (max-width: 767px) { :root { --glass-blur: 10px; } .glass .glass { backdrop-filter: none; } }
```

### 3.3 Typography
- `font-family: "Inter", "IBM Plex Sans Thai", system-ui` (ละติน/ตัวเลข = Inter, ไทย = Plex Thai)
- Hero figure 36–40px / semibold / proportional figures · ตัวเลขใน tile 22–24px · หัวข้อการ์ด 17px/semibold · เนื้อหา 14px · แกนกราฟ/ตาราง 12px พร้อม `tabular-nums` เฉพาะคอลัมน์ตัวเลข
- ขนาดไทยไม่ต่ำกว่า 13px (สระ/วรรณยุกต์เล็กอ่านยาก), `line-height` ไทย ≥ 1.5

### 3.4 หมายเหตุประสิทธิภาพ
- `backdrop-filter` แพง: ใช้เฉพาะ **sidebar, top bar, การ์ดระดับบนสุด, แชท** ไม่ใช้กับแถวในตาราง/ไอเท็มรายการ/ tooltip
- ไม่ animate ค่า `blur`/`backdrop-filter`; animate แค่ `transform`/`opacity`
- มือถือ: blur 10px, ไม่ซ้อนแก้ว, mesh เป็น CSS gradient (ไม่ใช้รูปใหญ่)
- ถ้าวัด FPS ตกในหน้าที่มีกราฟ ECharts หลายอัน → สลับเป็น `.glass` แบบทึบผ่าน class บน `<html data-glass="off">` (ปุ่มใน Settings)

---

## 4. Fallback และการเข้าถึงของแก้ว

| เงื่อนไข | พฤติกรรม |
|---|---|
| เบราว์เซอร์ไม่รองรับ `backdrop-filter` | `@supports not` → การ์ดทึบขาว |
| `prefers-reduced-transparency` | การ์ดทึบ ปิดแสงสะท้อน ปิด mesh |
| `prefers-contrast: more` | ขอบเข้ม พื้นทึบ |
| `prefers-reduced-motion` | ปิด animation กราฟ/ทรานซิชัน |
| ผู้ใช้ปิดใน Settings | `data-glass="off"` |
- ทดสอบ contrast อัตโนมัติด้วยพื้นหลังที่เลวร้ายสุด 3 จุดของ mesh (script ใน TASKS Phase 6)

---

## 5. Chart engine: Apache ECharts

ใช้ **ECharts** ตัวเดียวทั้งระบบ (import แบบ tree-shaken จาก `echarts/core` ผ่าน `next/dynamic` ปิด SSR) + **TanStack Table v8** สำหรับตาราง · ลงทะเบียนธีมเดียว `echarts.registerTheme('skillbi', …)` (สี series ตามตัวตน, ฟอนต์, tooltip, hairline grid)

| ชนิดกราฟ | ECharts |
|---|---|
| Sankey | `sankey` |
| Line + badge annotation | `line` + `markPoint` |
| Range / Box plot | `boxplot` / `custom` |
| Small multiples | `grid[]` หลายช่อง |
| Radar | `radar` |
| Calendar heatmap | `calendar` + `heatmap` |
| Gauge | `gauge` (splitNumber) |
| Area + range slider | `line(areaStyle)` + `dataZoom` |
| Scatter + quadrant | `scatter` + `markArea` |
| Network (co-occurrence) | `graph` หรือ matrix `heatmap` |

---

## 6. จับคู่การ์ดในภาพกับฟีเจอร์ E′

| # | การ์ดในภาพ | ใช้เป็น (E′) | หน้า | รูปแบบที่ปรับแล้ว | ข้อมูลจาก |
|---|---|---|---|---|---|
| 1 | **Sales Report** (Sankey + รายการ + tile) | **Skill Flow:** ภาค/จังหวัด → หมวดอาชีพ → ทักษะยอดนิยม (ประกาศไหลไปหาทักษะ), รายการ = ทักษะอันดับสูง, tile = จำนวนประกาศ / ประกาศที่ระบุเงินเดือน | Market Explorer | Sankey ≤ 6 node/ชั้น, ทักษะที่เลือก = ม่วง, ที่เหลือเทา | `mart.skill_demand_weekly` |
| 2 | **Fraud Score** (เส้น + badge) | **Skill Demand Trend:** สัดส่วนประกาศที่ขอทักษะ X รายสัปดาห์ (ถ่วงน้ำหนัก, เทียบตลาดรวม), badge ที่จุดเปลี่ยน/จุดสูงสุด + คำอธิบายสั้นใต้กราฟ | Skill detail | Line 2 series, label เฉพาะ peak | `mart.skill_demand_weekly` |
| 3 | **Dividends** (candlestick + รายการสถานะ) | **Salary Range Ladder:** กล่อง p25–p75 + whisker ต่อ occupation หรือจังหวัด, จุดม่วง = ค่าประมาณของฉัน; ล่าง = รายการตำแหน่งที่ตรงพร้อมชิป "ตรง 8/10 ทักษะ" | Salary Explorer | Box/range plot แสดง n ใต้แท่ง | `mart.salary_stats`, `mart.salary_prediction` |
| 4 | **Budget** (คลื่นรายเดือน) | **Small multiples ทักษะ:** แถวละทักษะ (Excel, SQL, Python, Power BI, English) แนวโน้มรายสัปดาห์แกน y เดียวกัน | Market Explorer | Small multiples, เส้นตรง/monotone | `mart.skill_demand_weekly` |
| 5 | **Client info** (โปรไฟล์ + radar) | **My Skills vs Market Radar:** ม่วง = ทักษะของฉัน (ระดับ 0–3), คอรัล = ความต้องการของตำแหน่งเป้าหมาย (สัดส่วนประกาศ) ≤ 8 แกน; tile = coverage %, ทักษะที่ขาด | Skill Gap | Radar 2 series + ตารางแทน | `app_user_skill` + `mart.occupation_skill_profile` |
| 6 | **Transaction History** (rose + รายการ) | **Skill Ranking:** ทักษะที่ถูกขอมากสุดในกลุ่ม/ตำแหน่ง + รายการแถว (ชื่อ, % ประกาศ, จำนวน) | Occupation detail | **Ranked horizontal bars** | `mart.occupation_skill_profile` |
| 7 | **Intensity** (stream + slider) | **Posting Volume over time:** area จำนวนประกาศรายสัปดาห์ + range slider เลือกช่วง ส่งผลกับการ์ดอื่น | Market Explorer | Area ซีกเดียว + `dataZoom` | `mart.posting_volume_daily` |
| 8 | **Overview** (calendar heatmap + 4 tile) | **Posting Calendar:** ปริมาณประกาศใหม่รายวัน (ชิปสลับปี/จังหวัด) + 4 tile: ทั้งหมด / ระบุเงินเดือน / เฉลี่ยทักษะต่อประกาศ / อัปเดตล่าสุด | Landing / Market Explorer | Sequential ม่วง + legend สเกล | `mart.posting_volume_daily` |
| 9 | **Investment** (gradient + วงซ้อน + ชิป 3/5/7%) | **Champion Card:** gradient = "ประมาณเงินเดือนจากโมเดล champion" (ชื่อโมเดล, MAE, ช่วงค่าคาด), meter list = ทักษะที่เพิ่มแล้วเงินเดือนคาดเพิ่มขึ้น, ชิปเลือก "ถ้าเรียนเพิ่ม: SQL / Power BI / Python" | Salary Estimator | Meter list แทนวงซ้อน | `ml.*`, `/api/salary/estimate` |
| 10 | **Statistics** (gauge + pill columns) | **Curriculum Coverage:** gauge/meter 0–100% ของทักษะสำคัญที่หลักสูตรครอบคลุม + column ประกาศใหม่รายสัปดาห์ (สัปดาห์ล่าสุดม่วง ที่เหลือเทา) | Curriculum Alignment | Meter + column | `app_curriculum_skill` + `mart.curriculum_coverage_ref` |
| + | (ไม่มีในภาพ) **Skill Co-occurrence** | ทักษะที่มักมาคู่กัน (top 15) เมื่อเลือกทักษะหนึ่ง | Skill detail | Matrix heatmap หรือ ranked bars "มักมาคู่กับ" | `mart.skill_cooccurrence` |
| + | (ไม่มีในภาพ) **ML Leaderboard** | ตาราง 5 โมเดล + baseline, แท่ง RMSE พร้อม error bar (SD ข้าม fold), strip plot ราย fold | ML Lab | Table + bar + strip | `mart.ml_leaderboard` |
| + | (ไม่มีในภาพ) **Pipeline/DQ** | ไทม์ไลน์รอบ scrape, ตาราง check pass/fail, ความคืบหน้า taxonomy | Admin | Status chip + progress meter | `mart.pipeline_status`, `mart.dq_summary` |

### 6.0 Global Context Bar (ติดด้านบนทุกหน้า, glass-strong)
```text
[ จังหวัด/ภาค ▾ ]  [ กลุ่มอาชีพ ▾ ]  [ ช่วงเวลา ▾ ]        อัปเดต 18 พ.ย. 2569 · แหล่ง: JobThai (ตัวอย่าง n = …)
```

### 6.1 ตัวอย่างเลย์เอาต์ (Desktop 12 คอลัมน์)

**Market Explorer**
```text
┌ KPI ×4 (ประกาศ / ระบุเงินเดือน / ทักษะต่อประกาศ / อัปเดต) ┐  3+3+3+3
├ Skill Ranking (bars) 5 ┬ Skill Flow (Sankey) 7                      ┤
├ Small multiples แนวโน้มทักษะ 7 ┬ Posting Calendar 5                 ┤
├ Posting Volume + range slider 12                                  ┤
```
**Skill Gap (Student)**
```text
┌ เลือกตำแหน่งเป้าหมาย + ทักษะของฉัน (chips) 4 ┬ Radar ฉัน vs ตลาด 4 ┬ Coverage tile + ทักษะที่ขาด 4 ┤
├ ทักษะที่ควรเพิ่ม (ranked bars + "ขาดแล้วได้ประโยชน์" เรียงลำดับ) 6 ┬ ตำแหน่งที่ตรง + ลิงก์ต้นฉบับ 6 ┤
```
**Salary Estimator**
```text
┌ ฟอร์มกรอก (ตำแหน่ง จังหวัด ประสบการณ์ วุฒิ ทักษะ) 4 ┬ Champion Card (ช่วงค่าคาด) 8 ┤
├ Salary Range Ladder 7 ┬ ทักษะที่เพิ่มแล้วคาดว่าเงินเดือนขึ้น (meter list) 5 ┤
```
**Curriculum Alignment, ML Lab, Admin** — ใช้การ์ด #10 / Leaderboard / Pipeline ตามตารางบน และเลย์เอาต์รายละเอียดใน FRONTEND_SPEC.md

### 6.2 มือถือ (< 768px)
คอลัมน์เดียว: Context Bar ย่อเป็น sheet → KPI เลื่อนแนวนอน → การ์ดตามลำดับสำคัญ; แชทเปิดเป็น bottom sheet เต็มจอ; ตารางเลื่อนแนวนอนหรือเปลี่ยนเป็นการ์ดรายแถว

---

## 7. Component Inventory

| Component | หน้าที่ | หมายเหตุ |
|---|---|---|
| `<GlassCard>` | โครงการ์ด: title, action icon, chip, `<ChartSurface>`, footer tiles | ทุกการ์ดมีปุ่ม "ดูเป็นตาราง" + `<ProvenanceBadge>` |
| `<ChartSurface>` | พื้นทึบใต้กราฟ/ตาราง | `.chart-surface` |
| `<KpiTile>` | ตัวเลข + delta (▲▼) + sparkline | ไม่ใช้สีอย่างเดียว |
| `<HeroFigure>` | ตัวเลขเด่น 36–40px | proportional figures |
| `<ProvenanceBadge>` | "แหล่ง · n · อัปเดตเมื่อ" + ป้าย "ตัวอย่างจากประกาศ" | บังคับทุกการ์ด |
| `<AiCard>` / `<ChampionCard>` | gradient card ของโมเดล/คำแนะนำ | ✦ + gradient |
| `<StatusChip>` | pass/warn/fail, pending | ไอคอน + ข้อความ |
| `<SegmentedControl>` / `<RangeSlider>` | สลับมุมมอง / เลือกช่วง | keyboard ได้ |
| `<MeterList>` | แทน radial bars | |
| `<SkillChipPicker>` | เลือก/ค้นหาทักษะ (alias ไทย/อังกฤษ) | autocomplete จาก taxonomy |
| `<EmptyState>` / `<LowDataState>` | n < 5 หรือยังไม่มีข้อมูล | ลิงก์ไปหน้าที่เกี่ยวข้อง |
| `<SourceLink>` | "ดูประกาศต้นฉบับ ↗" | `rel="noopener noreferrer"`, ชี้ไปเว็บเจ้าของ |
| `<ChatFab>` / `<ChatPanel>` | ไอคอนแชทลอย + แผงสนทนา | glass-strong, บน mobile เป็น bottom sheet |

---

## 8. Accessibility & Interaction Checklist
- [ ] Contrast ข้อความ ≥ 4.5:1 บนทุกพื้น (ทดสอบกับ mesh สีเลวร้ายสุด), mark ≥ 3:1
- [ ] ไม่สื่อความหมายด้วยสีอย่างเดียว (legend, direct label, ไอคอน)
- [ ] ทุกกราฟมี table view และ `aria-label`
- [ ] Tooltip เปิดได้ทั้ง hover และ keyboard focus; focus ring `--focus-ring` เห็นชัดบนแก้ว
- [ ] `prefers-reduced-motion`, `prefers-reduced-transparency`, `prefers-contrast` ถูกเคารพ
- [ ] Texture fill แบบ opt-in สำหรับตาบอดสี/พิมพ์
- [ ] ภาษาไทยไม่ถูกตัดในแกน (width + ellipsis + tooltip ชื่อเต็ม)
- [ ] Hit target ≥ 40px บนมือถือ
