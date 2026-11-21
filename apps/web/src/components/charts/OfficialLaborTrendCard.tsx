"use client";

import React, { useMemo, useState } from "react";
import { ExternalLink, Landmark } from "lucide-react";
import { EChartBox } from "@/components/charts/EChartBox";
import { EmptyState, GlassCard, StatusChip } from "@/components/ui/DesignPrimitives";
import { SKILLBI_PALETTE } from "@/lib/echarts-theme";
import { useI18n } from "@/lib/i18n";
import type { LaborMonthlyRow } from "@/types/marts";

export function OfficialLaborTrendCard({
  rows,
  selectedMetric,
  onMetricChange,
}: {
  rows: LaborMonthlyRow[];
  selectedMetric?: string;
  onMetricChange?: (metric: string) => void;
}) {
  const { locale } = useI18n();

  const metrics = useMemo(() => {
    const map = new Map<
      string,
      { metric: string; metric_th: string; unit: string; source: string; dataset_url: string; dataset_id: string }
    >();
    for (const r of rows) {
      if (!map.has(r.metric)) {
        map.set(r.metric, {
          metric: r.metric,
          metric_th: r.metric_th,
          unit: r.unit,
          source: r.source,
          dataset_url: r.dataset_url,
          dataset_id: r.dataset_id,
        });
      }
    }
    return Array.from(map.values());
  }, [rows]);

  const [internalMetric, setInternalMetric] = useState<string>(
    metrics[0]?.metric || ""
  );
  const activeMetric = selectedMetric || internalMetric || metrics[0]?.metric || "";
  const setMetric = (m: string) => {
    setInternalMetric(m);
    onMetricChange?.(m);
  };

  const activeMeta = metrics.find((m) => m.metric === activeMetric) || metrics[0];

  const seriesRows = useMemo(
    () =>
      rows
        .filter((r) => r.metric === activeMetric)
        .sort((a, b) => a.date_key - b.date_key),
    [rows, activeMetric]
  );

  const option = useMemo(
    () => ({
      tooltip: {
        trigger: "axis",
        formatter: (params: Array<{ name: string; value: number }>) => {
          const p = params[0];
          if (!p) return "";
          return `${p.name}: <b>${Number(p.value).toLocaleString("en-US")}</b> ${
            activeMeta?.unit || ""
          }`;
        },
      },
      grid: { top: 20, right: 24, bottom: 64, left: 64 },
      xAxis: {
        type: "category",
        data: seriesRows.map((r) => r.period_label),
      },
      yAxis: {
        type: "value",
        name: activeMeta?.unit || "",
        nameTextStyle: { color: SKILLBI_PALETTE.inkMuted, fontSize: 11 },
      },
      dataZoom: [
        { type: "inside" },
        { type: "slider", height: 22, bottom: 10 },
      ],
      series: [
        {
          name: locale === "th" ? activeMeta?.metric_th : activeMeta?.metric,
          type: "line",
          smooth: false,
          areaStyle: { color: "rgba(14, 154, 174, 0.14)" },
          lineStyle: { color: SKILLBI_PALETTE.compare, width: 2 },
          itemStyle: { color: SKILLBI_PALETTE.compare },
          data: seriesRows.map((r) => r.value),
        },
      ],
    }),
    [seriesRows, activeMeta, locale]
  );

  if (rows.length === 0) {
    return (
      <GlassCard
        title={
          locale === "th"
            ? "แนวโน้มตลาดแรงงานจากหน่วยงานรัฐย้อนหลัง ≤ 2 ปี (T3.9)"
            : "Official Thai Labor Market Context (≤ 2 Years, T3.9)"
        }
        icon={<Landmark className="h-5 w-5" />}
      >
        <EmptyState
          title={
            locale === "th"
              ? "รอโหลดข้อมูลสถิติหน่วยงานรัฐ (labor_monthly_2y)"
              : "Official 2-year labor statistics not yet populated"
          }
          description={
            locale === "th"
              ? "ส่วนนี้แสดงบริบทระดับมหภาคจากหน่วยงานรัฐ แยกจากประกาศงานล่าสุด JobThai + JobBKK"
              : "Macro context from official agencies, separated from live JobThai + JobBKK postings."
          }
        />
      </GlassCard>
    );
  }

  return (
    <GlassCard
      title={
        locale === "th"
          ? "แนวโน้มตลาดแรงงานจากหน่วยงานรัฐย้อนหลัง ≤ 2 ปี (T3.9)"
          : "Official Thai Labor Market Trends (≤ 2 Years, T3.9)"
      }
      subtitle={
        locale === "th"
          ? "ข้อมูลสถิติหน่วยงานรัฐย้อนหลัง 2 ปี (แยกชัดเจนจากประกาศงานจริงล่าสุด JobThai + JobBKK · แกนเดียว ไม่มี dual-axis)"
          : "Official macro labor series over the past 2 years (single-axis selector, separated from JobThai + JobBKK sample)"
      }
      icon={<Landmark className="h-5 w-5" />}
      actions={
        metrics.length > 0 ? (
          <div className="flex flex-wrap items-center gap-2">
            <StatusChip
              variant="neutral"
              label={
                locale === "th"
                  ? "ข้อมูลสถิติหน่วยงานรัฐ (ไม่ใช่ประกาศงานล่าสุด)"
                  : "Official Agency Context"
              }
            />
            <select
              aria-label={locale === "th" ? "เลือกตัวชี้วัดสถิติรัฐ" : "Select official labor metric"}
              value={activeMetric}
              onChange={(e) => setMetric(e.target.value)}
              className="min-h-[36px] max-w-[260px] rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-2.5 text-[12px] font-medium text-[var(--ink-primary)]"
            >
              {metrics.map((m) => (
                <option key={m.metric} value={m.metric}>
                  {locale === "th" ? m.metric_th : m.metric} ({m.unit})
                </option>
              ))}
            </select>
          </div>
        ) : null
      }
      provenance={{
        source: activeMeta?.source || "Official Open Data",
        n: seriesRows.length,
        isSample: false,
      }}
      footer={
        activeMeta?.dataset_url ? (
          <a
            href={activeMeta.dataset_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-[12px] font-medium text-[var(--series-compare)] hover:underline"
          >
            <span>Dataset: {activeMeta.dataset_id}</span>
            <ExternalLink className="h-3 w-3" aria-hidden="true" />
          </a>
        ) : undefined
      }
      tableData={{
        csvFilename: "official-labor-2y.csv",
        columns: [
          { key: "period", label: locale === "th" ? "งวดเวลา" : "Period" },
          { key: "granularity", label: locale === "th" ? "ความถี่" : "Granularity" },
          { key: "value", label: activeMeta?.unit || "Value", numeric: true },
          { key: "source", label: locale === "th" ? "แหล่งข้อมูล" : "Source" },
        ],
        rows: seriesRows.map((r) => ({
          period: r.period_label,
          granularity: r.granularity,
          value: r.value,
          source: r.source,
        })),
      }}
    >
      <EChartBox
        option={option}
        height={280}
        ariaLabel="Official 2-year Thai labor market trend chart"
      />
    </GlassCard>
  );
}
