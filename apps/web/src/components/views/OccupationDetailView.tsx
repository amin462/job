"use client";

import React, { useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, BarChart3, Briefcase, ExternalLink, Wallet } from "lucide-react";
import { EChartBox } from "@/components/charts/EChartBox";
import { useRegisterPageContext } from "@/components/chat/PageContextProvider";
import {
  EmptyState,
  GlassCard,
  LowDataState,
  SourceLink,
  StatusChip,
} from "@/components/ui/DesignPrimitives";
import { SKILLBI_PALETTE } from "@/lib/echarts-theme";
import { formatBaht, useI18n } from "@/lib/i18n";
import type {
  DimOccupation,
  OccupationSkillProfileRow,
  PublicSummary,
  SalaryStatsRow,
  TopLinkRow,
} from "@/types/marts";

export function OccupationDetailView({
  occupation,
  skills,
  salaryStats,
  topLinks,
  publicSummary,
}: {
  occupation: DimOccupation | null;
  skills: OccupationSkillProfileRow[];
  salaryStats: SalaryStatsRow[];
  topLinks: TopLinkRow[];
  publicSummary: PublicSummary;
}) {
  const { locale } = useI18n();
  const router = useRouter();

  const visibleSkills = useMemo(
    () => skills.filter((s) => !s.is_suppressed && s.weighted_share !== null).slice(0, 15),
    [skills]
  );

  const nOccPostings = skills[0]?.n_occ_postings ?? occupation?.n_titles ?? 0;

  const expSalaryBands = useMemo(
    () =>
      salaryStats.filter(
        (s) =>
          (s.scope_type === "occ_exp" || s.scope_type === "occ") &&
          !s.is_suppressed &&
          s.salary_p50 !== null
      ),
    [salaryStats]
  );

  useRegisterPageContext({
    page: "occupation-detail",
    route: occupation ? `/occupations/${occupation.occupation_slug}` : "/occupations",
    title: occupation
      ? locale === "th"
        ? occupation.occupation_name_th
        : occupation.occupation_cluster
      : "Occupation Detail",
    kpis: [
      { label: locale === "th" ? "จำนวนประกาศ" : "Postings", value: nOccPostings },
    ],
    charts: [
      {
        id: "occ-skills",
        title: locale === "th" ? "ทักษะที่ตำแหน่งนี้ขอมากสุด" : "Top Requested Skills",
        rows: visibleSkills.map((s) => [
          locale === "th" ? s.skill_name_th : s.skill_canonical,
          Number(((s.weighted_share ?? 0) * 100).toFixed(1)),
          s.n_postings,
        ]),
      },
      {
        id: "occ-salary",
        title: locale === "th" ? "ช่วงเงินเดือนตามประสบการณ์" : "Salary Range Ladder",
        rows: expSalaryBands.map((s) => [
          s.experience_band,
          s.salary_p25,
          s.salary_p50,
          s.salary_p75,
          s.n_postings,
        ]),
      },
    ],
    asOf: publicSummary.last_updated_at || undefined,
  });

  if (!occupation) {
    return (
      <EmptyState
        title={locale === "th" ? "ไม่พบกลุ่มอาชีพนี้" : "Occupation not found"}
        action={
          <Link
            href="/market"
            className="inline-flex min-h-[40px] items-center rounded-xl bg-[var(--series-me)] px-4 text-[13px] font-semibold text-white"
          >
            {locale === "th" ? "กลับสู่ตลาดทักษะ" : "Back to Market Explorer"}
          </Link>
        }
      />
    );
  }

  const skillOption = {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { top: 8, right: 44, bottom: 24, left: 165 },
    xAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
    yAxis: {
      type: "category",
      data: [...visibleSkills]
        .reverse()
        .map((s) => {
          const lbl = locale === "th" ? s.skill_name_th : s.skill_canonical;
          return lbl.length > 24 ? lbl.slice(0, 22) + "…" : lbl;
        }),
    },
    series: [
      {
        type: "bar",
        data: [...visibleSkills].reverse().map((s) => ({
          value: Number(((s.weighted_share ?? 0) * 100).toFixed(1)),
          slug: s.skill_slug,
        })),
        itemStyle: { color: SKILLBI_PALETTE.market, borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: "right", formatter: "{c}%", fontSize: 11 },
      },
    ],
  };

  const salaryOption = {
    tooltip: { trigger: "axis" },
    legend: { bottom: 0, data: ["p25", "p50 (Median)", "p75"] },
    grid: { top: 20, right: 20, bottom: 42, left: 64 },
    xAxis: {
      type: "category",
      data: expSalaryBands.map((s) => `${s.experience_band} (n=${s.n_postings})`),
    },
    yAxis: {
      type: "value",
      axisLabel: { formatter: (v: number) => `฿${(v / 1000).toFixed(0)}k` },
    },
    series: [
      {
        name: "p25",
        type: "bar",
        data: expSalaryBands.map((s) => s.salary_p25),
        itemStyle: { color: SKILLBI_PALETTE.context },
      },
      {
        name: "p50 (Median)",
        type: "bar",
        data: expSalaryBands.map((s) => s.salary_p50),
        itemStyle: { color: SKILLBI_PALETTE.me },
      },
      {
        name: "p75",
        type: "bar",
        data: expSalaryBands.map((s) => s.salary_p75),
        itemStyle: { color: SKILLBI_PALETTE.market },
      },
    ],
  };

  return (
    <div className="space-y-6">
      <Link
        href="/market"
        className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[var(--ink-secondary)] hover:text-[var(--series-me)]"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        <span>{locale === "th" ? "กลับสู่ตลาดทักษะ" : "Back to Market Explorer"}</span>
      </Link>

      <section className="glass p-6">
        <div className="relative z-10 flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <Briefcase className="h-5 w-5 text-[var(--series-me)]" aria-hidden="true" />
              <StatusChip variant="pending" label={`${nOccPostings} ประกาศ`} />
              {occupation.onet_ref ? (
                <span className="text-[12px] text-[var(--ink-muted)]">
                  O*NET: {occupation.onet_ref}
                </span>
              ) : null}
            </div>
            <h1 className="text-[24px] font-semibold text-[var(--ink-primary)]">
              {locale === "th" ? occupation.occupation_name_th : occupation.occupation_cluster}
            </h1>
            <p className="text-[14px] text-[var(--ink-secondary)]">
              {occupation.occupation_cluster}
            </p>
          </div>

          <Link
            href="/salary"
            className="inline-flex min-h-[42px] items-center gap-2 rounded-xl bg-[var(--series-me)] px-4 text-[13px] font-semibold text-white"
          >
            <Wallet className="h-4 w-4" aria-hidden="true" />
            <span>{locale === "th" ? "ประมาณเงินเดือนกลุ่มนี้" : "Estimate Salary for Role"}</span>
          </Link>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        <div className="lg:col-span-6">
          <GlassCard
            title={locale === "th" ? "Skill Ranking ของกลุ่มอาชีพนี้" : "Skill Ranking"}
            icon={<BarChart3 className="h-5 w-5" />}
            suppressBelowMinN
            provenance={{ source: "JobThai", n: nOccPostings, updatedAt: publicSummary.last_updated_at }}
            tableData={{
              csvFilename: `${occupation.occupation_slug}-skills.csv`,
              columns: [
                { key: "skill", label: locale === "th" ? "ทักษะ" : "Skill" },
                { key: "share", label: "%", numeric: true },
                { key: "n", label: "n", numeric: true },
              ],
              rows: visibleSkills.map((s) => ({
                skill: locale === "th" ? s.skill_name_th : s.skill_canonical,
                share: `${((s.weighted_share ?? 0) * 100).toFixed(1)}%`,
                n: s.n_postings,
              })),
            }}
          >
            {visibleSkills.length === 0 ? (
              <LowDataState n={nOccPostings} />
            ) : (
              <EChartBox
                option={skillOption}
                height={330}
                ariaLabel="Occupation skill ranking"
                onItemClick={(params: unknown) => {
                  const p = params as { data?: { slug?: string } };
                  if (p?.data?.slug) router.push(`/skills/${p.data.slug}`);
                }}
              />
            )}
          </GlassCard>
        </div>

        <div className="lg:col-span-6">
          <GlassCard
            title={locale === "th" ? "Salary Range Ladder (p25–p50–p75)" : "Salary Range Ladder"}
            subtitle={
              locale === "th"
                ? "แสดงเฉพาะกลุ่มที่มีประกาศระบุเงินเดือน n ≥ 5"
                : "Shown only where salaried postings n >= 5"
            }
            icon={<Wallet className="h-5 w-5" />}
            provenance={{ source: "JobThai", n: expSalaryBands.reduce((a, b) => a + b.n_postings, 0) }}
            tableData={{
              columns: [
                { key: "band", label: locale === "th" ? "ประสบการณ์" : "Experience" },
                { key: "p25", label: "p25", numeric: true },
                { key: "p50", label: "p50", numeric: true },
                { key: "p75", label: "p75", numeric: true },
                { key: "n", label: "n", numeric: true },
              ],
              rows: expSalaryBands.map((s) => ({
                band: s.experience_band,
                p25: formatBaht(s.salary_p25),
                p50: formatBaht(s.salary_p50),
                p75: formatBaht(s.salary_p75),
                n: s.n_postings,
              })),
            }}
          >
            {expSalaryBands.length === 0 ? (
              <LowDataState n={0} />
            ) : (
              <EChartBox option={salaryOption} height={330} ariaLabel="Salary range ladder by experience" />
            )}
          </GlassCard>
        </div>
      </div>

      {/* Top Links (<= 5 short titles + external source links ONLY, ZERO descriptions) */}
      <GlassCard
        title={locale === "th" ? "ตัวอย่างประกาศงานในกลุ่มอาชีพนี้ (ลิงก์ต้นฉบับ ≤ 5 รายการ)" : "Sample Source Postings (≤ 5 Links)"}
        subtitle={
          locale === "th"
            ? "แสดงเฉพาะชื่อตำแหน่งสั้นๆ และลิงก์ไปยังเว็บต้นฉบับตามกติกา ToS"
            : "Displays short job titles and external links only (no descriptions)"
        }
        icon={<ExternalLink className="h-5 w-5" />}
        provenance={{ source: "JobThai", n: nOccPostings }}
      >
        {topLinks.length === 0 ? (
          <LowDataState n={nOccPostings} />
        ) : (
          <div className="space-y-2.5">
            {topLinks.slice(0, 5).map((link, i) => (
              <SourceLink
                key={`${link.source_url}-${i}`}
                url={link.source_url}
                titleShort={link.title_short}
                sourceName={link.source_name}
                datePosted={link.date_posted}
              />
            ))}
          </div>
        )}
      </GlassCard>
    </div>
  );
}
