import { afterEach, describe, expect, it, vi } from "vitest";
import { findForbiddenKeysDeep } from "@/lib/compliance";
import * as supabaseServer from "@/lib/supabase/server";
import {
  getLandingData,
  getMarketExplorerData,
  getOccupationDetailData,
  getSalaryFallbackContext,
  loadSeedMarts,
} from "@/lib/data";

describe("Supabase Mart Data Loader, Seed Fallback & Privacy Guards (T0.2, T5.4)", () => {
  const origUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const origAnon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const origPub = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

  afterEach(() => {
    vi.restoreAllMocks();
    if (origUrl !== undefined) process.env.NEXT_PUBLIC_SUPABASE_URL = origUrl;
    else delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    if (origAnon !== undefined) process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = origAnon;
    else delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (origPub !== undefined) process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = origPub;
    else delete process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  });

  it("falls back to seed_marts.json when Supabase env is not configured", async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    delete process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

    const seed = loadSeedMarts();
    const landing = await getLandingData();
    expect(landing.publicSummary.n_postings).toBe(seed.public_summary.n_postings);
    expect(landing.skillDemandWeekly.length).toBe(seed.skill_demand_weekly.length);
    expect(findForbiddenKeysDeep(landing)).toEqual([]);
  });

  it("reads mart.* from Supabase when configured and enforces n < 5 suppression + zero raw text", async () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://mock-proj.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "sb_publishable_mock";

    const fakeMartTables: Record<string, unknown[]> = {
      public_summary: [
        {
          n_postings: 420,
          n_with_salary: 210,
          pct_with_salary: 50.0,
          n_with_skills: 410,
          pct_with_skills: 97.6,
          avg_skills_per_posting: 5.5,
          n_provinces: 40,
          n_occupations: 18,
          n_skills_catalog: 128,
          min_date_posted: "2026-11-01",
          max_date_posted: "2026-11-21",
          last_updated_at: "2026-11-21T12:00:00Z",
          description: "SHOULD_BE_STRIPPED",
        },
      ],
      posting_volume_daily: [
        {
          date_key: 20261121,
          full_date: "2026-11-21",
          year: 2026,
          month: 11,
          week: 47,
          week_start: "2026-11-16",
          scope_level: "national",
          region: "ทั้งประเทศ",
          province_th: "ทั้งประเทศ",
          is_south14: null,
          n_postings: 3, // < 5 must be suppressed
          n_with_salary: 2,
          weighted_volume: 99.0,
          salary_share: 0.67,
          is_suppressed: false,
        },
      ],
      skill_demand_weekly: [
        {
          week_start: "2026-11-16",
          scope_level: "national",
          region: "ทั้งประเทศ",
          province_th: "ทั้งประเทศ",
          is_south14: null,
          skill_key: 9,
          skill_canonical: "SQL",
          skill_slug: "sql",
          skill_name_th: "SQL",
          skill_type: "technical",
          skill_group: "Data & BI",
          n_postings: 4, // < 5 must be suppressed
          n_new_postings: 2,
          n_scope_postings: 20,
          weighted_active_sum: 12.3,
          weighted_new_sum: 5.0,
          weighted_share: 0.2,
          weighted_new_share: 0.1,
          is_suppressed: false,
          qualifications: "SHOULD_BE_STRIPPED",
        },
      ],
      occupation_skill_profile: [
        {
          occupation_cluster: "Data & Analytics",
          occupation_slug: "data-analytics",
          occupation_name_th: "วิเคราะห์ข้อมูล",
          skill_key: 9,
          skill_canonical: "SQL",
          skill_slug: "sql",
          skill_name_th: "SQL",
          skill_type: "technical",
          skill_group: "Data & BI",
          n_occ_postings: 10,
          n_postings: 8,
          weighted_share: 0.8,
          raw_share: 0.8,
          rank_in_occupation: 1,
          is_suppressed: false,
        },
      ],
      top_links: [
        {
          occupation_cluster: "Data & Analytics",
          occupation_slug: "data-analytics",
          province_th: "ทั้งประเทศ",
          region: "ทั้งประเทศ",
          source_name: "jobthai",
          source_url: "https://www.jobthai.com/th/company/job/123",
          title_short: "Data Analyst",
          date_posted: "2026-11-21",
          n_postings: 10,
          rank_order: 1,
          description: "MUST_REMOVE",
        },
        {
          occupation_cluster: "Data & Analytics",
          occupation_slug: "data-analytics",
          province_th: "สงขลา",
          region: "ใต้",
          source_name: "jobthai",
          source_url: "https://www.jobthai.com/th/company/job/456",
          title_short: "Low Count Link",
          date_posted: "2026-11-21",
          n_postings: 2, // < 5 must be filtered out
          rank_order: 1,
        },
      ],
      salary_stats: [
        {
          scope_type: "occ",
          occupation_cluster: "Data & Analytics",
          occupation_slug: "data-analytics",
          region: "ทั้งประเทศ",
          province_th: "ทั้งประเทศ",
          experience_band: "ทั้งหมด",
          n_postings: 4, // < 5 must be suppressed
          salary_p25: 15000,
          salary_p50: 20000,
          salary_p75: 25000,
          salary_mean: 20000,
          salary_min_obs: 15000,
          salary_max_obs: 25000,
          is_suppressed: false,
        },
      ],
      ml_leaderboard: [],
      salary_prediction: [],
    };

    const fakeRpcs: Record<string, unknown[]> = {
      get_dim_locations: [
        {
          location_key: 1,
          province_code: "01",
          province_th: "กรุงเทพมหานคร",
          province_en: "Bangkok",
          region: "กลาง",
          is_south14: false,
        },
      ],
      get_dim_occupations: [
        {
          occupation_cluster: "Data & Analytics",
          occupation_slug: "data-analytics",
          occupation_name_th: "วิเคราะห์ข้อมูล",
          onet_ref: "15-2051.01",
          n_titles: 10,
        },
      ],
      get_dim_skills: [
        {
          skill_key: 9,
          skill_canonical: "SQL",
          skill_slug: "sql",
          skill_name_th: "SQL",
          skill_type: "technical",
          skill_group: "Data & BI",
          onet_ref: null,
          esco_ref: null,
          aliases: ["sql"],
        },
      ],
    };

    const fakeClient = {
      schema: () => ({
        from: (table: string) => ({
          select: () => ({
            range: async () => ({ data: fakeMartTables[table] ?? [], error: null }),
          }),
        }),
      }),
      rpc: async (fnName: string) => ({ data: fakeRpcs[fnName] ?? [], error: null }),
    };

    vi.spyOn(supabaseServer, "createSupabasePublicClient").mockReturnValue(
      fakeClient as unknown as ReturnType<typeof supabaseServer.createSupabasePublicClient>
    );

    const landing = await getLandingData();
    expect(landing.publicSummary.n_postings).toBe(420);
    expect(landing.postingVolumeDaily[0].is_suppressed).toBe(true);
    expect(landing.postingVolumeDaily[0].weighted_volume).toBeNull();
    expect(landing.skillDemandWeekly[0].is_suppressed).toBe(true);
    expect(landing.skillDemandWeekly[0].weighted_share).toBeNull();
    expect(findForbiddenKeysDeep(landing)).toEqual([]);

    const market = await getMarketExplorerData();
    expect(market.dimLocations.length).toBe(1);
    expect(market.dimSkills.length).toBe(1);
    expect(findForbiddenKeysDeep(market)).toEqual([]);

    const occDetail = await getOccupationDetailData("data-analytics");
    expect(occDetail.topLinks.length).toBe(1);
    expect(occDetail.topLinks[0].n_postings).toBeGreaterThanOrEqual(5);
    expect(occDetail.salaryStats[0].is_suppressed).toBe(true);
    expect(occDetail.salaryStats[0].salary_p50).toBeNull();
    expect(findForbiddenKeysDeep(occDetail)).toEqual([]);

    const salCtx = await getSalaryFallbackContext();
    expect(salCtx.salaryStats[0].salary_p50).toBeNull();
  });
});
