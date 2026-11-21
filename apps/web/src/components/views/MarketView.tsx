"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Activity,
  BarChart3,
  CalendarDays,
  GitBranch,
  Globe2,
  Layers,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { EChartBox } from "@/components/charts/EChartBox";
import { OfficialLaborTrendCard } from "@/components/charts/OfficialLaborTrendCard";
import { useRegisterPageContext } from "@/components/chat/PageContextProvider";
import { useGlobalFilters } from "@/components/context/FilterContext";
import {
  EmptyState,
  GlassCard,
  KpiTile,
  LowDataState,
  RangeSlider,
  SegmentedControl,
} from "@/components/ui/DesignPrimitives";
import { SKILLBI_PALETTE } from "@/lib/echarts-theme";
import { formatDateByLocale, formatPercent, useI18n } from "@/lib/i18n";
import type {
  LaborMonthlyRow,
  OccupationSkillProfileRow,
  OnetSkillBenchmarkRow,
  PostingVolumeDailyRow,
  PublicSummary,
  SkillDemandWeeklyRow,
} from "@/types/marts";

export function MarketView({
  publicSummary,
  skillDemandWeekly,
  occupationSkillProfile,
  postingVolumeDaily,
  laborMonthly2y = [],
  onetSkillBenchmark = [],
}: {
  publicSummary: PublicSummary;
  skillDemandWeekly: SkillDemandWeeklyRow[];
  occupationSkillProfile: OccupationSkillProfileRow[];
  postingVolumeDaily: PostingVolumeDailyRow[];
  laborMonthly2y?: LaborMonthlyRow[];
  onetSkillBenchmark?: OnetSkillBenchmarkRow[];
}) {
  const { locale } = useI18n();
  const router = useRouter();
  const { filters, setFilters } = useGlobalFilters();
  const [selectedSkillKey, setSelectedSkillKey] = useState<number | null>(null);
  const [selectedLaborMetric, setSelectedLaborMetric] = useState<string>(
    laborMonthly2y[0]?.metric || ""
  );
  const [viewportWidth, setViewportWidth] = useState<number>(1200);

  useEffect(() => {
    const update = () => setViewportWidth(window.innerWidth);
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  const isNarrow = viewportWidth < 420;

  // All available weeks sorted
  const allWeeks = useMemo(
    () =>
      Array.from(new Set(skillDemandWeekly.map((r) => r.week_start))).sort(),
    [skillDemandWeekly]
  );

  const [weekCutoffIdx, setWeekCutoffIdx] = useState<number>(
    Math.max(0, allWeeks.length - 1)
  );

  // Filter weekly demand rows by Global Context Bar province/region & skillType
  const scopedWeekly = useMemo(() => {
    const provFilter = filters.provinceOrRegion;
    return skillDemandWeekly.filter((row) => {
      if (provFilter === "ALL") {
        if (row.scope_level !== "national") return false;
      } else if (provFilter === "SOUTH14") {
        if (row.scope_level !== "province" || !row.is_south14) return false;
      } else if (provFilter.startsWith("REGION:")) {
        const reg = provFilter.replace("REGION:", "");
        if (row.scope_level !== "region" || row.region !== reg) return false;
      } else {
        if (row.scope_level !== "province" || row.province_th !== provFilter)
          return false;
      }
      if (filters.skillType !== "ALL" && row.skill_type !== filters.skillType) {
        return false;
      }
      if (allWeeks.length > 0 && weekCutoffIdx < allWeeks.length) {
        const cutoff = allWeeks[weekCutoffIdx];
        if (row.week_start > cutoff) return false;
      }
      return true;
    });
  }, [skillDemandWeekly, filters.provinceOrRegion, filters.skillType, allWeeks, weekCutoffIdx]);

  // If occupation filter is active, blend occupation_skill_profile for skill ranking
  const rankedSkills = useMemo(() => {
    if (filters.occupationCluster !== "ALL") {
      return occupationSkillProfile
        .filter((r) => {
          if (r.occupation_cluster !== filters.occupationCluster) return false;
          if (filters.skillType !== "ALL" && r.skill_type !== filters.skillType)
            return false;
          return !r.is_suppressed && r.weighted_share !== null;
        })
        .sort((a, b) => (b.weighted_share ?? 0) - (a.weighted_share ?? 0))
        .slice(0, 15)
        .map((r) => ({
          skill_key: r.skill_key,
          skill_canonical: r.skill_canonical,
          skill_name_th: r.skill_name_th,
          skill_slug: r.skill_slug,
          skill_type: r.skill_type,
          n_postings: r.n_postings,
          n_scope_postings: r.n_occ_postings,
          share: r.weighted_share ?? 0,
        }));
    }

    const bySkill = new Map<
      number,
      {
        skill_key: number;
        skill_canonical: string;
        skill_name_th: string;
        skill_slug: string;
        skill_type: string;
        n_postings: number;
        n_scope_postings: number;
        share: number;
      }
    >();

    for (const r of scopedWeekly) {
      const shareVal =
        filters.activeMode === "new"
          ? r.weighted_new_share
          : r.weighted_share;
      const cnt = filters.activeMode === "new" ? r.n_new_postings : r.n_postings;
      if (r.is_suppressed || shareVal === null || cnt < 5) continue;
      const prev = bySkill.get(r.skill_key);
      if (!prev || cnt > prev.n_postings) {
        bySkill.set(r.skill_key, {
          skill_key: r.skill_key,
          skill_canonical: r.skill_canonical,
          skill_name_th: r.skill_name_th,
          skill_slug: r.skill_slug,
          skill_type: r.skill_type,
          n_postings: cnt,
          n_scope_postings: r.n_scope_postings,
          share: shareVal,
        });
      }
    }

    return Array.from(bySkill.values())
      .sort((a, b) => b.share - a.share || b.n_postings - a.n_postings)
      .slice(0, 15);
  }, [
    filters.occupationCluster,
    filters.skillType,
    filters.activeMode,
    occupationSkillProfile,
    scopedWeekly,
  ]);

  // Scoped daily volume
  const scopedDaily = useMemo(() => {
    const provFilter = filters.provinceOrRegion;
    const rows = postingVolumeDaily.filter((r) => {
      if (provFilter === "ALL") return r.scope_level === "national";
      if (provFilter === "SOUTH14")
        return r.scope_level === "province" && Boolean(r.is_south14);
      if (provFilter.startsWith("REGION:"))
        return (
          r.scope_level === "region" &&
          r.region === provFilter.replace("REGION:", "")
        );
      return r.scope_level === "province" && r.province_th === provFilter;
    });

    const byDate = new Map<string, { n: number; nSal: number }>();
    for (const r of rows) {
      const cur = byDate.get(r.full_date) ?? { n: 0, nSal: 0 };
      cur.n += r.n_postings;
      cur.nSal += r.n_with_salary;
      byDate.set(r.full_date, cur);
    }
    return Array.from(byDate.entries())
      .map(([full_date, v]) => ({ full_date, n_postings: v.n, n_with_salary: v.nSal }))
      .sort((a, b) => a.full_date.localeCompare(b.full_date));
  }, [postingVolumeDaily, filters.provinceOrRegion]);

  const scopePostingsCount = useMemo(() => {
    if (filters.occupationCluster !== "ALL") {
      const match = occupationSkillProfile.find(
        (r) => r.occupation_cluster === filters.occupationCluster
      );
      return match?.n_occ_postings ?? 0;
    }
    return scopedDaily.reduce((acc, d) => acc + d.n_postings, 0);
  }, [filters.occupationCluster, occupationSkillProfile, scopedDaily]);

  const scopeSalaryShare = useMemo(() => {
    const total = scopedDaily.reduce((acc, d) => acc + d.n_postings, 0);
    const sal = scopedDaily.reduce((acc, d) => acc + d.n_with_salary, 0);
    if (total < 5) return null;
    return (sal / total) * 100;
  }, [scopedDaily]);

  // Top 6 skills for Small Multiples
  const top6ForMultiples = useMemo(
    () => rankedSkills.slice(0, 6),
    [rankedSkills]
  );

  // Sankey flow data (<= 6 nodes per layer: Scope/Region -> Occupation Cluster -> Top Skill)
  const sankeyFlow = useMemo(() => {
    const topOccs = Array.from(
      new Set(
        occupationSkillProfile
          .filter((r) => !r.is_suppressed)
          .map((r) => r.occupation_cluster)
      )
    ).slice(0, 5);

    const topFlowSkills = rankedSkills.slice(0, 6);
    const links: Array<{ source: string; target: string; value: number }> = [];
    const nodesSet = new Set<string>();
    const activeSkillName = selectedSkillKey
      ? rankedSkills.find((s) => s.skill_key === selectedSkillKey)?.skill_canonical
      : topFlowSkills[0]?.skill_canonical;

    const rootNode =
      filters.provinceOrRegion === "ALL"
        ? locale === "th"
          ? "ตลาดรวมไทย"
          : "All Thailand"
        : filters.provinceOrRegion.replace("REGION:", "ภาค");
    nodesSet.add(rootNode);

    for (const occ of topOccs) {
      if (
        filters.occupationCluster !== "ALL" &&
        occ !== filters.occupationCluster
      ) {
        continue;
      }
      const occRows = occupationSkillProfile.filter(
        (r) => r.occupation_cluster === occ && !r.is_suppressed
      );
      if (occRows.length === 0) continue;
      const occTotal = occRows[0]?.n_occ_postings ?? 0;
      if (occTotal < 5) continue;

      nodesSet.add(occ);
      links.push({ source: rootNode, target: occ, value: occTotal });

      for (const sk of topFlowSkills) {
        const match = occRows.find((r) => r.skill_key === sk.skill_key);
        if (match && match.n_postings >= 5) {
          const skLabel =
            locale === "th" ? sk.skill_name_th : sk.skill_canonical;
          nodesSet.add(skLabel);
          links.push({ source: occ, target: skLabel, value: match.n_postings });
        }
      }
    }

    const activeLabel = topFlowSkills.find(
      (s) => s.skill_canonical === activeSkillName
    );
    const highlightTarget = activeLabel
      ? locale === "th"
        ? activeLabel.skill_name_th
        : activeLabel.skill_canonical
      : "";

    const nodes = Array.from(nodesSet).map((name) => ({
      name,
      itemStyle: {
        color:
          name === highlightTarget
            ? SKILLBI_PALETTE.me
            : name === rootNode
            ? SKILLBI_PALETTE.market
            : SKILLBI_PALETTE.context,
      },
    }));

    return { nodes, links };
  }, [
    occupationSkillProfile,
    rankedSkills,
    selectedSkillKey,
    filters.provinceOrRegion,
    filters.occupationCluster,
    locale,
  ]);

  useRegisterPageContext({
    page: "market-explorer",
    route: "/market",
    title: locale === "th" ? "Market Explorer — ตลาดทักษะ" : "Market Explorer",
    filters: {
      province: filters.provinceOrRegion,
      occupation: filters.occupationCluster,
      skillType: filters.skillType,
      mode: filters.activeMode,
    },
    kpis: [
      {
        label: locale === "th" ? "ประกาศในขอบเขต" : "Postings in Scope",
        value: scopePostingsCount,
      },
      {
        label: locale === "th" ? "ระบุเงินเดือน" : "With Salary",
        value: scopeSalaryShare !== null ? Number(scopeSalaryShare.toFixed(1)) : null,
        unit: "%",
      },
      {
        label: locale === "th" ? "ทักษะเฉลี่ยต่อประกาศ" : "Avg Skills/Posting",
        value: publicSummary.avg_skills_per_posting,
      },
    ],
    charts: [
      {
        id: "skill-rank",
        title: locale === "th" ? "อันดับทักษะที่ตลาดต้องการ" : "Skill Demand Ranking",
        rows: rankedSkills.map((s) => [
          locale === "th" ? s.skill_name_th : s.skill_canonical,
          Number((s.share * 100).toFixed(1)),
          s.n_postings,
        ]),
      },
      {
        id: "posting-volume",
        title: locale === "th" ? "ปริมาณประกาศรายวัน" : "Daily Posting Volume",
        rows: scopedDaily.map((d) => [d.full_date, d.n_postings]),
      },
      ...(laborMonthly2y.length > 0
        ? [
            {
              id: "official-labor-2y",
              title:
                locale === "th"
                  ? "แนวโน้มตลาดแรงงานจากหน่วยงานรัฐย้อนหลัง ≤ 2 ปี (T3.9)"
                  : "Official Thai Labor Market Trends (<= 2 Years)",
              rows: laborMonthly2y
                .filter((r) => !selectedLaborMetric || r.metric === selectedLaborMetric)
                .slice(-20)
                .map((r) => [r.period_label, r.metric_th, r.value, r.unit, r.source]),
            },
          ]
        : []),
      ...(onetSkillBenchmark.length > 0
        ? [
            {
              id: "onet-benchmark",
              title:
                locale === "th"
                  ? "Global Benchmark: O*NET 31.0 Hot Technology"
                  : "Global Benchmark: O*NET 31.0 Hot Technology",
              rows: [...onetSkillBenchmark]
                .sort((a, b) => b.hot_tech_count - a.hot_tech_count)
                .slice(0, 15)
                .map((o) => [o.skill_canonical, o.n_onet_occupations, o.hot_tech_count]),
            },
          ]
        : []),
    ],
    asOf: publicSummary.last_updated_at || undefined,
    dataNotes: [
      "สัดส่วนคำนวณแบบถ่วงน้ำหนัก sample_weight ตามชั้นจังหวัด x หมวดงาน",
      "ค่าที่ n < 5 ถูกซ่อนตามกติกา ToS/สถิติ",
    ],
  });

  const rankingOption = useMemo(() => {
    const ordered = [...rankedSkills].reverse();
    return {
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params: Array<{ name: string; value: number }>) => {
          const p = params[0];
          return p ? `${p.name}: <b>${p.value}%</b>` : "";
        },
      },
      grid: { top: 8, right: 44, bottom: 24, left: 160 },
      xAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
      yAxis: {
        type: "category",
        data: ordered.map((s) => {
          const txt = locale === "th" ? s.skill_name_th : s.skill_canonical;
          return txt.length > 24 ? txt.slice(0, 22) + "…" : txt;
        }),
      },
      series: [
        {
          type: "bar",
          data: ordered.map((s) => ({
            value: Number((s.share * 100).toFixed(1)),
            skillSlug: s.skill_slug,
            skillKey: s.skill_key,
            itemStyle: {
              color:
                selectedSkillKey === s.skill_key
                  ? SKILLBI_PALETTE.me
                  : SKILLBI_PALETTE.market,
              borderRadius: [0, 4, 4, 0],
            },
          })),
          label: { show: true, position: "right", formatter: "{c}%", fontSize: 11 },
        },
      ],
    };
  }, [rankedSkills, selectedSkillKey, locale]);

  const sankeyOption = useMemo(
    () => ({
      tooltip: { trigger: "item" },
      series: [
        {
          type: "sankey",
          layoutIterations: 16,
          emphasis: { focus: "adjacency" },
          nodeGap: 10,
          lineStyle: { color: "source", curveness: 0.45, opacity: 0.35 },
          label: { color: SKILLBI_PALETTE.inkPrimary, fontSize: 11 },
          data: sankeyFlow.nodes,
          links: sankeyFlow.links,
        },
      ],
    }),
    [sankeyFlow]
  );

  const volumeOption = useMemo(
    () => ({
      tooltip: { trigger: "axis" },
      grid: { top: 18, right: 20, bottom: 64, left: 48 },
      xAxis: {
        type: "category",
        data: scopedDaily.map((d) => formatDateByLocale(d.full_date, locale)),
      },
      yAxis: { type: "value" },
      dataZoom: [
        { type: "inside" },
        { type: "slider", height: 22, bottom: 10 },
      ],
      series: [
        {
          name: locale === "th" ? "จำนวนประกาศ" : "Postings",
          type: "line",
          smooth: false,
          areaStyle: { color: "rgba(108, 92, 231, 0.16)" },
          lineStyle: { color: SKILLBI_PALETTE.me, width: 2 },
          itemStyle: { color: SKILLBI_PALETTE.me },
          data: scopedDaily.map((d) => d.n_postings),
        },
      ],
    }),
    [scopedDaily, locale]
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[24px] font-semibold text-[var(--ink-primary)]">
            {locale === "th" ? "Market Explorer — สำรวจตลาดทักษะ" : "Market Explorer"}
          </h1>
          <p className="text-[13px] text-[var(--ink-secondary)]">
            {locale === "th"
              ? "สัดส่วนความต้องการทักษะแบบถ่วงน้ำหนัก (sample_weight) และแนวโน้มรายสัปดาห์"
              : "Stratified weighted skill demand share and weekly trends"}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <SegmentedControl
            ariaLabel="Posting mode toggle"
            value={filters.activeMode}
            onChange={(val) => setFilters((f) => ({ ...f, activeMode: val }))}
            options={[
              { value: "active", label: locale === "th" ? "ประกาศที่เปิดอยู่" : "Active" },
              { value: "new", label: locale === "th" ? "ประกาศใหม่" : "New" },
            ]}
          />
          {allWeeks.length > 1 ? (
            <div className="min-w-[200px]">
              <RangeSlider
                label={locale === "th" ? "ถึงสัปดาห์" : "Up to week"}
                min={0}
                max={allWeeks.length - 1}
                value={weekCutoffIdx}
                onChange={setWeekCutoffIdx}
                formatValue={(idx) =>
                  formatDateByLocale(allWeeks[idx] || "", locale)
                }
              />
            </div>
          ) : null}
        </div>
      </div>

      {/* 4 KPIs */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiTile
          label={locale === "th" ? "ประกาศในขอบเขต" : "Postings in Scope"}
          value={scopePostingsCount.toLocaleString("en-US")}
          accent="me"
          icon={<Activity className="h-4 w-4" />}
        />
        <KpiTile
          label={locale === "th" ? "สัดส่วนระบุเงินเดือน" : "With Salary"}
          value={
            scopeSalaryShare !== null ? formatPercent(scopeSalaryShare, true) : "n < 5"
          }
          accent="market"
          icon={<Wallet className="h-4 w-4" />}
        />
        <KpiTile
          label={locale === "th" ? "ทักษะเฉลี่ย / ประกาศ" : "Avg Skills / Posting"}
          value={publicSummary.avg_skills_per_posting ?? "—"}
          accent="compare"
          icon={<Layers className="h-4 w-4" />}
        />
        <KpiTile
          label={locale === "th" ? "ช่วงวันที่เก็บข้อมูล" : "Snapshot Window"}
          value={
            publicSummary.max_date_posted
              ? formatDateByLocale(publicSummary.max_date_posted, locale)
              : "—"
          }
          hint={
            publicSummary.min_date_posted
              ? `${locale === "th" ? "เริ่ม" : "From"} ${formatDateByLocale(publicSummary.min_date_posted, locale)}`
              : undefined
          }
          accent="context"
          icon={<CalendarDays className="h-4 w-4" />}
        />
      </section>

      {scopePostingsCount === 0 ? (
        <EmptyState />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
            {/* Skill Ranking */}
            <div className="lg:col-span-5">
              <GlassCard
                title={
                  locale === "th"
                    ? "อันดับทักษะที่ถูกขอมากที่สุด"
                    : "Top Requested Skills"
                }
                subtitle={
                  locale === "th"
                    ? "คลิกแท่งกราฟเพื่อเปิดหน้ารายละเอียดทักษะ"
                    : "Click a bar to open Skill Detail"
                }
                icon={<BarChart3 className="h-5 w-5" />}
                suppressBelowMinN
                provenance={{
                  source: "JobThai",
                  n: scopePostingsCount,
                  updatedAt: publicSummary.last_updated_at,
                }}
                tableData={{
                  csvFilename: "market-skill-ranking.csv",
                  columns: [
                    { key: "skill", label: locale === "th" ? "ทักษะ" : "Skill" },
                    { key: "type", label: locale === "th" ? "ประเภท" : "Type" },
                    { key: "sharePct", label: "%", numeric: true },
                    { key: "n_postings", label: "n", numeric: true },
                  ],
                  rows: rankedSkills.map((s) => ({
                    skill: locale === "th" ? s.skill_name_th : s.skill_canonical,
                    type: s.skill_type,
                    sharePct: `${(s.share * 100).toFixed(1)}%`,
                    n_postings: s.n_postings,
                  })),
                }}
              >
                {rankedSkills.length === 0 ? (
                  <LowDataState n={scopePostingsCount} />
                ) : (
                  <EChartBox
                    option={rankingOption}
                    height={360}
                    ariaLabel="Weighted skill demand ranking bars"
                    onItemClick={(params: unknown) => {
                      const p = params as {
                        data?: { skillSlug?: string; skillKey?: number };
                      };
                      if (p?.data?.skillKey) {
                        setSelectedSkillKey(p.data.skillKey);
                      }
                      if (p?.data?.skillSlug) {
                        router.push(`/skills/${p.data.skillSlug}`);
                      }
                    }}
                  />
                )}
              </GlassCard>
            </div>

            {/* Skill Flow (Sankey <= 6 nodes/layer, collapses to bars < 420px) */}
            <div className="lg:col-span-7">
              <GlassCard
                title={
                  locale === "th"
                    ? "Skill Flow: พื้นที่ → กลุ่มอาชีพ → ทักษะยอดนิยม"
                    : "Skill Flow: Scope → Occupation → Top Skills"
                }
                subtitle={
                  locale === "th"
                    ? "จำกัด ≤ 6 node ต่อชั้น · ย่อเป็นแท่งบนจอมือถือแคบ"
                    : "Capped at <= 6 nodes per layer; collapses to bars below 420px"
                }
                icon={<GitBranch className="h-5 w-5" />}
                suppressBelowMinN
                provenance={{
                  source: "JobThai",
                  n: scopePostingsCount,
                  updatedAt: publicSummary.last_updated_at,
                }}
                tableData={{
                  csvFilename: "market-skill-flow.csv",
                  columns: [
                    { key: "source", label: locale === "th" ? "ต้นทาง" : "From" },
                    { key: "target", label: locale === "th" ? "ปลายทาง" : "To" },
                    { key: "value", label: "n", numeric: true },
                  ],
                  rows: sankeyFlow.links,
                }}
              >
                {sankeyFlow.links.length === 0 ? (
                  <LowDataState n={scopePostingsCount} />
                ) : isNarrow ? (
                  <EChartBox
                    option={rankingOption}
                    height={320}
                    ariaLabel="Collapsed mobile skill ranking bars"
                  />
                ) : (
                  <EChartBox
                    option={sankeyOption}
                    height={360}
                    ariaLabel="Skill demand flow Sankey diagram"
                  />
                )}
              </GlassCard>
            </div>
          </div>

          {/* Small Multiples (<= 6 skills weekly trend) */}
          <GlassCard
            title={
              locale === "th"
                ? "Small Multiples: แนวโน้มรายสัปดาห์ของทักษะเด่น (≤ 6 ทักษะ)"
                : "Weekly Demand Small Multiples (Top 6 Skills)"
            }
            subtitle={
              locale === "th"
                ? "ใช้สัดส่วนถ่วงน้ำหนักและแกนตั้งร่วมกันเพื่อเปรียบเทียบตรงไปตรงมา"
                : "Shared Y-axis across top skills using weekly weighted share"
            }
            icon={<TrendingUp className="h-5 w-5" />}
            provenance={{
              source: "JobThai",
              n: scopePostingsCount,
              updatedAt: publicSummary.last_updated_at,
            }}
          >
            {top6ForMultiples.length === 0 ? (
              <LowDataState n={scopePostingsCount} />
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {top6ForMultiples.map((sk) => {
                  const seriesRows = allWeeks.map((wk) => {
                    const hit = scopedWeekly.find(
                      (r) => r.skill_key === sk.skill_key && r.week_start === wk
                    );
                    return hit && !hit.is_suppressed && hit.weighted_share !== null
                      ? Number((hit.weighted_share * 100).toFixed(1))
                      : 0;
                  });
                  const miniOpt = {
                    tooltip: { trigger: "axis" },
                    grid: { top: 14, right: 12, bottom: 24, left: 36 },
                    xAxis: {
                      type: "category",
                      data: allWeeks.map((w) => formatDateByLocale(w, locale)),
                      axisLabel: { fontSize: 10 },
                    },
                    yAxis: {
                      type: "value",
                      min: 0,
                      max: 100,
                      axisLabel: { formatter: "{value}%", fontSize: 10 },
                    },
                    series: [
                      {
                        type: "line",
                        data: seriesRows,
                        itemStyle: { color: SKILLBI_PALETTE.me },
                        lineStyle: { width: 2 },
                      },
                    ],
                  };
                  return (
                    <div
                      key={sk.skill_key}
                      className="rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-3"
                    >
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="truncate text-[13px] font-semibold text-[var(--ink-primary)]">
                          {locale === "th" ? sk.skill_name_th : sk.skill_canonical}
                        </span>
                        <span className="tabular-nums text-[12px] font-semibold text-[var(--series-me)]">
                          {(sk.share * 100).toFixed(1)}%
                        </span>
                      </div>
                      <EChartBox
                        option={miniOpt}
                        height={145}
                        ariaLabel={`Weekly trend for ${sk.skill_canonical}`}
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </GlassCard>

          {/* Posting Volume + dataZoom slider */}
          <GlassCard
            title={
              locale === "th"
                ? "ปริมาณประกาศงานรายวัน (พร้อม Range Slider)"
                : "Daily Posting Volume with Range Slider"
            }
            icon={<Activity className="h-5 w-5" />}
            provenance={{
              source: "JobThai",
              n: scopePostingsCount,
              updatedAt: publicSummary.last_updated_at,
            }}
            tableData={{
              csvFilename: "posting-volume-daily.csv",
              columns: [
                { key: "date", label: locale === "th" ? "วันที่" : "Date" },
                { key: "n_postings", label: locale === "th" ? "ประกาศ" : "Postings", numeric: true },
                { key: "n_with_salary", label: locale === "th" ? "ระบุเงินเดือน" : "With Salary", numeric: true },
              ],
              rows: scopedDaily.map((d) => ({
                date: formatDateByLocale(d.full_date, locale),
                n_postings: d.n_postings,
                n_with_salary: d.n_with_salary,
              })),
            }}
          >
            <EChartBox
              option={volumeOption}
              height={280}
              ariaLabel="Daily job posting volume area chart with range zoom"
            />
          </GlassCard>

          {/* T3.9 Official 2-Year Labor Context + O*NET 31.0 Global Benchmark */}
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
            <div className="lg:col-span-7">
              <OfficialLaborTrendCard
                rows={laborMonthly2y}
                selectedMetric={selectedLaborMetric}
                onMetricChange={setSelectedLaborMetric}
              />
            </div>

            <div className="lg:col-span-5">
              <GlassCard
                title={
                  locale === "th"
                    ? "Global Benchmark: O*NET 31.0 Hot Technology"
                    : "Global Benchmark: O*NET 31.0 Hot Technology"
                }
                subtitle={
                  locale === "th"
                    ? "เทียบจำนวนอาชีพ O*NET ที่ระบุทักษะว่าเป็น Hot Technology (CC BY 4.0)"
                    : "O*NET occupation count & Hot Technology flags across 31,821 rows (CC BY 4.0)"
                }
                icon={<Globe2 className="h-5 w-5" />}
                provenance={{
                  source: "O*NET 31.0 (CC BY 4.0)",
                  n: onetSkillBenchmark.length,
                  isSample: false,
                }}
                tableData={{
                  csvFilename: "onet-31-benchmark.csv",
                  columns: [
                    { key: "skill", label: locale === "th" ? "ทักษะ" : "Skill" },
                    { key: "occupations", label: locale === "th" ? "อาชีพ O*NET" : "O*NET Occs", numeric: true },
                    { key: "hotTech", label: "Hot Tech", numeric: true },
                    { key: "inDemand", label: "In Demand", numeric: true },
                  ],
                  rows: [...onetSkillBenchmark]
                    .sort((a, b) => b.hot_tech_count - a.hot_tech_count)
                    .slice(0, 15)
                    .map((o) => ({
                      skill: o.skill_canonical,
                      occupations: o.n_onet_occupations,
                      hotTech: o.hot_tech_count,
                      inDemand: o.in_demand_count,
                    })),
                }}
              >
                {onetSkillBenchmark.length === 0 ? (
                  <EmptyState
                    title={
                      locale === "th"
                        ? "รอข้อมูล O*NET 31.0 Benchmark"
                        : "O*NET 31.0 benchmark pending"
                    }
                    description={
                      locale === "th"
                        ? "กำลังจับคู่กับชุดข้อมูล O*NET Software Skills 31,821 แถว"
                        : "Matching canonical skills against 31,821 O*NET Software Skills rows."
                    }
                  />
                ) : (
                  <EChartBox
                    option={{
                      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
                      grid: { top: 8, right: 36, bottom: 24, left: 150 },
                      xAxis: { type: "value" },
                      yAxis: {
                        type: "category",
                        data: [...onetSkillBenchmark]
                          .sort((a, b) => b.hot_tech_count - a.hot_tech_count)
                          .slice(0, 10)
                          .reverse()
                          .map((o) =>
                            o.skill_canonical.length > 22
                              ? o.skill_canonical.slice(0, 20) + "…"
                              : o.skill_canonical
                          ),
                      },
                      series: [
                        {
                          name: "Hot Tech Occupations",
                          type: "bar",
                          data: [...onetSkillBenchmark]
                            .sort((a, b) => b.hot_tech_count - a.hot_tech_count)
                            .slice(0, 10)
                            .reverse()
                            .map((o) => o.hot_tech_count),
                          itemStyle: {
                            color: SKILLBI_PALETTE.compare,
                            borderRadius: [0, 4, 4, 0],
                          },
                          label: { show: true, position: "right", fontSize: 11 },
                        },
                      ],
                    }}
                    height={280}
                    ariaLabel="O*NET 31.0 Hot Technology benchmark bar chart"
                  />
                )}
              </GlassCard>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
