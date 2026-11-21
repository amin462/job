"use client";

import React from "react";
import { EChartBox } from "@/components/charts/EChartBox";
import { useRegisterPageContext } from "@/components/chat/PageContextProvider";
import {
  ChampionCard,
  GlassCard,
  HeroFigure,
  KpiTile,
  LowDataState,
  MeterList,
  StatusChip,
} from "@/components/ui/DesignPrimitives";
import { SKILLBI_PALETTE } from "@/lib/echarts-theme";

export function StyleGuideView() {
  useRegisterPageContext({
    page: "style-guide",
    route: "/style-guide",
    title: "Liquid Glass Design System Style Guide",
    kpis: [{ label: "Identity Colors", value: 4 }],
    charts: [
      { id: "sample-bar", title: "Sample Ranked Bar", rows: [["SQL", 48], ["Excel", 42], ["Python", 35]] },
      { id: "sample-line", title: "Sample Trend Line", rows: [["W1", 28], ["W2", 34], ["W3", 41]] },
      { id: "sample-radar", title: "Sample Skill Radar", rows: [["Excel", 80], ["SQL", 65], ["Python", 50]] },
    ],
  });

  const barOption = {
    tooltip: { trigger: "axis" },
    grid: { top: 16, right: 24, bottom: 24, left: 100 },
    xAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
    yAxis: { type: "category", data: ["Python", "Excel", "SQL"] },
    series: [
      {
        type: "bar",
        data: [35, 42, 48],
        itemStyle: { color: SKILLBI_PALETTE.market, borderRadius: [0, 4, 4, 0] },
      },
    ],
  };

  const lineOption = {
    tooltip: { trigger: "axis" },
    legend: { bottom: 0, data: ["ทักษะตัวอย่าง", "ค่าเฉลี่ยตลาด"] },
    grid: { top: 20, right: 20, bottom: 36, left: 44 },
    xAxis: { type: "category", data: ["W1", "W2", "W3", "W4"] },
    yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
    series: [
      {
        name: "ทักษะตัวอย่าง",
        type: "line",
        data: [28, 34, 38, 41],
        itemStyle: { color: SKILLBI_PALETTE.me },
      },
      {
        name: "ค่าเฉลี่ยตลาด",
        type: "line",
        data: [25, 27, 29, 30],
        itemStyle: { color: SKILLBI_PALETTE.market },
      },
    ],
  };

  const radarOption = {
    tooltip: {},
    legend: { bottom: 0, data: ["ฉัน", "ตลาด"] },
    radar: {
      indicator: [
        { name: "Excel", max: 100 },
        { name: "SQL", max: 100 },
        { name: "Python", max: 100 },
        { name: "Power BI", max: 100 },
        { name: "Communication", max: 100 },
      ],
    },
    series: [
      {
        type: "radar",
        data: [
          { value: [80, 70, 50, 40, 75], name: "ฉัน", itemStyle: { color: SKILLBI_PALETTE.me } },
          { value: [75, 85, 65, 60, 80], name: "ตลาด", itemStyle: { color: SKILLBI_PALETTE.market } },
        ],
      },
    ],
  };

  return (
    <div className="space-y-6">
      <div className="glass p-6">
        <div className="relative z-10 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-[24px] font-semibold text-[var(--ink-primary)]">
              Liquid Glass Design System & ECharts Style Guide
            </h1>
            <p className="text-[13px] text-[var(--ink-secondary)]">
              การ์ดโปร่งแสงเฉพาะเปลือก · พื้นกราฟทึบ `.chart-surface` · Fallback `data-glass=&quot;off&quot;`
            </p>
          </div>
          <HeroFigure value="40px Hero" sublabel="Inter + IBM Plex Sans Thai" />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <KpiTile label="Glass KPI Tile (Me)" value="68.4%" delta="+4.2%" deltaDirection="up" sparkline={[20, 35, 32, 48, 68]} />
        <ChampionCard badge="Champion Card" title="ตัวอย่าง Gradient Card">
          <div className="text-[28px] font-semibold text-white">฿22,500 – ฿31,000</div>
        </ChampionCard>
        <div className="surface-solid flex flex-col justify-between p-5">
          <div className="text-[15px] font-semibold text-[var(--ink-primary)]">Solid Card & Status Chips</div>
          <div className="mt-3 flex flex-wrap gap-2">
            <StatusChip variant="good" label="Pass" />
            <StatusChip variant="warning" label="Low n" />
            <StatusChip variant="critical" label="Stopped 429" />
            <StatusChip variant="pending" label="Pending" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <GlassCard
          title="Sample Bar Chart"
          provenance={{ source: "StyleGuide", n: 126 }}
          tableData={{
            columns: [
              { key: "name", label: "Skill" },
              { key: "pct", label: "Share %", numeric: true },
            ],
            rows: [
              { name: "SQL", pct: 48 },
              { name: "Excel", pct: 42 },
              { name: "Python", pct: 35 },
            ],
          }}
        >
          <EChartBox option={barOption} height={240} ariaLabel="Sample horizontal bar chart" />
        </GlassCard>

        <GlassCard
          title="Sample Line Chart"
          provenance={{ source: "StyleGuide", n: 126 }}
          tableData={{
            columns: [
              { key: "week", label: "Week" },
              { key: "sample", label: "Sample", numeric: true },
              { key: "market", label: "Market", numeric: true },
            ],
            rows: [
              { week: "W1", sample: 28, market: 25 },
              { week: "W2", sample: 34, market: 27 },
              { week: "W3", sample: 38, market: 29 },
              { week: "W4", sample: 41, market: 30 },
            ],
          }}
        >
          <EChartBox option={lineOption} height={240} ariaLabel="Sample trend line chart" />
        </GlassCard>

        <GlassCard
          title="Sample Radar Chart"
          provenance={{ source: "StyleGuide", n: 126 }}
          tableData={{
            columns: [
              { key: "skill", label: "Skill" },
              { key: "me", label: "Me", numeric: true },
              { key: "market", label: "Market", numeric: true },
            ],
            rows: [
              { skill: "Excel", me: 80, market: 75 },
              { skill: "SQL", me: 70, market: 85 },
              { skill: "Python", me: 50, market: 65 },
            ],
          }}
        >
          <EChartBox option={radarOption} height={240} ariaLabel="Sample radar chart" />
        </GlassCard>
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        <GlassCard title="Meter List Component" provenance={{ source: "StyleGuide", n: 20 }}>
          <MeterList
            items={[
              { id: 1, label: "SQL", value: 4200, valueText: "+฿4,200" },
              { id: 2, label: "Power BI", value: 3100, valueText: "+฿3,100" },
            ]}
          />
        </GlassCard>
        <GlassCard title="Low Data State (n < 5)">
          <LowDataState n={3} />
        </GlassCard>
      </div>
    </div>
  );
}
