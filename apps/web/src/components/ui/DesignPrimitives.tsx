"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock,
  Download,
  ExternalLink,
  Info,
  ShieldAlert,
  Sparkles,
  Table2,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { isLowData, isSafeExternalJobUrl } from "@/lib/compliance";
import { formatDateByLocale, useI18n } from "@/lib/i18n";
import { DataTable, type SimpleColumn } from "./DataTable";

export function ChartSurface({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={`chart-surface min-w-0 ${className}`}>{children}</div>;
}

export function HeroFigure({
  value,
  sublabel,
  className = "",
}: {
  value: string | number;
  sublabel?: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="text-[36px] leading-tight font-semibold tracking-tight text-[var(--ink-primary)] sm:text-[40px]">
        {value}
      </div>
      {sublabel ? (
        <div className="mt-1 text-[13px] text-[var(--ink-secondary)]">
          {sublabel}
        </div>
      ) : null}
    </div>
  );
}

export function ProvenanceBadge({
  source = "JobThai",
  n,
  updatedAt,
  isSample = true,
}: {
  source?: string;
  n?: number | null;
  updatedAt?: string | null;
  isSample?: boolean;
}) {
  const { locale, t } = useI18n();
  const formattedDate = updatedAt ? formatDateByLocale(updatedAt, locale) : null;

  return (
    <div className="flex flex-wrap items-center gap-2 text-[12px] text-[var(--ink-muted)]">
      <span>
        {locale === "th" ? "แหล่ง:" : "Source:"} <strong className="font-medium text-[var(--ink-secondary)]">{source}</strong>
      </span>
      {typeof n === "number" ? (
        <span className="tabular-nums">
          · n = {n.toLocaleString("en-US")}
        </span>
      ) : null}
      {formattedDate ? (
        <span>
          · {t("app.updatedLabel")} {formattedDate}
        </span>
      ) : null}
      {isSample ? (
        <span className="inline-flex items-center rounded-full border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-2 py-0.5 text-[11px] font-medium text-[var(--ink-secondary)]">
          {t("app.sampleBadge")}
        </span>
      ) : null}
    </div>
  );
}

export function KpiTile({
  label,
  value,
  hint,
  delta,
  deltaDirection,
  accent = "me",
  sparkline,
  icon,
}: {
  label: string;
  value: string | number;
  hint?: string;
  delta?: string;
  deltaDirection?: "up" | "down" | "neutral";
  accent?: "me" | "market" | "compare" | "context";
  sparkline?: number[];
  icon?: React.ReactNode;
}) {
  const accentColor =
    accent === "me"
      ? "var(--series-me)"
      : accent === "market"
      ? "var(--series-market)"
      : accent === "compare"
      ? "var(--series-compare)"
      : "var(--series-context)";

  const sparkPath = React.useMemo(() => {
    if (!sparkline || sparkline.length < 2) return null;
    const min = Math.min(...sparkline);
    const max = Math.max(...sparkline);
    const span = max - min || 1;
    const w = 72;
    const h = 24;
    return sparkline
      .map((v, i) => {
        const x = (i / (sparkline.length - 1)) * w;
        const y = h - ((v - min) / span) * (h - 4) - 2;
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [sparkline]);

  return (
    <div className="glass min-w-[210px] flex-1 p-4 sm:min-w-0 sm:p-5">
      <div className="relative z-10 flex items-start justify-between gap-2">
        <span className="text-[13px] font-medium text-[var(--ink-secondary)]">
          {label}
        </span>
        {icon ? (
          <span
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[var(--surface-solid)] text-[var(--ink-secondary)] shadow-xs"
            aria-hidden="true"
          >
            {icon}
          </span>
        ) : null}
      </div>
      <div className="relative z-10 mt-2 flex items-end justify-between gap-2">
        <div>
          <div className="tabular-nums text-[24px] leading-tight font-semibold text-[var(--ink-primary)]">
            {value}
          </div>
          {hint ? (
            <div className="mt-1 text-[12px] text-[var(--ink-muted)]">{hint}</div>
          ) : null}
          {delta ? (
            <div className="mt-1.5 inline-flex items-center gap-1 text-[12px] font-medium text-[var(--ink-secondary)]">
              {deltaDirection === "up" ? (
                <TrendingUp className="h-3.5 w-3.5 text-[var(--status-good)]" aria-hidden="true" />
              ) : deltaDirection === "down" ? (
                <TrendingDown className="h-3.5 w-3.5 text-[var(--status-critical)]" aria-hidden="true" />
              ) : null}
              <span>{delta}</span>
            </div>
          ) : null}
        </div>
        {sparkPath ? (
          <svg
            width="72"
            height="24"
            viewBox="0 0 72 24"
            className="shrink-0"
            aria-hidden="true"
          >
            <path
              d={sparkPath}
              fill="none"
              stroke={accentColor}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        ) : null}
      </div>
    </div>
  );
}

export function StatusChip({
  variant,
  label,
}: {
  variant: "good" | "warning" | "critical" | "pending" | "neutral";
  label: string;
}) {
  const config = {
    good: {
      icon: CheckCircle2,
      classes: "border-[#138A4B]/30 bg-[#138A4B]/10 text-[#0F6E3B]",
    },
    warning: {
      icon: AlertTriangle,
      classes: "border-[#8A5A00]/30 bg-[#8A5A00]/10 text-[#734A00]",
    },
    critical: {
      icon: ShieldAlert,
      classes: "border-[#C92A2A]/30 bg-[#C92A2A]/10 text-[#A82020]",
    },
    pending: {
      icon: Clock,
      classes: "border-[#6C5CE7]/30 bg-[#ECE9FC] text-[#4B3DBF]",
    },
    neutral: {
      icon: Info,
      classes: "border-[var(--border-hairline)] bg-[var(--surface-sunken)] text-[var(--ink-secondary)]",
    },
  }[variant];

  const Icon = config.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[12px] font-medium ${config.classes}`}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

export function LowDataState({
  n,
  title,
  description,
  actionHref = "/market",
  actionLabel,
}: {
  n?: number | null;
  title?: string;
  description?: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  const { locale, t } = useI18n();
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border-hairline)] bg-[var(--surface-solid)] px-4 py-8 text-center">
      <AlertTriangle className="h-7 w-7 text-[var(--status-warning)]" aria-hidden="true" />
      <h4 className="mt-2 text-[15px] font-semibold text-[var(--ink-primary)]">
        {title || t("app.lowDataTitle")}
      </h4>
      <p className="mt-1 max-w-md text-[13px] text-[var(--ink-secondary)]">
        {description || t("app.lowDataDesc")}
        {typeof n === "number"
          ? locale === "th"
            ? ` (พบ ${n} ประกาศ)`
            : ` (found ${n} postings)`
          : ""}
      </p>
      {actionHref ? (
        <Link
          href={actionHref}
          className="mt-3 inline-flex min-h-[40px] items-center rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-sunken)] px-3.5 py-1.5 text-[13px] font-medium text-[var(--ink-primary)] hover:bg-[var(--tint-me)]"
        >
          {actionLabel ||
            (locale === "th" ? "ดูภาพรวมตลาดทักษะ →" : "Explore Market Overview →")}
        </Link>
      ) : null}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title?: string;
  description?: string;
  action?: React.ReactNode;
}) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border-hairline)] bg-[var(--surface-solid)] px-4 py-8 text-center">
      <Info className="h-7 w-7 text-[var(--ink-muted)]" aria-hidden="true" />
      <h4 className="mt-2 text-[15px] font-semibold text-[var(--ink-primary)]">
        {title || t("app.emptyTitle")}
      </h4>
      <p className="mt-1 max-w-md text-[13px] text-[var(--ink-secondary)]">
        {description || t("app.emptyDesc")}
      </p>
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  );
}

export function downloadAggregateCsv(
  filename: string,
  columns: Array<{ key: string; label: string }>,
  rows: Array<Record<string, unknown>>
) {
  const escapeCell = (val: unknown) => {
    const s = String(val ?? "");
    if (s.includes(",") || s.includes('"') || s.includes("\n")) {
      return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
  };
  const header = columns.map((c) => escapeCell(c.label)).join(",");
  const body = rows
    .map((r) => columns.map((c) => escapeCell(r[c.key])).join(","))
    .join("\n");
  const bom = "\uFEFF";
  const blob = new Blob([bom + header + "\n" + body], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function GlassCard<T extends Record<string, unknown>>({
  title,
  subtitle,
  icon,
  actions,
  provenance,
  tableData,
  suppressBelowMinN = false,
  solid = false,
  className = "",
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
  provenance?: {
    source?: string;
    n?: number | null;
    updatedAt?: string | null;
    isSample?: boolean;
  };
  tableData?: {
    columns: SimpleColumn<T>[];
    rows: T[];
    csvFilename?: string;
  };
  suppressBelowMinN?: boolean;
  solid?: boolean;
  className?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  const [showTable, setShowTable] = useState(false);
  const { t } = useI18n();
  const isSuppressed =
    suppressBelowMinN &&
    provenance?.n !== undefined &&
    provenance?.n !== null &&
    isLowData(provenance.n);

  return (
    <section
      className={`${solid ? "surface-solid" : "glass"} flex min-w-0 flex-col p-4 sm:p-5 ${className}`}
    >
      <header className="relative z-10 mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {icon ? (
              <span className="text-[var(--series-me)]" aria-hidden="true">
                {icon}
              </span>
            ) : null}
            <h3 className="text-[17px] leading-snug font-semibold text-[var(--ink-primary)]">
              {title}
            </h3>
          </div>
          {subtitle ? (
            <p className="mt-0.5 text-[13px] text-[var(--ink-secondary)]">
              {subtitle}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {actions}
          {tableData && !isSuppressed ? (
            <button
              type="button"
              onClick={() => setShowTable((prev) => !prev)}
              className="inline-flex min-h-[36px] items-center gap-1.5 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-2.5 py-1 text-[12px] font-medium text-[var(--ink-secondary)] transition hover:bg-[var(--tint-me)] hover:text-[var(--ink-primary)]"
            >
              {showTable ? (
                <>
                  <BarChart3 className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>{t("app.chartView")}</span>
                </>
              ) : (
                <>
                  <Table2 className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>{t("app.tableView")}</span>
                </>
              )}
            </button>
          ) : null}
          {tableData?.csvFilename && tableData.rows.length > 0 && !isSuppressed ? (
            <button
              type="button"
              onClick={() =>
                downloadAggregateCsv(
                  tableData.csvFilename!,
                  tableData.columns.map((c) => ({ key: c.key, label: c.label })),
                  tableData.rows
                )
              }
              title={t("app.downloadCsv")}
              aria-label={`${t("app.downloadCsv")} ${title}`}
              className="inline-flex min-h-[36px] items-center gap-1 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-2.5 py-1 text-[12px] font-medium text-[var(--ink-secondary)] transition hover:bg-[var(--tint-me)] hover:text-[var(--ink-primary)]"
            >
              <Download className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="hidden sm:inline">CSV</span>
            </button>
          ) : null}
        </div>
      </header>

      <div className="relative z-10 flex-1">
        {isSuppressed ? (
          <LowDataState n={provenance?.n} />
        ) : showTable && tableData ? (
          <ChartSurface>
            <DataTable
              columns={tableData.columns}
              data={tableData.rows}
              caption={title}
            />
          </ChartSurface>
        ) : (
          <ChartSurface>{children}</ChartSurface>
        )}
      </div>

      {provenance || footer ? (
        <footer className="relative z-10 mt-3 flex flex-wrap items-center justify-between gap-2 pt-1">
          {provenance ? <ProvenanceBadge {...provenance} /> : <span />}
          {footer}
        </footer>
      ) : null}
    </section>
  );
}

export function ChampionCard({
  badge,
  title,
  children,
  footer,
}: {
  badge: string;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <section className="ai-card flex flex-col justify-between">
      <div className="ai-card-scrim flex h-full flex-col justify-between p-5 sm:p-6">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-white/20 px-3 py-1 text-[12px] font-semibold text-white backdrop-blur-xs">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            <span>{badge}</span>
          </div>
          <h3 className="mt-3 text-[18px] font-semibold text-white">{title}</h3>
          <div className="mt-2">{children}</div>
        </div>
        {footer ? (
          <div className="mt-4 border-t border-white/25 pt-3 text-[12px] font-medium text-white/95">
            {footer}
          </div>
        ) : null}
      </div>
    </section>
  );
}

export const AiCard = ChampionCard;

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  ariaLabel,
}: {
  options: Array<{ value: T; label: string }>;
  value: T;
  onChange: (val: T) => void;
  ariaLabel: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className="inline-flex flex-wrap rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-sunken)] p-1"
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            className={`min-h-[34px] rounded-lg px-3 py-1 text-[12px] font-medium transition ${
              active
                ? "bg-[var(--surface-solid)] text-[var(--ink-primary)] shadow-xs"
                : "text-[var(--ink-secondary)] hover:text-[var(--ink-primary)]"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

export function RangeSlider({
  label,
  min,
  max,
  step = 1,
  value,
  onChange,
  formatValue,
}: {
  label: string;
  min: number;
  max: number;
  step?: number;
  value: number;
  onChange: (val: number) => void;
  formatValue?: (val: number) => string;
}) {
  return (
    <label className="flex flex-col gap-1.5 text-[13px]">
      <div className="flex items-center justify-between">
        <span className="font-medium text-[var(--ink-secondary)]">{label}</span>
        <span className="tabular-nums font-semibold text-[var(--series-me)]">
          {formatValue ? formatValue(value) : value}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-10 w-full cursor-pointer accent-[#6C5CE7]"
      />
    </label>
  );
}

export function MeterList({
  items,
  maxVal,
  accent = "me",
}: {
  items: Array<{
    id: string | number;
    label: string;
    sublabel?: string;
    value: number;
    valueText: string;
  }>;
  maxVal?: number;
  accent?: "me" | "market" | "compare";
}) {
  const computedMax =
    maxVal ?? Math.max(...items.map((i) => Math.abs(i.value)), 1);
  const barColor =
    accent === "market"
      ? "bg-[var(--series-market)]"
      : accent === "compare"
      ? "bg-[var(--series-compare)]"
      : "bg-[var(--series-me)]";

  return (
    <ul className="space-y-3">
      {items.map((item) => {
        const pct = Math.max(
          4,
          Math.min(100, (Math.abs(item.value) / computedMax) * 100)
        );
        return (
          <li key={item.id} className="space-y-1">
            <div className="flex items-baseline justify-between gap-2 text-[13px]">
              <div className="min-w-0">
                <span className="font-medium text-[var(--ink-primary)]">
                  {item.label}
                </span>
                {item.sublabel ? (
                  <span className="ml-2 text-[12px] text-[var(--ink-muted)]">
                    {item.sublabel}
                  </span>
                ) : null}
              </div>
              <span className="tabular-nums shrink-0 font-semibold text-[var(--ink-primary)]">
                {item.valueText}
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--surface-sunken)]">
              <div
                className={`h-full rounded-full ${barColor}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function SourceLink({
  url,
  titleShort,
  sourceName = "JobThai",
  datePosted,
}: {
  url: string;
  titleShort: string;
  sourceName?: string;
  datePosted?: string | null;
}) {
  const { locale, t } = useI18n();
  const safe = isSafeExternalJobUrl(url);

  if (!safe) {
    return null;
  }

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex min-h-[44px] items-center justify-between gap-3 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3.5 py-2.5 text-[13px] transition hover:border-[var(--series-me)] hover:bg-[var(--tint-me)]/40"
    >
      <div className="min-w-0 flex-1">
        <div className="truncate font-medium text-[var(--ink-primary)] group-hover:text-[var(--series-me)]">
          {titleShort}
        </div>
        <div className="text-[12px] text-[var(--ink-muted)]">
          {sourceName.toUpperCase()}
          {datePosted ? ` · ${formatDateByLocale(datePosted, locale)}` : ""}
        </div>
      </div>
      <span className="inline-flex shrink-0 items-center gap-1 text-[12px] font-semibold text-[var(--series-me)]">
        <span>{t("app.sourceLinkLabel")}</span>
        <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
      </span>
    </a>
  );
}
