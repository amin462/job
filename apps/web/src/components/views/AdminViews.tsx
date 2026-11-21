"use client";

import React, { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Activity,
  Check,
  Database,
  Layers,
  MessageSquare,
  ShieldAlert,
  ShieldCheck,
  X,
} from "lucide-react";
import { EChartBox } from "@/components/charts/EChartBox";
import { useRegisterPageContext } from "@/components/chat/PageContextProvider";
import {
  GlassCard,
  KpiTile,
  StatusChip,
} from "@/components/ui/DesignPrimitives";
import { DataTable } from "@/components/ui/DataTable";
import { ALLOWED_SOURCES, FORBIDDEN_SOURCES } from "@/lib/compliance";
import { SKILLBI_PALETTE } from "@/lib/echarts-theme";
import { formatDateByLocale, useI18n } from "@/lib/i18n";
import type {
  DimSkill,
  DqSummaryRow,
  PendingAliasRow,
  PipelineStatusRow,
  PostingVolumeDailyRow,
  PublicSummary,
} from "@/types/marts";

function statusToVariant(status: string): "good" | "warning" | "critical" | "pending" | "neutral" {
  if (status === "done") return "good";
  if (status.startsWith("stopped_")) return "critical";
  if (status === "running") return "pending";
  if (status === "error") return "critical";
  return "neutral";
}

export function AdminPipelineView({
  pipelineStatus,
  postingVolumeDaily,
  chatLogs,
  publicSummary,
}: {
  pipelineStatus: PipelineStatusRow[];
  postingVolumeDaily: PostingVolumeDailyRow[];
  chatLogs: Array<{ chat_id: number; page: string; question: string; answered: boolean; created_at: string }>;
  publicSummary: PublicSummary;
}) {
  const { locale } = useI18n();
  const nationalDaily = useMemo(
    () =>
      postingVolumeDaily
        .filter((d) => d.scope_level === "national")
        .sort((a, b) => a.full_date.localeCompare(b.full_date)),
    [postingVolumeDaily]
  );

  const blockedRuns = pipelineStatus.filter(
    (r) =>
      r.is_blocked_flag ||
      r.status === "stopped_403" ||
      r.status === "stopped_429" ||
      r.status === "stopped_captcha"
  );

  useRegisterPageContext({
    page: "admin-pipeline",
    route: "/admin/pipeline",
    title: "Admin: Scrape Pipeline",
    kpis: [
      { label: "Total Runs", value: pipelineStatus.length },
      { label: "Blocked Stops (403/429/CAPTCHA)", value: blockedRuns.length },
      { label: "Recent Chat Questions", value: chatLogs.length },
    ],
    tableTop: pipelineStatus.slice(0, 10).map((r) => ({
      runId: r.scrape_run_id,
      source: r.source,
      status: r.status,
      fetched: r.n_fetched,
      failed: r.n_failed,
    })),
    asOf: publicSummary.last_updated_at || undefined,
  });

  const barOption = {
    tooltip: { trigger: "axis" },
    grid: { top: 18, right: 20, bottom: 28, left: 48 },
    xAxis: {
      type: "category",
      data: nationalDaily.map((d) => formatDateByLocale(d.full_date, locale)),
    },
    yAxis: { type: "value" },
    series: [
      {
        name: "Postings",
        type: "bar",
        data: nationalDaily.map((d) => d.n_postings),
        itemStyle: { color: SKILLBI_PALETTE.me },
      },
    ],
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[24px] font-semibold text-[var(--ink-primary)]">
            Admin: Scrape Pipeline & Chat Insights
          </h1>
          <p className="text-[13px] text-[var(--ink-secondary)]">
            ติดตามสถานะรอบ scrape (หยุดทันทีเมื่อเจอ 403/429/CAPTCHA) และคำถามยอดนิยมจากแชท
          </p>
        </div>
        <StatusChip
          variant={blockedRuns.length > 0 ? "critical" : "good"}
          label={
            blockedRuns.length > 0
              ? `พบ stopped_403/429/captcha (${blockedRuns.length})`
              : "ไม่พบการถูกบล็อก"
          }
        />
      </div>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiTile label="รอบ Scrape ทั้งหมด" value={pipelineStatus.length} icon={<Activity className="h-4 w-4" />} />
        <KpiTile label="รอบที่หยุดเพราะ 403/429/CAPTCHA" value={blockedRuns.length} accent="market" icon={<ShieldAlert className="h-4 w-4" />} />
        <KpiTile label="คำถามแชทล่าสุด" value={chatLogs.length} accent="compare" icon={<MessageSquare className="h-4 w-4" />} />
      </section>

      <GlassCard title="ประวัติรอบ Scrape (staging.scrape_run)" provenance={{ source: "Admin Mart", n: pipelineStatus.length, isSample: false }}>
        <DataTable
          columns={[
            { key: "scrape_run_id", label: "Run ID", numeric: true },
            { key: "source", label: "Source" },
            { key: "scope", label: "Scope" },
            {
              key: "status",
              label: "Status",
              render: (row) => (
                <StatusChip
                  variant={statusToVariant(String(row.status))}
                  label={String(row.status)}
                />
              ),
            },
            { key: "n_discovered", label: "Discovered", numeric: true },
            { key: "n_fetched", label: "Fetched", numeric: true },
            { key: "n_failed", label: "Failed", numeric: true },
          ]}
          data={pipelineStatus.map((r) => ({
            ...r,
            scope: r.scope || "—",
          }))}
        />
      </GlassCard>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        <div className="lg:col-span-6">
          <GlassCard title="ปริมาณประกาศใหม่รายวัน" provenance={{ source: "JobThai", n: publicSummary.n_postings }}>
            <EChartBox option={barOption} height={240} ariaLabel="Daily postings bar chart" />
          </GlassCard>
        </div>
        <div className="lg:col-span-6">
          <GlassCard title="คำถามยอดนิยมจากแชท (app_chat_log)" provenance={{ source: "Chat Log", n: chatLogs.length, isSample: false }}>
            <DataTable
              columns={[
                { key: "page", label: "Page" },
                { key: "question", label: "Question" },
                { key: "answered", label: "Answered" },
              ]}
              data={chatLogs.slice(0, 15).map((c) => ({
                page: c.page,
                question: c.question,
                answered: c.answered ? "Yes" : "No",
              }))}
            />
          </GlassCard>
        </div>
      </div>
    </div>
  );
}

export function AdminQualityView({
  dqSummary,
  publicSummary,
}: {
  dqSummary: DqSummaryRow[];
  publicSummary: PublicSummary;
}) {
  const passCount = dqSummary.filter((d) => d.pass).length;
  const failCount = dqSummary.length - passCount;

  useRegisterPageContext({
    page: "admin-quality",
    route: "/admin/quality",
    title: "Admin: Data Quality Checks",
    kpis: [
      { label: "Total DQ Checks", value: dqSummary.length },
      { label: "Passed", value: passCount },
      { label: "Failed", value: failCount },
      { label: "Skill Mapping Rate", value: publicSummary.pct_with_skills ?? 0, unit: "%" },
    ],
    tableTop: dqSummary.map((d) => ({
      dimension: d.dimension,
      check: d.check_name,
      pass: d.pass,
      fail_rate: d.fail_rate,
    })),
    asOf: publicSummary.last_updated_at || undefined,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[24px] font-semibold text-[var(--ink-primary)]">
          Admin: Data Quality (8 มิติ)
        </h1>
        <p className="text-[13px] text-[var(--ink-secondary)]">
          Completeness, Validity, Uniqueness, Consistency, Freshness, Taxonomy, Compliance, Sampling
        </p>
      </div>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <KpiTile label="ผ่านเกณฑ์ (Pass)" value={`${passCount}/${dqSummary.length}`} icon={<ShieldCheck className="h-4 w-4" />} />
        <KpiTile label="ไม่ผ่านเกณฑ์ (Fail)" value={failCount} accent="market" icon={<ShieldAlert className="h-4 w-4" />} />
        <KpiTile label="% ประกาศที่มีทักษะ" value={`${publicSummary.pct_with_skills ?? 0}%`} accent="compare" />
        <KpiTile label="Gold Set Evaluation" value="200 Postings" hint="eval/evaluate_skills.py + Cohen's κ" accent="context" />
      </section>

      <GlassCard title="ผลตรวจสอบคุณภาพข้อมูลราย Check (mart.dq_summary)" provenance={{ source: "Admin DQ", n: dqSummary.length, isSample: false }}>
        <DataTable
          columns={[
            { key: "dimension", label: "Dimension" },
            { key: "check_name", label: "Check" },
            {
              key: "pass",
              label: "Result",
              render: (row) => (
                <StatusChip
                  variant={row.pass ? "good" : "critical"}
                  label={row.pass ? "PASS" : "FAIL"}
                />
              ),
            },
            { key: "n_total", label: "Total", numeric: true },
            { key: "n_fail", label: "Fail", numeric: true },
            { key: "fail_rate", label: "Fail %", numeric: true },
            { key: "details", label: "Details" },
          ]}
          data={dqSummary.map((d) => ({
            ...d,
            details: d.details || "—",
          }))}
        />
      </GlassCard>
    </div>
  );
}

export function AdminTaxonomyView({
  initialPendingAliases,
  dimSkills,
  publicSummary,
}: {
  initialPendingAliases: PendingAliasRow[];
  dimSkills: DimSkill[];
  publicSummary: PublicSummary;
}) {
  const router = useRouter();
  const [queue, setQueue] = useState<PendingAliasRow[]>(initialPendingAliases);
  const [remapTargets, setRemapTargets] = useState<Record<number, number>>({});
  const [busyId, setBusyId] = useState<number | null>(null);

  const pendingOnly = useMemo(
    () => queue.filter((q) => q.status === "pending"),
    [queue]
  );

  useRegisterPageContext({
    page: "admin-taxonomy",
    route: "/admin/taxonomy",
    title: "Admin: Taxonomy & Alias Review Queue",
    kpis: [
      { label: "Pending Aliases", value: pendingOnly.length },
      { label: "Canonical Skills", value: dimSkills.length },
    ],
    tableTop: pendingOnly.slice(0, 15).map((q) => ({
      alias: q.pending_alias,
      freq: q.freq,
      suggested: q.suggested_skill_canonical || "—",
      similarity: q.similarity_score ?? 0,
    })),
    asOf: publicSummary.last_updated_at || undefined,
    dataNotes: ["คำแนะนำทักษะคำนวณด้วย pg_trgm similarity >= 0.4 เท่านั้น ไม่ใช้ AI/LLM (D7, D18)"],
  });

  const handleReview = async (
    suggestionId: number,
    action: "approve" | "reject" | "map",
    targetSkillKey?: number
  ) => {
    setBusyId(suggestionId);
    try {
      const res = await fetch("/api/user-state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "admin_review_alias",
          suggestion_id: suggestionId,
          review_action: action,
          target_skill_key: targetSkillKey,
        }),
      });
      if (res.ok) {
        setQueue((prev) =>
          prev.map((q) =>
            q.suggestion_id === suggestionId
              ? {
                  ...q,
                  status: action === "reject" ? "rejected" : "approved",
                }
              : q
          )
        );
        router.refresh();
      }
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[24px] font-semibold text-[var(--ink-primary)]">
            Admin: Taxonomy & Pending Alias Queue
          </h1>
          <p className="text-[13px] text-[var(--ink-secondary)]">
            เสนอคู่ทักษะด้วย <strong>pg_trgm similarity ≥ 0.4 (Rule-based only · ไม่ใช้ AI/LLM)</strong>
          </p>
        </div>
        <StatusChip variant="pending" label="Rule-based pg_trgm (No AI/LLM)" />
      </div>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiTile label="Alias รอตรวจ (Pending)" value={pendingOnly.length} icon={<Layers className="h-4 w-4" />} />
        <KpiTile label="ทักษะมาตรฐาน (dim_skill)" value={dimSkills.length} accent="me" />
        <KpiTile label="% ประกาศที่ Map ทักษะได้" value={`${publicSummary.pct_with_skills ?? 0}%`} accent="compare" />
      </section>

      <GlassCard title="คิว Alias Pending (Top Frequency)" provenance={{ source: "pg_trgm similarity", n: pendingOnly.length, isSample: false }}>
        <div className="space-y-2.5">
          {pendingOnly.slice(0, 30).map((item) => {
            const chosenSkill =
              remapTargets[item.suggestion_id] ??
              item.suggested_skill_key ??
              dimSkills[0]?.skill_key;
            return (
              <div
                key={item.suggestion_id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-3.5"
              >
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[14px] font-semibold text-[var(--ink-primary)]">
                      {item.pending_alias}
                    </span>
                    <StatusChip variant="neutral" label={`freq: ${item.freq}`} />
                    {item.similarity_score ? (
                      <StatusChip
                        variant="good"
                        label={`pg_trgm: ${item.similarity_score.toFixed(2)} → ${item.suggested_skill_canonical}`}
                      />
                    ) : (
                      <StatusChip variant="warning" label="ยังไม่มีคู่ที่ sim ≥ 0.4" />
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <select
                    aria-label={`Target skill for ${item.pending_alias}`}
                    value={chosenSkill}
                    onChange={(e) =>
                      setRemapTargets((prev) => ({
                        ...prev,
                        [item.suggestion_id]: Number(e.target.value),
                      }))
                    }
                    className="min-h-[36px] max-w-[200px] rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-sunken)] px-2.5 text-[12px]"
                  >
                    {dimSkills.map((sk) => (
                      <option key={sk.skill_key} value={sk.skill_key}>
                        {sk.skill_canonical}
                      </option>
                    ))}
                  </select>

                  <button
                    type="button"
                    disabled={busyId === item.suggestion_id}
                    onClick={() =>
                      handleReview(item.suggestion_id, "approve", chosenSkill)
                    }
                    className="inline-flex min-h-[36px] items-center gap-1 rounded-xl bg-[#138A4B] px-3 text-[12px] font-semibold text-white"
                  >
                    <Check className="h-3.5 w-3.5" />
                    <span>Approve / Map</span>
                  </button>
                  <button
                    type="button"
                    disabled={busyId === item.suggestion_id}
                    onClick={() => handleReview(item.suggestion_id, "reject")}
                    className="inline-flex min-h-[36px] items-center gap-1 rounded-xl border border-[#C92A2A]/30 px-3 text-[12px] font-semibold text-[#A82020]"
                  >
                    <X className="h-3.5 w-3.5" />
                    <span>Reject</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </GlassCard>
    </div>
  );
}

export function AdminSourcesView({
  publicSummary,
}: {
  publicSummary: PublicSummary;
}) {
  useRegisterPageContext({
    page: "admin-sources",
    route: "/admin/sources",
    title: "Admin: Data Sources & ToS Compliance",
    kpis: [
      { label: "Allowed Sources", value: ALLOWED_SOURCES.length },
      { label: "Forbidden Sources", value: FORBIDDEN_SOURCES.length },
    ],
    asOf: publicSummary.last_updated_at || undefined,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[24px] font-semibold text-[var(--ink-primary)]">
          Admin: แหล่งข้อมูลและสถานะ ToS / หนังสืออนุญาต
        </h1>
        <p className="text-[13px] text-[var(--ink-secondary)]">
          ตรวจสอบสิทธิ์และข้อกำหนดการเก็บข้อมูลอย่างสุภาพ (Polite Scraping & Forbidden Sources)
        </p>
      </div>

      <GlassCard
        title="แหล่งข้อมูลที่อนุญาต (Allowed Sources)"
        icon={<Database className="h-5 w-5" />}
        provenance={{ source: "CONTEXT §4-5", n: ALLOWED_SOURCES.length, isSample: false }}
      >
        <DataTable
          columns={[
            { key: "name", label: "แหล่งข้อมูล" },
            { key: "role", label: "บทบาท" },
            { key: "robotsStatus", label: "robots.txt" },
            { key: "politeRate", label: "กติกา Polite Rate" },
            { key: "permissionStatus", label: "หนังสืออนุญาต (T0.3)" },
            { key: "tosSummary", label: "เงื่อนไข ToS" },
          ]}
          data={[...ALLOWED_SOURCES]}
        />
      </GlassCard>

      <GlassCard
        title="แหล่งข้อมูลต้องห้าม (Forbidden Sources — บังคับบล็อกใน config.py)"
        icon={<ShieldAlert className="h-5 w-5" />}
      >
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {[
            { name: "JobTopGun", reason: "ToS ข้อ 3.3 ห้าม screen scraping และ data mining" },
            { name: "JobsDB (SEEK)", reason: "robots.txt ระบุ Disallow: */job/" },
            { name: "Indeed", reason: "ห้ามใช้งานตามกติกาโครงงาน (D2)" },
          ].map((f) => (
            <div
              key={f.name}
              className="rounded-xl border border-[#C92A2A]/30 bg-[#C92A2A]/5 p-4 space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <strong className="text-[15px] text-[#9E1C1C]">{f.name}</strong>
                <StatusChip variant="critical" label="FORBIDDEN" />
              </div>
              <p className="text-[12px] text-[var(--ink-secondary)]">{f.reason}</p>
            </div>
          ))}
        </div>
      </GlassCard>
    </div>
  );
}
