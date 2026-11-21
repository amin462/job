"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Briefcase, Check, Layers, Plus, TrendingUp, Wallet } from "lucide-react";
import { EChartBox } from "@/components/charts/EChartBox";
import { useRegisterPageContext } from "@/components/chat/PageContextProvider";
import {
  EmptyState,
  GlassCard,
  LowDataState,
  StatusChip,
} from "@/components/ui/DesignPrimitives";
import { SKILLBI_PALETTE } from "@/lib/echarts-theme";
import { formatBaht, formatDateByLocale, useI18n } from "@/lib/i18n";
import type {
  DimSkill,
  OccupationSkillProfileRow,
  PublicSummary,
  SalaryStatsRow,
  SkillCooccurrenceRow,
  SkillDemandWeeklyRow,
  UserSession,
} from "@/types/marts";

export function SkillDetailView({
  skill,
  weeklyTrend,
  occupationsRequesting,
  cooccurrence,
  salaryStats,
  publicSummary,
  session,
}: {
  skill: DimSkill | null;
  weeklyTrend: SkillDemandWeeklyRow[];
  occupationsRequesting: OccupationSkillProfileRow[];
  cooccurrence: SkillCooccurrenceRow[];
  salaryStats: SalaryStatsRow[];
  publicSummary: PublicSummary;
  session: UserSession | null;
}) {
  const { locale } = useI18n();
  const router = useRouter();
  const [added, setAdded] = useState(false);
  const [saving, setSaving] = useState(false);

  const visibleOccs = useMemo(
    () => occupationsRequesting.filter((r) => !r.is_suppressed && r.weighted_share !== null),
    [occupationsRequesting]
  );

  // Compare salary median of occupations heavily requesting this skill vs national median
  const salaryComparison = useMemo(() => {
    const national = salaryStats.find(
      (s) => s.scope_type === "national" && !s.is_suppressed
    );
    const matchingOccs = visibleOccs
      .map((o) =>
        salaryStats.find(
          (s) =>
            s.scope_type === "occ" &&
            s.occupation_cluster === o.occupation_cluster &&
            !s.is_suppressed
        )
      )
      .filter((s): s is SalaryStatsRow => Boolean(s));

    const bestMatch = matchingOccs[0] ?? null;
    return { national, withSkillOcc: bestMatch };
  }, [salaryStats, visibleOccs]);

  const totalOccCount = useMemo(
    () => occupationsRequesting.reduce((acc, r) => acc + r.n_postings, 0),
    [occupationsRequesting]
  );

  useRegisterPageContext({
    page: "skill-detail",
    route: skill ? `/skills/${skill.skill_slug}` : "/skills",
    title: skill
      ? locale === "th"
        ? skill.skill_name_th
        : skill.skill_canonical
      : "Skill Detail",
    kpis: skill
      ? [
          { label: locale === "th" ? "ประกาศที่ขอทักษะนี้" : "Postings Requesting", value: totalOccCount },
          { label: locale === "th" ? "กลุ่มทักษะ" : "Skill Group", value: skill.skill_group },
        ]
      : [],
    charts: [
      {
        id: "co-occurrence",
        title: locale === "th" ? "ทักษะที่มักมาคู่กัน (Top 15)" : "Top 15 Co-occurring Skills",
        rows: cooccurrence.map((c) => [
          locale === "th" ? c.co_skill_name_th : c.co_skill_canonical,
          Number((c.co_share * 100).toFixed(1)),
          c.n_postings,
        ]),
      },
      {
        id: "top-occupations",
        title: locale === "th" ? "กลุ่มอาชีพที่ขอทักษะนี้" : "Top Occupations Requesting",
        rows: visibleOccs.map((o) => [
          locale === "th" ? o.occupation_name_th : o.occupation_cluster,
          Number(((o.weighted_share ?? 0) * 100).toFixed(1)),
          o.n_postings,
        ]),
      },
    ],
    asOf: publicSummary.last_updated_at || undefined,
  });

  if (!skill) {
    return (
      <EmptyState
        title={locale === "th" ? "ไม่พบทักษะนี้ในระบบ" : "Skill not found"}
        action={
          <Link
            href="/market"
            className="inline-flex min-h-[40px] items-center rounded-xl bg-[var(--series-me)] px-4 text-[13px] font-semibold text-white"
          >
            {locale === "th" ? "กลับไปหน้า Market Explorer" : "Back to Market Explorer"}
          </Link>
        }
      />
    );
  }

  const handleAddToMySkills = async () => {
    if (!session) {
      router.push(`/login?next=/skills/${skill.skill_slug}`);
      return;
    }
    setSaving(true);
    try {
      const res = await fetch("/api/user-state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "upsert_skill",
          skill_key: skill.skill_key,
          level: 2,
        }),
      });
      if (res.ok) setAdded(true);
    } finally {
      setSaving(false);
    }
  };

  const trendOption = {
    tooltip: { trigger: "axis" },
    grid: { top: 24, right: 24, bottom: 28, left: 48 },
    xAxis: {
      type: "category",
      data: weeklyTrend.map((w) => formatDateByLocale(w.week_start, locale)),
    },
    yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
    series: [
      {
        name: skill.skill_canonical,
        type: "line",
        data: weeklyTrend.map((w) =>
          w.weighted_share !== null ? Number((w.weighted_share * 100).toFixed(1)) : 0
        ),
        itemStyle: { color: SKILLBI_PALETTE.me },
        markPoint: { data: [{ type: "max", name: "Peak" }] },
      },
    ],
  };

  const coOption = {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { top: 8, right: 44, bottom: 24, left: 160 },
    xAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
    yAxis: {
      type: "category",
      data: [...cooccurrence]
        .reverse()
        .map((c) => {
          const lbl = locale === "th" ? c.co_skill_name_th : c.co_skill_canonical;
          return lbl.length > 24 ? lbl.slice(0, 22) + "…" : lbl;
        }),
    },
    series: [
      {
        type: "bar",
        data: [...cooccurrence].reverse().map((c) => ({
          value: Number((c.co_share * 100).toFixed(1)),
          slug: c.co_skill_slug,
        })),
        itemStyle: { color: SKILLBI_PALETTE.compare, borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: "right", formatter: "{c}%", fontSize: 11 },
      },
    ],
  };

  const occOption = {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { top: 8, right: 44, bottom: 24, left: 160 },
    xAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
    yAxis: {
      type: "category",
      data: [...visibleOccs]
        .slice(0, 10)
        .reverse()
        .map((o) => {
          const lbl = locale === "th" ? o.occupation_name_th : o.occupation_cluster;
          return lbl.length > 24 ? lbl.slice(0, 22) + "…" : lbl;
        }),
    },
    series: [
      {
        type: "bar",
        data: [...visibleOccs]
          .slice(0, 10)
          .reverse()
          .map((o) => ({
            value: Number(((o.weighted_share ?? 0) * 100).toFixed(1)),
            slug: o.occupation_slug,
          })),
        itemStyle: { color: SKILLBI_PALETTE.market, borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: "right", formatter: "{c}%", fontSize: 11 },
      },
    ],
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          href="/market"
          className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[var(--ink-secondary)] hover:text-[var(--series-me)]"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          <span>{locale === "th" ? "กลับสู่ตลาดทักษะ" : "Back to Market Explorer"}</span>
        </Link>

        <button
          type="button"
          onClick={handleAddToMySkills}
          disabled={saving || added}
          className="inline-flex min-h-[42px] items-center gap-2 rounded-xl bg-[var(--series-me)] px-4 text-[13px] font-semibold text-white hover:opacity-95 disabled:opacity-70"
        >
          {added ? <Check className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          <span>
            {added
              ? locale === "th"
                ? "เพิ่มเข้าทักษะของฉันแล้ว"
                : "Added to My Skills"
              : locale === "th"
              ? "เพิ่มเข้าทักษะของฉัน"
              : "Add to My Skills"}
          </span>
        </button>
      </div>

      {/* Header Card */}
      <section className="glass p-6">
        <div className="relative z-10 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <StatusChip variant="pending" label={skill.skill_type} />
            <StatusChip variant="neutral" label={skill.skill_group} />
            {skill.onet_ref ? (
              <span className="text-[12px] text-[var(--ink-muted)]">
                O*NET: {skill.onet_ref}
              </span>
            ) : null}
          </div>
          <h1 className="text-[26px] font-semibold text-[var(--ink-primary)]">
            {locale === "th" ? skill.skill_name_th : skill.skill_canonical}
          </h1>
          <p className="text-[14px] text-[var(--ink-secondary)]">
            {skill.skill_canonical} · {skill.skill_name_th}
          </p>
          <div className="pt-1">
            <div className="mb-1.5 text-[12px] font-medium text-[var(--ink-muted)]">
              {locale === "th" ? "คำพ้อง / Aliases ที่พบในประกาศงาน:" : "Matched Aliases:"}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {(skill.aliases || []).map((al) => (
                <span
                  key={al}
                  className="rounded-full border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-2.5 py-0.5 text-[12px] text-[var(--ink-secondary)]"
                >
                  {al}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        <div className="lg:col-span-6">
          <GlassCard
            title={locale === "th" ? "แนวโน้มความต้องการรายสัปดาห์" : "Weekly Demand Trend"}
            icon={<TrendingUp className="h-5 w-5" />}
            provenance={{ source: "JobThai", n: totalOccCount, updatedAt: publicSummary.last_updated_at }}
            tableData={{
              columns: [
                { key: "week", label: locale === "th" ? "สัปดาห์" : "Week" },
                { key: "share", label: "%", numeric: true },
                { key: "n", label: "n", numeric: true },
              ],
              rows: weeklyTrend.map((w) => ({
                week: formatDateByLocale(w.week_start, locale),
                share: w.weighted_share !== null ? `${(w.weighted_share * 100).toFixed(1)}%` : "n < 5",
                n: w.n_postings,
              })),
            }}
          >
            {weeklyTrend.every((w) => w.is_suppressed) ? (
              <LowDataState n={totalOccCount} />
            ) : (
              <EChartBox option={trendOption} height={260} ariaLabel="Skill weekly demand trend" />
            )}
          </GlassCard>
        </div>

        <div className="lg:col-span-6">
          <GlassCard
            title={locale === "th" ? "เงินเดือนเปรียบเทียบ (กลุ่มที่ขอทักษะนี้ vs ภาพรวม)" : "Salary Range Comparison"}
            icon={<Wallet className="h-5 w-5" />}
            provenance={{ source: "JobThai", n: salaryComparison.withSkillOcc?.n_postings ?? 0 }}
          >
            {!salaryComparison.withSkillOcc ? (
              <LowDataState n={0} />
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-4">
                  <div className="text-[12px] font-medium text-[var(--series-me)]">
                    {salaryComparison.withSkillOcc.occupation_cluster}
                  </div>
                  <div className="tabular-nums mt-1 text-[22px] font-semibold text-[var(--ink-primary)]">
                    {formatBaht(salaryComparison.withSkillOcc.salary_p50)}
                  </div>
                  <div className="text-[12px] text-[var(--ink-secondary)]">
                    p25–p75: {formatBaht(salaryComparison.withSkillOcc.salary_p25)} –{" "}
                    {formatBaht(salaryComparison.withSkillOcc.salary_p75)} (n ={" "}
                    {salaryComparison.withSkillOcc.n_postings})
                  </div>
                </div>
                {salaryComparison.national ? (
                  <div className="rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-4">
                    <div className="text-[12px] font-medium text-[var(--series-market)]">
                      {locale === "th" ? "มัธยฐานตลาดรวม" : "National Market Median"}
                    </div>
                    <div className="tabular-nums mt-1 text-[22px] font-semibold text-[var(--ink-primary)]">
                      {formatBaht(salaryComparison.national.salary_p50)}
                    </div>
                    <div className="text-[12px] text-[var(--ink-secondary)]">
                      p25–p75: {formatBaht(salaryComparison.national.salary_p25)} –{" "}
                      {formatBaht(salaryComparison.national.salary_p75)} (n ={" "}
                      {salaryComparison.national.n_postings})
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </GlassCard>
        </div>

        <div className="lg:col-span-6">
          <GlassCard
            title={locale === "th" ? "กลุ่มอาชีพที่ขอทักษะนี้มากที่สุด" : "Top Occupations Requesting This Skill"}
            icon={<Briefcase className="h-5 w-5" />}
            provenance={{ source: "JobThai", n: totalOccCount }}
            tableData={{
              columns: [
                { key: "occ", label: locale === "th" ? "กลุ่มอาชีพ" : "Occupation" },
                { key: "share", label: "%", numeric: true },
                { key: "n", label: "n", numeric: true },
              ],
              rows: visibleOccs.map((o) => ({
                occ: locale === "th" ? o.occupation_name_th : o.occupation_cluster,
                share: `${((o.weighted_share ?? 0) * 100).toFixed(1)}%`,
                n: o.n_postings,
              })),
            }}
          >
            {visibleOccs.length === 0 ? (
              <LowDataState n={totalOccCount} />
            ) : (
              <EChartBox
                option={occOption}
                height={300}
                ariaLabel="Occupations requesting this skill"
                onItemClick={(params: unknown) => {
                  const p = params as { data?: { slug?: string } };
                  if (p?.data?.slug) router.push(`/occupations/${p.data.slug}`);
                }}
              />
            )}
          </GlassCard>
        </div>

        <div className="lg:col-span-6">
          <GlassCard
            title={locale === "th" ? "ทักษะที่มักมาคู่กัน (Top 15 Co-occurrence)" : "Top 15 Co-occurring Skills"}
            icon={<Layers className="h-5 w-5" />}
            provenance={{ source: "JobThai", n: totalOccCount }}
            tableData={{
              columns: [
                { key: "co", label: locale === "th" ? "ทักษะคู่กัน" : "Co-occurring Skill" },
                { key: "share", label: "%", numeric: true },
                { key: "n", label: "n", numeric: true },
              ],
              rows: cooccurrence.map((c) => ({
                co: locale === "th" ? c.co_skill_name_th : c.co_skill_canonical,
                share: `${(c.co_share * 100).toFixed(1)}%`,
                n: c.n_postings,
              })),
            }}
          >
            {cooccurrence.length === 0 ? (
              <LowDataState n={totalOccCount} />
            ) : (
              <EChartBox
                option={coOption}
                height={300}
                ariaLabel="Co-occurring skills bar chart"
                onItemClick={(params: unknown) => {
                  const p = params as { data?: { slug?: string } };
                  if (p?.data?.slug) router.push(`/skills/${p.data.slug}`);
                }}
              />
            )}
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
