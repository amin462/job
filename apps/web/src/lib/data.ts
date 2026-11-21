import fs from "node:fs";
import path from "node:path";
import type {
  CurriculumCoverageRefRow,
  CurriculumItem,
  DimLocation,
  DimOccupation,
  DimSkill,
  DqSummaryRow,
  LaborMonthlyRow,
  MlFeatureImportanceRow,
  MlLeaderboardRow,
  OccupationSkillProfileRow,
  OnetSkillBenchmarkRow,
  PendingAliasRow,
  PipelineStatusRow,
  PostingVolumeDailyRow,
  PublicSummary,
  SalaryPredictionRow,
  SalaryStatsRow,
  SeedMartsData,
  SkillCooccurrenceRow,
  SkillDemandWeeklyRow,
  TopLinkRow,
  UserSession,
  UserSkill,
} from "@/types/marts";
import { isSupabaseConfigured } from "./supabase/config";
import { createSupabaseServerClient } from "./supabase/server";
import {
  applyDemoAliasOverrides,
  getDemoStore,
  getDemoUserCurricula,
  getDemoUserSkills,
} from "./auth";
import { checkRouteAccess } from "./compliance";

let cachedSeed: { mtimeMs: number; data: SeedMartsData } | null = null;

function resolveSeedPath(): string | null {
  const candidates = [
    path.resolve(process.cwd(), "../../data/processed/seed_marts.json"),
    path.resolve(process.cwd(), "data/processed/seed_marts.json"),
    path.resolve(process.cwd(), "../data/processed/seed_marts.json"),
  ];
  for (const p of candidates) {
    if (fs.existsSync(/*turbopackIgnore: true*/ p)) return p;
  }
  return null;
}

export function loadSeedMarts(): SeedMartsData {
  const seedPath = resolveSeedPath();
  if (!seedPath) {
    return {
      public_summary: {
        n_postings: 0,
        n_with_salary: 0,
        pct_with_salary: null,
        n_with_skills: 0,
        pct_with_skills: null,
        avg_skills_per_posting: null,
        n_provinces: 0,
        n_occupations: 0,
        n_skills_catalog: 0,
        min_date_posted: null,
        max_date_posted: null,
        last_updated_at: null,
      },
      skill_demand_weekly: [],
      skill_cooccurrence: [],
      occupation_skill_profile: [],
      salary_stats: [],
      posting_volume_daily: [],
      curriculum_coverage_ref: [],
      pipeline_status: [],
      dq_summary: [],
      top_links: [],
      pending_aliases: [],
      dim_skills: [],
      dim_occupations: [],
      dim_locations: [],
      ml_leaderboard: [],
      ml_feature_importance: [],
      salary_prediction: [],
      labor_monthly_2y: [],
      onet_skill_benchmark: [],
    };
  }

  const stat = fs.statSync(/*turbopackIgnore: true*/ seedPath);
  if (cachedSeed && cachedSeed.mtimeMs === stat.mtimeMs) {
    return cachedSeed.data;
  }
  const raw = fs.readFileSync(/*turbopackIgnore: true*/ seedPath, "utf-8");
  const parsed = JSON.parse(raw) as SeedMartsData;
  cachedSeed = { mtimeMs: stat.mtimeMs, data: parsed };
  return parsed;
}

async function querySupabaseMart<T>(
  table: string,
  limit = 2000
): Promise<T[] | null> {
  if (!isSupabaseConfigured()) return null;
  try {
    const supabase = await createSupabaseServerClient();
    if (!supabase) return null;
    const { data, error } = await supabase
      .schema("mart")
      .from(table)
      .select("*")
      .limit(limit);
    if (error || !data || data.length === 0) return null;
    return data as T[];
  } catch {
    return null;
  }
}

async function callPublicRpc<T>(fnName: string): Promise<T[] | null> {
  if (!isSupabaseConfigured()) return null;
  try {
    const supabase = await createSupabaseServerClient();
    if (!supabase) return null;
    const { data, error } = await supabase.rpc(fnName);
    if (error || !data || !Array.isArray(data) || data.length === 0) return null;
    return data as T[];
  } catch {
    return null;
  }
}

/**
 * Landing page reads ONLY `mart.public_summary`, `mart.posting_volume_daily`,
 * and `mart.skill_demand_weekly` (never `mart.pipeline_status` or `mart.dq_summary`).
 */
export async function getLandingData(): Promise<{
  publicSummary: PublicSummary;
  postingVolumeDaily: PostingVolumeDailyRow[];
  skillDemandWeekly: SkillDemandWeeklyRow[];
  laborMonthly2y: LaborMonthlyRow[];
}> {
  const seed = loadSeedMarts();
  const [sbSummary, sbVol, sbSkill] = await Promise.all([
    querySupabaseMart<PublicSummary>("public_summary", 1),
    querySupabaseMart<PostingVolumeDailyRow>("posting_volume_daily", 2000),
    querySupabaseMart<SkillDemandWeeklyRow>("skill_demand_weekly", 3000),
  ]);

  return {
    publicSummary: sbSummary?.[0] ?? seed.public_summary,
    postingVolumeDaily: sbVol ?? seed.posting_volume_daily,
    skillDemandWeekly: sbSkill ?? seed.skill_demand_weekly,
    laborMonthly2y: seed.labor_monthly_2y ?? [],
  };
}

export async function getMarketExplorerData(): Promise<{
  publicSummary: PublicSummary;
  skillDemandWeekly: SkillDemandWeeklyRow[];
  occupationSkillProfile: OccupationSkillProfileRow[];
  postingVolumeDaily: PostingVolumeDailyRow[];
  dimLocations: DimLocation[];
  dimOccupations: DimOccupation[];
  dimSkills: DimSkill[];
  laborMonthly2y: LaborMonthlyRow[];
  onetSkillBenchmark: OnetSkillBenchmarkRow[];
}> {
  const seed = loadSeedMarts();
  const [sbSummary, sbSdw, sbOcc, sbVol, sbLoc, sbDimOcc, sbDimSkill] =
    await Promise.all([
      querySupabaseMart<PublicSummary>("public_summary", 1),
      querySupabaseMart<SkillDemandWeeklyRow>("skill_demand_weekly", 5000),
      querySupabaseMart<OccupationSkillProfileRow>("occupation_skill_profile", 3000),
      querySupabaseMart<PostingVolumeDailyRow>("posting_volume_daily", 3000),
      callPublicRpc<DimLocation>("get_dim_locations"),
      callPublicRpc<DimOccupation>("get_dim_occupations"),
      callPublicRpc<DimSkill>("get_dim_skills"),
    ]);

  return {
    publicSummary: sbSummary?.[0] ?? seed.public_summary,
    skillDemandWeekly: sbSdw ?? seed.skill_demand_weekly,
    occupationSkillProfile: sbOcc ?? seed.occupation_skill_profile,
    postingVolumeDaily: sbVol ?? seed.posting_volume_daily,
    dimLocations: sbLoc ?? seed.dim_locations,
    dimOccupations: sbDimOcc ?? seed.dim_occupations,
    dimSkills: sbDimSkill ?? seed.dim_skills,
    laborMonthly2y: seed.labor_monthly_2y ?? [],
    onetSkillBenchmark: seed.onet_skill_benchmark ?? [],
  };
}

export async function getSkillDetailData(slug: string): Promise<{
  skill: DimSkill | null;
  weeklyTrend: SkillDemandWeeklyRow[];
  marketWeeklyScope: SkillDemandWeeklyRow[];
  occupationsRequesting: OccupationSkillProfileRow[];
  cooccurrence: SkillCooccurrenceRow[];
  salaryStats: SalaryStatsRow[];
  publicSummary: PublicSummary;
}> {
  const seed = loadSeedMarts();
  const [sbSkills, sbSdw, sbOcc, sbCo, sbSal, sbSum] = await Promise.all([
    callPublicRpc<DimSkill>("get_dim_skills"),
    querySupabaseMart<SkillDemandWeeklyRow>("skill_demand_weekly", 5000),
    querySupabaseMart<OccupationSkillProfileRow>("occupation_skill_profile", 3000),
    querySupabaseMart<SkillCooccurrenceRow>("skill_cooccurrence", 2000),
    querySupabaseMart<SalaryStatsRow>("salary_stats", 2000),
    querySupabaseMart<PublicSummary>("public_summary", 1),
  ]);

  const dimSkills = sbSkills ?? seed.dim_skills;
  const skill =
    dimSkills.find(
      (s) =>
        s.skill_slug === slug ||
        String(s.skill_key) === slug ||
        s.skill_canonical.toLowerCase().replace(/[^a-z0-9]+/g, "-") === slug
    ) ?? null;

  const sdw = sbSdw ?? seed.skill_demand_weekly;
  const occ = sbOcc ?? seed.occupation_skill_profile;
  const co = sbCo ?? seed.skill_cooccurrence;
  const sal = sbSal ?? seed.salary_stats;

  return {
    skill,
    weeklyTrend: skill
      ? sdw.filter(
          (r) => r.skill_key === skill.skill_key && r.scope_level === "national"
        )
      : [],
    marketWeeklyScope: sdw.filter((r) => r.scope_level === "national"),
    occupationsRequesting: skill
      ? occ
          .filter((r) => r.skill_key === skill.skill_key)
          .sort((a, b) => b.n_postings - a.n_postings)
      : [],
    cooccurrence: skill
      ? co
          .filter((r) => r.skill_key === skill.skill_key)
          .sort((a, b) => a.rank_order - b.rank_order)
      : [],
    salaryStats: sal,
    publicSummary: sbSum?.[0] ?? seed.public_summary,
  };
}

export async function getOccupationDetailData(slug: string): Promise<{
  occupation: DimOccupation | null;
  skills: OccupationSkillProfileRow[];
  salaryStats: SalaryStatsRow[];
  topLinks: TopLinkRow[];
  publicSummary: PublicSummary;
}> {
  const seed = loadSeedMarts();
  const [sbOccDim, sbProfile, sbSal, sbLinks, sbSum] = await Promise.all([
    callPublicRpc<DimOccupation>("get_dim_occupations"),
    querySupabaseMart<OccupationSkillProfileRow>("occupation_skill_profile", 3000),
    querySupabaseMart<SalaryStatsRow>("salary_stats", 2000),
    querySupabaseMart<TopLinkRow>("top_links", 1000),
    querySupabaseMart<PublicSummary>("public_summary", 1),
  ]);

  const occDim = sbOccDim ?? seed.dim_occupations;
  const occupation =
    occDim.find((o) => o.occupation_slug === slug) ??
    occDim.find(
      (o) =>
        o.occupation_cluster.toLowerCase().replace(/[^a-z0-9]+/g, "-") === slug
    ) ??
    null;

  const profileRows = sbProfile ?? seed.occupation_skill_profile;
  const salRows = sbSal ?? seed.salary_stats;
  const linkRows = sbLinks ?? seed.top_links;

  const targetCluster = occupation?.occupation_cluster;

  return {
    occupation,
    skills: targetCluster
      ? profileRows
          .filter((r) => r.occupation_cluster === targetCluster)
          .sort((a, b) => a.rank_in_occupation - b.rank_in_occupation)
      : [],
    salaryStats: targetCluster
      ? salRows.filter((r) => r.occupation_cluster === targetCluster)
      : [],
    topLinks: targetCluster
      ? linkRows
          .filter((r) => r.occupation_cluster === targetCluster)
          .slice(0, 5)
      : [],
    publicSummary: sbSum?.[0] ?? seed.public_summary,
  };
}

export async function getSalaryExplorerData(): Promise<{
  publicSummary: PublicSummary;
  salaryStats: SalaryStatsRow[];
  salaryPrediction: SalaryPredictionRow[];
  occupationSkillProfile: OccupationSkillProfileRow[];
  dimOccupations: DimOccupation[];
  dimLocations: DimLocation[];
  dimSkills: DimSkill[];
  mlLeaderboard: MlLeaderboardRow[];
}> {
  const seed = loadSeedMarts();
  const [sbSum, sbStats, sbPred, sbOccProf, sbDimOcc, sbDimLoc, sbDimSkill, sbMl] =
    await Promise.all([
      querySupabaseMart<PublicSummary>("public_summary", 1),
      querySupabaseMart<SalaryStatsRow>("salary_stats", 2000),
      querySupabaseMart<SalaryPredictionRow>("salary_prediction", 1000),
      querySupabaseMart<OccupationSkillProfileRow>("occupation_skill_profile", 3000),
      callPublicRpc<DimOccupation>("get_dim_occupations"),
      callPublicRpc<DimLocation>("get_dim_locations"),
      callPublicRpc<DimSkill>("get_dim_skills"),
      querySupabaseMart<MlLeaderboardRow>("ml_leaderboard", 500),
    ]);

  return {
    publicSummary: sbSum?.[0] ?? seed.public_summary,
    salaryStats: sbStats ?? seed.salary_stats,
    salaryPrediction: sbPred ?? seed.salary_prediction ?? [],
    occupationSkillProfile: sbOccProf ?? seed.occupation_skill_profile,
    dimOccupations: sbDimOcc ?? seed.dim_occupations,
    dimLocations: sbDimLoc ?? seed.dim_locations,
    dimSkills: sbDimSkill ?? seed.dim_skills,
    mlLeaderboard: sbMl ?? seed.ml_leaderboard ?? [],
  };
}

export async function getMlLabData(): Promise<{
  publicSummary: PublicSummary;
  leaderboard: MlLeaderboardRow[];
  featureImportance: MlFeatureImportanceRow[];
}> {
  const seed = loadSeedMarts();
  const [sbSum, sbLb, sbFi] = await Promise.all([
    querySupabaseMart<PublicSummary>("public_summary", 1),
    querySupabaseMart<MlLeaderboardRow>("ml_leaderboard", 500),
    querySupabaseMart<MlFeatureImportanceRow>("ml_feature_importance", 500),
  ]);

  return {
    publicSummary: sbSum?.[0] ?? seed.public_summary,
    leaderboard: sbLb ?? seed.ml_leaderboard ?? [],
    featureImportance: sbFi ?? seed.ml_feature_importance ?? [],
  };
}

export async function getSkillCatalogData(): Promise<{
  publicSummary: PublicSummary;
  dimSkills: DimSkill[];
  dimOccupations: DimOccupation[];
  dimLocations: DimLocation[];
  occupationSkillProfile: OccupationSkillProfileRow[];
  curriculumCoverageRef: CurriculumCoverageRefRow[];
  topLinks: TopLinkRow[];
}> {
  const seed = loadSeedMarts();
  const [sbSum, sbSkills, sbOcc, sbLoc, sbOccProf, sbCurRef, sbLinks] =
    await Promise.all([
      querySupabaseMart<PublicSummary>("public_summary", 1),
      callPublicRpc<DimSkill>("get_dim_skills"),
      callPublicRpc<DimOccupation>("get_dim_occupations"),
      callPublicRpc<DimLocation>("get_dim_locations"),
      querySupabaseMart<OccupationSkillProfileRow>("occupation_skill_profile", 3000),
      querySupabaseMart<CurriculumCoverageRefRow>("curriculum_coverage_ref", 3000),
      querySupabaseMart<TopLinkRow>("top_links", 1000),
    ]);

  return {
    publicSummary: sbSum?.[0] ?? seed.public_summary,
    dimSkills: sbSkills ?? seed.dim_skills,
    dimOccupations: sbOcc ?? seed.dim_occupations,
    dimLocations: sbLoc ?? seed.dim_locations,
    occupationSkillProfile: sbOccProf ?? seed.occupation_skill_profile,
    curriculumCoverageRef: sbCurRef ?? seed.curriculum_coverage_ref,
    topLinks: sbLinks ?? seed.top_links,
  };
}

export async function getUserSkills(session: UserSession | null): Promise<UserSkill[]> {
  if (!session) return [];
  const seed = loadSeedMarts();
  const skillByKey = new Map(seed.dim_skills.map((s) => [s.skill_key, s]));

  if (!session.is_demo && isSupabaseConfigured()) {
    const supabase = await createSupabaseServerClient();
    if (supabase) {
      const { data } = await supabase
        .from("app_user_skill")
        .select("skill_key, level")
        .eq("user_id", session.user_id);
      if (data) {
        return data.map((row) => {
          const meta = skillByKey.get(row.skill_key);
          return {
            skill_key: row.skill_key,
            level: (row.level as 1 | 2 | 3) || 1,
            skill_canonical: meta?.skill_canonical,
            skill_slug: meta?.skill_slug,
            skill_name_th: meta?.skill_name_th,
            skill_type: meta?.skill_type,
            skill_group: meta?.skill_group,
          };
        });
      }
    }
  }

  return getDemoUserSkills(session.user_id).map((s) => {
    const meta = skillByKey.get(s.skill_key);
    return {
      ...s,
      skill_canonical: s.skill_canonical ?? meta?.skill_canonical,
      skill_slug: s.skill_slug ?? meta?.skill_slug,
      skill_name_th: s.skill_name_th ?? meta?.skill_name_th,
      skill_type: s.skill_type ?? meta?.skill_type,
      skill_group: s.skill_group ?? meta?.skill_group,
    };
  });
}

export async function getUserCurricula(
  session: UserSession | null
): Promise<CurriculumItem[]> {
  if (!session) return [];

  if (!session.is_demo && isSupabaseConfigured()) {
    const supabase = await createSupabaseServerClient();
    if (supabase) {
      const { data: currics } = await supabase
        .from("app_curriculum")
        .select("*")
        .eq("owner_id", session.user_id)
        .order("curriculum_id", { ascending: true });
      if (currics) {
        const ids = currics.map((c) => c.curriculum_id);
        const { data: cSkills } = ids.length
          ? await supabase
              .from("app_curriculum_skill")
              .select("*")
              .in("curriculum_id", ids)
          : { data: [] };
        return currics.map((c) => ({
          ...c,
          skills: (cSkills || []).filter(
            (cs) => cs.curriculum_id === c.curriculum_id
          ),
        }));
      }
    }
  }

  return getDemoUserCurricula(session.user_id);
}

/**
 * Admin-only loader: strictly rejects non-admin roles.
 * Never exposed on public or Landing routes.
 */
export async function getAdminData(session: UserSession | null): Promise<{
  publicSummary: PublicSummary;
  pipelineStatus: PipelineStatusRow[];
  dqSummary: DqSummaryRow[];
  pendingAliases: PendingAliasRow[];
  postingVolumeDaily: PostingVolumeDailyRow[];
  dimSkills: DimSkill[];
  chatLogs: Array<{
    chat_id: number;
    page: string;
    question: string;
    answered: boolean;
    created_at: string;
  }>;
} | null> {
  const access = checkRouteAccess("/admin/pipeline", session?.role);
  if (!access.allowed || !session || session.role !== "admin") {
    return null;
  }

  const seed = loadSeedMarts();

  if (!session.is_demo && isSupabaseConfigured()) {
    const supabase = await createSupabaseServerClient();
    if (supabase) {
      const [ps, dq, tq, chats] = await Promise.all([
        supabase.rpc("get_admin_pipeline_status"),
        supabase.rpc("get_admin_dq_summary"),
        supabase.rpc("get_admin_taxonomy_queue"),
        supabase
          .from("app_chat_log")
          .select("chat_id, page, question, answered, created_at")
          .order("created_at", { ascending: false })
          .limit(50),
      ]);
      if (!ps.error && !dq.error) {
        return {
          publicSummary: seed.public_summary,
          pipelineStatus: (ps.data as PipelineStatusRow[]) ?? seed.pipeline_status,
          dqSummary: (dq.data as DqSummaryRow[]) ?? seed.dq_summary,
          pendingAliases: (tq.data as PendingAliasRow[]) ?? seed.pending_aliases,
          postingVolumeDaily: seed.posting_volume_daily,
          dimSkills: seed.dim_skills,
          chatLogs: (chats.data as any[]) ?? [],
        };
      }
    }
  }

  const demoStore = getDemoStore();
  return {
    publicSummary: seed.public_summary,
    pipelineStatus: seed.pipeline_status,
    dqSummary: seed.dq_summary,
    pendingAliases: applyDemoAliasOverrides(seed.pending_aliases),
    postingVolumeDaily: seed.posting_volume_daily,
    dimSkills: seed.dim_skills,
    chatLogs: demoStore.chatLogs,
  };
}
