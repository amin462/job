# ARCHITECTURE.md — Technical Blueprint & Data Engineering Specification

## 1. System Architecture & Zero-Cost Serverless Stack

SouthBiz Pulse BI is engineered to run at **$0/month infrastructure cost** without cold-start stalls during live academic defense or real entrepreneur usage.

### 1.1 Technology Stack Matrix

| Architectural Layer | Technology Choice | Zero-Cost Strategy & Rationale |
| :--- | :--- | :--- |
| **Frontend & API Layer** | **Next.js 14+ (App Router, TypeScript)** on **Vercel** | Instant edge/serverless response (avoids $15\text{-minute}$ container sleep issues); native React Server Components and API Routes. |
| **UI & Design System** | **Tailwind CSS + shadcn/ui + Lucide Icons** | Enterprise-clean aesthetic, lightweight bundle, full customization, strict `tabular-nums` alignment for financial tables. |
| **Charts & Data Tables** | **Recharts + TanStack Table v8** | Responsive business visualizations, 4-quadrant scatter matrices, and high-speed client/server sorting across $200+$ SKUs. |
| **Geospatial Visualization** | **MapLibre GL JS + OpenFreeMap / OSM Tiles** | $100\%$ free open-source WebGL vector maps; zero credit card requirement and no per-load billing traps. |
| **Data Warehouse & Auth** | **Supabase (PostgreSQL 15+ & PostGIS & Auth)** | $500\text{ MB}$ relational/spatial storage (holds $>150,000$ text records by strictly excluding raw images), native `JSONB`, spatial indexing, and Row-Level Security (RLS). |
| **ETL & Keep-Alive Scheduler** | **Python 3.11 (`Playwright`, `Pandas`) + GitHub Actions** | $2,000$ free CI/CD minutes/month; runs weekly incremental scraping and twice-weekly health pings so Supabase Free Tier never pauses after $7$ days of inactivity. |
| **LLM & Vision Engine** | **Google Gemini API (`gemini-2.5-flash`)** | Generous free tier; handles Thai/Malay/English/Chinese aspect-sentiment batching, AI Vision menu extraction, and Text-to-SQL generation. |
| **Machine Learning Suite** | **Scikit-Learn, XGBoost, LightGBM, CatBoost, ONNX** | Trained offline/CI in Python; champion model exported to lightweight ONNX/JSON for zero-cost real-time inference inside Next.js without a paid Python server. |

### 1.2 End-to-End Data Flow (4-Layer Pipeline)

```text
[Public Web Sources: Maps, Directories, Gov Weather & Holidays, FX Rates]
       |
       v  (1. Ingestion & PDPA Filter - Python + GitHub Actions Cron)
[Zone A: Supabase Staging Tables (stg_*)] -- Strips reviewer names/avatars/URLs
       |
       v  (2. Batch ETL & AI Enrichment - Gemini Batch 25 rows/call + ML Pipeline)
[Zone B: Public Enterprise Data Warehouse - Galaxy Schema (dim_* & fact_*)]
       |
       +---> [Zone C: Private Tenant Workspace (app_*) protected by Supabase RLS]
       |
       v  (3. PostGIS Spatial RPCs + Read-Only Text-to-SQL + ONNX ML Scorer)
[Next.js Decision Workspace on Vercel: Overview | Radar | Multi-SKU Pricing | Reviews | AI Co-pilot]
```

---

## 2. Database Architecture (3-Zone PostgreSQL + PostGIS Schema)

All tables reside in a single Supabase PostgreSQL instance logically separated into three zones: **Staging**, **Public Galaxy Warehouse**, and **Private Multi-Tenant OLTP**.

### 2.1 Extensions & Read-Only Role Setup

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Dedicated read-only role for safe Conversational BI (Text-to-SQL) execution
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'bi_readonly_exec') THEN
    CREATE ROLE bi_readonly_exec NOLOGIN;
  END IF;
END
$$;
```

### 2.2 Zone A — Staging Tables (Raw Sanitized Ingestion)

```sql
CREATE TABLE stg_raw_reviews (
    raw_review_id BIGSERIAL PRIMARY KEY,
    external_outlet_id TEXT NOT NULL,
    raw_outlet_name TEXT NOT NULL,
    raw_category TEXT,
    country_code CHAR(2) DEFAULT 'TH',
    province_state TEXT,
    district_city TEXT,
    latitude NUMERIC(9,6),
    longitude NUMERIC(9,6),
    star_rating SMALLINT CHECK (star_rating BETWEEN 1 AND 5),
    review_text TEXT,                       -- Reviewer name & profile URL stripped prior to insert (PDPA)
    relative_date_text TEXT,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    review_hash TEXT UNIQUE NOT NULL,       -- Deduplication fingerprint
    is_processed BOOLEAN DEFAULT FALSE
);

CREATE TABLE stg_raw_catalog_items (
    raw_item_id BIGSERIAL PRIMARY KEY,
    external_outlet_id TEXT NOT NULL,
    raw_item_name TEXT NOT NULL,
    raw_price_value NUMERIC(12,2) NOT NULL,
    raw_promo_price NUMERIC(12,2),
    currency_code CHAR(3) DEFAULT 'THB',
    raw_unit_text TEXT,
    extra_metadata JSONB DEFAULT '{}'::jsonb,
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    is_processed BOOLEAN DEFAULT FALSE
);
```

### 2.3 Zone B — Public Data Warehouse (Galaxy / Fact Constellation Schema)

The warehouse models **three distinct Fact tables** sharing **six conformed Dimension tables** so multi-currency product pricing, monthly market leadership velocity, and multilingual customer sentiment can be queried together without fan-trap distortions.

```sql
-- Dimension 1: Global & Regional Geography
CREATE TABLE dim_geography (
    geo_key SERIAL PRIMARY KEY,
    country_code CHAR(2) NOT NULL,          -- 'TH', 'MY', 'SG'
    country_name TEXT NOT NULL,
    region_name TEXT,                       -- 'Southern Gulf', 'Southern Andaman', 'Northern Malaysia'
    coast_type TEXT CHECK (coast_type IN ('gulf', 'andaman', 'inland', 'foreign')),
    province_state TEXT NOT NULL,           -- 'Songkhla', 'Phuket', 'Nakhon Si Thammarat', 'Penang'
    district_city TEXT NOT NULL,
    sub_district TEXT DEFAULT 'General',
    area_character TEXT,                    -- 'commercial_cbd', 'old_town_tourism', 'residential', 'border_hub'
    UNIQUE (country_code, province_state, district_city, sub_district)
);

-- Dimension 2: Unrestricted Industry Taxonomy
CREATE TABLE dim_category (
    category_key SERIAL PRIMARY KEY,
    industry_sector TEXT NOT NULL,          -- 'F&B', 'Fashion & Retail', 'Personal & Tech Services', 'Hospitality'
    sub_category TEXT NOT NULL,             -- 'Local Cafe', 'Halal Made-to-Order', 'Boutique Apparel', 'Barbershop'
    service_model TEXT NOT NULL,            -- 'dine_in', 'grab_and_go', 'appointment_service', 'retail_floor', 'nightly_stay'
    matching_mode TEXT NOT NULL DEFAULT 'standardized_item'
        CHECK (matching_mode IN ('standardized_item', 'attribute_band')),
    default_aspects JSONB DEFAULT '[]'::jsonb, -- Dynamic UI aspect labels for this industry
    UNIQUE (industry_sector, sub_category, service_model)
);

-- Dimension 3: Brand Hierarchy (Separates Corporate Chains from Individual Branches)
CREATE TABLE dim_brand (
    brand_key SERIAL PRIMARY KEY,
    brand_name TEXT UNIQUE NOT NULL,
    market_tier TEXT NOT NULL
        CHECK (market_tier IN ('local_micro', 'local_leader', 'national_brand', 'global_brand', 'cross_border')),
    ownership_type TEXT NOT NULL
        CHECK (ownership_type IN ('independent', 'franchise', 'corporate_chain')),
    origin_country CHAR(2) DEFAULT 'TH'
);

-- Dimension 4: Canonical Item & Price-Band Taxonomy
CREATE TABLE dim_standard_item (
    std_item_key SERIAL PRIMARY KEY,
    category_key INT NOT NULL REFERENCES dim_category(category_key),
    standard_item_name TEXT NOT NULL,       -- e.g., 'Iced Americano', 'Seafood Pad Kra Pao', 'Men Standard Haircut'
    standard_unit TEXT NOT NULL,            -- e.g., '16 oz cup', 'single dish', 'per session', 'cotton blouse'
    price_band_tier TEXT DEFAULT 'core'
        CHECK (price_band_tier IN ('entry', 'core', 'premium')),
    canonical_attributes JSONB DEFAULT '{}'::jsonb, -- Mode B attributes: {"fabric": "linen", "style": "minimal"}
    UNIQUE (category_key, standard_item_name, standard_unit)
);

-- Dimension 5: Regional Calendar & Monsoon/Holiday Flags
CREATE TABLE dim_date (
    date_key DATE PRIMARY KEY,
    year SMALLINT NOT NULL,
    quarter SMALLINT NOT NULL,
    month SMALLINT NOT NULL,
    day_of_week SMALLINT NOT NULL,
    is_weekend BOOLEAN DEFAULT FALSE,
    is_gulf_monsoon BOOLEAN DEFAULT FALSE,      -- Oct-Dec peak rain on Gulf coast
    is_andaman_monsoon BOOLEAN DEFAULT FALSE,   -- May-Oct peak rain on Andaman coast
    is_thai_holiday BOOLEAN DEFAULT FALSE,
    is_malaysia_sg_holiday BOOLEAN DEFAULT FALSE
);

-- Dimension 6: Business Outlet (Spatial Entity + Flexible JSONB Attributes)
CREATE TABLE dim_business_outlet (
    outlet_key SERIAL PRIMARY KEY,
    external_ref_id TEXT UNIQUE NOT NULL,
    brand_key INT NOT NULL REFERENCES dim_brand(brand_key),
    category_key INT NOT NULL REFERENCES dim_category(category_key),
    geo_key INT NOT NULL REFERENCES dim_geography(geo_key),
    outlet_name TEXT NOT NULL,
    location_point GEOGRAPHY(Point, 4326) NOT NULL,
    price_positioning TEXT CHECK (price_positioning IN ('budget', 'mass', 'premium')),
    operating_hours JSONB DEFAULT '{}'::jsonb,      -- e.g., {"open": "07:00", "close": "17:00", "late_night": false}
    dynamic_attributes JSONB DEFAULT '{}'::jsonb,   -- e.g., {"halal": true, "parking": false, "cross_border_qr": true}
    outlet_status TEXT DEFAULT 'active' CHECK (outlet_status IN ('active', 'temporarily_closed', 'closed')),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_outlet_location_gist ON dim_business_outlet USING GIST (location_point);
CREATE INDEX idx_outlet_dyn_attrs_gin ON dim_business_outlet USING GIN (dynamic_attributes);

-- Fact 1: Multi-Currency Product & Service Pricing
CREATE TABLE fact_product_pricing (
    pricing_fact_id BIGSERIAL PRIMARY KEY,
    outlet_key INT NOT NULL REFERENCES dim_business_outlet(outlet_key),
    std_item_key INT NOT NULL REFERENCES dim_standard_item(std_item_key),
    recorded_date_key DATE NOT NULL REFERENCES dim_date(date_key),
    raw_item_name TEXT NOT NULL,
    currency_code CHAR(3) NOT NULL DEFAULT 'THB',
    original_price NUMERIC(12,2) NOT NULL CHECK (original_price >= 0),
    exchange_rate_to_thb NUMERIC(10,4) NOT NULL DEFAULT 1.0000,
    price_thb_normalized NUMERIC(12,2) NOT NULL CHECK (price_thb_normalized >= 0),
    promo_price_thb NUMERIC(12,2),
    item_attributes JSONB DEFAULT '{}'::jsonb       -- Size, fabric, or add-on metadata
);

CREATE INDEX idx_fact_pricing_lookup ON fact_product_pricing (std_item_key, outlet_key, recorded_date_key);

-- Fact 2: Monthly Market Share & Dynamic Leader Velocity
CREATE TABLE fact_market_snapshot (
    snapshot_id BIGSERIAL PRIMARY KEY,
    outlet_key INT NOT NULL REFERENCES dim_business_outlet(outlet_key),
    snapshot_date_key DATE NOT NULL REFERENCES dim_date(date_key),
    cumulative_reviews INT NOT NULL DEFAULT 0,
    monthly_new_reviews INT NOT NULL DEFAULT 0,
    avg_star_rating NUMERIC(3,2),
    popularity_index NUMERIC(7,2),                  -- Composite velocity & rating score
    is_dynamic_local_leader BOOLEAN DEFAULT FALSE,  -- True if in top 5% of province + category
    UNIQUE (outlet_key, snapshot_date_key)
);

-- Fact 3: Multilingual Customer Voice & Aspect Sentiment
CREATE TABLE fact_customer_reviews (
    review_fact_id BIGSERIAL PRIMARY KEY,
    outlet_key INT NOT NULL REFERENCES dim_business_outlet(outlet_key),
    review_date_key DATE NOT NULL REFERENCES dim_date(date_key),
    star_rating SMALLINT NOT NULL CHECK (star_rating BETWEEN 1 AND 5),
    reviewer_language CHAR(2) NOT NULL DEFAULT 'th', -- 'th', 'ms', 'en', 'zh'
    customer_segment TEXT CHECK (customer_segment IN ('local_resident', 'domestic_tourist', 'foreign_tourist')),
    aspect_category TEXT NOT NULL,                   -- 'taste_quality', 'price_value', 'queue_speed', 'parking', 'wifi'
    sentiment_score NUMERIC(4,2) NOT NULL CHECK (sentiment_score BETWEEN -1.00 AND 1.00),
    clean_review_text TEXT NOT NULL
);

CREATE INDEX idx_fact_reviews_outlet_aspect ON fact_customer_reviews (outlet_key, aspect_category, reviewer_language);

GRANT SELECT ON ALL TABLES IN SCHEMA public TO bi_readonly_exec;
```

### 2.4 Zone C — Private Multi-Tenant Workspace & ML Leaderboard (`app_*` with RLS)

Private store economics (COGS, packaging cost, GP commissions, simulated locations, and chat logs) are strictly isolated per authenticated user.

```sql
CREATE TABLE app_user_profiles (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    user_role TEXT NOT NULL DEFAULT 'existing_owner'
        CHECK (user_role IN ('existing_owner', 'new_investor', 'admin', 'demo_guest')),
    display_business_name TEXT NOT NULL,
    claimed_outlet_key INT REFERENCES dim_business_outlet(outlet_key),
    target_category_key INT NOT NULL REFERENCES dim_category(category_key),
    target_geo_key INT REFERENCES dim_geography(geo_key),
    virtual_pin GEOGRAPHY(Point, 4326),             -- Used by new_investor or unindexed micro-shops
    default_gp_pct NUMERIC(5,2) DEFAULT 0.00,       -- Delivery/OTA commission %
    monthly_fixed_cost_thb NUMERIC(12,2) DEFAULT 0.00,
    onboarding_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE app_user_sku_portfolio (
    sku_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    std_item_key INT REFERENCES dim_standard_item(std_item_key),
    item_name TEXT NOT NULL,
    sub_group TEXT NOT NULL,                        -- e.g., 'Signature Drinks', 'Linen Tops', 'Seafood Dishes'
    price_band TEXT DEFAULT 'core' CHECK (price_band IN ('entry', 'core', 'premium')),
    unit_label TEXT DEFAULT 'unit',
    walkin_price_thb NUMERIC(12,2) NOT NULL CHECK (walkin_price_thb >= 0),
    delivery_price_thb NUMERIC(12,2),
    unit_cogs_thb NUMERIC(12,2) DEFAULT 0.00,       -- Strictly private ingredient/wholesale cost
    packaging_cost_thb NUMERIC(12,2) DEFAULT 0.00,
    channel_gp_pct NUMERIC(5,2) DEFAULT 0.00,
    est_monthly_qty INT DEFAULT 0,
    item_specs JSONB DEFAULT '{}'::jsonb,           -- Variants, sizes, fabric tags
    is_hero_item BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE app_competitor_watchlist (
    watchlist_id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    outlet_key INT NOT NULL REFERENCES dim_business_outlet(outlet_key),
    alert_note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, outlet_key)
);

CREATE TABLE app_ai_chat_logs (
    chat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    generated_sql TEXT,
    answer_summary TEXT NOT NULL,
    execution_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Publicly readable ML Experiment Registry for Academic Committee Inspection
CREATE TABLE ml_model_experiments (
    experiment_id SERIAL PRIMARY KEY,
    task_type TEXT NOT NULL,                        -- 'optimal_price_regression' | 'review_priority_classification'
    model_name TEXT NOT NULL,                       -- Ridge, SVR, RandomForest, XGBoost, LightGBM, CatBoost
    algorithm_family TEXT NOT NULL,
    cv_folds SMALLINT DEFAULT 5,
    r2_score NUMERIC(6,4),
    rmse_score NUMERIC(10,4),
    mae_score NUMERIC(10,4),
    mape_pct NUMERIC(6,2),
    f1_macro NUMERIC(6,4),
    top_shap_features JSONB DEFAULT '[]'::jsonb,
    hyperparameters JSONB DEFAULT '{}'::jsonb,
    is_champion BOOLEAN DEFAULT FALSE,
    trained_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enforce Row-Level Security on all private tenant tables
ALTER TABLE app_user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_user_sku_portfolio ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_competitor_watchlist ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_ai_chat_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_profiles ON app_user_profiles
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY tenant_isolation_skus ON app_user_sku_portfolio
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY tenant_isolation_watchlist ON app_competitor_watchlist
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY tenant_isolation_chats ON app_ai_chat_logs
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- Ensure the Text-to-SQL role can NEVER read private user costs
REVOKE ALL ON app_user_profiles, app_user_sku_portfolio, app_competitor_watchlist, app_ai_chat_logs FROM bi_readonly_exec;
```

---

## 3. Geospatial RPC & Store Economics Formulas

### 3.1 PostGIS Spatial Competitor Radar Function

```sql
CREATE OR REPLACE FUNCTION rpc_get_competitors_in_radius(
    p_lng DOUBLE PRECISION,
    p_lat DOUBLE PRECISION,
    p_radius_meters DOUBLE PRECISION,
    p_category_key INT
)
RETURNS TABLE (
    outlet_key INT,
    outlet_name TEXT,
    brand_name TEXT,
    market_tier TEXT,
    distance_km NUMERIC,
    lng DOUBLE PRECISION,
    lat DOUBLE PRECISION,
    operating_hours JSONB,
    dynamic_attributes JSONB,
    avg_star_rating NUMERIC
)
LANGUAGE sql STABLE AS $$
    SELECT
        o.outlet_key,
        o.outlet_name,
        b.brand_name,
        CASE
            WHEN ms.is_dynamic_local_leader IS TRUE AND b.market_tier = 'local_micro' THEN 'local_leader'
            ELSE b.market_tier
        END AS market_tier,
        ROUND((ST_Distance(o.location_point, ST_SetSRID(ST_MakePoint(p_lng, p_lat), 4326)::geography) / 1000.0)::numeric, 2) AS distance_km,
        ST_X(o.location_point::geometry) AS lng,
        ST_Y(o.location_point::geometry) AS lat,
        o.operating_hours,
        o.dynamic_attributes,
        COALESCE(ms.avg_star_rating, 0.0) AS avg_star_rating
    FROM dim_business_outlet o
    JOIN dim_brand b ON o.brand_key = b.brand_key
    LEFT JOIN LATERAL (
        SELECT avg_star_rating, is_dynamic_local_leader
        FROM fact_market_snapshot s
        WHERE s.outlet_key = o.outlet_key
        ORDER BY s.snapshot_date_key DESC
        LIMIT 1
    ) ms ON TRUE
    WHERE o.category_key = p_category_key
      AND o.outlet_status = 'active'
      AND (
          ST_DWithin(o.location_point, ST_SetSRID(ST_MakePoint(p_lng, p_lat), 4326)::geography, p_radius_meters)
          OR b.market_tier IN ('national_brand', 'global_brand', 'cross_border')
      )
    ORDER BY distance_km ASC;
$$;
```

### 3.2 Dynamic Local Market Leader Formula
During weekly ETL snapshot generation, an independent outlet (`local_micro`) is automatically promoted to `is_dynamic_local_leader = TRUE` if its composite popularity score ranks in the top $5\%$ of its province and category:

$$\text{Popularity Index} = (0.60 \times \ln(1 + N_{\text{cumulative}})) + (0.40 \times \ln(1 + N_{\text{monthly\_new}})) \times \left(\frac{\bar{S}_{\text{rating}}}{5.0}\right)$$

### 3.3 Private Store Economics & Delivery GP Formulas
For every SKU in `app_user_sku_portfolio`, the Pricing & What-If Simulator computes:
* **Walk-in Unit Gross Margin ($\text{THB}$ and $\%$):**
  $$\text{Margin}_{\text{walk-in}} = P_{\text{walk-in}} - C_{\text{cogs}}, \quad \text{Margin}\% = \left(\frac{P_{\text{walk-in}} - C_{\text{cogs}}}{P_{\text{walk-in}}}\right) \times 100$$
* **Delivery / OTA Net Profit After Commission ($\text{GP}\%$) & Packaging:**
  $$\text{Net Profit}_{\text{delivery}} = P_{\text{delivery}} \times \left(1 - \frac{\text{GP}\%}{100}\right) - (C_{\text{cogs}} + C_{\text{pack}})$$
* **Market Price Gap Percentage:**
  $$\text{Price Gap}\% = \left(\frac{P_{\text{walk-in}} - \bar{P}_{\text{peer}}}{\bar{P}_{\text{peer}}}\right) \times 100$$

---

## 4. Six-Model Machine Learning Benchmark Pipeline

To satisfy rigorous Data Science evaluation, the repository includes an automated ML benchmarking pipeline (`/ml/train_benchmark.py`) that trains and cross-validates **6 distinct algorithm families** for **Fair Market Price & Competitiveness Estimation**:

1. **Ridge / ElasticNet Regression** (*Regularized Linear Baseline*)
2. **Support Vector Regressor — SVR with RBF Kernel** (*Kernel Distance Margin Family*)
3. **Random Forest Regressor** (*Bagging Decision Trees Family*)
4. **XGBoost Regressor** (*Depth-wise Gradient Boosted Trees*)
5. **LightGBM Regressor** (*Leaf-wise Histogram Gradient Boosting*)
6. **CatBoost Regressor** (*Symmetric Oblivious Trees with Ordered Target Encoding* — handles high-cardinality features like `sub_category`, `province_state`, `price_band_tier`, and `area_character` natively without one-hot explosion)

### 4.1 Validation Protocol & Selection Metrics
All 6 models are evaluated using **$5\text{-Fold Stratified/Group Cross-Validation}$** (grouped by `outlet_key` to prevent data leakage across items from the same store) using four metrics:

$$R^2 = 1 - \frac{\sum_{i=1}^{n}(y_i - \hat{y}_i)^2}{\sum_{i=1}^{n}(y_i - \bar{y})^2}, \quad \text{RMSE} = \sqrt{\frac{1}{n}\sum_{i=1}^{n}(y_i - \hat{y}_i)^2}, \quad \text{MAE} = \frac{1}{n}\sum_{i=1}^{n}|y_i - \hat{y}_i|, \quad \text{MAPE} = \frac{100\%}{n}\sum_{i=1}^{n}\left|\frac{y_i - \hat{y}_i}{y_i}\right|$$

### 4.2 Zero-Cost Champion Deployment Pattern
1. **Leaderboard Logging:** All 6 cross-validated scores and **SHAP** feature importance weights are written to `ml_model_experiments`, flagging the lowest-$\text{RMSE}$ / highest-$R^2$ model with `is_champion = TRUE`.
2. **Serverless Inference Without Paid Python Hosting:** The winning model is exported via `onnxmltools` / `skl2onnx` into `/public/models/champion_pricing.onnx` ($< 2\text{ MB}$) and executed inside Next.js API Routes using `onnxruntime-node` for sub-$15\text{ ms}$ What-If Pricing Slider predictions on Vercel Free Tier.

---

## 5. Explainable Conversational BI (Safe Text-to-SQL Engine)

To eliminate LLM arithmetic hallucinations, the AI Business Co-pilot never guesses numbers from raw text. Every analytical question follows a strict 5-stage pipeline:

1. **Tenant Context Injection:** The Next.js route `/api/copilot/query` reads the user's `claimed_outlet_key`, `target_category_key`, `province_state`, and active UI filters (`season`, `currency`, `market_tier`).
2. **Schema-Scoped SQL Generation:** Gemini receives only the DDL summary of the 9 public Galaxy Schema tables (`dim_*`, `fact_*`) and generates a single PostgreSQL `SELECT` statement.
3. **AST / Regex Security Guardrail:** Before database execution, a server-side validator enforces:
   * Query must start with `SELECT` or `WITH`.
   * Rejects any semicolon-chained statements or forbidden keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `GRANT`, `COPY`, `pg_sleep`, `app_user_`).
   * Automatically appends `LIMIT 100` if no limit is present.
4. **Sandboxed Read-Only Execution:** Executed via a restricted database function running under `bi_readonly_exec` with `SET LOCAL statement_timeout = '4000ms'`.
5. **Grounded Synthesis + Data Lineage Payload:** Gemini summarizes the exact returned rows into actionable Thai business advice, and the API returns `{ answerMarkdown, executedSql, rowCount, executionMs }` so the frontend renders the expandable **"View Data Lineage / SQL"** badge.

---

## 6. Design System & Repository Structure

### 6.1 Visual & Semantic Tokens
* **Typography:** `IBM Plex Sans Thai` paired with `Inter`; mandatory `font-variant-numeric: tabular-nums` on all KPI cards, currency columns, percentages, and distance badges.
* **Semantic Palette:**
  * `--color-my-store` (`#2563EB` Deep Blue) — Always represents the logged-in user's store.
  * `--color-market-leader` (`#F59E0B` Amber Gold) — Provincial Champions & National/Global Benchmarks.
  * `--color-market-avg` (`#64748B` Slate) — Local peer average.
  * `--color-advantage` (`#10B981` Emerald) — Competitive strengths & healthy net margins.
  * `--color-risk-gap` (`#EF4444` Rose Red) — Urgent customer pain points & overpriced/low-margin SKUs.
  * `--color-ai-accent` (`#7C3AED` Violet) — Explainable AI briefs, SQL lineage badges, and Co-pilot drawer.

### 6.2 Monorepo Directory Layout

```text
southbiz-pulse-bi/
├── CONTEXT.md                        # Business domain, Southern Thailand factors & functional spec
├── ARCHITECTURE.md                   # Technical architecture, Galaxy Schema DDL, ML & Text-to-SQL spec
├── .github/workflows/
│   ├── weekly_scrape_etl.yml         # Scheduled scraping + Gemini batch enrichment + snapshot refresh
│   └── supabase_keepalive.yml        # Twice-weekly lightweight query preventing free-tier DB pause
├── supabase/
│   ├── migrations/
│   │   ├── 001_staging_and_galaxy_warehouse.sql
│   │   ├── 002_private_workspace_and_rls.sql
│   │   └── 003_postgis_rpc_and_readonly_role.sql
│   └── seed_demo_roles.sql           # PDPA-safe demo datasets for 1-click Committee Inspector login
├── etl/
│   ├── scraper_public_places.py      # Public listing/review scraper with immediate PII stripping
│   ├── enrich_reviews_gemini.py      # Batched (25 reviews/call) multilingual aspect-sentiment tagger
│   ├── normalize_catalog_items.py    # Maps raw menus/garments to dim_standard_item & FX rates
│   └── update_market_leaders.py      # Computes monthly Popularity Index & top 5% local_leader flags
├── ml/
│   ├── train_benchmark.py            # Trains 6 ML models (5-fold CV), computes SHAP, logs leaderboard
│   └── export_onnx.py                # Exports winning champion model to public/models/champion.onnx
└── src/
    ├── app/
    │   ├── (auth)/login/page.tsx     # Supabase Auth + 1-click Demo Role buttons for examiners
    │   ├── onboarding/page.tsx       # 3-step store binding / virtual pin / multi-SKU import wizard
    │   ├── workspace/
    │   │   ├── layout.tsx            # Sticky Global Context Bar + 4-view Sidebar + AI Co-pilot Drawer
    │   │   ├── overview/page.tsx     # KPIs, Proactive Explainable AI Card, 5-axis benchmark
    │   │   ├── radar/page.tsx        # MapLibre GL JS + PostGIS radius rings + JSONB attribute table
    │   │   ├── pricing/page.tsx      # 3-level SKU drill-down, 4-quadrant matrix, What-If GP Simulator
    │   │   ├── reviews/page.tsx      # Industry-adaptive aspect sentiment + TH/MS/EN/ZH feed
    │   │   └── ml-lab/page.tsx       # 6-Model ML Leaderboard & SHAP explainability view for defense
    │   └── api/
    │       ├── copilot/query/route.ts    # Guardrailed Text-to-SQL endpoint
    │       ├── catalog/vision/route.ts   # Gemini Vision menu/lookbook table extractor (no image save)
    │       └── simulator/predict/route.ts # Real-time ONNX champion model inference
    ├── components/
    └── lib/
        ├── supabase/
        ├── sql-guardrail.ts
        └── store-economics.ts
```
