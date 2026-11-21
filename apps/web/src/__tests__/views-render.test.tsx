import React from "react";
import { cleanup, render } from "@testing-library/react";
import { fireEvent, screen, waitFor } from "@testing-library/dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "@/lib/i18n";
import { FilterProvider } from "@/components/context/FilterContext";
import { PageContextProvider } from "@/components/chat/PageContextProvider";
import { ChatWidget } from "@/components/chat/ChatWidget";
import { AppShell } from "@/components/layout/AppShell";
import { loadSeedMarts } from "@/lib/data";
import { DEMO_PERSONAS } from "@/lib/demo-personas";
import { StyleGuideView } from "@/components/views/StyleGuideView";
import { LandingView } from "@/components/views/LandingView";
import { MarketView } from "@/components/views/MarketView";
import { SkillDetailView } from "@/components/views/SkillDetailView";
import { OccupationDetailView } from "@/components/views/OccupationDetailView";
import { MySkillsView, SkillGapView } from "@/components/views/StudentViews";
import {
  CurriculaListView,
  CurriculumDetailView,
} from "@/components/views/InstitutionViews";
import { SalaryView } from "@/components/views/SalaryView";
import { MlLabView } from "@/components/views/MlLabView";
import {
  AdminPipelineView,
  AdminQualityView,
  AdminSourcesView,
  AdminTaxonomyView,
} from "@/components/views/AdminViews";
import {
  AboutView,
  PrivacyView,
  SettingsView,
} from "@/components/views/InfoSettingsViews";
import type { UserSession } from "@/types/marts";

const pushMock = vi.fn();
const refreshMock = vi.fn();
let currentPathname = "/";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    refresh: refreshMock,
    replace: pushMock,
    back: vi.fn(),
  }),
  usePathname: () => currentPathname,
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/components/charts/EChartBox", () => ({
  EChartBox: ({ ariaLabel }: { ariaLabel: string }) => (
    <div data-testid="mock-echart" aria-label={ariaLabel} />
  ),
}));

function Wrapper({
  children,
  initialLocale = "th",
}: {
  children: React.ReactNode;
  initialLocale?: "th" | "en";
}) {
  return (
    <I18nProvider initialLocale={initialLocale}>
      <FilterProvider>
        <PageContextProvider>{children}</PageContextProvider>
      </FilterProvider>
    </I18nProvider>
  );
}

describe("Phase 5 & Phase 7 Rendered Views Verification", () => {
  const seed = loadSeedMarts();
  const fetchMock = vi.fn();

  beforeEach(() => {
    localStorage.clear();
    currentPathname = "/";
    pushMock.mockReset();
    refreshMock.mockReset();
    fetchMock.mockReset();
    fetchMock.mockImplementation(async (url: string) => {
      if (url.includes("/api/salary/estimate?warm=1")) {
        return { ok: true, json: async () => ({ warmed: true, configured: true, status: "ok" }) };
      }
      if (url.includes("/api/salary/estimate")) {
        return {
          ok: true,
          json: async () => ({
            p25: 20000,
            p50: 25000,
            p75: 32000,
            model_name: "XGBoost",
            source: "ml-api",
            uplifts: [],
            disclaimer: "ประมาณการจากประกาศที่ระบุเงินเดือน ไม่ใช่เงินเดือนจริง",
          }),
        };
      }
      return {
        ok: true,
        json: async () => ({ ok: true, status: "ok", answer: "คำตอบทดสอบ", mode: "fallback" }),
      };
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("T5.1/T5.2: renders StyleGuideView with Liquid Glass cards, solid fallback card & 3 sample charts", () => {
    const { container } = render(
      <Wrapper>
        <StyleGuideView />
      </Wrapper>
    );
    expect(screen.getByText(/Liquid Glass Design System/i)).toBeTruthy();
    expect(container.querySelector(".glass")).toBeTruthy();
    expect(container.querySelector(".surface-solid")).toBeTruthy();
    expect(screen.getAllByTestId("mock-echart").length).toBe(3);
  });

  it("T5.3: renders AppShell navigation, role controls, Context Bar and i18n switch", () => {
    currentPathname = "/market";
    const studentSession: UserSession = {
      user_id: "u1",
      email: "student@demo.local",
      role: "student",
      display_name: "นักศึกษาทดสอบ",
      preferred_language: "th",
      province_th: "สงขลา",
      target_occupation_cluster: "Data & Analytics",
      is_demo: true,
    };

    render(
      <Wrapper>
        <AppShell
          session={studentSession}
          publicSummary={seed.public_summary}
          locations={seed.dim_locations}
          occupations={seed.dim_occupations}
          showContextBar
        >
          <div>MARKET_BODY</div>
        </AppShell>
      </Wrapper>
    );

    expect(screen.getByText("MARKET_BODY")).toBeTruthy();
    expect(screen.getByRole("link", { name: /ตลาดทักษะ/i })).toBeTruthy();
    expect(screen.getByRole("link", { name: /ทักษะของฉัน/i })).toBeTruthy();
    expect(screen.getByRole("link", { name: /ประมาณเงินเดือน/i })).toBeTruthy();
    expect(screen.getAllByText(/นักศึกษาทดสอบ/i).length).toBeGreaterThanOrEqual(1);
    fireEvent.click(screen.getByRole("button", { name: /Switch language TH\/EN/i }));
    expect(screen.getAllByRole("link", { name: /Market/i }).length).toBeGreaterThanOrEqual(1);
  });

  it("T5.5-T5.8: renders public analytics pages (Landing, Market, SkillDetail, OccupationDetail)", () => {
    render(
      <Wrapper>
        <LandingView
          publicSummary={seed.public_summary}
          postingVolumeDaily={seed.posting_volume_daily}
          skillDemandWeekly={seed.skill_demand_weekly}
        />
      </Wrapper>
    );
    expect(screen.getByText(/10 อันดับทักษะ/i)).toBeTruthy();
    cleanup();

    render(
      <Wrapper>
        <MarketView
          publicSummary={seed.public_summary}
          skillDemandWeekly={seed.skill_demand_weekly}
          occupationSkillProfile={seed.occupation_skill_profile}
          postingVolumeDaily={seed.posting_volume_daily}
        />
      </Wrapper>
    );
    expect(screen.getByText(/Market Explorer/i)).toBeTruthy();
    cleanup();

    const firstSkill = seed.dim_skills[0];
    render(
      <Wrapper>
        <SkillDetailView
          skill={firstSkill}
          weeklyTrend={seed.skill_demand_weekly}
          occupationsRequesting={seed.occupation_skill_profile}
          cooccurrence={seed.skill_cooccurrence}
          salaryStats={seed.salary_stats}
          publicSummary={seed.public_summary}
          session={null}
        />
      </Wrapper>
    );
    expect(screen.getAllByText(firstSkill.skill_name_th).length).toBeGreaterThanOrEqual(1);
    cleanup();

    const firstOcc = seed.dim_occupations[0];
    render(
      <Wrapper>
        <OccupationDetailView
          occupation={firstOcc}
          skills={seed.occupation_skill_profile}
          salaryStats={seed.salary_stats}
          topLinks={seed.top_links}
          publicSummary={seed.public_summary}
        />
      </Wrapper>
    );
    expect(screen.getAllByText(firstOcc.occupation_cluster).length).toBeGreaterThanOrEqual(1);
  });

  it("T5.9-T5.11: renders Student & Institution views with real dimSkills and curriculum data", () => {
    const studentSession: UserSession = {
      user_id: "u-stu",
      email: "stu@demo.local",
      role: "student",
      display_name: "นักศึกษาทดสอบ",
      preferred_language: "th",
      province_th: "สงขลา",
      target_occupation_cluster: "Data & Analytics",
      is_demo: true,
    };
    const userSkills = seed.dim_skills.slice(0, 3).map((s) => ({ ...s, level: 2 as const }));

    render(
      <Wrapper>
        <MySkillsView
          session={studentSession}
          initialSkills={userSkills}
          skillsCatalog={seed.dim_skills}
          occupationSkillProfile={seed.occupation_skill_profile}
          publicSummary={seed.public_summary}
        />
      </Wrapper>
    );
    expect(screen.getByText(/ทักษะของฉัน/i)).toBeTruthy();
    cleanup();

    render(
      <Wrapper>
        <SkillGapView
          session={studentSession}
          userSkills={userSkills}
          dimOccupations={seed.dim_occupations}
          dimLocations={seed.dim_locations}
          occupationSkillProfile={seed.occupation_skill_profile}
          topLinks={seed.top_links}
          publicSummary={seed.public_summary}
        />
      </Wrapper>
    );
    expect(screen.getByText(/Skill Gap/i)).toBeTruthy();
    cleanup();

    const sampleCurriculum = DEMO_PERSONAS.institution.initialCurricula[0];
    render(
      <Wrapper>
        <CurriculaListView
          initialCurricula={[sampleCurriculum]}
          dimOccupations={seed.dim_occupations}
          dimSkills={seed.dim_skills}
          curriculumCoverageRef={seed.curriculum_coverage_ref}
          publicSummary={seed.public_summary}
        />
      </Wrapper>
    );
    expect(screen.getAllByText(sampleCurriculum.name).length).toBeGreaterThanOrEqual(1);
    cleanup();

    render(
      <Wrapper>
        <CurriculumDetailView
          initialCurriculum={sampleCurriculum}
          dimSkills={seed.dim_skills}
          curriculumCoverageRef={seed.curriculum_coverage_ref}
          publicSummary={seed.public_summary}
        />
      </Wrapper>
    );
    expect(screen.getAllByText(sampleCurriculum.name).length).toBeGreaterThanOrEqual(1);
  });

  it("T5.12-T5.13: renders SalaryView (with pre-warm ping) and MlLabView (filtering to latest experiment_id)", async () => {
    render(
      <Wrapper>
        <SalaryView
          publicSummary={seed.public_summary}
          salaryStats={seed.salary_stats}
          occupationSkillProfile={seed.occupation_skill_profile}
          dimOccupations={seed.dim_occupations}
          dimLocations={seed.dim_locations}
          dimSkills={seed.dim_skills}
          userSkills={[]}
        />
      </Wrapper>
    );
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/salary/estimate?warm=1");
    });
    cleanup();

    const oldExpRows = seed.ml_leaderboard.map((r) => ({
      ...r,
      experiment_id: 1,
      model_name: r.model_name === "XGBoost" ? "OldExperimentModel" : r.model_name,
    }));
    const newExpRows = seed.ml_leaderboard.map((r) => ({
      ...r,
      experiment_id: 2,
    }));

    render(
      <Wrapper>
        <MlLabView
          publicSummary={seed.public_summary}
          leaderboard={[...oldExpRows, ...newExpRows]}
          featureImportance={seed.ml_feature_importance}
        />
      </Wrapper>
    );
    expect(screen.queryByText("OldExperimentModel")).toBeNull();
    expect(screen.getByText(/ML Lab — ห้องทดลองเปรียบเทียบโมเดล/i)).toBeTruthy();
  });

  it("T5.14-T5.15 & T7.3: renders Admin views, Settings delete actions, Privacy/About, and ChatWidget", async () => {
    render(
      <Wrapper>
        <AdminPipelineView
          pipelineStatus={seed.pipeline_status}
          postingVolumeDaily={seed.posting_volume_daily}
          chatLogs={[]}
          publicSummary={seed.public_summary}
        />
        <AdminQualityView dqSummary={seed.dq_summary} publicSummary={seed.public_summary} />
        <AdminTaxonomyView
          initialPendingAliases={seed.pending_aliases}
          dimSkills={seed.dim_skills}
          publicSummary={seed.public_summary}
        />
        <AdminSourcesView publicSummary={seed.public_summary} />
        <PrivacyView />
        <AboutView publicSummary={seed.public_summary} />
      </Wrapper>
    );
    expect(screen.getAllByText(/JobThai/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/JobTopGun/i).length).toBeGreaterThanOrEqual(1);
    cleanup();

    const stu: UserSession = {
      user_id: "u-del",
      email: "del@demo.local",
      role: "student",
      display_name: "Test",
      preferred_language: "th",
      province_th: "สงขลา",
      target_occupation_cluster: "Data & Analytics",
      is_demo: false,
    };

    render(
      <Wrapper>
        <SettingsView session={stu} />
        <LandingView
          publicSummary={seed.public_summary}
          postingVolumeDaily={seed.posting_volume_daily}
          skillDemandWeekly={seed.skill_demand_weekly}
        />
        <ChatWidget />
      </Wrapper>
    );

    fireEvent.click(screen.getByRole("button", { name: /ลบทักษะของฉันทั้งหมด/i }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/user-state",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ action: "clear_skills" }),
        })
      );
    });

    fireEvent.click(screen.getByRole("button", { name: /ลบบัญชีและออกจากระบบ/i }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/user-state",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ action: "delete_account" }),
        })
      );
    });

    const chatBtn = screen.getByRole("button", { name: /ผู้ช่วยวิเคราะห์ข้อมูลหน้านี้/i });
    fireEvent.click(chatBtn);
    expect(screen.getByText(/ตอนนี้มีประกาศงานกี่รายการ/i)).toBeTruthy();
  });
});
