import React from "react";
import { render } from "@testing-library/react";
import { fireEvent, screen } from "@testing-library/dom";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "@/lib/i18n";
import {
  ChampionCard,
  GlassCard,
  LowDataState,
  SourceLink,
  StatusChip,
} from "@/components/ui/DesignPrimitives";
import { OfficialLaborTrendCard } from "@/components/charts/OfficialLaborTrendCard";
import { SkillChipPicker } from "@/components/ui/SkillChipPicker";
import type { DimSkill, LaborMonthlyRow } from "@/types/marts";

const SAMPLE_SKILLS: DimSkill[] = [
  {
    skill_key: 1,
    skill_canonical: "Microsoft Excel",
    skill_slug: "microsoft-excel",
    skill_name_th: "ไมโครซอฟท์ เอ็กเซล",
    skill_type: "tool",
    skill_group: "Office & Productivity",
    onet_ref: "2.E.4.i",
    esco_ref: null,
    aliases: ["excel", "เอ็กเซล", "vlookup"],
  },
  {
    skill_key: 9,
    skill_canonical: "SQL",
    skill_slug: "sql",
    skill_name_th: "ภาษา SQL และฐานข้อมูล",
    skill_type: "technical",
    skill_group: "Data & BI",
    onet_ref: "2.E.6.f",
    esco_ref: null,
    aliases: ["sql", "mysql", "postgresql"],
  },
];

describe("Design System UI Components", () => {
  it("suppresses chart content when suppressBelowMinN is true and n < 5", () => {
    render(
      <I18nProvider>
        <GlassCard
          title="Sample Suppressed Card"
          suppressBelowMinN
          provenance={{ source: "JobThai", n: 3 }}
        >
          <div>SECRET_VALUE_999</div>
        </GlassCard>
      </I18nProvider>
    );

    expect(screen.queryByText("SECRET_VALUE_999")).toBeNull();
    expect(screen.getByText(/ข้อมูลน้อยเกินไป/i)).toBeTruthy();
  });

  it("toggles between Chart View and Table View in GlassCard", () => {
    render(
      <I18nProvider>
        <GlassCard
          title="Skill Demand"
          provenance={{ source: "JobThai", n: 20 }}
          tableData={{
            columns: [
              { key: "skill", label: "Skill" },
              { key: "share", label: "%", numeric: true },
            ],
            rows: [{ skill: "SQL", share: "48.0%" }],
          }}
        >
          <div>CHART_CANVAS_PLACEHOLDER</div>
        </GlassCard>
      </I18nProvider>
    );

    expect(screen.getByText("CHART_CANVAS_PLACEHOLDER")).toBeTruthy();
    const toggleBtn = screen.getByRole("button", { name: /ดูเป็นตาราง/i });
    fireEvent.click(toggleBtn);
    expect(screen.queryByText("CHART_CANVAS_PLACEHOLDER")).toBeNull();
    expect(screen.getByText("48.0%")).toBeTruthy();
  });

  it("renders SourceLink ONLY for allowed job sites and blocks JobTopGun/JobsDB/Indeed", () => {
    const { container } = render(
      <I18nProvider>
        <div>
          <SourceLink
            url="https://www.jobthai.com/th/company/job/1947385"
            titleShort="Data Analyst"
          />
          <SourceLink
            url="https://www.jobtopgun.com/th/jobs/999"
            titleShort="Blocked JobTopGun"
          />
          <SourceLink
            url="https://th.jobsdb.com/th/job/888"
            titleShort="Blocked JobsDB"
          />
        </div>
      </I18nProvider>
    );

    expect(screen.getByText("Data Analyst")).toBeTruthy();
    expect(screen.queryByText("Blocked JobTopGun")).toBeNull();
    expect(screen.queryByText("Blocked JobsDB")).toBeNull();
    const anchor = container.querySelector("a");
    expect(anchor?.getAttribute("rel")).toBe("noopener noreferrer");
    expect(anchor?.getAttribute("target")).toBe("_blank");
  });

  it("filters SkillChipPicker by Thai and English aliases", () => {
    const onAdd = vi.fn();
    render(
      <I18nProvider>
        <SkillChipPicker
          skillsCatalog={SAMPLE_SKILLS}
          selectedKeys={[]}
          onAdd={onAdd}
          onRemove={() => {}}
        />
      </I18nProvider>
    );

    const input = screen.getByRole("textbox");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "เอ็กเซล" } });

    const option = screen.getByText("ไมโครซอฟท์ เอ็กเซล");
    fireEvent.mouseDown(option);
    expect(onAdd).toHaveBeenCalledWith(SAMPLE_SKILLS[0]);
  });

  it("renders ChampionCard, StatusChip, and LowDataState cleanly", () => {
    render(
      <I18nProvider>
        <div>
          <ChampionCard badge="Live" title="CatBoost">
            <div>฿20,000 – ฿30,000</div>
          </ChampionCard>
          <StatusChip variant="critical" label="stopped_429" />
          <LowDataState n={2} />
        </div>
      </I18nProvider>
    );
    expect(screen.getByText("CatBoost")).toBeTruthy();
    expect(screen.getByText("stopped_429")).toBeTruthy();
    expect(screen.getByText(/พบ 2 ประกาศ/)).toBeTruthy();
  });

  it("renders OfficialLaborTrendCard with metric selector and Table View toggle", () => {
    const sampleLabor: LaborMonthlyRow[] = [
      {
        date_key: 20250101,
        period_label: "2025-Q1",
        granularity: "quarter",
        metric: "unemployment_rate",
        metric_th: "อัตราการว่างงาน",
        value: 0.9,
        unit: "%",
        source: "NSO / BOT",
        dataset_id: "ds-860",
        dataset_url: "https://data.go.th",
      },
      {
        date_key: 20250401,
        period_label: "2025-Q2",
        granularity: "quarter",
        metric: "unemployment_rate",
        metric_th: "อัตราการว่างงาน",
        value: 1.0,
        unit: "%",
        source: "NSO / BOT",
        dataset_id: "ds-860",
        dataset_url: "https://data.go.th",
      },
    ];
    render(
      <I18nProvider>
        <OfficialLaborTrendCard rows={sampleLabor} />
      </I18nProvider>
    );
    expect(screen.getByText(/ข้อมูลสถิติหน่วยงานรัฐ/)).toBeTruthy();
    const toggleBtn = screen.getByRole("button", { name: /ดูเป็นตาราง/i });
    fireEvent.click(toggleBtn);
    expect(screen.getByText("2025-Q1")).toBeTruthy();
    expect(screen.getByText("2025-Q2")).toBeTruthy();
  });
});
