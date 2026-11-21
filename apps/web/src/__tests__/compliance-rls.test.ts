import { describe, expect, it } from "vitest";
import {
  checkProfileRoleUpdateAllowed,
  checkRouteAccess,
  findForbiddenKeysDeep,
  isLowData,
  isSafeExternalJobUrl,
  suppressIfLowN,
} from "@/lib/compliance";
import { getDemoUserCurricula, getDemoUserSkills } from "@/lib/auth";
import { getAdminData, getLandingData, loadSeedMarts } from "@/lib/data";
import { DEMO_PERSONAS } from "@/lib/demo-personas";

describe("ToS / PDPA Compliance & n < 5 Suppression (D2, D4, D6, D18)", () => {
  it("suppresses numeric values whenever n < 5", () => {
    expect(isLowData(0)).toBe(true);
    expect(isLowData(4)).toBe(true);
    expect(isLowData(5)).toBe(false);
    expect(suppressIfLowN(4, 25000)).toBeNull();
    expect(suppressIfLowN(5, 25000)).toBe(25000);
  });

  it("verifies seed_marts.json contains zero description/qualifications/HR PII keys", () => {
    const seed = loadSeedMarts();
    const hits = findForbiddenKeysDeep(seed);
    expect(hits).toEqual([]);
  });

  it("verifies n < 5 suppression across all public marts in seed_marts.json", () => {
    const seed = loadSeedMarts();
    for (const row of seed.skill_demand_weekly) {
      if (row.n_postings < 5 || row.n_scope_postings < 5) {
        expect(row.is_suppressed).toBe(true);
        expect(row.weighted_share).toBeNull();
      }
    }
    for (const row of seed.occupation_skill_profile) {
      if (row.n_postings < 5 || row.n_occ_postings < 5) {
        expect(row.is_suppressed).toBe(true);
        expect(row.weighted_share).toBeNull();
      }
    }
    for (const row of seed.salary_stats) {
      if (row.n_postings < 5) {
        expect(row.is_suppressed).toBe(true);
        expect(row.salary_p50).toBeNull();
      }
    }
    for (const link of seed.top_links) {
      expect(link.n_postings).toBeGreaterThanOrEqual(5);
      expect(link.rank_order).toBeLessThanOrEqual(5);
      expect(isSafeExternalJobUrl(link.source_url)).toBe(true);
    }
  });

  it("blocks forbidden job portals in SourceLink URL validation", () => {
    expect(isSafeExternalJobUrl("https://www.jobthai.com/th/company/job/123")).toBe(true);
    expect(isSafeExternalJobUrl("https://www.jobtopgun.com/th/jobs/123")).toBe(false);
    expect(isSafeExternalJobUrl("https://th.jobsdb.com/th/job/123")).toBe(false);
    expect(isSafeExternalJobUrl("https://th.indeed.com/viewjob?jk=123")).toBe(false);
  });
});

describe("RLS & Role Access Control Matrix (T6.4, D10, D18)", () => {
  it("blocks visitors from protected routes (/me/*, /institution/*, /admin/*, /settings)", () => {
    expect(checkRouteAccess("/me/skills", "visitor").allowed).toBe(false);
    expect(checkRouteAccess("/me/gap", "visitor").allowed).toBe(false);
    expect(checkRouteAccess("/institution/curricula", "visitor").allowed).toBe(false);
    expect(checkRouteAccess("/admin/pipeline", "visitor").allowed).toBe(false);
    expect(checkRouteAccess("/admin/quality", "visitor").allowed).toBe(false);
    expect(checkRouteAccess("/settings", "visitor").allowed).toBe(false);
  });

  it("blocks student & institution users from /admin/* routes", () => {
    expect(checkRouteAccess("/admin/pipeline", "student").allowed).toBe(false);
    expect(checkRouteAccess("/admin/taxonomy", "student").allowed).toBe(false);
    expect(checkRouteAccess("/admin/pipeline", "institution").allowed).toBe(false);
    expect(checkRouteAccess("/admin/quality", "institution").allowed).toBe(false);
    expect(checkRouteAccess("/admin/pipeline", "admin").allowed).toBe(true);
  });

  it("blocks non-admin users from self-elevating role to 'admin' (D18)", () => {
    expect(checkProfileRoleUpdateAllowed("student", "admin").allowed).toBe(false);
    expect(checkProfileRoleUpdateAllowed("institution", "admin").allowed).toBe(false);
    expect(checkProfileRoleUpdateAllowed("student", "institution").allowed).toBe(true);
    expect(checkProfileRoleUpdateAllowed("admin", "admin").allowed).toBe(true);
  });

  it("blocks non-admin callers from reading admin marts (pipeline_status / dq_summary)", async () => {
    const studentSession = DEMO_PERSONAS.student_data.session;
    const adminSession = DEMO_PERSONAS.admin.session;

    expect(await getAdminData(null)).toBeNull();
    expect(await getAdminData(studentSession)).toBeNull();
    const adminResult = await getAdminData(adminSession);
    expect(adminResult).not.toBeNull();
    expect(adminResult?.dqSummary.length).toBeGreaterThan(0);

    // Landing loader never exposes pipeline_status or dq_summary
    const landing = await getLandingData();
    expect("pipeline_status" in landing).toBe(false);
    expect("dq_summary" in landing).toBe(false);
  });

  it("isolates User A data from User B", () => {
    const userA = DEMO_PERSONAS.student_data.session.user_id;
    const userB = DEMO_PERSONAS.student_acc.session.user_id;
    const skillsA = getDemoUserSkills(userA).map((s) => s.skill_canonical);
    const skillsB = getDemoUserSkills(userB).map((s) => s.skill_canonical);
    expect(skillsA).toContain("Python");
    expect(skillsB).not.toContain("Python");
    expect(skillsB).toContain("Accounting");
    expect(getDemoUserCurricula(userA)).toEqual([]);
    expect(getDemoUserCurricula(DEMO_PERSONAS.institution.session.user_id).length).toBeGreaterThan(0);
  });
});
