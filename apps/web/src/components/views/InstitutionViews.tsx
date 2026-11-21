"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Download,
  FileSpreadsheet,
  GitCompare,
  GraduationCap,
  Plus,
  Printer,
  Trash2,
  Upload,
} from "lucide-react";
import { EChartBox } from "@/components/charts/EChartBox";
import { useRegisterPageContext } from "@/components/chat/PageContextProvider";
import {
  EmptyState,
  GlassCard,
  LowDataState,
  StatusChip,
  downloadAggregateCsv,
} from "@/components/ui/DesignPrimitives";
import { DataTable } from "@/components/ui/DataTable";
import { SkillChipPicker } from "@/components/ui/SkillChipPicker";
import { SKILLBI_PALETTE } from "@/lib/echarts-theme";
import { useI18n } from "@/lib/i18n";
import type {
  CurriculumCoverageRefRow,
  CurriculumItem,
  DimOccupation,
  DimSkill,
  PublicSummary,
} from "@/types/marts";

function computeAlignment(
  curriculum: CurriculumItem,
  refRows: CurriculumCoverageRefRow[],
  dimSkills: DimSkill[],
  topK = 30
) {
  const targetRef = refRows
    .filter(
      (r) =>
        r.occupation_cluster === curriculum.target_occupation_cluster &&
        !r.is_suppressed &&
        r.rank_order <= topK
    )
    .sort((a, b) => a.rank_order - b.rank_order);

  const fallbackRef =
    targetRef.length > 0
      ? targetRef
      : refRows.filter((r) => !r.is_suppressed && r.rank_order <= 15).slice(0, topK);

  const taughtSet = new Set(curriculum.skills.map((s) => s.skill_key));
  const marketSet = new Set(fallbackRef.map((r) => r.skill_key));

  const totalW = fallbackRef.reduce(
    (acc, r) => acc + (r.importance_weight ?? r.weighted_share ?? 0),
    0
  );
  const coveredW = fallbackRef.reduce(
    (acc, r) =>
      taughtSet.has(r.skill_key)
        ? acc + (r.importance_weight ?? r.weighted_share ?? 0)
        : acc,
    0
  );
  const coveragePct = totalW > 0 ? (coveredW / totalW) * 100 : 0;

  const gaps = fallbackRef.filter((r) => !taughtSet.has(r.skill_key));
  const skillMap = new Map(dimSkills.map((s) => [s.skill_key, s]));
  const overCoverage = Array.from(taughtSet)
    .filter((k) => !marketSet.has(k))
    .map((k) => skillMap.get(k))
    .filter((s): s is DimSkill => Boolean(s));

  return {
    usedFallback: targetRef.length === 0,
    coveragePct,
    coveredCount: fallbackRef.filter((r) => taughtSet.has(r.skill_key)).length,
    totalMarketSkills: fallbackRef.length,
    gaps,
    overCoverage,
  };
}

export function CurriculaListView({
  initialCurricula,
  dimOccupations,
  dimSkills,
  curriculumCoverageRef,
  publicSummary,
}: {
  initialCurricula: CurriculumItem[];
  dimOccupations: DimOccupation[];
  dimSkills: DimSkill[];
  curriculumCoverageRef: CurriculumCoverageRefRow[];
  publicSummary: PublicSummary;
}) {
  const { locale } = useI18n();
  const router = useRouter();
  const [curricula, setCurricula] = useState<CurriculumItem[]>(initialCurricula);
  const [name, setName] = useState("");
  const [targetOcc, setTargetOcc] = useState(
    dimOccupations[0]?.occupation_cluster || "Data & Analytics"
  );
  const [creating, setCreating] = useState(false);

  const [compareA, setCompareA] = useState<number>(
    initialCurricula[0]?.curriculum_id ?? 0
  );
  const [compareB, setCompareB] = useState<number>(
    initialCurricula[1]?.curriculum_id ?? initialCurricula[0]?.curriculum_id ?? 0
  );

  const alignedList = useMemo(
    () =>
      curricula.map((c) => ({
        curriculum: c,
        alignment: computeAlignment(c, curriculumCoverageRef, dimSkills),
      })),
    [curricula, curriculumCoverageRef, dimSkills]
  );

  const cmpA = alignedList.find((a) => a.curriculum.curriculum_id === compareA);
  const cmpB = alignedList.find((a) => a.curriculum.curriculum_id === compareB);

  useRegisterPageContext({
    page: "institution-curricula",
    route: "/institution/curricula",
    title: locale === "th" ? "รายการหลักสูตรและการเทียบตลาด" : "Institution Curricula",
    kpis: [{ label: locale === "th" ? "จำนวนหลักสูตร" : "Curricula Count", value: curricula.length }],
    tableTop: alignedList.map((a) => ({
      name: a.curriculum.name,
      target: a.curriculum.target_occupation_cluster,
      coveragePct: Number(a.alignment.coveragePct.toFixed(1)),
      gaps: a.alignment.gaps.length,
    })),
    asOf: publicSummary.last_updated_at || undefined,
  });

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    try {
      const res = await fetch("/api/user-state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "create_curriculum",
          name,
          target_occupation_cluster: targetOcc,
        }),
      });
      const data = (await res.json()) as { curriculum?: CurriculumItem };
      if (res.ok && data.curriculum) {
        setCurricula((prev) => [...prev, data.curriculum!]);
        setName("");
        router.refresh();
      }
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: number) => {
    await fetch("/api/user-state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "delete_curriculum", curriculum_id: id }),
    });
    setCurricula((prev) => prev.filter((c) => c.curriculum_id !== id));
    router.refresh();
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[24px] font-semibold text-[var(--ink-primary)]">
          {locale === "th" ? "หลักสูตรและความสอดคล้องกับตลาด" : "Curriculum Alignment"}
        </h1>
        <p className="text-[13px] text-[var(--ink-secondary)]">
          {locale === "th"
            ? "สร้างหลักสูตร จับคู่รายวิชา→ทักษะ และเปรียบเทียบความครอบคลุมระหว่าง 2 หลักสูตร"
            : "Manage curricula, map courses to skills, and compare alignment side-by-side"}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        <section className="glass p-5 lg:col-span-4">
          <form onSubmit={handleCreate} className="relative z-10 space-y-3.5">
            <div className="flex items-center gap-2">
              <Plus className="h-5 w-5 text-[var(--series-me)]" aria-hidden="true" />
              <h2 className="text-[16px] font-semibold text-[var(--ink-primary)]">
                {locale === "th" ? "สร้างหลักสูตรใหม่" : "Create Curriculum"}
              </h2>
            </div>

            <label className="block text-[13px]">
              <span className="font-medium text-[var(--ink-secondary)]">
                {locale === "th" ? "ชื่อหลักสูตร" : "Curriculum Name"}
              </span>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={locale === "th" ? "เช่น วท.บ. คอมพิวเตอร์ธุรกิจ" : "e.g. B.Sc. Business Computing"}
                className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3"
              />
            </label>

            <label className="block text-[13px]">
              <span className="font-medium text-[var(--ink-secondary)]">
                {locale === "th" ? "กลุ่มอาชีพเป้าหมาย" : "Target Occupation"}
              </span>
              <select
                value={targetOcc}
                onChange={(e) => setTargetOcc(e.target.value)}
                className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3"
              >
                {dimOccupations.map((o) => (
                  <option key={o.occupation_slug} value={o.occupation_cluster}>
                    {locale === "th" ? o.occupation_name_th : o.occupation_cluster}
                  </option>
                ))}
              </select>
            </label>

            <button
              type="submit"
              disabled={creating}
              className="min-h-[44px] w-full rounded-xl bg-[var(--series-me)] font-semibold text-white"
            >
              {creating
                ? locale === "th"
                  ? "กำลังสร้าง..."
                  : "Creating..."
                : locale === "th"
                ? "สร้างหลักสูตร"
                : "Create Curriculum"}
            </button>
          </form>
        </section>

        <div className="space-y-3 lg:col-span-8">
          {alignedList.length === 0 ? (
            <EmptyState
              title={locale === "th" ? "ยังไม่มีหลักสูตร" : "No curricula yet"}
              description={locale === "th" ? "สร้างหลักสูตรแรกทางด้านซ้าย" : "Create your first curriculum on the left."}
            />
          ) : (
            alignedList.map(({ curriculum, alignment }) => (
              <div
                key={curriculum.curriculum_id}
                className="glass flex flex-wrap items-center justify-between gap-4 p-5"
              >
                <div className="relative z-10 min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <GraduationCap className="h-4 w-4 text-[var(--series-me)]" aria-hidden="true" />
                    <Link
                      href={`/institution/curricula/${curriculum.curriculum_id}`}
                      className="text-[16px] font-semibold text-[var(--ink-primary)] hover:text-[var(--series-me)]"
                    >
                      {curriculum.name}
                    </Link>
                  </div>
                  <div className="text-[12px] text-[var(--ink-secondary)]">
                    {locale === "th" ? "เป้าหมาย:" : "Target:"} {curriculum.target_occupation_cluster} ·{" "}
                    {curriculum.skills.length} {locale === "th" ? "คู่รายวิชา-ทักษะ" : "course-skill mappings"}
                  </div>
                </div>

                <div className="relative z-10 flex items-center gap-3">
                  <StatusChip
                    variant={alignment.coveragePct >= 60 ? "good" : "warning"}
                    label={`Coverage ${alignment.coveragePct.toFixed(1)}%`}
                  />
                  <Link
                    href={`/institution/curricula/${curriculum.curriculum_id}`}
                    className="inline-flex min-h-[38px] items-center rounded-xl bg-[var(--series-me)] px-3.5 text-[13px] font-semibold text-white"
                  >
                    {locale === "th" ? "เปิดรายงาน →" : "Open →"}
                  </Link>
                  <button
                    type="button"
                    onClick={() => handleDelete(curriculum.curriculum_id)}
                    aria-label={`Delete ${curriculum.name}`}
                    className="flex h-9 w-9 items-center justify-center rounded-lg text-[var(--ink-muted)] hover:bg-[#C92A2A]/10 hover:text-[#C92A2A]"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* T5.16 Compare 2 Curricula */}
      {curricula.length >= 2 && cmpA && cmpB ? (
        <GlassCard
          title={locale === "th" ? "เปรียบเทียบ 2 หลักสูตร (Side-by-Side Comparison)" : "Compare 2 Curricula"}
          icon={<GitCompare className="h-5 w-5" />}
          provenance={{ source: "JobThai", n: publicSummary.n_postings }}
        >
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <select
                aria-label="Curriculum A"
                value={compareA}
                onChange={(e) => setCompareA(Number(e.target.value))}
                className="min-h-[40px] rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3 text-[13px]"
              >
                {curricula.map((c) => (
                  <option key={c.curriculum_id} value={c.curriculum_id}>
                    A: {c.name}
                  </option>
                ))}
              </select>
              <select
                aria-label="Curriculum B"
                value={compareB}
                onChange={(e) => setCompareB(Number(e.target.value))}
                className="min-h-[40px] rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3 text-[13px]"
              >
                {curricula.map((c) => (
                  <option key={c.curriculum_id} value={c.curriculum_id}>
                    B: {c.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {[cmpA, cmpB].map((entry, idx) => (
                <div
                  key={`${entry.curriculum.curriculum_id}-${idx}`}
                  className="rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-4 space-y-2"
                >
                  <div className="text-[14px] font-semibold text-[var(--ink-primary)]">
                    {idx === 0 ? "A: " : "B: "}
                    {entry.curriculum.name}
                  </div>
                  <div className="tabular-nums text-[24px] font-semibold text-[var(--series-me)]">
                    {entry.alignment.coveragePct.toFixed(1)}%
                  </div>
                  <div className="text-[12px] text-[var(--ink-secondary)]">
                    {locale === "th" ? "ครอบคลุม:" : "Covered:"} {entry.alignment.coveredCount}/{entry.alignment.totalMarketSkills} ·{" "}
                    {locale === "th" ? "ขาด:" : "Gaps:"} {entry.alignment.gaps.length} ·{" "}
                    Over-coverage: {entry.alignment.overCoverage.length}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </GlassCard>
      ) : null}
    </div>
  );
}

export function CurriculumDetailView({
  initialCurriculum,
  dimSkills,
  curriculumCoverageRef,
  publicSummary,
}: {
  initialCurriculum: CurriculumItem | null;
  dimSkills: DimSkill[];
  curriculumCoverageRef: CurriculumCoverageRefRow[];
  publicSummary: PublicSummary;
}) {
  const { locale } = useI18n();
  const router = useRouter();
  const [curriculum, setCurriculum] = useState<CurriculumItem | null>(initialCurriculum);
  const [courseName, setCourseName] = useState("การวิเคราะห์ข้อมูลทางธุรกิจ");
  const [csvText, setCsvText] = useState("");
  const [importStatus, setImportStatus] = useState<string | null>(null);
  const [topK, setTopK] = useState(30);

  const skillByKey = useMemo(
    () => new Map(dimSkills.map((s) => [s.skill_key, s])),
    [dimSkills]
  );

  const alignment = useMemo(() => {
    if (!curriculum) return null;
    return computeAlignment(curriculum, curriculumCoverageRef, dimSkills, topK);
  }, [curriculum, curriculumCoverageRef, dimSkills, topK]);

  useRegisterPageContext({
    page: "curriculum-detail",
    route: curriculum ? `/institution/curricula/${curriculum.curriculum_id}` : "/institution/curricula",
    title: curriculum?.name || "Curriculum Alignment",
    kpis: alignment
      ? [
          { label: "Coverage", value: Number(alignment.coveragePct.toFixed(1)), unit: "%" },
          { label: "Gaps Count", value: alignment.gaps.length },
          { label: "Over-coverage Count", value: alignment.overCoverage.length },
        ]
      : [],
    charts: alignment
      ? [
          {
            id: "curriculum-gaps",
            title: locale === "th" ? "ทักษะที่ตลาดขอสูงแต่หลักสูตรยังไม่มี (Gaps)" : "Top Curriculum Gaps",
            rows: alignment.gaps.slice(0, 15).map((g) => [
              locale === "th" ? g.skill_name_th : g.skill_canonical,
              Number(((g.weighted_share ?? 0) * 100).toFixed(1)),
            ]),
          },
          {
            id: "curriculum-over",
            title: locale === "th" ? "ทักษะที่สอนแต่ตลาดขอน้อย (Over-coverage)" : "Over-coverage Skills",
            rows: alignment.overCoverage.slice(0, 10).map((o) => [
              locale === "th" ? o.skill_name_th : o.skill_canonical,
              o.skill_group,
            ]),
          },
        ]
      : [],
    asOf: publicSummary.last_updated_at || undefined,
  });

  if (!curriculum || !alignment) {
    return (
      <EmptyState
        title={locale === "th" ? "ไม่พบหลักสูตรนี้" : "Curriculum not found"}
        action={
          <Link
            href="/institution/curricula"
            className="inline-flex min-h-[40px] items-center rounded-xl bg-[var(--series-me)] px-4 text-[13px] font-semibold text-white"
          >
            {locale === "th" ? "กลับสู่รายการหลักสูตร" : "Back to Curricula"}
          </Link>
        }
      />
    );
  }

  const handleAddSkill = async (sk: DimSkill) => {
    const course = courseName.trim() || "รายวิชาทั่วไป";
    const res = await fetch("/api/user-state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "add_curriculum_skill",
        curriculum_id: curriculum.curriculum_id,
        skill_key: sk.skill_key,
        course_name: course,
      }),
    });
    if (res.ok) {
      setCurriculum((prev) =>
        prev
          ? {
              ...prev,
              skills: [
                ...prev.skills,
                { curriculum_id: prev.curriculum_id, skill_key: sk.skill_key, course_name: course },
              ],
            }
          : prev
      );
      router.refresh();
    }
  };

  const handleRemoveSkill = async (skillKey: number, course: string) => {
    await fetch("/api/user-state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "remove_curriculum_skill",
        curriculum_id: curriculum.curriculum_id,
        skill_key: skillKey,
        course_name: course,
      }),
    });
    setCurriculum((prev) =>
      prev
        ? {
            ...prev,
            skills: prev.skills.filter(
              (s) => !(s.skill_key === skillKey && s.course_name === course)
            ),
          }
        : prev
    );
    router.refresh();
  };

  const handleCsvImport = async () => {
    const lines = csvText
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean);
    const parsed = lines
      .filter((l) => !l.toLowerCase().startsWith("course,"))
      .map((l) => {
        const [course, skill] = l.split(",").map((x) => x.trim());
        return { course, skill };
      })
      .filter((r) => r.course && r.skill);

    if (parsed.length === 0) return;

    const res = await fetch("/api/user-state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "import_curriculum_csv",
        curriculum_id: curriculum.curriculum_id,
        rows: parsed,
      }),
    });
    const data = (await res.json()) as { importedCount?: number };
    setImportStatus(
      locale === "th"
        ? `นำเข้าสำเร็จ ${data.importedCount ?? 0} คู่รายวิชา-ทักษะ`
        : `Imported ${data.importedCount ?? 0} course-skill mappings`
    );
    router.refresh();
    // Refresh local curriculum state cleanly
    window.location.reload();
  };

  const gaugeOption = {
    series: [
      {
        type: "gauge",
        startAngle: 200,
        endAngle: -20,
        min: 0,
        max: 100,
        splitNumber: 5,
        progress: { show: true, width: 16, itemStyle: { color: SKILLBI_PALETTE.me } },
        axisLine: { lineStyle: { width: 16, color: [[1, "#E8E8F0"]] } },
        axisTick: { show: false },
        splitLine: { length: 8 },
        axisLabel: { distance: 20, fontSize: 11 },
        detail: {
          valueAnimation: true,
          formatter: "{value}%",
          fontSize: 28,
          fontWeight: 600,
          color: SKILLBI_PALETTE.inkPrimary,
          offsetCenter: [0, "15%"],
        },
        data: [{ value: Number(alignment.coveragePct.toFixed(1)), name: "Coverage" }],
      },
    ],
  };

  // Course x Skill Heatmap
  const courses = Array.from(new Set(curriculum.skills.map((s) => s.course_name)));
  const taughtSkills = Array.from(new Set(curriculum.skills.map((s) => s.skill_key))).map(
    (k) => skillByKey.get(k)?.skill_canonical || String(k)
  );
  const heatPoints = curriculum.skills.map((entry) => {
    const xIdx = taughtSkills.indexOf(
      skillByKey.get(entry.skill_key)?.skill_canonical || String(entry.skill_key)
    );
    const yIdx = courses.indexOf(entry.course_name);
    return [xIdx, yIdx, 1];
  });

  const heatmapOption = {
    tooltip: { position: "top" },
    grid: { top: 20, right: 20, bottom: 56, left: 160 },
    xAxis: {
      type: "category",
      data: taughtSkills,
      axisLabel: { rotate: 25, fontSize: 11 },
    },
    yAxis: {
      type: "category",
      data: courses,
      axisLabel: { fontSize: 11 },
    },
    visualMap: {
      show: false,
      min: 0,
      max: 1,
      inRange: { color: ["#F1EFFD", SKILLBI_PALETTE.me] },
    },
    series: [
      {
        type: "heatmap",
        data: heatPoints,
        itemStyle: { borderColor: "#FFFFFF", borderWidth: 2 },
      },
    ],
  };

  const handleExportReport = () => {
    downloadAggregateCsv(
      `curriculum-alignment-${curriculum.curriculum_id}.csv`,
      [
        { key: "status", label: "Status" },
        { key: "skill", label: "Skill" },
        { key: "marketShare", label: "Market Share %" },
      ],
      [
        ...alignment.gaps.map((g) => ({
          status: "GAP (Missing in curriculum)",
          skill: g.skill_canonical,
          marketShare: `${((g.weighted_share ?? 0) * 100).toFixed(1)}%`,
        })),
        ...alignment.overCoverage.map((o) => ({
          status: "OVER-COVERAGE (Low market demand)",
          skill: o.skill_canonical,
          marketShare: "0%",
        })),
      ]
    );
  };

  return (
    <div className="space-y-6">
      <div className="no-print flex flex-wrap items-center justify-between gap-3">
        <Link
          href="/institution/curricula"
          className="inline-flex items-center gap-1.5 text-[13px] font-medium text-[var(--ink-secondary)] hover:text-[var(--series-me)]"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          <span>{locale === "th" ? "กลับสู่รายการหลักสูตร" : "Back to Curricula"}</span>
        </Link>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleExportReport}
            className="inline-flex min-h-[40px] items-center gap-1.5 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3.5 text-[13px] font-semibold text-[var(--ink-primary)]"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            <span>Export CSV</span>
          </button>
          <button
            type="button"
            onClick={() => window.print()}
            className="inline-flex min-h-[40px] items-center gap-1.5 rounded-xl bg-[var(--series-me)] px-3.5 text-[13px] font-semibold text-white"
          >
            <Printer className="h-4 w-4" aria-hidden="true" />
            <span>{locale === "th" ? "พิมพ์ / PDF รายงาน" : "Print / PDF Report"}</span>
          </button>
        </div>
      </div>

      <section className="glass p-6">
        <div className="relative z-10 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-[24px] font-semibold text-[var(--ink-primary)]">
              {curriculum.name}
            </h1>
            <p className="text-[13px] text-[var(--ink-secondary)]">
              {locale === "th" ? "กลุ่มอาชีพเป้าหมาย:" : "Target Cluster:"}{" "}
              <strong>{curriculum.target_occupation_cluster}</strong>
              {alignment.usedFallback
                ? locale === "th"
                  ? " (ใช้เกณฑ์ตลาดรวมเนื่องจากกลุ่มอาชีพนี้มี n < 5 ในตัวอย่าง)"
                  : " (using broader market benchmark as cluster n < 5)"
                : ""}
            </p>
          </div>
          <label className="no-print flex items-center gap-2 text-[12px]">
            <span>Top-K:</span>
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="min-h-[36px] rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-2.5"
            >
              <option value={15}>Top 15</option>
              <option value={30}>Top 30</option>
            </select>
          </label>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        {/* Coverage Gauge */}
        <div className="lg:col-span-5">
          <GlassCard
            title={locale === "th" ? "Curriculum Coverage Gauge" : "Coverage Gauge"}
            provenance={{ source: "JobThai", n: publicSummary.n_postings }}
          >
            <EChartBox option={gaugeOption} height={250} ariaLabel="Curriculum coverage gauge" />
            <div className="mt-2 text-center text-[13px] text-[var(--ink-secondary)]">
              {locale === "th"
                ? `ครอบคลุม ${alignment.coveredCount} จาก ${alignment.totalMarketSkills} ทักษะสำคัญ`
                : `Covers ${alignment.coveredCount} of ${alignment.totalMarketSkills} market skills`}
            </div>
          </GlassCard>
        </div>

        {/* Course -> Skill Mapping & CSV Import */}
        <section className="no-print glass p-5 lg:col-span-7">
          <div className="relative z-10 space-y-4">
            <h2 className="text-[16px] font-semibold text-[var(--ink-primary)]">
              {locale === "th" ? "เพิ่มรายวิชาและทักษะที่สอน" : "Map Course → Skill"}
            </h2>
            <label className="block text-[13px]">
              <span className="font-medium text-[var(--ink-secondary)]">
                {locale === "th" ? "ชื่อรายวิชา" : "Course Name"}
              </span>
              <input
                type="text"
                value={courseName}
                onChange={(e) => setCourseName(e.target.value)}
                className="mt-1 min-h-[40px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3"
              />
            </label>
            <SkillChipPicker
              skillsCatalog={dimSkills}
              selectedKeys={[]}
              onAdd={handleAddSkill}
              onRemove={() => {}}
              placeholder={
                locale === "th"
                  ? "เลือกทักษะเพื่อผูกเข้ากับรายวิชาด้านบน..."
                  : "Pick a skill to map to this course..."
              }
            />

            <div className="border-t border-[var(--border-hairline)] pt-3">
              <div className="mb-1 flex items-center gap-1.5 text-[13px] font-semibold text-[var(--ink-primary)]">
                <Upload className="h-4 w-4 text-[var(--series-me)]" aria-hidden="true" />
                <span>{locale === "th" ? "นำเข้าจาก CSV (course,skill)" : "CSV Import (course,skill)"}</span>
              </div>
              <textarea
                rows={3}
                value={csvText}
                onChange={(e) => setCsvText(e.target.value)}
                placeholder={"course,skill\nการจัดการฐานข้อมูล,SQL\nการวิเคราะห์ข้อมูล,Python"}
                className="w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-2.5 text-[12px]"
              />
              <div className="mt-2 flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={handleCsvImport}
                  className="min-h-[38px] rounded-xl bg-[var(--series-compare)] px-4 text-[12px] font-semibold text-white"
                >
                  {locale === "th" ? "นำเข้า CSV" : "Import CSV"}
                </button>
                {importStatus ? (
                  <span className="text-[12px] font-medium text-[var(--status-good)]">
                    {importStatus}
                  </span>
                ) : null}
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Course x Skill Heatmap */}
      {curriculum.skills.length > 0 ? (
        <GlassCard
          title={locale === "th" ? "แผนที่รายวิชา × ทักษะ (Course × Skill Matrix)" : "Course × Skill Heatmap"}
          icon={<FileSpreadsheet className="h-5 w-5" />}
          provenance={{ source: "Curriculum", n: curriculum.skills.length, isSample: false }}
        >
          <EChartBox option={heatmapOption} height={280} ariaLabel="Course by skill heatmap" />
          <div className="no-print mt-3 flex flex-wrap gap-1.5">
            {curriculum.skills.map((cs, i) => {
              const sk = skillByKey.get(cs.skill_key);
              return (
                <span
                  key={`${cs.course_name}-${cs.skill_key}-${i}`}
                  className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-2.5 py-1 text-[12px]"
                >
                  <span>
                    <strong>{cs.course_name}</strong>: {sk?.skill_canonical || cs.skill_key}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleRemoveSkill(cs.skill_key, cs.course_name)}
                    className="text-[var(--ink-muted)] hover:text-[#C92A2A]"
                  >
                    ×
                  </button>
                </span>
              );
            })}
          </div>
        </GlassCard>
      ) : (
        <LowDataState
          n={0}
          title={locale === "th" ? "หลักสูตรนี้ยังไม่มีรายวิชาที่จับคู่ทักษะ" : "No mapped courses yet"}
          description={locale === "th" ? "เพิ่มรายวิชาและทักษะด้านบนหรือนำเข้า CSV" : "Add course-skill mappings above or import CSV."}
          actionHref=""
        />
      )}

      {/* Gaps & Over-coverage Tables */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <GlassCard
          title={locale === "th" ? "Gaps: ทักษะที่ตลาดขอสูงแต่หลักสูตรยังไม่มี" : "Gaps (High Market Demand, Not Taught)"}
          provenance={{ source: "JobThai", n: publicSummary.n_postings }}
        >
          <DataTable
            columns={[
              { key: "skill", label: locale === "th" ? "ทักษะ" : "Skill" },
              { key: "group", label: locale === "th" ? "กลุ่ม" : "Group" },
              { key: "share", label: "% ตลาด", numeric: true },
            ]}
            data={alignment.gaps.map((g) => ({
              skill: locale === "th" ? g.skill_name_th : g.skill_canonical,
              group: g.skill_group,
              share: `${((g.weighted_share ?? 0) * 100).toFixed(1)}%`,
            }))}
          />
        </GlassCard>

        <GlassCard
          title={locale === "th" ? "Over-coverage: ทักษะที่สอนแต่ไม่อยู่ใน Top-K ตลาด" : "Over-coverage (Taught, Outside Market Top-K)"}
          provenance={{ source: "Curriculum", n: curriculum.skills.length, isSample: false }}
        >
          <DataTable
            columns={[
              { key: "skill", label: locale === "th" ? "ทักษะ" : "Skill" },
              { key: "group", label: locale === "th" ? "กลุ่ม" : "Group" },
              { key: "type", label: locale === "th" ? "ประเภท" : "Type" },
            ]}
            data={alignment.overCoverage.map((o) => ({
              skill: locale === "th" ? o.skill_name_th : o.skill_canonical,
              group: o.skill_group,
              type: o.skill_type,
            }))}
          />
        </GlassCard>
      </div>
    </div>
  );
}
