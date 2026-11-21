export type Locale = "th" | "en";

export type UserRole = "visitor" | "student" | "institution" | "admin";

export type DemoPersonaKey =
  | "student_data"
  | "student_acc"
  | "institution"
  | "admin";

export interface PublicSummary {
  n_postings: number;
  n_with_salary: number;
  pct_with_salary: number | null;
  n_with_skills: number;
  pct_with_skills: number | null;
  avg_skills_per_posting: number | null;
  n_provinces: number;
  n_occupations: number;
  n_skills_catalog: number;
  min_date_posted: string | null;
  max_date_posted: string | null;
  last_updated_at: string | null;
}

export interface SkillDemandWeeklyRow {
  week_start: string;
  scope_level: "national" | "region" | "province";
  region: string;
  province_th: string;
  is_south14: boolean | null;
  skill_key: number;
  skill_canonical: string;
  skill_slug: string;
  skill_name_th: string;
  skill_type: string;
  skill_group: string;
  n_postings: number;
  n_new_postings: number;
  n_scope_postings: number;
  weighted_active_sum: number | null;
  weighted_new_sum: number | null;
  weighted_share: number | null;
  weighted_new_share: number | null;
  is_suppressed: boolean;
}

export interface SkillCooccurrenceRow {
  skill_key: number;
  skill_canonical: string;
  skill_slug: string;
  skill_name_th: string;
  skill_group: string;
  co_skill_key: number;
  co_skill_canonical: string;
  co_skill_slug: string;
  co_skill_name_th: string;
  co_skill_group: string;
  n_postings: number;
  weighted_co_count: number;
  co_share: number;
  jaccard_similarity: number;
  rank_order: number;
}

export interface OccupationSkillProfileRow {
  occupation_cluster: string;
  occupation_slug: string;
  occupation_name_th: string;
  skill_key: number;
  skill_canonical: string;
  skill_slug: string;
  skill_name_th: string;
  skill_type: string;
  skill_group: string;
  n_occ_postings: number;
  n_postings: number;
  weighted_share: number | null;
  raw_share: number | null;
  rank_in_occupation: number;
  is_suppressed: boolean;
}

export interface SalaryStatsRow {
  scope_type: string;
  occupation_cluster: string;
  occupation_slug: string;
  region: string;
  province_th: string;
  experience_band: string;
  n_postings: number;
  salary_p25: number | null;
  salary_p50: number | null;
  salary_p75: number | null;
  salary_mean: number | null;
  salary_min_obs: number | null;
  salary_max_obs: number | null;
  is_suppressed: boolean;
}

export interface PostingVolumeDailyRow {
  date_key: number;
  full_date: string;
  year: number;
  month: number;
  week: number;
  week_start: string;
  scope_level: "national" | "region" | "province";
  region: string;
  province_th: string;
  is_south14: boolean | null;
  n_postings: number;
  n_with_salary: number;
  weighted_volume: number | null;
  salary_share: number | null;
  is_suppressed: boolean;
}

export interface CurriculumCoverageRefRow {
  occupation_cluster: string;
  occupation_slug: string;
  occupation_name_th: string;
  skill_key: number;
  skill_canonical: string;
  skill_slug: string;
  skill_name_th: string;
  skill_type: string;
  skill_group: string;
  n_occ_postings: number;
  n_postings: number;
  weighted_share: number | null;
  importance_weight: number | null;
  rank_order: number;
  is_core_skill: boolean;
  is_suppressed: boolean;
}

export interface PipelineStatusRow {
  scrape_run_id: number;
  source: string;
  scope: string | null;
  started_at: string;
  finished_at: string | null;
  status: string;
  n_discovered: number;
  n_fetched: number;
  n_failed: number;
  is_blocked_flag: boolean;
  duration_seconds: number | null;
  n_listings_seen: number;
}

export interface DqSummaryRow {
  dq_id: number;
  scrape_run_id: number | null;
  source: string | null;
  dimension: string;
  check_name: string;
  table_name: string;
  n_total: number;
  n_fail: number;
  fail_rate: number;
  pass: boolean;
  details: string | null;
  checked_at: string;
}

export interface TopLinkRow {
  occupation_cluster: string;
  occupation_slug: string;
  province_th: string;
  region: string;
  source_name: string;
  source_url: string;
  title_short: string;
  date_posted: string | null;
  n_postings: number;
  rank_order: number;
}

export interface PendingAliasRow {
  suggestion_id: number;
  pending_alias: string;
  freq: number;
  status: "pending" | "approved" | "rejected";
  suggested_skill_key: number | null;
  suggested_skill_canonical: string | null;
  suggested_matched_alias: string | null;
  similarity_score: number | null;
  sample_context?: string | null;
}

export interface DimSkill {
  skill_key: number;
  skill_canonical: string;
  skill_slug: string;
  skill_name_th: string;
  skill_type: string;
  skill_group: string;
  onet_ref: string | null;
  esco_ref: string | null;
  aliases: string[];
}

export interface DimOccupation {
  occupation_cluster: string;
  occupation_slug: string;
  occupation_name_th: string;
  onet_ref: string | null;
  n_titles: number;
}

export interface DimLocation {
  location_key: number;
  province_code: string;
  province_th: string;
  province_en: string;
  region: string;
  is_south14: boolean;
}

export interface MlLeaderboardRow {
  experiment_id?: number;
  task?: string;
  dataset_version?: string;
  n_rows?: number;
  created_at?: string;
  model_name: string;
  fold: number;
  is_summary: boolean;
  r2: number;
  rmse: number;
  mae: number;
  mape: number;
  r2_sd?: number | null;
  rmse_sd?: number | null;
  mae_sd?: number | null;
  mape_sd?: number | null;
  fit_seconds: number;
  params?: Record<string, unknown> | null;
  is_champion: boolean;
}

export interface MlFeatureImportanceRow {
  experiment_id?: number;
  model_name: string;
  feature: string;
  importance: number;
}

export interface SalaryPredictionRow {
  prediction_id?: number;
  model_name: string;
  occupation_cluster: string;
  province_th: string;
  region: string;
  experience_band: string;
  education_level: string;
  employment_type: string;
  skill_bundle: string;
  pred_p25: number;
  pred_p50: number;
  pred_p75: number;
  mae_cv?: number | null;
  mape_cv?: number | null;
  n_train_support?: number;
}

export interface LaborMonthlyRow {
  date_key: number;
  period_label: string;
  granularity: string;
  metric: string;
  metric_th: string;
  value: number;
  unit: string;
  source: string;
  dataset_id: string;
  dataset_url: string;
}

export interface OnetSkillBenchmarkRow {
  skill_canonical: string;
  skill_slug?: string;
  skill_name_th?: string;
  n_onet_occupations: number;
  hot_tech_count: number;
  in_demand_count: number;
  sample_examples?: string;
}

export interface SeedMartsData {
  public_summary: PublicSummary;
  skill_demand_weekly: SkillDemandWeeklyRow[];
  skill_cooccurrence: SkillCooccurrenceRow[];
  occupation_skill_profile: OccupationSkillProfileRow[];
  salary_stats: SalaryStatsRow[];
  posting_volume_daily: PostingVolumeDailyRow[];
  curriculum_coverage_ref: CurriculumCoverageRefRow[];
  pipeline_status: PipelineStatusRow[];
  dq_summary: DqSummaryRow[];
  top_links: TopLinkRow[];
  pending_aliases: PendingAliasRow[];
  dim_skills: DimSkill[];
  dim_occupations: DimOccupation[];
  dim_locations: DimLocation[];
  ml_leaderboard: MlLeaderboardRow[];
  ml_feature_importance: MlFeatureImportanceRow[];
  salary_prediction: SalaryPredictionRow[];
  labor_monthly_2y?: LaborMonthlyRow[];
  onet_skill_benchmark?: OnetSkillBenchmarkRow[];
}

export interface UserSkill {
  skill_key: number;
  skill_canonical?: string;
  skill_slug?: string;
  skill_name_th?: string;
  skill_type?: string;
  skill_group?: string;
  level: 1 | 2 | 3;
}

export interface CurriculumSkillEntry {
  curriculum_id: number;
  skill_key: number;
  course_name: string;
}

export interface CurriculumItem {
  curriculum_id: number;
  owner_id: string;
  name: string;
  target_occupation_cluster: string;
  created_at: string;
  skills: CurriculumSkillEntry[];
}

export interface UserSession {
  user_id: string;
  email: string;
  role: Exclude<UserRole, "visitor">;
  display_name: string;
  province_th: string | null;
  target_occupation_cluster: string | null;
  preferred_language: Locale;
  is_demo: boolean;
  persona?: DemoPersonaKey;
}

export interface PageContextChart {
  id: string;
  title: string;
  rows: (string | number | boolean | null)[][];
}

export interface PageContextPayload {
  page: string;
  route: string;
  title: string;
  filters?: Record<string, string | number | boolean | null | undefined>;
  kpis?: Array<{ label: string; value: string | number | null; unit?: string }>;
  charts?: PageContextChart[];
  tableTop?: Record<string, string | number | boolean | null>[];
  asOf?: string;
  dataNotes?: string[];
}

export interface ChatApiResponse {
  answer: string;
  citedCards: string[];
  suggestedPages: Array<{ label: string; href: string }>;
  mode: "gemini" | "grounded-fallback";
}

export interface SalaryEstimateRequest {
  occupation_cluster: string;
  province_th: string;
  region?: string;
  experience_band: string;
  education_level: string;
  employment_type: string;
  skills: string[];
  candidate_skills?: string[];
  gender?: never;
  age?: never;
}

export interface SkillUpliftItem {
  skill: string;
  delta_p50: number;
  new_p50: number;
}

export interface SalaryEstimateResponse {
  p25: number;
  p50: number;
  p75: number;
  model_name: string;
  cv_mae: number | null;
  cv_mape: number | null;
  source: "ml-api" | "fallback_prediction" | "fallback_median";
  badge: string;
  disclaimer: string;
  n_support: number | null;
  low_support_warning: boolean;
  uplifts: SkillUpliftItem[];
}
