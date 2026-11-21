"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  FlaskConical,
  Sparkles,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { EChartBox } from "@/components/charts/EChartBox";
import { useRegisterPageContext } from "@/components/chat/PageContextProvider";
import {
  ChampionCard,
  GlassCard,
  LowDataState,
  MeterList,
  StatusChip,
} from "@/components/ui/DesignPrimitives";
import { SkillChipPicker } from "@/components/ui/SkillChipPicker";
import { SKILLBI_PALETTE } from "@/lib/echarts-theme";
import { formatBaht, useI18n } from "@/lib/i18n";
import type {
  DimLocation,
  DimOccupation,
  DimSkill,
  OccupationSkillProfileRow,
  PublicSummary,
  SalaryEstimateResponse,
  SalaryStatsRow,
  UserSkill,
} from "@/types/marts";

const EXPERIENCE_BANDS = [
  "ไม่ระบุ/ไม่จำเป็น",
  "0 ปี / จบใหม่",
  "1-2 ปี",
  "3-5 ปี",
  "5+ ปี",
];

const EDUCATION_LEVELS = [
  "ไม่ระบุ",
  "ม.3/ม.6",
  "ปวช./ปวส.",
  "ปริญญาตรี",
  "ปริญญาโท+",
];

const EMPLOYMENT_TYPES = ["FULL_TIME", "PART_TIME", "CONTRACT", "INTERN"];

export function SalaryView({
  publicSummary,
  salaryStats,
  occupationSkillProfile,
  dimOccupations,
  dimLocations,
  dimSkills,
  userSkills,
  defaultOccupation,
  defaultProvince,
}: {
  publicSummary: PublicSummary;
  salaryStats: SalaryStatsRow[];
  occupationSkillProfile: OccupationSkillProfileRow[];
  dimOccupations: DimOccupation[];
  dimLocations: DimLocation[];
  dimSkills: DimSkill[];
  userSkills: UserSkill[];
  defaultOccupation?: string | null;
  defaultProvince?: string | null;
}) {
  const { locale } = useI18n();

  const [occupation, setOccupation] = useState(
    defaultOccupation ||
      dimOccupations.find((o) => o.occupation_cluster === "Sales & Business Development")
        ?.occupation_cluster ||
      dimOccupations[0]?.occupation_cluster ||
      "Data & Analytics"
  );
  const [province, setProvince] = useState(defaultProvince || "กรุงเทพมหานคร");
  const [experienceBand, setExperienceBand] = useState("1-2 ปี");
  const [educationLevel, setEducationLevel] = useState("ปริญญาตรี");
  const [employmentType, setEmploymentType] = useState("FULL_TIME");
  const [selectedSkillKeys, setSelectedSkillKeys] = useState<number[]>(() =>
    userSkills.length > 0 ? userSkills.map((s) => s.skill_key) : [1, 104]
  );

  const [estimate, setEstimate] = useState<SalaryEstimateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Pre-warm Render/University ml-api on mount (DEPLOY.md §3)
  useEffect(() => {
    fetch("/api/salary/estimate?warm=1").catch(() => {});
  }, []);

  const skillMap = useMemo(
    () => new Map(dimSkills.map((s) => [s.skill_key, s])),
    [dimSkills]
  );

  const selectedCanonicalSkills = useMemo(
    () =>
      selectedSkillKeys
        .map((k) => skillMap.get(k)?.skill_canonical)
        .filter((s): s is string => Boolean(s)),
    [selectedSkillKeys, skillMap]
  );

  const candidateSkills = useMemo(() => {
    const selectedSet = new Set(selectedCanonicalSkills);
    const fromOcc = occupationSkillProfile
      .filter((r) => r.occupation_cluster === occupation && !selectedSet.has(r.skill_canonical))
      .slice(0, 6)
      .map((r) => r.skill_canonical);
    if (fromOcc.length >= 3) return fromOcc;
    return ["SQL", "Python", "Power BI", "Microsoft Excel", "English"]
      .filter((s) => !selectedSet.has(s))
      .slice(0, 5);
  }, [occupation, occupationSkillProfile, selectedCanonicalSkills]);

  const runEstimate = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await fetch("/api/salary/estimate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          occupation_cluster: occupation,
          province_th: province,
          experience_band: experienceBand,
          education_level: educationLevel,
          employment_type: employmentType,
          skills: selectedCanonicalSkills,
          candidate_skills: candidateSkills,
        }),
      });
      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { error?: string };
        throw new Error(err.error || "Estimate failed");
      }
      const data = (await res.json()) as SalaryEstimateResponse;
      setEstimate(data);
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Failed to estimate salary");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runEstimate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ladderRows = useMemo(
    () =>
      salaryStats.filter(
        (s) =>
          (s.occupation_cluster === occupation || s.scope_type === "national") &&
          !s.is_suppressed &&
          s.salary_p50 !== null
      ),
    [salaryStats, occupation]
  );

  useRegisterPageContext({
    page: "salary-estimator",
    route: "/salary",
    title: locale === "th" ? "Salary Explorer & Champion Estimator" : "Salary Estimator",
    filters: {
      occupation,
      province,
      experienceBand,
      educationLevel,
      skillsCount: selectedCanonicalSkills.length,
    },
    kpis: estimate
      ? [
          { label: "p25", value: estimate.p25, unit: "THB" },
          { label: "p50 (Median)", value: estimate.p50, unit: "THB" },
          { label: "p75", value: estimate.p75, unit: "THB" },
          { label: "Model", value: estimate.model_name },
        ]
      : [],
    charts: [
      {
        id: "salary-ladder",
        title: locale === "th" ? "Salary Range Ladder ตามกลุ่มและประสบการณ์" : "Salary Range Ladder",
        rows: ladderRows.slice(0, 12).map((r) => [
          `${r.occupation_cluster} (${r.experience_band})`,
          r.salary_p25,
          r.salary_p50,
          r.salary_p75,
          r.n_postings,
        ]),
      },
      {
        id: "skill-uplift",
        title: locale === "th" ? "ทักษะที่เพิ่มแล้วค่าคาดเพิ่มขึ้น" : "Skill Uplift Estimates",
        rows: (estimate?.uplifts || []).map((u) => [u.skill, u.delta_p50, u.new_p50]),
      },
    ],
    asOf: publicSummary.last_updated_at || undefined,
    dataNotes: [
      "ไม่ใช้เพศ (gender), อายุ (age) และชื่อบริษัทเป็น feature ของโมเดล (D6)",
      "ประมาณการจากประกาศที่ระบุเงินเดือน ไม่ใช่เงินเดือนจริง",
    ],
  });

  const ladderOption = useMemo(() => {
    const rows = ladderRows.slice(0, 8);
    return {
      tooltip: { trigger: "axis" },
      legend: { bottom: 0, data: ["p25", "p50 (ตลาด)", "p75", "ค่าประมาณของฉัน"] },
      grid: { top: 20, right: 20, bottom: 44, left: 60 },
      xAxis: {
        type: "category",
        data: rows.map((r) =>
          r.scope_type === "national"
            ? "ตลาดรวม"
            : `${r.experience_band}\n(n=${r.n_postings})`
        ),
        axisLabel: { fontSize: 11 },
      },
      yAxis: {
        type: "value",
        axisLabel: { formatter: (v: number) => `฿${(v / 1000).toFixed(0)}k` },
      },
      series: [
        {
          name: "p25",
          type: "bar",
          data: rows.map((r) => r.salary_p25),
          itemStyle: { color: SKILLBI_PALETTE.context },
        },
        {
          name: "p50 (ตลาด)",
          type: "bar",
          data: rows.map((r) => r.salary_p50),
          itemStyle: { color: SKILLBI_PALETTE.market },
        },
        {
          name: "p75",
          type: "bar",
          data: rows.map((r) => r.salary_p75),
          itemStyle: { color: "#F4B8A4" },
        },
        ...(estimate
          ? [
              {
                name: "ค่าประมาณของฉัน",
                type: "scatter",
                symbolSize: 14,
                itemStyle: { color: SKILLBI_PALETTE.me },
                data: rows.map(() => estimate.p50),
              },
            ]
          : []),
      ],
    };
  }, [ladderRows, estimate]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[24px] font-semibold text-[var(--ink-primary)]">
            {locale === "th" ? "Salary Explorer & Champion Estimator" : "Salary Explorer & Estimator"}
          </h1>
          <p className="text-[13px] text-[var(--ink-secondary)]">
            {locale === "th"
              ? "ประมาณช่วงเงินเดือนจากโมเดล Champion (ไม่ใช้เพศ อายุ หรือชื่อบริษัทเป็นตัวแปร)"
              : "Estimate expected monthly THB salary range using Champion ML model (no gender/age features)"}
          </p>
        </div>

        <Link
          href="/ml-lab"
          className="inline-flex min-h-[40px] items-center gap-2 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3.5 text-[13px] font-semibold text-[var(--series-me)] hover:bg-[var(--tint-me)]"
        >
          <FlaskConical className="h-4 w-4" aria-hidden="true" />
          <span>{locale === "th" ? "ดูผลการเทียบ 5 โมเดลใน ML Lab →" : "Compare 5 Models in ML Lab →"}</span>
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        {/* Form (No gender or age fields!) */}
        <section className="glass p-5 lg:col-span-5">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              runEstimate();
            }}
            className="relative z-10 space-y-3.5"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-[16px] font-semibold text-[var(--ink-primary)]">
                {locale === "th" ? "ระบุคุณสมบัติและทักษะ" : "Role & Skill Inputs"}
              </h2>
              {userSkills.length > 0 ? (
                <button
                  type="button"
                  onClick={() => setSelectedSkillKeys(userSkills.map((s) => s.skill_key))}
                  className="text-[12px] font-semibold text-[var(--series-me)] hover:underline"
                >
                  {locale === "th" ? "โหลดจากทักษะของฉัน" : "Load My Skills"}
                </button>
              ) : null}
            </div>

            <label className="block text-[13px]">
              <span className="font-medium text-[var(--ink-secondary)]">
                {locale === "th" ? "กลุ่มอาชีพ" : "Occupation Cluster"}
              </span>
              <select
                value={occupation}
                onChange={(e) => setOccupation(e.target.value)}
                className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3"
              >
                {dimOccupations.map((o) => (
                  <option key={o.occupation_slug} value={o.occupation_cluster}>
                    {locale === "th" ? o.occupation_name_th : o.occupation_cluster}
                  </option>
                ))}
              </select>
            </label>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="text-[13px]">
                <span className="font-medium text-[var(--ink-secondary)]">
                  {locale === "th" ? "จังหวัด" : "Province"}
                </span>
                <select
                  value={province}
                  onChange={(e) => setProvince(e.target.value)}
                  className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3"
                >
                  {dimLocations.map((loc) => (
                    <option key={loc.location_key} value={loc.province_th}>
                      {locale === "th" ? loc.province_th : loc.province_en}
                    </option>
                  ))}
                </select>
              </label>

              <label className="text-[13px]">
                <span className="font-medium text-[var(--ink-secondary)]">
                  {locale === "th" ? "ประสบการณ์" : "Experience"}
                </span>
                <select
                  value={experienceBand}
                  onChange={(e) => setExperienceBand(e.target.value)}
                  className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3"
                >
                  {EXPERIENCE_BANDS.map((b) => (
                    <option key={b} value={b}>
                      {b}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <label className="text-[13px]">
                <span className="font-medium text-[var(--ink-secondary)]">
                  {locale === "th" ? "วุฒิการศึกษา" : "Education"}
                </span>
                <select
                  value={educationLevel}
                  onChange={(e) => setEducationLevel(e.target.value)}
                  className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3"
                >
                  {EDUCATION_LEVELS.map((ed) => (
                    <option key={ed} value={ed}>
                      {ed}
                    </option>
                  ))}
                </select>
              </label>

              <label className="text-[13px]">
                <span className="font-medium text-[var(--ink-secondary)]">
                  {locale === "th" ? "ประเภทการจ้าง" : "Employment Type"}
                </span>
                <select
                  value={employmentType}
                  onChange={(e) => setEmploymentType(e.target.value)}
                  className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3"
                >
                  {EMPLOYMENT_TYPES.map((et) => (
                    <option key={et} value={et}>
                      {et}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div>
              <div className="mb-1 text-[13px] font-medium text-[var(--ink-secondary)]">
                {locale === "th" ? "ทักษะที่มี" : "Skills"}
              </div>
              <SkillChipPicker
                skillsCatalog={dimSkills}
                selectedKeys={selectedSkillKeys}
                onAdd={(sk) => setSelectedSkillKeys((prev) => [...prev, sk.skill_key])}
                onRemove={(k) => setSelectedSkillKeys((prev) => prev.filter((x) => x !== k))}
              />
            </div>

            <button
              type="submit"
              disabled={loading || !occupation}
              className="min-h-[44px] w-full rounded-xl bg-[var(--series-me)] px-4 text-[14px] font-semibold text-white hover:opacity-95 disabled:opacity-60"
            >
              {loading
                ? locale === "th"
                  ? "กำลังคำนวณช่วงเงินเดือน..."
                  : "Estimating..."
                : locale === "th"
                ? "ประมาณช่วงเงินเดือน"
                : "Estimate Salary Range"}
            </button>
          </form>
        </section>

        {/* Champion Card */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          {errorMsg ? (
            <div className="rounded-2xl border border-[#C92A2A]/30 bg-[#C92A2A]/10 p-4 text-[14px] text-[#9E1C1C]">
              {errorMsg}
            </div>
          ) : null}

          <ChampionCard
            badge={estimate?.badge || (locale === "th" ? "โมเดล Champion" : "Champion Estimator")}
            title={
              locale === "th"
                ? `ช่วงเงินเดือนที่คาด (${occupation})`
                : `Estimated Monthly Salary (${occupation})`
            }
            footer={
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  {estimate?.disclaimer ||
                    "ประมาณการจากประกาศที่ระบุเงินเดือน ไม่ใช่เงินเดือนจริง"}
                </span>
                <span className="inline-flex items-center gap-1">
                  <Sparkles className="h-3.5 w-3.5" />
                  {estimate?.model_name || "Champion"}
                </span>
              </div>
            }
          >
            {estimate ? (
              <div className="space-y-3">
                <div className="tabular-nums text-[32px] leading-tight font-bold text-white sm:text-[38px]">
                  {formatBaht(estimate.p25)} – {formatBaht(estimate.p75)}
                </div>
                <div className="flex flex-wrap items-center gap-3 text-[14px] font-medium text-white/95">
                  <span>
                    {locale === "th" ? "ค่ากลางคาดการณ์ (p50):" : "Median (p50):"}{" "}
                    <strong className="tabular-nums">{formatBaht(estimate.p50)}</strong>
                  </span>
                  {estimate.cv_mae ? (
                    <span className="tabular-nums">
                      · CV MAE ±{formatBaht(estimate.cv_mae)}
                    </span>
                  ) : null}
                  {estimate.cv_mape ? (
                    <span className="tabular-nums">
                      · MAPE {estimate.cv_mape.toFixed(1)}%
                    </span>
                  ) : null}
                </div>
                {estimate.low_support_warning ? (
                  <div className="inline-flex items-center gap-1.5 rounded-xl bg-black/25 px-3 py-1.5 text-[12px] font-medium text-white">
                    <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
                    <span>
                      {locale === "th"
                        ? "ข้อมูลสนับสนุนในกลุ่มนี้ยังมีจำนวนน้อย ค่าคาดอาจมีความไม่แน่นอนสูง"
                        : "Low training support for this combination — wider uncertainty"}
                    </span>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="py-6 text-[14px] text-white/90">
                {locale === "th" ? "กำลังโหลดผลประมาณการ..." : "Loading estimate..."}
              </div>
            )}
          </ChampionCard>

          <div className="surface-solid flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-[12px] text-[var(--ink-secondary)]">
            <span>
              {locale === "th"
                ? "นโยบายความเป็นธรรม (D6): ไม่มีช่องกรอกเพศ อายุ หรือชื่อบริษัทในแบบจำลอง"
                : "Fairness Policy (D6): Gender, age, and company name are excluded from ML features."}
            </span>
            <StatusChip
              variant={estimate?.source === "ml-api" ? "good" : "pending"}
              label={estimate?.source === "ml-api" ? "Live FastAPI" : "Mart Fallback"}
            />
          </div>
        </div>
      </div>

      {/* Salary Range Ladder & Skill Uplift */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <GlassCard
            title={locale === "th" ? "Salary Range Ladder (ตลาด vs ค่าประมาณของฉัน)" : "Salary Range Ladder"}
            icon={<Wallet className="h-5 w-5" />}
            provenance={{ source: "JobThai", n: publicSummary.n_with_salary }}
            tableData={{
              csvFilename: "salary-ladder.csv",
              columns: [
                { key: "scope", label: locale === "th" ? "กลุ่ม / ประสบการณ์" : "Scope" },
                { key: "p25", label: "p25", numeric: true },
                { key: "p50", label: "p50", numeric: true },
                { key: "p75", label: "p75", numeric: true },
                { key: "n", label: "n", numeric: true },
              ],
              rows: ladderRows.map((r) => ({
                scope:
                  r.scope_type === "national"
                    ? "ภาพรวมทั้งประเทศ"
                    : `${r.occupation_cluster} (${r.experience_band})`,
                p25: formatBaht(r.salary_p25),
                p50: formatBaht(r.salary_p50),
                p75: formatBaht(r.salary_p75),
                n: r.n_postings,
              })),
            }}
          >
            {ladderRows.length === 0 ? (
              <LowDataState n={0} />
            ) : (
              <EChartBox option={ladderOption} height={300} ariaLabel="Salary range ladder chart" />
            )}
          </GlassCard>
        </div>

        <div className="lg:col-span-5">
          <GlassCard
            title={
              locale === "th"
                ? "ทักษะที่ถ้าเพิ่มแล้วค่าคาดเพิ่มขึ้น (1 Batch Call)"
                : "Top Skill Uplift Impact"
            }
            subtitle={
              locale === "th"
                ? "คำนวณจากการลองเพิ่มทีละทักษะผ่าน /predict/batch"
                : "Marginal uplift computed via single batch inference"
            }
            icon={<TrendingUp className="h-5 w-5" />}
            provenance={{ source: estimate?.model_name || "Champion", n: publicSummary.n_with_salary }}
          >
            {!estimate || estimate.uplifts.length === 0 ? (
              <LowDataState n={0} />
            ) : (
              <MeterList
                accent="me"
                items={estimate.uplifts.map((u, idx) => ({
                  id: `${u.skill}-${idx}`,
                  label: u.skill,
                  sublabel: `p50 → ${formatBaht(u.new_p50)}`,
                  value: Math.max(u.delta_p50, 0),
                  valueText: `${u.delta_p50 >= 0 ? "+" : ""}${formatBaht(u.delta_p50)}`,
                }))}
              />
            )}
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
