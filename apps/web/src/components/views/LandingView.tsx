"use client";

import React, { useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  BarChart3,
  CalendarDays,
  CheckCircle2,
  Database,
  Layers,
  Sparkles,
  Wallet,
} from "lucide-react";
import { EChartBox } from "@/components/charts/EChartBox";
import { OfficialLaborTrendCard } from "@/components/charts/OfficialLaborTrendCard";
import { useRegisterPageContext } from "@/components/chat/PageContextProvider";
import {
  EmptyState,
  GlassCard,
  KpiTile,
} from "@/components/ui/DesignPrimitives";
import { SKILLBI_PALETTE } from "@/lib/echarts-theme";
import { formatDateByLocale, formatPercent, useI18n } from "@/lib/i18n";
import type {
  LaborMonthlyRow,
  PostingVolumeDailyRow,
  PublicSummary,
  SkillDemandWeeklyRow,
} from "@/types/marts";

export function LandingView({
  publicSummary,
  postingVolumeDaily,
  skillDemandWeekly,
  laborMonthly2y = [],
}: {
  publicSummary: PublicSummary;
  postingVolumeDaily: PostingVolumeDailyRow[];
  skillDemandWeekly: SkillDemandWeeklyRow[];
  laborMonthly2y?: LaborMonthlyRow[];
}) {
  const { locale, t } = useI18n();
  const router = useRouter();
  const [selectedLaborMetric, setSelectedLaborMetric] = React.useState<string>(
    laborMonthly2y[0]?.metric || ""
  );

  const nationalDaily = useMemo(
    () =>
      postingVolumeDaily
        .filter((r) => r.scope_level === "national")
        .sort((a, b) => a.full_date.localeCompare(b.full_date)),
    [postingVolumeDaily]
  );

  // Aggregate national non-suppressed skill demand across latest available week (or overall weighted share)
  const topSkills = useMemo(() => {
    const nationalRows = skillDemandWeekly.filter(
      (r) => r.scope_level === "national" && !r.is_suppressed && r.weighted_share !== null
    );
    const bySkill = new Map<
      number,
      {
        skill_key: number;
        skill_canonical: string;
        skill_name_th: string;
        skill_slug: string;
        skill_type: string;
        n_postings: number;
        weighted_share: number;
      }
    >();

    for (const r of nationalRows) {
      const prev = bySkill.get(r.skill_key);
      if (!prev || r.n_postings > prev.n_postings) {
        bySkill.set(r.skill_key, {
          skill_key: r.skill_key,
          skill_canonical: r.skill_canonical,
          skill_name_th: r.skill_name_th,
          skill_slug: r.skill_slug,
          skill_type: r.skill_type,
          n_postings: r.n_postings,
          weighted_share: r.weighted_share ?? 0,
        });
      }
    }

    return Array.from(bySkill.values())
      .sort((a, b) => b.weighted_share - a.weighted_share || b.n_postings - a.n_postings)
      .slice(0, 10);
  }, [skillDemandWeekly]);

  useRegisterPageContext({
    page: "landing",
    route: "/",
    title: locale === "th" ? "ภาพรวมตลาดแรงงานไทย" : "Thailand Job Market Overview",
    kpis: [
      {
        label: locale === "th" ? "ประกาศที่วิเคราะห์" : "Analyzed Postings",
        value: publicSummary.n_postings,
      },
      {
        label: locale === "th" ? "ระบุเงินเดือนเป็นตัวเลข" : "With Numeric Salary",
        value: publicSummary.pct_with_salary ?? 0,
        unit: "%",
      },
      {
        label: locale === "th" ? "ดึงทักษะได้ ≥ 1" : "Mapped ≥ 1 Skill",
        value: publicSummary.pct_with_skills ?? 0,
        unit: "%",
      },
      {
        label: locale === "th" ? "ทักษะเฉลี่ยต่อประกาศ" : "Avg Skills / Posting",
        value: publicSummary.avg_skills_per_posting ?? 0,
      },
    ],
    charts: [
      {
        id: "top-10-skills",
        title: locale === "th" ? "10 อันดับทักษะที่ตลาดต้องการมากที่สุด" : "Top 10 In-Demand Skills",
        rows: topSkills.map((s) => [
          locale === "th" ? s.skill_name_th : s.skill_canonical,
          Number((s.weighted_share * 100).toFixed(1)),
          s.n_postings,
        ]),
      },
      {
        id: "posting-calendar",
        title: locale === "th" ? "ปฏิทินปริมาณประกาศงานรายวัน" : "Daily Posting Calendar",
        rows: nationalDaily.map((d) => [d.full_date, d.n_postings, d.n_with_salary]),
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
    ],
    asOf: publicSummary.last_updated_at || undefined,
    dataNotes: [
      "ตัวอย่างจากประกาศงาน JobThai (n=" + publicSummary.n_postings + ")",
      "แสดงเฉพาะค่าสถิติรวม (n >= 5) และลิงก์ไปยังประกาศต้นฉบับ",
    ],
  });

  const calendarOption = useMemo(() => {
    const dates = nationalDaily.map((d) => d.full_date);
    const minDate = dates[0] || "2026-11-01";
    const maxDate = dates[dates.length - 1] || "2026-11-30";
    const yearMonth = minDate.slice(0, 7);
    const maxVal = Math.max(...nationalDaily.map((d) => d.n_postings), 10);

    return {
      tooltip: {
        trigger: "item",
        formatter: (params: { value?: [string, number] }) => {
          const val = params.value;
          if (!val) return "";
          return `${formatDateByLocale(val[0], locale)}: <b>${val[1]}</b> ${
            locale === "th" ? "ประกาศ" : "postings"
          }`;
        },
      },
      visualMap: {
        min: 0,
        max: maxVal,
        orient: "horizontal",
        left: "center",
        bottom: 6,
        inRange: {
          color: ["#F1EFFD", "#B7ACF4", "#6C5CE7", "#2F2680"],
        },
        textStyle: { fontSize: 11, color: SKILLBI_PALETTE.inkSecondary },
      },
      calendar: {
        top: 28,
        left: 36,
        right: 20,
        bottom: 52,
        cellSize: ["auto", 28],
        range: dates.length > 0 && dates[0].slice(0, 7) === maxDate.slice(0, 7) ? yearMonth : [minDate, maxDate],
        itemStyle: { borderWidth: 2, borderColor: "#FFFFFF" },
        yearLabel: { show: false },
      },
      series: [
        {
          type: "calendar",
          coordinateSystem: "calendar",
          data: nationalDaily.map((d) => [d.full_date, d.n_postings]),
        },
      ],
    };
  }, [nationalDaily, locale]);

  const topBarOption = useMemo(() => {
    const ordered = [...topSkills].reverse();
    return {
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params: Array<{ name: string; value: number }>) => {
          const p = params[0];
          if (!p) return "";
          return `${p.name}: <b>${p.value}%</b>`;
        },
      },
      grid: { top: 10, right: 44, bottom: 24, left: 160, containLabel: false },
      xAxis: {
        type: "value",
        axisLabel: { formatter: "{value}%" },
      },
      yAxis: {
        type: "category",
        data: ordered.map((s) => {
          const label = locale === "th" ? s.skill_name_th : s.skill_canonical;
          return label.length > 24 ? label.slice(0, 22) + "…" : label;
        }),
      },
      series: [
        {
          name: locale === "th" ? "สัดส่วนประกาศ (ถ่วงน้ำหนัก)" : "Weighted Share",
          type: "bar",
          data: ordered.map((s) => ({
            value: Number((s.weighted_share * 100).toFixed(1)),
            skillSlug: s.skill_slug,
          })),
          itemStyle: {
            color: SKILLBI_PALETTE.market,
            borderRadius: [0, 4, 4, 0],
          },
          label: {
            show: true,
            position: "right",
            formatter: "{c}%",
            color: SKILLBI_PALETTE.inkSecondary,
            fontSize: 11,
          },
        },
      ],
    };
  }, [topSkills, locale]);

  const hasData = publicSummary.n_postings > 0;

  return (
    <div className="space-y-6">
      {/* Hero Banner */}
      <section className="glass p-6 sm:p-8">
        <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-2xl space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#6C5CE7]/30 bg-[var(--tint-me)] px-3 py-1 text-[12px] font-semibold text-[#2F2680]">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              <span>
                {locale === "th"
                  ? "Data Warehouse + Taxonomy ไทย/อังกฤษ + ML Champion"
                  : "Data Warehouse + TH/EN Skill Taxonomy + ML Champion"}
              </span>
            </div>
            <h1 className="text-[26px] leading-tight font-semibold tracking-tight text-[var(--ink-primary)] sm:text-[34px]">
              {locale === "th"
                ? "ตลาดแรงงานไทยต้องการทักษะอะไร และเงินเดือนช่วงไหนสมเหตุสมผล"
                : "What Skills Does Thailand’s Job Market Demand — and What Salary Should You Expect?"}
            </h1>
            <p className="text-[14px] leading-relaxed text-[var(--ink-secondary)]">
              {locale === "th"
                ? "วิเคราะห์ประกาศรับสมัครงานจริงทั่วประเทศแบบแบ่งชั้น พร้อมวิเคราะห์ Skill Gap สำหรับนักศึกษา เทียบความสอดคล้องหลักสูตรสำหรับสถาบัน และห้องทดลองเปรียบเทียบโมเดล ML"
                : "Stratified analysis of Thai job postings with student Skill Gap matching, institutional Curriculum Alignment, and a transparent ML Salary Benchmark Lab."}
            </p>
            <div className="flex flex-wrap gap-2.5 pt-1">
              <Link
                href="/market"
                className="inline-flex min-h-[44px] items-center gap-2 rounded-xl bg-[var(--series-me)] px-5 py-2.5 text-[14px] font-semibold text-white shadow-sm hover:opacity-95"
              >
                <span>{locale === "th" ? "ดูตลาดทักษะ" : "Explore Skill Market"}</span>
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              <Link
                href="/login"
                className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-4 py-2.5 text-[14px] font-semibold text-[var(--ink-primary)] hover:bg-[var(--tint-me)]"
              >
                <span>{locale === "th" ? "เข้าสู่ระบบ / ลองเดโม 4 บทบาท" : "Sign In / Try 4-Role Demo"}</span>
              </Link>
              <Link
                href="/salary"
                className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-4 py-2.5 text-[14px] font-medium text-[var(--ink-secondary)] hover:bg-[var(--tint-market)]/50"
              >
                <Wallet className="h-4 w-4 text-[var(--series-market)]" aria-hidden="true" />
                <span>{locale === "th" ? "ประมาณเงินเดือน" : "Estimate Salary"}</span>
              </Link>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:min-w-[300px]">
            <div className="rounded-2xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-4">
              <div className="text-[12px] text-[var(--ink-muted)]">
                {locale === "th" ? "ครอบคลุมพื้นที่" : "Provinces Covered"}
              </div>
              <div className="tabular-nums mt-1 text-[24px] font-semibold text-[var(--ink-primary)]">
                {publicSummary.n_provinces}
              </div>
              <div className="text-[11px] text-[var(--ink-secondary)]">
                {locale === "th" ? "จังหวัดในตัวอย่าง" : "provinces in sample"}
              </div>
            </div>
            <div className="rounded-2xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-4">
              <div className="text-[12px] text-[var(--ink-muted)]">
                {locale === "th" ? "ทักษะใน Taxonomy" : "Skill Catalog"}
              </div>
              <div className="tabular-nums mt-1 text-[24px] font-semibold text-[var(--series-me)]">
                {publicSummary.n_skills_catalog}
              </div>
              <div className="text-[11px] text-[var(--ink-secondary)]">
                {publicSummary.n_occupations}{" "}
                {locale === "th" ? "กลุ่มอาชีพ" : "occupation clusters"}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 4 Public KPI Tiles from mart.public_summary */}
      <section aria-label="Key Market Metrics" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiTile
          label={locale === "th" ? "ประกาศที่วิเคราะห์" : "Postings Analyzed"}
          value={publicSummary.n_postings.toLocaleString("en-US")}
          hint={locale === "th" ? "ผ่านเกณฑ์คลีนและ dedupe" : "Cleaned & deduplicated"}
          accent="me"
          icon={<Database className="h-4 w-4" />}
        />
        <KpiTile
          label={locale === "th" ? "ระบุเงินเดือนเป็นตัวเลข" : "Numeric Salary Rate"}
          value={
            publicSummary.pct_with_salary !== null
              ? formatPercent(publicSummary.pct_with_salary, true)
              : "—"
          }
          hint={`${publicSummary.n_with_salary.toLocaleString("en-US")} ${
            locale === "th" ? "ประกาศ" : "postings"
          }`}
          accent="market"
          icon={<Wallet className="h-4 w-4" />}
        />
        <KpiTile
          label={locale === "th" ? "ดึงทักษะได้ ≥ 1 ทักษะ" : "Skill Mapping Rate"}
          value={
            publicSummary.pct_with_skills !== null
              ? formatPercent(publicSummary.pct_with_skills, true)
              : "—"
          }
          hint={`${locale === "th" ? "เฉลี่ย" : "Avg"} ${
            publicSummary.avg_skills_per_posting ?? "—"
          } ${locale === "th" ? "ทักษะ/ประกาศ" : "skills/posting"}`}
          accent="compare"
          icon={<CheckCircle2 className="h-4 w-4" />}
        />
        <KpiTile
          label={locale === "th" ? "อัปเดตข้อมูลล่าสุด" : "Last Updated"}
          value={formatDateByLocale(publicSummary.last_updated_at, locale)}
          hint={
            publicSummary.min_date_posted && publicSummary.max_date_posted
              ? `${formatDateByLocale(publicSummary.min_date_posted, locale)} – ${formatDateByLocale(publicSummary.max_date_posted, locale)}`
              : undefined
          }
          accent="context"
          icon={<CalendarDays className="h-4 w-4" />}
        />
      </section>

      {!hasData ? (
        <EmptyState
          title={locale === "th" ? "ยังไม่มีข้อมูลใน mart" : "No mart data yet"}
          description={
            locale === "th"
              ? "กรุณารัน pipeline เพื่อสร้างข้อมูลสรุป หรืออ่านรายละเอียดเพิ่มเติมที่หน้า About"
              : "Run the ETL pipeline to populate mart data, or read project details in About."
          }
          action={
            <Link
              href="/about"
              className="inline-flex min-h-[40px] items-center rounded-xl bg-[var(--series-me)] px-4 text-[13px] font-semibold text-white"
            >
              {t("nav.about")}
            </Link>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
          <div className="lg:col-span-7">
            <GlassCard
              title={
                locale === "th"
                  ? "10 อันดับทักษะที่ตลาดต้องการมากที่สุด"
                  : "Top 10 In-Demand Skills"
              }
              subtitle={
                locale === "th"
                  ? "สัดส่วนถ่วงน้ำหนักตามชั้นการสุ่ม (คลิกแท่งเพื่อดูรายละเอียดทักษะ)"
                  : "Stratified weighted share (click a bar to open Skill Detail)"
              }
              icon={<BarChart3 className="h-5 w-5" />}
              provenance={{
                source: "JobThai",
                n: publicSummary.n_postings,
                updatedAt: publicSummary.last_updated_at,
                isSample: true,
              }}
              tableData={{
                csvFilename: "top-10-skills.csv",
                columns: [
                  { key: "skill", label: locale === "th" ? "ทักษะ" : "Skill" },
                  { key: "type", label: locale === "th" ? "ประเภท" : "Type" },
                  { key: "sharePct", label: locale === "th" ? "% ประกาศ" : "Share (%)", numeric: true },
                  { key: "n_postings", label: locale === "th" ? "จำนวนประกาศ" : "Postings", numeric: true },
                ],
                rows: topSkills.map((s) => ({
                  skill: locale === "th" ? s.skill_name_th : s.skill_canonical,
                  type: s.skill_type,
                  sharePct: `${(s.weighted_share * 100).toFixed(1)}%`,
                  n_postings: s.n_postings,
                })),
              }}
            >
              <EChartBox
                option={topBarOption}
                height={330}
                ariaLabel={
                  locale === "th"
                    ? "กราฟแท่งแนวนอนแสดง 10 อันดับทักษะที่ตลาดต้องการ"
                    : "Horizontal bar chart of top 10 in-demand skills"
                }
                onItemClick={(params: unknown) => {
                  const p = params as { data?: { skillSlug?: string } };
                  if (p?.data?.skillSlug) {
                    router.push(`/skills/${p.data.skillSlug}`);
                  }
                }}
              />
            </GlassCard>
          </div>

          <div className="lg:col-span-5">
            <GlassCard
              title={
                locale === "th" ? "ปฏิทินปริมาณประกาศงานรายวัน" : "Daily Posting Calendar"
              }
              subtitle={
                locale === "th"
                  ? "จำนวนประกาศใหม่ที่พบตามวันที่ประกาศ (ทั้งประเทศ)"
                  : "Posting count by date posted (national scope)"
              }
              icon={<Layers className="h-5 w-5" />}
              provenance={{
                source: "JobThai",
                n: publicSummary.n_postings,
                updatedAt: publicSummary.last_updated_at,
                isSample: true,
              }}
              tableData={{
                csvFilename: "posting-calendar.csv",
                columns: [
                  { key: "date", label: locale === "th" ? "วันที่" : "Date" },
                  { key: "n_postings", label: locale === "th" ? "ประกาศทั้งหมด" : "Postings", numeric: true },
                  { key: "n_with_salary", label: locale === "th" ? "ระบุเงินเดือน" : "With Salary", numeric: true },
                ],
                rows: nationalDaily.map((d) => ({
                  date: formatDateByLocale(d.full_date, locale),
                  n_postings: d.n_postings,
                  n_with_salary: d.n_with_salary,
                })),
              }}
            >
              <EChartBox
                option={calendarOption}
                height={330}
                ariaLabel={
                  locale === "th"
                    ? "ปฏิทินความหนาแน่นประกาศงานรายวัน"
                    : "Calendar heatmap of daily job postings"
                }
              />
            </GlassCard>
          </div>
        </div>
      )}

      {/* T3.9 Official 2-Year Labor Market Trend Card */}
      <OfficialLaborTrendCard
        rows={laborMonthly2y}
        selectedMetric={selectedLaborMetric}
        onMetricChange={setSelectedLaborMetric}
      />

      {/* Limitations Notice */}
      <footer className="surface-solid px-5 py-4 text-[13px] text-[var(--ink-secondary)]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p>{t("limitations.short")}</p>
          <Link
            href="/about"
            className="shrink-0 font-semibold text-[var(--series-me)] hover:underline"
          >
            {locale === "th" ? "อ่านข้อจำกัดข้อมูลทั้งหมด →" : "Read full methodology & limitations →"}
          </Link>
        </div>
      </footer>
    </div>
  );
}
