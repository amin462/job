# DESIGN_SYSTEM.md — ภาษาภาพ, Design Tokens และการจับคู่กราฟจากภาพอ้างอิง

> **สถานะ:** ร่างข้อเสนอ · **วันที่:** 18 พ.ย. 2569 · ใช้คู่กับ [PLAN.md](PLAN.md)
> **ภาพอ้างอิง:** `design/stock-vector-modern-financial-dashboard-...jpg`
>
> ⚠️ **เรื่องลิขสิทธิ์:** ภาพนี้เป็นตัวอย่างจาก Shutterstock ที่ติดลายน้ำ ใช้เป็น mood reference ได้ แต่ห้ามนำไฟล์ขึ้น public repo หรือ deploy และห้ามลอกแบบ 1:1 ควรใส่ `design/*.jpg` ไว้ใน `.gitignore` ส่วน design system นี้สร้างสไตล์ขึ้นใหม่ด้วย token ของโปรเจกต์เอง

---

## 1. DNA ของภาพอ้างอิง

| องค์ประกอบ | สิ่งที่เห็นในภาพ | นำมาใช้อย่างไร |
|---|---|---|
| Layout | การ์ดขาวแนวตั้งวางเป็นกริดบนพื้นเทาอ่อน, ไม่มีเงาหนัก | Bento grid 12 คอลัมน์ บนมือถือเป็นคอลัมน์เดียว การ์ดเรียงตามลำดับความสำคัญ |
| มุม | การ์ดมนมาก (~20px), ปุ่ม/ชิปมน | `--radius-card: 20px`, `--radius-control: 12px`, ชิปเป็น pill |
| สี | **ม่วงอินดิโก** เป็นสีหลัก + **พีช/คอรัล** เป็นสีรอง + กรมท่าเข้มเป็น accent | ม่วง = ร้านของฉัน, คอรัล = ผู้นำ/benchmark (ผ่าน validator แล้ว ดูหัวข้อ 3) |
| Anatomy ของการ์ด | หัวข้อซ้าย + ไอคอนปุ่มขวา (filter/menu/heart), ชิปตัวกรองเล็ก, กราฟ, รายการแถวที่ตัวเลขชิดขวา, tile ตัวเลข 2 ช่อง, ปุ่มเต็มความกว้าง | เป็น `<InsightCard>` มาตรฐานของทุก view |
| ตัวเลขใหญ่ | `$46,897`, `1,825,327` เด่นชัด | Hero figure ใช้ฟอนต์ sans เดียวกัน, **proportional figures** (ไม่ใช้ tabular-nums กับตัวเลขขนาดใหญ่) |
| Gradient | การ์ดเครดิต ม่วงไล่ไปพีช | ใช้กับ **AI Brief / Champion Model card** เท่านั้น เป็นเอกลักษณ์ของ "AI" |
| กราฟ | Sankey, step line + badge, candlestick, small-multiple waves, radar, rose, mirrored stream, calendar heatmap, radial bars, segmented gauge, pill columns | จับคู่กับฟีเจอร์จริงในหัวข้อ 5 และปรับบางตัวให้อ่านค่าได้แม่นขึ้น |

---

## 2. หลักการ: สวยแบบภาพอ้างอิง แต่ต้องอ่านค่าได้จริง

ภาพอ้างอิงเป็นภาพ stock ที่เน้นความสวย บางกราฟอ่านค่าได้ยาก ในเครื่องมือตัดสินใจของ SME ต้องปรับตามกฎนี้:

| กราฟในภาพ | ปัญหา | ใช้แบบนี้แทน |
|---|---|---|
| Rose / Pie (Transaction History) | เทียบขนาดชิ้นที่ใกล้กันไม่ได้ | **Ranked horizontal bars** หรือ **segmented bar + รายการตัวเลข** (คง style รายการแบบในภาพไว้) |
| Concentric radial bars (Investment) | ความยาววงนอกกับวงในไม่เท่ากัน ทำให้เทียบผิด | **Meter list** (ชื่อ + แถบ + ตัวเลข ต่อแถว) ถ้าต้องใช้ radial ให้ใช้เป็นภาพประกอบ ≤ 4 รายการ และมีตัวเลขกำกับ |
| Mirrored stream (Intensity) | สองซีกที่เป็นคนละหน่วยเท่ากับ dual-axis แอบแฝง | **Area เดียว** (ซีกเดียว) + range slider |
| Wavy lines (Budget) | smoothing มากเกินทำให้มีจุดยอดปลอม | `smooth` แบบ monotone เบาๆ หรือเส้นตรง + small multiples |
| Candlestick (Dividends) | open/close ไม่มีความหมายในข้อมูลเรา | **Range/box plot**: แท่ง p25–p75, whisker min–max, จุด = ราคาของฉัน |
| Segmented radial gauge (Statistics) | ใช้ได้ เพราะเป็นค่าเดียวเทียบเพดาน | Meter แบบ radial สำหรับ Health Score 0–100 |

**กฎบังคับ** (จาก dataviz method):
- ห้าม dual-axis เด็ดขาด ถ้ามีสองหน่วยให้แยกกราฟ หรือ index เป็น 100
- สีผูกกับ **ตัวตน** ไม่ผูกกับอันดับ (ร้านฉันเป็นม่วงเสมอไม่ว่าจะ filter อย่างไร)
- ≥ 2 series ต้องมี legend และ ≤ 4 series ให้ direct label ด้วย **เลือกติดป้ายเฉพาะจุดสำคัญ** (ปลายเส้น, จุดสูงสุด) ไม่ติดตัวเลขทุกจุด
- เส้น 2px, data-end มน 4px, ช่องว่าง 2px ระหว่างชิ้นที่ซ้อนกัน, gridline เป็น hairline ทึบ (ไม่ใช้เส้นประ)
- ทุกกราฟมี tooltip + **table view** (ปุ่มสลับ "ดูเป็นตาราง") และ keyboard focus แสดงเหมือน hover
- ตัวกรองอยู่ **แถวเดียวด้านบน** (Global Context Bar) ไม่ใส่ filter ในการ์ด ยกเว้นชิปสลับมุมมองของการ์ดนั้นเอง
- refetch ให้คงภาพเดิมที่ opacity ลดลง ไม่แสดง skeleton กะพริบ
- ข้อความใช้สีหมึก (`--ink-*`) ไม่ใช้สีของ series

---

## 3. Design Tokens

### 3.1 สีตามตัวตน (Categorical, ผ่าน `validate_palette.js --mode light` แล้ว)

| Token | Hex | ความหมาย | ผล validator |
|---|---|---|---|
| `--series-my-store` | `#6C5CE7` | ร้านของฉัน / หมุดของฉัน | ✅ |
| `--series-benchmark` | `#E0623F` | ผู้นำจังหวัด / national-global benchmark | ✅ |
| `--series-cross-border` | `#0E9AAE` | คู่แข่งข้ามแดน (กลันตัน/เคดาห์/เประ/ปีนัง) | ✅ |
| `--series-peer` | `#B4B3C6` | ค่าเฉลี่ย peer / บริบท (สีเทา de-emphasis ไม่นับเป็น categorical) | — |

ผล validator (surface `#fcfcfb`): lightness band ผ่าน, chroma ผ่าน, CVD ΔE คู่ที่แย่ที่สุด 15.9 (protan), normal-vision ΔE 27.3, contrast ≥ 3:1 ทั้ง 3 สี
> ข้อเปลี่ยนจาก ARCH 6.1: ร้านของฉันเปลี่ยนจาก Blue `#2563EB` เป็น **Violet** ให้ตรงภาพ, Amber `#F59E0B` เปลี่ยนเป็น **Coral** (amber contrast ต่ำกว่า 3:1 บนพื้นขาว), AI ไม่ใช้สีม่วงล้วนแล้ว (ชนกับร้านของฉัน) เปลี่ยนไปใช้ **gradient + ไอคอน ✦** แทน
> Dark mode: ชุดสีสว่างตอนนี้สอบตก lightness band บนพื้นมืด ต้องหาค่าใหม่จาก ramp เดิมแล้ว validate แยก (อยู่ในหมวด Could)

### 3.2 Token ทั้งหมด

```css
:root {
  /* Surfaces */
  --surface-page:    #F4F4F7;
  --surface-card:    #FFFFFF;
  --surface-sunken:  #F7F7FA;   /* tile ย่อยในการ์ด เช่น Monthly / Yearly */
  --border-hairline: #ECECF2;

  /* Ink (ข้อความ) */
  --ink-primary:   #1B1A2E;
  --ink-secondary: #55546B;
  --ink-muted:     #8E8DA3;

  /* Identity (categorical, ลำดับตายตัว) */
  --series-my-store:     #6C5CE7;
  --series-benchmark:    #E0623F;
  --series-cross-border: #0E9AAE;
  --series-peer:         #B4B3C6;

  /* Tint สำหรับพื้นที่ใหญ่แบบพาสเทลในภาพ (ห้ามใช้สีอิ่มกับพื้นที่ใหญ่) */
  --tint-my-store:  #ECE9FC;
  --tint-benchmark: #FBE4DC;

  /* Sequential (ปริมาณ เช่น heatmap): ม่วงเดียว อ่อน → เข้ม */
  --seq-1: #F1EFFD; --seq-2: #D9D3FA; --seq-3: #B7ACF4; --seq-4: #9384EE;
  --seq-5: #6C5CE7; --seq-6: #4B3DBF; --seq-7: #2F2680;

  /* Diverging (sentiment, price gap): ใช้ในกราฟที่ไม่มีสีตัวตนปนเท่านั้น */
  --div-neg: #E8590C; --div-mid: #E4E4EC; --div-pos: #1971C2;

  /* Status: ต้องมีไอคอน + ข้อความเสมอ */
  --status-good:     #138A4B;
  --status-warning:  #B7791F;
  --status-critical: #C92A2A;

  /* AI identity */
  --ai-gradient: linear-gradient(135deg, #6C5CE7 0%, #A77BE8 55%, #F0A58C 100%);

  /* Shape */
  --radius-card: 20px; --radius-control: 12px; --radius-chip: 999px;
  --space-card: 20px;  --gap-grid: 16px;
}
```

### 3.3 Typography
- `font-family: "Inter", "IBM Plex Sans Thai", system-ui` ให้ตัวละติน/ตัวเลขใช้ Inter และภาษาไทย fallback ไป Plex Thai
- **Hero figure** 36–40px / semibold / proportional figures
- **ตัวเลขใน tile** 22–24px / semibold / proportional figures
- **หัวข้อการ์ด** 17px / semibold
- **เนื้อหา** 14px · **แกนกราฟและตาราง** 12px / `tabular-nums` (เฉพาะตัวเลขที่ต้องเรียงตรงกันแนวตั้ง)
> ข้อเปลี่ยนจาก ARCH 6.1: ไม่บังคับ `tabular-nums` กับ KPI ขนาดใหญ่ ใช้เฉพาะตาราง แกน และคอลัมน์ตัวเลข

---

## 4. Chart Engine: แนะนำ Apache ECharts

| ชนิดกราฟในภาพ | Recharts | **ECharts** |
|---|---|---|
| Sankey (Sales Report) | ✅ (ปรับ style ยาก) | ✅ `sankey` |
| Line + badge annotation (Fraud Score) | ✅ (custom label) | ✅ `markPoint` |
| Range / Box plot (Dividends) | ❌ ต้อง custom shape | ✅ `boxplot` / `custom` |
| Small-multiple lines (Budget) | ✅ | ✅ `grid[]` หลายช่อง |
| Radar (Client info) | ✅ | ✅ |
| Calendar heatmap (Overview) | ❌ | ✅ `calendar` + `heatmap` |
| Segmented gauge (Statistics) | ⚠️ RadialBar | ✅ `gauge` (splitNumber) |
| Area + range slider (Intensity) | ✅ | ✅ + `dataZoom`/`brush` |
| Scatter 4-quadrant + เงาแบ่งโซน | ✅ | ✅ `markArea` |
| ธีมเดียวทั้งระบบ | ทำเองทีละ component | `echarts.registerTheme('southbiz', …)` |

**ข้อสรุป:** ใช้ **ECharts** (import แบบ tree-shaken จาก `echarts/core` ผ่าน `next/dynamic` ปิด SSR ของ component กราฟ) คู่กับ **TanStack Table v8** สำหรับตาราง SKU และ **MapLibre GL** สำหรับแผนที่ ใช้ library กราฟตัวเดียวทั้งระบบเพื่อให้ธีม tooltip และ interaction เหมือนกันหมด

---

## 5. จับคู่การ์ดในภาพกับฟีเจอร์ SouthBiz

| # | การ์ดในภาพ | ใช้เป็นอะไรใน SouthBiz | View | รูปแบบที่ปรับแล้ว | ข้อมูลจาก |
|---|---|---|---|---|---|
| 1 | **Sales Report** (flow + รายการเมือง + Monthly/Yearly) | **"เงิน 100 บาทไปไหน" (Profit Flow):** ราคาขาย → COGS / แพ็กเกจ / GP+VAT / โปร / **กำไรสุทธิ** แยก walk-in กับ delivery, รายการ = กำไรตาม sub-group, tile = กำไร/เดือน, กำไร/ปี | Pricing (+ ย่อใน Overview) | Sankey ≤ 6 node ต่อชั้น, กำไรสีม่วง, รั่วไหลเป็นสีเทา, GP เป็นคอรัล | `app_user_sku_portfolio` + `lib/economics` |
| 2 | **Fraud Score** (เส้นขั้นบันได + badge ที่จุดยอด) | **Popularity Velocity:** Popularity Index รายเดือน ร้านฉัน vs ผู้นำ, badge เฉพาะจุดยอดหรือเหตุการณ์ (ฮารีรายอ, มรสุม) + คำอธิบายสั้นใต้กราฟ, ปุ่ม "แชร์" / "บันทึกรายงาน" | Overview | Line 2 series, label เฉพาะ peak, แถบพื้นหลังจางๆ ช่วงมรสุม | `fact_market_snapshot`, `dim_date` |
| 3 | **Dividends** (candlestick + Clients list พร้อมสถานะ) | บน: **Price Range Ladder** ต่อ canonical item (กล่อง p25–p75, whisker min–max, จุดม่วง = ราคาฉัน) ล่าง: **Watchlist** คู่แข่งพร้อมชิปสถานะ ("ขึ้นราคา", "รีวิวลบใหม่", "เปิดสาขาใหม่") | Pricing / Radar | Box/range plot แนวตั้ง, แสดง n ใต้แต่ละแท่ง | `mart.peer_price_stats`, `app_competitor_watchlist` |
| 4 | **Budget** (คลื่นรายเดือน + Balance) | **Seasonality small multiples:** แถวละบริบท (Baseline / มรสุม พ.ย.–ม.ค. / รอมฎอน / ช่วงหยุดยาวไทย-มาเลเซีย) แสดงดัชนีปริมาณรีวิวรายสัปดาห์ ร้านฉัน vs ตลาด, tile ล่าง = "1 MYR = x.xx THB วันนี้" หรือ "ฝนสัปดาห์นี้ xx มม." | Overview / Context Bar | Small multiples ใช้แกน y เดียวกัน, smoothing เบา | `fact_review`, `fact_weather_daily`, `fact_fx_daily` |
| 5 | **Client info** (โปรไฟล์ + radar + 2 KPI) | **Store Profile + Capability Radar 5 แกน** (ร้านฉัน vs ผู้นำ), tile = เรตติ้ง (Bayesian) ของฉัน vs ผู้นำ | Overview | Radar ≤ 2 series, ชื่อแกนเปลี่ยนตามอุตสาหกรรม | `mart.outlet_scorecard_monthly` |
| 6 | **Transaction History** (rose + รายการหมวดพร้อมจำนวน) | **Customer Voice Mix:** สัดส่วนภาษาของรีวิว (TH/MS/EN/ZH) หรือหมวดที่ถูกบ่นมากที่สุด, รายการแถว = aspect + จำนวนรีวิว, ปุ่ม = "ดูรีวิวทั้งหมด" | Reviews | **Segmented bar + รายการ** (ไม่ใช้ rose) | `mart.aspect_sentiment_monthly` |
| 7 | **Intensity** (stream + range sliders) | **Operating-Hour Gap Detector:** area = จำนวนคู่แข่งที่เปิดในแต่ละชั่วโมง (0–24) ในรัศมี, แถบม่วง = ช่วงเวลาที่ร้านฉันเปิด, **range slider** ลากเวลาเปิด-ปิดแล้วเห็น "ชั่วโมงที่ไม่มีคู่แข่ง" ทันที | Radar | Area ซีกเดียว + แถบ highlight ช่วงว่าง | `mart.hourly_coverage` |
| 7b | (slider แบบเดียวกัน) | **What-If Panel:** slider ราคา / COGS / GP% + ชิปเลือก elasticity | Pricing | Single slider + ค่าตัวเลขสด | `lib/economics` + ONNX ใน browser |
| 8 | **Overview** (calendar heatmap 2025/2024 + 4 tile ค่าใช้จ่าย) | **Calendar Heatmap:** ปริมาณรีวิวหรือ sentiment รายวัน, **ช่องที่มีกรอบ = วันหยุด** (ไทย/มาเลย์/ฮารีรายอ) แบบช่องกรอบในภาพ, ชิปสลับปี 4 tile = โครงสร้างต้นทุน COGS% / แพ็กเกจ% / GP% / Fixed cost | Reviews / Overview | Sequential ม่วงเดียว + legend สเกล | `fact_review`, `dim_date` |
| 9 | **Investment** (การ์ด gradient + วงซ้อน + ชิป 3/5/7% + Proceed) | **AI Price Move Card:** การ์ด gradient = "ข้อเสนอจาก AI" (ชื่อร้าน, ระดับ tier, ความมั่นใจ), meter list = margin ตาม sub-group, **ชิป +3% / +5% / +7%** = สถานการณ์ขึ้นราคา, ปุ่ม "จำลองผล" | Pricing / Overview | Meter list แทนวงซ้อน | ML conformal + economics |
| 10 | **Statistics** (segmented gauge + pill columns) | **Market Health Score** 0–100 (gauge แบ่งช่อง) + **รีวิวใหม่รายเดือน** (column มน แท่งเดือนล่าสุดสีม่วง เดือนอื่นสีเทา) | Overview | Gauge = meter, column ใช้ emphasis | `mart.outlet_scorecard_monthly`, `fact_review` |
| + | (ไม่มีในภาพ) **4-Quadrant SKU Matrix** | Scatter: X = Price Gap%, Y = Net Margin%, เงาพื้นหลังแต่ละ quadrant ใช้ tint, ป้ายชื่อเฉพาะ SKU ที่อยู่ใน Margin Bleeders, สลับ Market Lens / Menu Engineering Lens | Pricing | จุด 8px + วงขาว 2px, hover แบบ nearest-point | economics + peer stats |
| + | (ไม่มีในภาพ) **Aspect Gap Bars** | แท่ง diverging ต่อ aspect: sentiment ร้านฉัน − ผู้นำ | Reviews | Diverging bar ศูนย์กลางที่ 0 | `mart.aspect_sentiment_monthly` |

---

## 6. Layout ราย View (Desktop 12 คอลัมน์)

### 6.0 Global Context Bar (ติดด้านบนทุก view)
```text
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ [☕ กาแฟบ้านกิมหยง ▾]  [เทียบกับ: ในรัศมี 1 กม. ▾]  [บริบท: Baseline ▾]  [THB│MYR│USD]  [✦ Copilot] │
│  อัปเดต 3 วันก่อน · แหล่ง: Google Maps + LINE MAN                                     │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.1 Overview: "ร้านฉันอยู่ตรงไหน และสัปดาห์นี้ควรทำอะไร"
```text
┌ KPI: Health Score ┬ KPI: Price Position ┬ KPI: Net Margin ┬ KPI: Sentiment Gap ┐  (3+3+3+3)
├ ✦ AI Brief (gradient, ดู SQL/Lineage ได้)          8 ┬ Health Gauge + รีวิวรายเดือน  4 ┤  (#10)
├ Profile + Radar 5 แกน  4 ┬ Popularity Velocity (badge ที่จุดยอด)                  8 ┤  (#5, #2)
├ Profit Flow (ย่อ)               6 ┬ Seasonality small multiples                   6 ┤  (#1, #4)
```

### 6.2 Radar: "คู่แข่งรอบตัวฉันคือใคร และช่องว่างอยู่ตรงไหน"
```text
┌ แผนที่ MapLibre + วง 1/3/5/10 กม. + hex density      8 ┬ Saturation (Red/Blue Ocean)  4 ┤
│   ● ม่วง = ฉัน  ● คอรัล = ผู้นำ/chain  ● เทา = peer  ● teal = ข้ามแดน │ + Opportunity Score  │
├ Operating-Hour Gap (area + range slider, แยกวันศุกร์) 6 ┬ Watchlist (รายการ + ชิปสถานะ) 6 ┤  (#7, #3)
├ ตารางเทียบ attribute (JSONB): ตราฮาลาล / ที่จอด / Wi-Fi / QR-DuitNow / เปิดดึก / ปิดละหมาดวันศุกร์ 12 ┤
```

### 6.3 Pricing: "SKU ไหนทำเงิน SKU ไหนรั่ว"
```text
┌ Sub-group summary cards (เลื่อนแนวนอน: กาแฟ / ชา / ขนมปัง …)                     12 ┤
├ 4-Quadrant Matrix [Market Lens │ Menu Eng. Lens]   8 ┬ What-If Panel (sliders)       4 ┤
├ Price Range Ladder (box + จุดของฉัน)              6 ┬ Profit Flow Sankey            6 ┤  (#3, #1)
├ AI Price Move Card (+3/+5/+7%)                     4 ┬ SKU Table (TanStack)          8 ┤  (#9)
```

### 6.4 Reviews: "ลูกค้าแต่ละภาษาพูดถึงเราว่าอะไร"
```text
┌ Aspect Gap Bars (ฉัน − ผู้นำ)                       8 ┬ Voice Mix (ภาษา/หมวด)         4 ┤  (#6)
├ Calendar Heatmap (กรอบ = วันหยุด)                   6 ┬ Review Feed + ตัวกรอง          6 ┤  (#8)
```

### 6.5 ML Lab: "โมเดลไหนดีที่สุด และเชื่อได้แค่ไหน"
```text
┌ Leaderboard (ตาราง + แท่ง RMSE พร้อม error bar)    8 ┬ Champion Card (gradient)      4 ┤
├ SHAP importance (bar / beeswarm)                    6 ┬ Predicted vs Actual (scatter) 6 ┤
├ ผลราย fold (strip plot ทุกโมเดล) + Friedman/Nemenyi                            12 ┤
├ Sentiment labeler: κ / macro-F1 ต่อภาษา  6 ┬ Copilot eval: EX + ablation        6 ┤
```

### 6.6 มือถือ (< 768px)
คอลัมน์เดียว เรียง: Context Bar (ย่อเป็น sheet) → KPI (เลื่อนแนวนอน) → AI Brief → การ์ดตามลำดับ, Copilot เปิดเป็น bottom sheet เต็มจอ, แผนที่สูง 60vh

---

## 7. Component Inventory

| Component | หน้าที่ | หมายเหตุ |
|---|---|---|
| `<InsightCard>` | โครงการ์ดมาตรฐาน: title, action icon, chip, body, footer tiles, primary button | ทุกการ์ดมีปุ่ม "ดูเป็นตาราง" และ `<ProvenanceBadge>` |
| `<KpiTile>` | ตัวเลข + delta + sparkline + **next action** 1 บรรทัด | delta มีไอคอน ▲▼ ไม่ใช้สีอย่างเดียว |
| `<HeroFigure>` | ตัวเลขเด่น 36–40px | proportional figures |
| `<ProvenanceBadge>` | "แหล่ง · n · อัปเดตเมื่อ" + ป้าย "ข้อมูลจำลอง" ถ้าเป็น synthetic | บังคับใช้ทุกการ์ด |
| `<LineageDrawer>` | แสดง SQL ที่รันจริง, rowCount, executionMs | สไตล์ AI (gradient border) |
| `<AiBriefCard>` | ข้อเสนอเชิงรุก + ปุ่ม action | gradient + ✦ |
| `<StatusChip>` | สถานะใน watchlist / quadrant | ไอคอน + ข้อความ + สี status |
| `<SegmentedControl>` | THB/MYR/USD, รัศมี, lens | pill |
| `<RangeSlider>` | เวลาเปิด-ปิด, What-If | รองรับ keyboard (ลูกศร) |
| `<MeterList>` | margin ตาม sub-group | แทน radial bars |
| `<EmptyState>` / `<LowDataState>` | n < 3 หรืออยู่นอกพื้นที่ข้อมูล | มีลิงก์ไป Data Coverage Map |
| `<ReadinessBadge>` | ระดับความพร้อมของข้อมูลราคาในอุตสาหกรรมนั้น | "พร้อม (n = 84)" / "ใช้สถิติ peer" / "เพิ่ม SKU เพื่อเริ่มเทียบ" |

### 7.1 ป้ายที่เปลี่ยนตามอุตสาหกรรม (อ่านจาก Industry Pack)
Layout และกราฟเหมือนกันทุกอุตสาหกรรม เปลี่ยนแค่ป้ายและหน่วยที่อ่านจาก `dim_category`

| ส่วน | F&B | Hospitality | Personal / Auto Services | Retail & Fashion |
|---|---|---|---|---|
| หน่วยราคา | ฿/แก้ว, ฿/จาน | ฿/คืน | ฿/ครั้ง | ฿/ชิ้น (Entry/Core/Premium) |
| แกน radar ที่ 1 | รสชาติ | ความสะอาดห้อง | ฝีมือช่าง | คุณภาพผ้า/สินค้า |
| aspect เด่น | รสชาติ, ความคุ้ม, คิว, แพ็กเกจเดลิเวอรี | ความสะอาด, Wi-Fi, เสียงรบกวน, ที่จอด | ฝีมือ, เวลารอ, การจองออนไลน์, แอร์ | ดีไซน์, ไซซ์, ห้องลอง, ราคา |
| Pricing view | Quadrant + Range Ladder เต็มรูปแบบ | Range Ladder ตามประเภทห้อง + ฤดูกาล | Internal Lens (Menu Engineering) จนกว่าข้อมูลตลาดพอ | Price band distribution + Internal Lens |

---

## 8. แผนที่ (MapLibre)
- Basemap: style สว่างโทนเทาของ OpenFreeMap (positron-like) ให้หมุดสีเด่นบนพื้น ใส่ attribution "© OpenStreetMap contributors"
- หมุด: ร้านฉัน = ม่วง ขนาดใหญ่ + วงขาว, ผู้นำ/chain = คอรัล, peer = เทา, ข้ามแดน = teal (แสดงในแผนที่แยกหรือ inset)
- วงรัศมี: เส้นม่วงบาง 1.5px + พื้น tint 6% ไม่ใช้สีแดง/น้ำเงินเต็มพื้น
- Red/Blue Ocean: ใช้ hex density แบบ **sequential ม่วงเดียว** + legend สเกล (ไม่ใช้สีแดงที่สื่อว่า "อันตราย")
- Hit target ของหมุด ≥ 24px, cluster เมื่อซูมออก

---

## 9. Accessibility & Interaction Checklist
- [ ] Contrast ข้อความ ≥ 4.5:1 และ mark ≥ 3:1 (สี series ผ่านแล้ว)
- [ ] ไม่สื่อความหมายด้วยสีอย่างเดียว (มี legend, direct label, ไอคอน)
- [ ] ทุกกราฟมี table view และ `aria-label` สรุปใจความ
- [ ] Tooltip เปิดได้ทั้ง hover และ keyboard focus
- [ ] Texture fill แบบ opt-in สำหรับพิมพ์และผู้ใช้ตาบอดสี (ตั้งค่าใน Settings)
- [ ] `prefers-reduced-motion`: ปิด animation ของกราฟ
- [ ] ภาษาไทยไม่ถูกตัดในแกน (ใช้ `width` + ellipsis + tooltip ชื่อเต็ม)
