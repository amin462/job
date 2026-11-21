"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Award,
  BarChart3,
  Briefcase,
  Compass,
  Plus,
  Sparkles,
  Trash2,
} from "lucide-react";
import { EChartBox } from "@/components/charts/EChartBox";
import { useRegisterPageContext } from "@/components/chat/PageContextProvider";
import {
  EmptyState,
  GlassCard,
  KpiTile,
  LowDataState,
  RangeSlider,
  SourceLink,
  StatusChip,
} from "@/components/ui/DesignPrimitives";
import { SkillChipPicker } from "@/components/ui/SkillChipPicker";
import { SKILLBI_PALETTE } from "@/lib/echarts-theme";
import { useI18n } from "@/lib/i18n";
import type {
  DimLocation,
  DimOccupation,
  DimSkill,
  OccupationSkillProfileRow,
  PublicSummary,
  TopLinkRow,
  UserSession,
  UserSkill,
} from "@/types/marts";

const LEVEL_LABELS_TH: Record<number, string> = {
  1: "1 · พื้นฐาน",
  2: "2 · ใช้งานได้",
  3: "3 · ชำนาญ",
};

const LEVEL_LABELS_EN: Record<number, string> = {
  1: "1 · Basic",
  2: "2 · Proficient",
  3: "3 · Advanced",
};

export function MySkillsView({
  session,
  initialSkills,
  skillsCatalog,
  occupationSkillProfile,
  publicSummary,
}: {
  session: UserSession;
  initialSkills: UserSkill[];
  skillsCatalog: DimSkill[];
  occupationSkillProfile: OccupationSkillProfileRow[];
  publicSummary: PublicSummary;
}) {
  const { locale } = useI18n();
  const router = useRouter();
  const [skills, setSkills] = useState<UserSkill[]>(initialSkills);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const selectedKeys = useMemo(() => skills.map((s) => s.skill_key), [skills]);

  const suggestedSkills = useMemo(() => {
    const target = session.target_occupation_cluster || "Data & Analytics";
    const owned = new Set(selectedKeys);
    const fromOcc = occupationSkillProfile
      .filter((r) => r.occupation_cluster === target && !owned.has(r.skill_key))
      .slice(0, 8)
      .map((r) => skillsCatalog.find((s) => s.skill_key === r.skill_key))
      .filter((s): s is DimSkill => Boolean(s));
    if (fromOcc.length >= 4) return fromOcc;
    return skillsCatalog
      .filter((s) => !owned.has(s.skill_key))
      .slice(0, 6);
  }, [session.target_occupation_cluster, selectedKeys, occupationSkillProfile, skillsCatalog]);

  useRegisterPageContext({
    page: "my-skills",
    route: "/me/skills",
    title: locale === "th" ? "ทักษะของฉัน (My Skills)" : "My Skills",
    kpis: [
      { label: locale === "th" ? "จำนวนทักษะที่มี" : "My Skills Count", value: skills.length },
      {
        label: locale === "th" ? "ตำแหน่งเป้าหมาย" : "Target Occupation",
        value: session.target_occupation_cluster || "—",
      },
    ],
    tableTop: skills.map((s) => ({
      skill: locale === "th" ? s.skill_name_th || s.skill_canonical || "" : s.skill_canonical || "",
      level: s.level,
      group: s.skill_group || "",
    })),
    asOf: publicSummary.last_updated_at || undefined,
  });

  const handleUpsert = async (sk: DimSkill, level: 1 | 2 | 3) => {
    setSavingId(sk.skill_key);
    setToast(null);
    try {
      const res = await fetch("/api/user-state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "upsert_skill",
          skill_key: sk.skill_key,
          level,
        }),
      });
      if (!res.ok) throw new Error("Save failed");
      setSkills((prev) => {
        const idx = prev.findIndex((p) => p.skill_key === sk.skill_key);
        const item: UserSkill = {
          skill_key: sk.skill_key,
          skill_canonical: sk.skill_canonical,
          skill_slug: sk.skill_slug,
          skill_name_th: sk.skill_name_th,
          skill_type: sk.skill_type,
          skill_group: sk.skill_group,
          level,
        };
        if (idx >= 0) {
          const copy = [...prev];
          copy[idx] = item;
          return copy;
        }
        return [...prev, item];
      });
      router.refresh();
    } catch {
      setToast(locale === "th" ? "บันทึกไม่สำเร็จ กรุณาลองใหม่" : "Save failed. Please retry.");
    } finally {
      setSavingId(null);
    }
  };

  const handleRemove = async (skillKey: number) => {
    setSavingId(skillKey);
    try {
      await fetch("/api/user-state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "remove_skill", skill_key: skillKey }),
      });
      setSkills((prev) => prev.filter((s) => s.skill_key !== skillKey));
      router.refresh();
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[24px] font-semibold text-[var(--ink-primary)]">
            {locale === "th" ? "ทักษะของฉัน (My Skills)" : "My Skills"}
          </h1>
          <p className="text-[13px] text-[var(--ink-secondary)]">
            {locale === "th"
              ? "ค้นหาทักษะด้วยชื่อไทย/อังกฤษ หรือคำพ้อง แล้วระบุระดับความชำนาญ 1–3"
              : "Search by Thai/English aliases and set your proficiency level (1–3)"}
          </p>
        </div>

        <Link
          href="/me/gap"
          className="inline-flex min-h-[42px] items-center gap-2 rounded-xl bg-[var(--series-me)] px-4 text-[13px] font-semibold text-white"
        >
          <Compass className="h-4 w-4" aria-hidden="true" />
          <span>{locale === "th" ? "วิเคราะห์ Skill Gap →" : "Analyze Skill Gap →"}</span>
        </Link>
      </div>

      {toast ? (
        <div role="alert" className="rounded-xl border border-[#C92A2A]/30 bg-[#C92A2A]/10 px-4 py-2.5 text-[13px] text-[#9E1C1C]">
          {toast}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        <section className="glass p-5 lg:col-span-7">
          <div className="relative z-10 space-y-4">
            <h2 className="text-[16px] font-semibold text-[var(--ink-primary)]">
              {locale === "th" ? "เพิ่มหรือค้นหาทักษะ" : "Add Skills"}
            </h2>
            <SkillChipPicker
              skillsCatalog={skillsCatalog}
              selectedKeys={selectedKeys}
              onAdd={(sk) => handleUpsert(sk, 2)}
              onRemove={handleRemove}
            />

            {skills.length === 0 ? (
              <EmptyState
                title={locale === "th" ? "ยังไม่มีทักษะในโปรไฟล์" : "No skills added yet"}
                description={
                  locale === "th"
                    ? "พิมพ์ค้นหาด้านบน หรือคลิกเพิ่มจากทักษะแนะนำด้านขวา"
                    : "Search above or click suggested skills on the right."
                }
              />
            ) : (
              <div className="space-y-2.5 pt-2">
                {skills.map((sk) => {
                  const fullMeta = skillsCatalog.find((d) => d.skill_key === sk.skill_key);
                  return (
                    <div
                      key={sk.skill_key}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3.5 py-2.5"
                    >
                      <div className="min-w-0">
                        <Link
                          href={`/skills/${sk.skill_slug || fullMeta?.skill_slug || sk.skill_key}`}
                          className="text-[14px] font-semibold text-[var(--ink-primary)] hover:text-[var(--series-me)]"
                        >
                          {locale === "th"
                            ? sk.skill_name_th || fullMeta?.skill_name_th || sk.skill_canonical
                            : sk.skill_canonical || fullMeta?.skill_canonical}
                        </Link>
                        <div className="text-[12px] text-[var(--ink-muted)]">
                          {sk.skill_group || fullMeta?.skill_group} · {sk.skill_type || fullMeta?.skill_type}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <div className="inline-flex rounded-lg border border-[var(--border-hairline)] bg-[var(--surface-sunken)] p-0.5">
                          {([1, 2, 3] as const).map((lv) => (
                            <button
                              key={lv}
                              type="button"
                              disabled={savingId === sk.skill_key}
                              onClick={() =>
                                fullMeta && handleUpsert(fullMeta, lv)
                              }
                              className={`min-h-[32px] rounded-md px-2.5 text-[11px] font-medium ${
                                sk.level === lv
                                  ? "bg-[var(--series-me)] text-white"
                                  : "text-[var(--ink-secondary)] hover:text-[var(--ink-primary)]"
                              }`}
                            >
                              {locale === "th" ? LEVEL_LABELS_TH[lv] : LEVEL_LABELS_EN[lv]}
                            </button>
                          ))}
                        </div>
                        <button
                          type="button"
                          onClick={() => handleRemove(sk.skill_key)}
                          aria-label={`Remove ${sk.skill_canonical}`}
                          className="flex h-9 w-9 items-center justify-center rounded-lg text-[var(--ink-muted)] hover:bg-[#C92A2A]/10 hover:text-[#C92A2A]"
                        >
                          <Trash2 className="h-4 w-4" aria-hidden="true" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </section>

        <section className="glass p-5 lg:col-span-5">
          <div className="relative z-10 space-y-3">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-[var(--series-me)]" aria-hidden="true" />
              <h2 className="text-[16px] font-semibold text-[var(--ink-primary)]">
                {locale === "th"
                  ? `ทักษะแนะนำสำหรับ ${session.target_occupation_cluster || "ตำแหน่งเป้าหมาย"}`
                  : `Suggested for ${session.target_occupation_cluster || "Target Role"}`}
              </h2>
            </div>
            <p className="text-[12px] text-[var(--ink-muted)]">
              {locale === "th"
                ? "อ้างอิงจากโปรไฟล์ทักษะที่ตลาดขอในกลุ่มอาชีพเป้าหมายของคุณ"
                : "Based on market demand profiles for your target occupation cluster"}
            </p>
            <div className="space-y-2">
              {suggestedSkills.map((sk) => (
                <button
                  key={sk.skill_key}
                  type="button"
                  onClick={() => handleUpsert(sk, 2)}
                  className="flex min-h-[42px] w-full items-center justify-between gap-2 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3.5 py-2 text-left hover:border-[var(--series-me)] hover:bg-[var(--tint-me)]/40"
                >
                  <div>
                    <div className="text-[13px] font-semibold text-[var(--ink-primary)]">
                      {locale === "th" ? sk.skill_name_th : sk.skill_canonical}
                    </div>
                    <div className="text-[11px] text-[var(--ink-muted)]">
                      {sk.skill_canonical} · {sk.skill_group}
                    </div>
                  </div>
                  <Plus className="h-4 w-4 shrink-0 text-[var(--series-me)]" aria-hidden="true" />
                </button>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

export function SkillGapView({
  session,
  userSkills,
  dimOccupations,
  dimLocations,
  occupationSkillProfile,
  topLinks,
  publicSummary,
}: {
  session: UserSession;
  userSkills: UserSkill[];
  dimOccupations: DimOccupation[];
  dimLocations: DimLocation[];
  occupationSkillProfile: OccupationSkillProfileRow[];
  topLinks: TopLinkRow[];
  publicSummary: PublicSummary;
}) {
  const { locale } = useI18n();
  const router = useRouter();

  // Default to an occupation that has n >= 5 skills if user's target is small in 126-posting spike
  const availableOccs = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of occupationSkillProfile) {
      if (!r.is_suppressed) {
        counts.set(r.occupation_cluster, (counts.get(r.occupation_cluster) ?? 0) + 1);
      }
    }
    return dimOccupations.map((o) => ({
      ...o,
      hasData: (counts.get(o.occupation_cluster) ?? 0) > 0,
    }));
  }, [dimOccupations, occupationSkillProfile]);

  const initialOcc = useMemo(() => {
    const userTarget = session.target_occupation_cluster;
    const targetHasData = availableOccs.find(
      (o) => o.occupation_cluster === userTarget && o.hasData
    );
    if (targetHasData) return targetHasData.occupation_cluster;
    return (
      availableOccs.find((o) => o.hasData)?.occupation_cluster ||
      userTarget ||
      dimOccupations[0]?.occupation_cluster ||
      ""
    );
  }, [session.target_occupation_cluster, availableOccs, dimOccupations]);

  const [targetOcc, setTargetOcc] = useState(initialOcc);
  const [province, setProvince] = useState(session.province_th || "ALL");
  const [thresholdPct, setThresholdPct] = useState(20);
  const [viewportWidth, setViewportWidth] = useState(1200);

  useEffect(() => {
    const update = () => setViewportWidth(window.innerWidth);
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  const userSkillMap = useMemo(
    () => new Map(userSkills.map((s) => [s.skill_key, s])),
    [userSkills]
  );

  // Top 30 non-suppressed skills in target occupation
  const targetMarketSkills = useMemo(
    () =>
      occupationSkillProfile
        .filter(
          (r) =>
            r.occupation_cluster === targetOcc &&
            !r.is_suppressed &&
            r.weighted_share !== null
        )
        .sort((a, b) => a.rank_in_occupation - b.rank_in_occupation)
        .slice(0, 30),
    [occupationSkillProfile, targetOcc]
  );

  const thresholdDecimal = thresholdPct / 100;

  const importantSkills = useMemo(
    () =>
      targetMarketSkills.filter(
        (r) => (r.weighted_share ?? r.raw_share ?? 0) >= thresholdDecimal
      ),
    [targetMarketSkills, thresholdDecimal]
  );

  // Weighted coverage formula (FRONTEND_SPEC §3.7)
  const coverageStats = useMemo(() => {
    const basis = targetMarketSkills;
    const totalW = basis.reduce((acc, r) => acc + (r.weighted_share ?? 0), 0);
    if (totalW === 0) return { coveragePct: 0, matchedCount: 0, missing: [] as OccupationSkillProfileRow[] };
    const matchedW = basis.reduce(
      (acc, r) => (userSkillMap.has(r.skill_key) ? acc + (r.weighted_share ?? 0) : acc),
      0
    );
    const missing = importantSkills.filter((r) => !userSkillMap.has(r.skill_key));
    const matchedCount = basis.filter((r) => userSkillMap.has(r.skill_key)).length;
    return {
      coveragePct: (matchedW / totalW) * 100,
      matchedCount,
      missing,
    };
  }, [targetMarketSkills, importantSkills, userSkillMap]);

  // Best-matching occupations across all clusters with n >= 5
  const bestMatchingOccs = useMemo(() => {
    const clusters = Array.from(
      new Set(
        occupationSkillProfile
          .filter((r) => !r.is_suppressed && r.weighted_share !== null)
          .map((r) => r.occupation_cluster)
      )
    );
    return clusters
      .map((cluster) => {
        const rows = occupationSkillProfile
          .filter(
            (r) =>
              r.occupation_cluster === cluster &&
              !r.is_suppressed &&
              r.weighted_share !== null
          )
          .slice(0, 30);
        const totalW = rows.reduce((a, b) => a + (b.weighted_share ?? 0), 0);
        const matchedW = rows.reduce(
          (a, b) => (userSkillMap.has(b.skill_key) ? a + (b.weighted_share ?? 0) : a),
          0
        );
        const matchPct = totalW > 0 ? (matchedW / totalW) * 100 : 0;
        const link =
          topLinks.find(
            (l) =>
              l.occupation_cluster === cluster &&
              (province === "ALL" || l.province_th === province)
          ) || topLinks.find((l) => l.occupation_cluster === cluster);
        return {
          cluster,
          slug: rows[0]?.occupation_slug || "",
          nameTh: rows[0]?.occupation_name_th || cluster,
          nOccPostings: rows[0]?.n_occ_postings ?? 0,
          matchPct,
          link,
        };
      })
      .sort((a, b) => b.matchPct - a.matchPct)
      .slice(0, 5);
  }, [occupationSkillProfile, userSkillMap, topLinks, province]);

  const radarAxes = useMemo(() => targetMarketSkills.slice(0, 8), [targetMarketSkills]);

  useRegisterPageContext({
    page: "skill-gap",
    route: "/me/gap",
    title: locale === "th" ? "วิเคราะห์ Skill Gap" : "Skill Gap Analysis",
    filters: { targetOcc, province, thresholdPct },
    kpis: [
      { label: locale === "th" ? "ความครอบคลุมทักษะ (Coverage)" : "Coverage", value: Number(coverageStats.coveragePct.toFixed(1)), unit: "%" },
      { label: locale === "th" ? "ทักษะที่ขาด" : "Missing Important Skills", value: coverageStats.missing.length },
      { label: locale === "th" ? "ทักษะของฉัน" : "My Skills", value: userSkills.length },
    ],
    charts: [
      {
        id: "missing-skills",
        title: locale === "th" ? "ทักษะที่ควรเพิ่ม (Missing Skills)" : "Top Missing Skills",
        rows: coverageStats.missing.slice(0, 15).map((m) => [
          locale === "th" ? m.skill_name_th : m.skill_canonical,
          Number(((m.weighted_share ?? 0) * 100).toFixed(1)),
          m.n_postings,
        ]),
      },
      {
        id: "radar-vs-market",
        title: locale === "th" ? "Radar ทักษะของฉัน vs ตลาด" : "My Skills vs Market Radar",
        rows: radarAxes.map((ax) => [
          locale === "th" ? ax.skill_name_th : ax.skill_canonical,
          Math.round(((userSkillMap.get(ax.skill_key)?.level ?? 0) / 3) * 100),
          Number(((ax.weighted_share ?? 0) * 100).toFixed(1)),
        ]),
      },
    ],
    asOf: publicSummary.last_updated_at || undefined,
  });

  if (userSkills.length === 0) {
    return (
      <EmptyState
        title={locale === "th" ? "คุณยังไม่ได้เลือกทักษะที่มี" : "You have no skills yet"}
        description={
          locale === "th"
            ? "ไปที่หน้า 'ทักษะของฉัน' เพื่อเพิ่มทักษะก่อนวิเคราะห์ Skill Gap"
            : "Add your current skills in My Skills before running Skill Gap analysis."
        }
        action={
          <Link
            href="/me/skills"
            className="inline-flex min-h-[42px] items-center rounded-xl bg-[var(--series-me)] px-5 text-[13px] font-semibold text-white"
          >
            {locale === "th" ? "ไปเพิ่มทักษะของฉัน →" : "Go to My Skills →"}
          </Link>
        }
      />
    );
  }

  const radarOption = {
    tooltip: {},
    legend: {
      bottom: 0,
      data: [locale === "th" ? "ทักษะของฉัน" : "My Skills", locale === "th" ? "ความต้องการตลาด" : "Market Demand"],
    },
    radar: {
      indicator: radarAxes.map((ax) => ({
        name:
          (locale === "th" ? ax.skill_name_th : ax.skill_canonical).slice(0, 16),
        max: 100,
      })),
      radius: "62%",
    },
    series: [
      {
        type: "radar",
        data: [
          {
            value: radarAxes.map((ax) =>
              Math.round(((userSkillMap.get(ax.skill_key)?.level ?? 0) / 3) * 100)
            ),
            name: locale === "th" ? "ทักษะของฉัน" : "My Skills",
            itemStyle: { color: SKILLBI_PALETTE.me },
            areaStyle: { color: "rgba(108, 92, 231, 0.22)" },
          },
          {
            value: radarAxes.map((ax) =>
              Number(((ax.weighted_share ?? 0) * 100).toFixed(1))
            ),
            name: locale === "th" ? "ความต้องการตลาด" : "Market Demand",
            itemStyle: { color: SKILLBI_PALETTE.market },
            areaStyle: { color: "rgba(224, 98, 63, 0.16)" },
          },
        ],
      },
    ],
  };

  const missingOption = {
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { top: 8, right: 44, bottom: 24, left: 165 },
    xAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
    yAxis: {
      type: "category",
      data: [...coverageStats.missing]
        .slice(0, 10)
        .reverse()
        .map((m) => {
          const lbl = locale === "th" ? m.skill_name_th : m.skill_canonical;
          return lbl.length > 24 ? lbl.slice(0, 22) + "…" : lbl;
        }),
    },
    series: [
      {
        type: "bar",
        data: [...coverageStats.missing]
          .slice(0, 10)
          .reverse()
          .map((m) => ({
            value: Number(((m.weighted_share ?? 0) * 100).toFixed(1)),
            slug: m.skill_slug,
          })),
        itemStyle: { color: SKILLBI_PALETTE.market, borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: "right", formatter: "{c}%", fontSize: 11 },
      },
    ],
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[24px] font-semibold text-[var(--ink-primary)]">
            {locale === "th" ? "วิเคราะห์ Skill Gap & ตำแหน่งที่ตรง" : "Skill Gap & Matching Roles"}
          </h1>
          <p className="text-[13px] text-[var(--ink-secondary)]">
            {locale === "th"
              ? "คำนวณ Weighted Coverage จากทักษะสำคัญของตำแหน่งเป้าหมาย"
              : "Weighted coverage against top market skills for your target occupation"}
          </p>
        </div>

        <Link
          href="/me/skills"
          className="inline-flex min-h-[40px] items-center gap-2 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-4 text-[13px] font-semibold text-[var(--series-me)]"
        >
          <Award className="h-4 w-4" aria-hidden="true" />
          <span>{locale === "th" ? "จัดการทักษะของฉัน" : "Edit My Skills"}</span>
        </Link>
      </div>

      {/* Controls & KPIs */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <section className="glass p-5 lg:col-span-5">
          <div className="relative z-10 space-y-3.5">
            <label className="block text-[13px]">
              <span className="font-medium text-[var(--ink-secondary)]">
                {locale === "th" ? "กลุ่มอาชีพเป้าหมาย" : "Target Occupation"}
              </span>
              <select
                value={targetOcc}
                onChange={(e) => setTargetOcc(e.target.value)}
                className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3"
              >
                {availableOccs.map((o) => (
                  <option key={o.occupation_slug} value={o.occupation_cluster}>
                    {locale === "th" ? o.occupation_name_th : o.occupation_cluster}
                    {!o.hasData ? " (n < 5)" : ""}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-[13px]">
              <span className="font-medium text-[var(--ink-secondary)]">
                {locale === "th" ? "จังหวัด (สำหรับลิงก์ตำแหน่ง)" : "Province (optional)"}
              </span>
              <select
                value={province}
                onChange={(e) => setProvince(e.target.value)}
                className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3"
              >
                <option value="ALL">{locale === "th" ? "ทั้งประเทศ" : "All Thailand"}</option>
                {dimLocations.map((l) => (
                  <option key={l.location_key} value={l.province_th}>
                    {locale === "th" ? l.province_th : l.province_en}
                  </option>
                ))}
              </select>
            </label>

            <RangeSlider
              label={locale === "th" ? "เกณฑ์ทักษะสำคัญ (≥ % ประกาศ)" : "Importance Threshold"}
              min={5}
              max={60}
              step={5}
              value={thresholdPct}
              onChange={setThresholdPct}
              formatValue={(v) => `${v}%`}
            />
          </div>
        </section>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:col-span-7">
          <KpiTile
            label={locale === "th" ? "Weighted Coverage" : "Weighted Coverage"}
            value={
              targetMarketSkills.length > 0
                ? `${coverageStats.coveragePct.toFixed(1)}%`
                : "n < 5"
            }
            hint={`${coverageStats.matchedCount}/${targetMarketSkills.length} ${
              locale === "th" ? "ทักษะตรงกัน" : "matched"
            }`}
            accent="me"
          />
          <KpiTile
            label={locale === "th" ? "ทักษะที่ขาด (ตามเกณฑ์)" : "Missing Skills"}
            value={coverageStats.missing.length}
            hint={`≥ ${thresholdPct}% ${locale === "th" ? "ของประกาศ" : "of postings"}`}
            accent="market"
          />
          <KpiTile
            label={locale === "th" ? "ทักษะของฉัน" : "My Skills"}
            value={userSkills.length}
            accent="compare"
          />
        </div>
      </div>

      {targetMarketSkills.length === 0 ? (
        <LowDataState
          n={0}
          description={
            locale === "th"
              ? `กลุ่มอาชีพ "${targetOcc}" มีประกาศในตัวอย่างน้อยกว่า 5 รายการ (n < 5) ลองเลือกกลุ่มอาชีพที่มี n ≥ 5 ด้านบน`
              : `Target cluster "${targetOcc}" has fewer than 5 postings in the current sample. Select another occupation cluster above.`
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
          <div className="lg:col-span-6">
            <GlassCard
              title={locale === "th" ? "Radar: ทักษะของฉัน vs ตลาด (≤ 8 แกน)" : "My Skills vs Market Radar"}
              icon={<Compass className="h-5 w-5" />}
              provenance={{
                source: "JobThai",
                n: targetMarketSkills[0]?.n_occ_postings ?? 0,
                updatedAt: publicSummary.last_updated_at,
              }}
              tableData={{
                columns: [
                  { key: "skill", label: locale === "th" ? "ทักษะ" : "Skill" },
                  { key: "me", label: locale === "th" ? "ฉัน (%)" : "Me (%)", numeric: true },
                  { key: "market", label: locale === "th" ? "ตลาด (%)" : "Market (%)", numeric: true },
                ],
                rows: radarAxes.map((ax) => ({
                  skill: locale === "th" ? ax.skill_name_th : ax.skill_canonical,
                  me: Math.round(((userSkillMap.get(ax.skill_key)?.level ?? 0) / 3) * 100),
                  market: Number(((ax.weighted_share ?? 0) * 100).toFixed(1)),
                })),
              }}
            >
              {radarAxes.length < 3 || viewportWidth < 420 ? (
                <div className="space-y-2">
                  {radarAxes.map((ax) => {
                    const myPct = Math.round(((userSkillMap.get(ax.skill_key)?.level ?? 0) / 3) * 100);
                    const mktPct = Number(((ax.weighted_share ?? 0) * 100).toFixed(1));
                    return (
                      <div key={ax.skill_key} className="rounded-lg border border-[var(--border-hairline)] p-2.5 text-[12px]">
                        <div className="font-semibold">{locale === "th" ? ax.skill_name_th : ax.skill_canonical}</div>
                        <div className="mt-1 flex justify-between text-[var(--ink-secondary)]">
                          <span>Me: {myPct}%</span>
                          <span>Market: {mktPct}%</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <EChartBox option={radarOption} height={320} ariaLabel="My skills vs market radar" />
              )}
            </GlassCard>
          </div>

          <div className="lg:col-span-6">
            <GlassCard
              title={locale === "th" ? "ทักษะที่ควรเพิ่ม (เรียงตามความสำคัญ)" : "Missing Skills to Add"}
              subtitle={locale === "th" ? "คลิกแท่งเพื่อดูรายละเอียดและแนวโน้มทักษะ" : "Click bar to view skill detail"}
              icon={<BarChart3 className="h-5 w-5" />}
              provenance={{ source: "JobThai", n: targetMarketSkills[0]?.n_occ_postings ?? 0 }}
              tableData={{
                columns: [
                  { key: "skill", label: locale === "th" ? "ทักษะที่ขาด" : "Missing Skill" },
                  { key: "share", label: "% ตลาด", numeric: true },
                  { key: "n", label: "n", numeric: true },
                ],
                rows: coverageStats.missing.map((m) => ({
                  skill: locale === "th" ? m.skill_name_th : m.skill_canonical,
                  share: `${((m.weighted_share ?? 0) * 100).toFixed(1)}%`,
                  n: m.n_postings,
                })),
              }}
            >
              {coverageStats.missing.length === 0 ? (
                <div className="py-10 text-center text-[14px] font-medium text-[var(--status-good)]">
                  {locale === "th"
                    ? "ทักษะของคุณครอบคลุมทักษะสำคัญตามเกณฑ์ที่เลือกครบทั้งหมดแล้ว!"
                    : "You cover all skills above the selected threshold!"}
                </div>
              ) : (
                <EChartBox
                  option={missingOption}
                  height={320}
                  ariaLabel="Missing skills ranked bars"
                  onItemClick={(params: unknown) => {
                    const p = params as { data?: { slug?: string } };
                    if (p?.data?.slug) router.push(`/skills/${p.data.slug}`);
                  }}
                />
              )}
            </GlassCard>
          </div>
        </div>
      )}

      {/* Best Matching Occupations + SourceLink */}
      <GlassCard
        title={locale === "th" ? "กลุ่มอาชีพที่ตรงกับทักษะของคุณ + ลิงก์ต้นฉบับ" : "Best-Matching Occupations & Source Links"}
        icon={<Briefcase className="h-5 w-5" />}
        provenance={{ source: "JobThai", n: publicSummary.n_postings }}
      >
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {bestMatchingOccs.map((item) => (
            <div
              key={item.cluster}
              className="flex flex-col justify-between gap-2.5 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-4"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <Link
                    href={`/occupations/${item.slug}`}
                    className="text-[15px] font-semibold text-[var(--ink-primary)] hover:text-[var(--series-me)]"
                  >
                    {locale === "th" ? item.nameTh : item.cluster}
                  </Link>
                  <div className="text-[12px] text-[var(--ink-muted)]">
                    {item.cluster} · n = {item.nOccPostings}
                  </div>
                </div>
                <StatusChip variant="good" label={`Match ${item.matchPct.toFixed(0)}%`} />
              </div>
              {item.link ? (
                <SourceLink
                  url={item.link.source_url}
                  titleShort={item.link.title_short}
                  sourceName={item.link.source_name}
                  datePosted={item.link.date_posted}
                />
              ) : null}
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  );
}
