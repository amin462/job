# CONTEXT.md — Project Domain, Business Logic & Functional Specification

## 1. Project Overview & Academic Positioning

**Project Name:** SouthBiz Pulse BI  
**Domain:** Decision Intelligence, Local Market Data Warehouse & Conversational BI for SMEs in Southern Thailand  
**Academic Context:** Business Computer Capstone Project (designed for evaluation by Data Engineering / Data Science committee members)

### 1.1 Problem Statement
Small and micro-entrepreneurs in Southern Thailand—ranging from street-side halal food stalls, local coffee shops, and neighborhood barbershops to boutique hotels and local fashion retailers—lack accessible market intelligence. Decisions regarding menu/product pricing, operating hours, service differentiation, and store location are typically made by guesswork rather than empirical market data. Meanwhile, traditional student capstone systems that only implement basic CRUD operations no longer demonstrate sufficient technical or analytical depth.

### 1.2 Core Value Proposition
SouthBiz Pulse BI transforms fragmented public web data (business listings, menus/catalogs, multilingual customer reviews, regional monsoon patterns, cross-border holidays, and foreign exchange rates) into an enterprise-grade **Decision Support Workspace**:
1. **Multi-Tier Competitive Intelligence:** Benchmarks any local shop against immediate street-level peers, provincial market leaders, national chains, global brands, and cross-border competitors (e.g., Penang and Kuala Lumpur, Malaysia).
2. **Unrestricted Industry Coverage:** Supports every local business sector—not limited to restaurants—through hierarchical category taxonomy, flexible `JSONB` attributes, and dual-mode SKU matching.
3. **Private Store Economics Meets Public Market Data:** Combines public competitor pricing with an owner's strictly private unit costs (COGS), packaging costs, and delivery/OTA commission rates (`GP%`) to optimize real net profit.
4. **Rigorous Data Engineering & Machine Learning:** Backed by a **Galaxy Schema (Fact Constellation)** Data Warehouse, a **6-Model Machine Learning Benchmark Pipeline** with SHAP explainability, and a **Safe Read-Only Text-to-SQL Conversational BI Co-pilot**—deployed at **$0/month infrastructure cost**.

---

## 2. Regional Domain Context: Southern Thailand Market Dynamics

The system explicitly models economic, geographic, and cultural variables unique to Southern Thailand:

### 2.1 Dual-Coast Monsoon Seasonality
Southern Thailand has two distinct coastlines with different monsoon cycles that directly shift customer foot traffic, delivery demand, raw seafood costs, and hotel occupancy:
* **Gulf of Thailand Coast (e.g., Songkhla, Hat Yai, Nakhon Si Thammarat, Surat Thani):** Peak northeast monsoon and heavy rainfall from **October to December**.
* **Andaman Coast (e.g., Phuket, Krabi, Trang, Satun):** Peak southwest monsoon (Green Season) from **May to October**.

### 2.2 Cross-Border Tourism & Multilingual Customer Base
Proximity to Malaysia and Singapore creates strong cross-border consumer flows during Malaysian school holidays, public holidays, and weekends:
* **Multilingual Voice of Customer:** Customer reviews in the region span **Thai (`th`)**, **Bahasa Melayu (`ms`)**, **English (`en`)**, and **Chinese (`zh`)**. Extracting aspect sentiment across languages reveals blind spots (e.g., Malaysian tourists praising taste in Malay while complaining about long queues or lack of DuitNow cross-border QR payment).
* **Multi-Currency Price Benchmarking:** Entrepreneurs in border and tourist cities compete for the same regional travelers as hubs like **Georgetown (Penang)** and **Kuala Lumpur**. Prices are stored in native currency and normalized into `THB` (with instant UI toggling across `THB`, `MYR`, and `USD`).

### 2.3 Local Operational Realities
* **Halal Market Visibility:** Crucial across Southern provinces for both local Muslim residents and Malaysian/Indonesian visitors.
* **Urban & Old Town Constraints:** Narrow streets in commercial hubs (e.g., Kim Yong Market in Hat Yai, Songkhla Old Town, Phuket Old Town) make car parking, rain shelter, Wi-Fi quality, and early-morning or late-night operating hours decisive competitive differentiators.

---

## 3. Unrestricted Industry Coverage & 5-Tier Benchmarking

### 3.1 Supported Business Sectors
Rather than hardcoding columns for a single industry, the platform supports all SME categories via `dim_category` and `dynamic_attributes`:
* **Food & Beverage (F&B):** Made-to-order street stalls, halal restaurants, specialty cafes, traditional kopi shops, bakeries.
* **Personal & Technical Services:** Barbershops, hair/beauty salons, massage & spas, auto/motorcycle repair shops, laundry services.
* **Hospitality & Stays:** Boutique hotels, hostels, guesthouses, resorts.
* **Fashion, Apparel & General Retail:** Local clothing boutiques, muslimah/batik fashion stores, souvenir shops, neighborhood grocery/convenience stores.

### 3.2 Five Competitive Benchmark Tiers
Users can filter or compare their business across five distinct competitive scopes:
1. **`local_micro` (Immediate Radius Peers):** Independent shops in the same category within a user-selected **PostGIS radius (`1 km`, `3 km`, or `5 km`)**.
2. **`local_leader` (Provincial Champions):** Top $5\%$ performing outlets in the same province and category, dynamically identified each month via the warehouse's composite **Popularity Index** (review volume + monthly review velocity + star rating).
3. **`national_brand` (National Chains & Franchises):** Major domestic chains (e.g., Cafe Amazon, Punthai, national retail/restaurant chains) operating in the area.
4. **`global_brand` (Global Chains):** International corporate chains setting premium market price ceilings.
5. **`cross_border` (Foreign Regional Peers):** Comparable businesses in neighboring markets (primarily Penang and Kuala Lumpur, Malaysia) normalized by unit size and exchange rate.

---

## 4. Target User Roles & Post-Login User Journey

### 4.1 User Roles
1. **Existing Business Owner (`existing_owner`):** Claims their existing store (or registers an unlisted micro-shop) to monitor health, compare multi-SKU pricing and net margins after GP, and fix customer complaints.
2. **New Entrepreneur / Location Investor (`new_investor`):** Does not yet own a physical shop; drops a **Virtual Pin** on a candidate street corner to inspect competitor saturation (Red vs. Blue Ocean), operating-hour gaps, local customer pain points, and recommended launch pricing.
3. **System Administrator / Data Engineer (`admin`):** Monitors scraping pipelines, reviews canonical item mappings, and inspects ML benchmark runs.
4. **One-Click Examiner Demo Guest (`demo_guest`):** Pre-configured instant login buttons on the Login screen (e.g., *Demo: Hat Yai Cafe*, *Demo: Songkhla Halal Kitchen*, *Demo: Nakhon Barber*, *Demo: Boutique Fashion / Phuket Stay*) allowing academic defense examiners to test full functionality immediately without registration friction.

### 4.2 Three-Step Onboarding Flow (First Login Only)
* **Step 1 — Role & Intent Selection:** Choose *"I operate an existing business"* or *"I am scouting a location for a new business"*.
* **Step 2 — Store Binding or Virtual Pinning:**
  * *Existing Owner:* Search and claim an outlet already indexed in `dim_business_outlet`, or pin an unlisted micro-shop on the map and select its industry category.
  * *New Investor:* Select target industry category and drop a Virtual Pin on the map to generate a simulated store profile.
* **Step 3 — Catalog & Private Cost Setup:** Import or add core products/services alongside private unit cost (COGS), packaging cost, and delivery/OTA commission (`GP%`). Subsequent logins bypass onboarding and open the user's personalized workspace directly.

### 4.3 Dynamic Industry Personalization
All users share a unified workspace layout, but `target_category_key` dynamically adapts the analytical lens:
* **F&B / Cafe Owner sees:** Taste, portion value, halal status, delivery packaging, queue speed, and cup/dish unit comparisons.
* **Barbershop / Service Owner sees:** Craftsman skill, walk-in wait time, online booking availability, air-conditioning, and per-session service rates.
* **Boutique Hotel Owner sees:** Room cleanliness, 3rd-floor Wi-Fi stability, street noise, parking, foreign guest mix, and seasonal/monsoon nightly rates.
* **Fashion / Retail Owner sees:** Fabric quality, design uniqueness, sizing variety, try-on comfort, and price-band positioning (`Entry / Core / Premium`).

---

## 5. Multi-SKU Catalog & Cross-Industry Matching Logic

Real businesses sell dozens or hundreds of items with varying sizes, add-ons, and seasonal collections. The platform prevents both manual data-entry fatigue and apples-to-oranges price distortion.

### 5.1 Three Low-Friction SKU Ingestion Channels
1. **1-Click Public Catalog Sync:** Automatically populates the owner's portfolio from public delivery/directory items already scraped for their claimed outlet.
2. **Gemini Vision Menu / Lookbook Extractor:** Owners upload a photo of a vinyl shop sign, printed menu, service price board, or fashion price tag list; Gemini Vision extracts structured item names, units, and prices into an editable table (discarding the raw image afterward to preserve zero-cost database storage).
3. **CSV / Bulk Table Import & Manual Quick-Add:** Rapid spreadsheet paste or inline editing for private COGS, packaging costs, and GP percentages.

### 5.2 Dual Product Matching Modes (`matching_mode`)
* **Mode A — Standardized Canonical Item Matching (`standardized_item`):**  
  Used for F&B, cafes, personal services, and standard hotel room types. Maps colloquial local names (e.g., *"โอเลี้ยงยกล้อ"* or *"Iced CEO Americano"*) to a shared canonical item in `dim_standard_item` (e.g., `Iced Black Coffee — 16 oz cup`) so prices compare accurately across tiers and countries.
* **Mode B — Attribute & Price-Band Cohort Matching (`attribute_band`):**  
  Used for fashion boutiques, apparel, handicrafts, and specialty retail where no two shops sell the exact same SKU. Items are tagged with structured attributes (`{"garment": "shirt", "fabric": "linen", "style": "minimal"}`) and grouped into **Price Architecture Tiers (`Entry`, `Core`, `Premium`)** to compare price positioning and margin structure against competing boutiques.

### 5.3 Clutter-Free Multi-SKU Visualization (3-Level Drill-Down)
To keep the UI fast and readable even when a store manages $100+$ SKUs:
1. **Sub-Category Summary Cards:** High-level margin and market price gap by product group (e.g., *Coffee*, *Tea*, *Toast* or *Tops*, *Dresses*, *Accessories*).
2. **4-Quadrant Portfolio Scatter Matrix:** Plots every SKU by **Market Price Competitiveness (X-axis)** vs. **Net Profit Margin After GP (Y-axis)** into four actionable buckets: *Hero Stars*, *Hidden Margin Gems*, *Traffic Pullers*, and *Margin Bleeders (Urgent Fix)*.
3. **Searchable & Sortable SKU Table:** Powered by tabular numeric alignment, price positioning bars, and inline What-If slider simulation.

---

## 6. Functional Workspace Modules

1. **Global Context Bar (Sticky Top):** Displays active business profile, Benchmark Tier selector, Seasonality/Holiday context selector (`Baseline`, `Southern Monsoon`, `Thai-Malaysia Long Holiday`), Currency switcher (`THB / MYR / USD`), and AI Co-pilot toggle.
2. **View 1 — Executive Overview & Proactive AI Brief:** 4 actionable KPI cards with concrete next-step recommendations, a Proactive Anomaly/Strategy Card with an expandable **"View Data Lineage / SQL"** panel, a 5-axis capability benchmark chart, and a monthly popularity velocity trend chart.
3. **View 2 — Geospatial Competitor Radar:** Interactive vector map with `1 km / 3 km / 5 km` radius rings, market saturation indicator (Red vs. Blue Ocean), operating-hour gap detector, and `JSONB` feature comparison table.
4. **View 3 — Multi-SKU Pricing, GP Margin & What-If Simulator:** Price positioning bars, 4-quadrant SKU matrix, delivery GP net-margin calculator, and interactive slider driven by the champion ML model.
5. **View 4 — Multilingual Customer Voice (`TH / MS / EN / ZH`):** Aspect-based sentiment comparison against market leaders, tourist language breakdown, and filterable PDPA-anonymized review feed.
6. **View 5 — ML Benchmark & Committee Inspector Lab:** Transparent academic defense screen displaying 5-fold cross-validation metrics ($R^2, \text{RMSE}, \text{MAE}, \text{MAPE}$) across all 6 trained ML models alongside SHAP feature importance charts.
7. **Right Drawer — Conversational BI Co-pilot:** Natural-language business Q&A powered by guardrailed read-only Text-to-SQL over the Galaxy Schema, returning grounded numbers plus the exact executed SQL query.

---

## 7. Data Governance, PDPA Compliance & Zero-Hallucination Standards

* **Strict PDPA Privacy by Design:** Scraping pipelines strip reviewer usernames, profile photos, and personal account links *before* staging insertion. Only public business metadata and anonymized review text are stored.
* **Multi-Tenant Cost Confidentiality:** Private business inputs (unit COGS, packaging cost, delivery GP%, watchlists, and AI chat logs) are protected by PostgreSQL Row-Level Security (`RLS`) and completely revoked from the read-only Text-to-SQL database role.
* **No Unverified LLM Arithmetic:** Every metric, price gap, and chart value comes from deterministic PostgreSQL/PostGIS aggregations or cross-validated ML model inference—never freehand LLM number generation.
