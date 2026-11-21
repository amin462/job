"use client";

import React, { useMemo } from "react";
import Link from "next/link";
import { Award, BarChart3, FlaskConical, ShieldCheck, Sparkles } from "lucide-react";
import { EChartBox } from "@/components/charts/EChartBox";
import { useRegisterPageContext } from "@/components/chat/PageContextProvider";
import {
  ChampionCard,
  EmptyState,
  GlassCard,
  StatusChip,
} from "@/components/ui/DesignPrimitives";
import { DataTable } from "@/components/ui/DataTable";
import { SKILLBI_PALETTE } from "@/lib/echarts-theme";
import { formatBaht, useI18n } from "@/lib/i18n";
import type {
  MlFeatureImportanceRow,
  MlLeaderboardRow,
  PublicSummary,
} from "@/types/marts";

export function MlLabView({
  publicSummary,
  leaderboard,
  featureImportance,
}: {
  publicSummary: PublicSummary;
  leaderboard: MlLeaderboardRow[];
  featureImportance: MlFeatureImportanceRow[];
}) {
  const { locale } = useI18n();

  const latestExperimentId = useMemo(() => {
    const ids = leaderboard
      .map((r) => (r.experiment_id !== undefined && r.experiment_id !== null ? Number(r.experiment_id) : NaN))
      .filter((id) => Number.isFinite(id));
    return ids.length > 0 ? Math.max(...ids) : null;
  }, [leaderboard]);

  const activeLeaderboard = useMemo(() => {
    if (latestExperimentId === null) return leaderboard;
    return leaderboard.filter(
      (r) => r.experiment_id === undefined || r.experiment_id === null || Number(r.experiment_id) === latestExperimentId
    );
  }, [leaderboard, latestExperimentId]);

  const activeFeatureImportance = useMemo(() => {
    if (latestExperimentId === null) return featureImportance;
    return featureImportance.filter(
      (f) => f.experiment_id === undefined || f.experiment_id === null || Number(f.experiment_id) === latestExperimentId
    );
  }, [featureImportance, latestExperimentId]);

  const summaryRows = useMemo(
    () =>
      activeLeaderboard
        .filter((r) => r.is_summary || Number(r.fold) === -1)
        .sort((a, b) => Number(a.rmse) - Number(b.rmse)),
    [activeLeaderboard]
  );

  const foldRows = useMemo(
    () => activeLeaderboard.filter((r) => !r.is_summary && Number(r.fold) >= 0),
    [activeLeaderboard]
  );

  const champion = useMemo(
    () => summaryRows.find((r) => r.is_champion) || summaryRows[0] || null,
    [summaryRows]
  );

  // Compute SD across folds per model when not explicitly present
  const summaryWithSd = useMemo(() => {
    return summaryRows.map((row) => {
      const folds = foldRows.filter((f) => f.model_name === row.model_name);
      const calcSd = (vals: number[]) => {
        if (vals.length < 2) return 0;
        const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
        const v = vals.reduce((a, b) => a + (b - mean) ** 2, 0) / vals.length;
        return Math.sqrt(v);
      };
      return {
        ...row,
        rmse_sd: row.rmse_sd ?? calcSd(folds.map((f) => f.rmse)),
        mae_sd: row.mae_sd ?? calcSd(folds.map((f) => f.mae)),
        r2_sd: row.r2_sd ?? calcSd(folds.map((f) => f.r2)),
        mape_sd: row.mape_sd ?? calcSd(folds.map((f) => f.mape)),
      };
    });
  }, [summaryRows, foldRows]);

  const topFeatures = useMemo(
    () =>
      [...activeFeatureImportance]
        .sort((a, b) => Number(b.importance) - Number(a.importance))
        .slice(0, 15),
    [activeFeatureImportance]
  );

  useRegisterPageContext({
    page: "ml-lab",
    route: "/ml-lab",
    title: locale === "th" ? "ML Lab — เปรียบเทียบโมเดลประมาณเงินเดือน" : "ML Lab Benchmark",
    kpis: champion
      ? [
          { label: "Champion Model", value: champion.model_name },
          { label: "Champion RMSE", value: Math.round(champion.rmse), unit: "THB" },
          { label: "Champion MAE", value: Math.round(champion.mae), unit: "THB" },
          { label: "Rows Trained", value: champion.n_rows ?? publicSummary.n_with_salary },
        ]
      : [{ label: "Salaried Rows", value: publicSummary.n_with_salary }],
    charts: [
      {
        id: "ml-leaderboard",
        title: locale === "th" ? "ตารางเทียบ 5 โมเดล + Baseline" : "5-Model + Baseline Leaderboard",
        rows: summaryWithSd.map((r) => [
          r.model_name,
          Number(r.r2.toFixed(3)),
          Math.round(r.rmse),
          Math.round(r.mae),
          Number(r.mape.toFixed(1)),
        ]),
      },
      {
        id: "feature-importance",
        title: locale === "th" ? "Feature Importance ของ Champion" : "Champion Feature Importance",
        rows: topFeatures.map((f) => [f.feature, Number(f.importance.toFixed(4))]),
      },
    ],
    asOf: champion?.created_at || publicSummary.last_updated_at || undefined,
    dataNotes: [
      "ระบบจริงเสิร์ฟเฉพาะโมเดล Champion ตัวเดียวผ่าน FastAPI (D5, D19)",
      "ประเมินด้วย GroupKFold(5, group=company_key) + Nested CV GroupKFold(3)",
      "ห้ามใช้เพศ (gender) อายุ (age) และชื่อบริษัทเป็น feature (D6)",
    ],
  });

  const rmseBarOption = useMemo(
    () => ({
      tooltip: { trigger: "axis" },
      grid: { top: 20, right: 24, bottom: 32, left: 60 },
      xAxis: {
        type: "category",
        data: summaryWithSd.map((r) => r.model_name),
        axisLabel: { fontSize: 11 },
      },
      yAxis: {
        type: "value",
        axisLabel: { formatter: (v: number) => `฿${Math.round(v).toLocaleString("en-US")}` },
      },
      series: [
        {
          name: "RMSE (Mean)",
          type: "bar",
          data: summaryWithSd.map((r) => ({
            value: Math.round(r.rmse),
            itemStyle: {
              color: r.is_champion ? SKILLBI_PALETTE.me : SKILLBI_PALETTE.context,
              borderRadius: [4, 4, 0, 0],
            },
          })),
        },
        {
          name: "RMSE ± SD",
          type: "custom",
          renderItem: (_params: unknown, api: { coord: (v: [number, number]) => [number, number]; value: (i: number) => number }) => {
            const xIdx = api.value(0);
            const low = api.coord([xIdx, api.value(1)]);
            const high = api.coord([xIdx, api.value(2)]);
            return {
              type: "group",
              children: [
                {
                  type: "line",
                  shape: { x1: low[0], y1: low[1], x2: high[0], y2: high[1] },
                  style: { stroke: SKILLBI_PALETTE.inkPrimary, lineWidth: 2 },
                },
                {
                  type: "line",
                  shape: { x1: low[0] - 6, y1: high[1], x2: low[0] + 6, y2: high[1] },
                  style: { stroke: SKILLBI_PALETTE.inkPrimary, lineWidth: 2 },
                },
                {
                  type: "line",
                  shape: { x1: low[0] - 6, y1: low[1], x2: low[0] + 6, y2: low[1] },
                  style: { stroke: SKILLBI_PALETTE.inkPrimary, lineWidth: 2 },
                },
              ],
            };
          },
          data: summaryWithSd.map((r, idx) => [
            idx,
            Math.max(0, r.rmse - (r.rmse_sd ?? 0)),
            r.rmse + (r.rmse_sd ?? 0),
          ]),
        },
      ],
    }),
    [summaryWithSd]
  );

  const stripPlotOption = useMemo(() => {
    const models = summaryWithSd.map((r) => r.model_name);
    return {
      tooltip: {
        trigger: "item",
        formatter: (p: { value?: [string, number, number] }) =>
          p.value
            ? `${p.value[0]} · Fold ${p.value[2] + 1}: <b>${formatBaht(p.value[1])}</b>`
            : "",
      },
      grid: { top: 20, right: 20, bottom: 32, left: 60 },
      xAxis: { type: "category", data: models, axisLabel: { fontSize: 11 } },
      yAxis: {
        type: "value",
        axisLabel: { formatter: (v: number) => `฿${Math.round(v).toLocaleString("en-US")}` },
      },
      series: [
        {
          type: "scatter",
          symbolSize: 11,
          itemStyle: { color: SKILLBI_PALETTE.market },
          data: foldRows.map((f) => [f.model_name, Math.round(f.rmse), f.fold]),
        },
      ],
    };
  }, [summaryWithSd, foldRows]);

  const fiOption = useMemo(() => {
    const ordered = [...topFeatures].reverse();
    return {
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { top: 8, right: 28, bottom: 24, left: 170 },
      xAxis: { type: "value" },
      yAxis: {
        type: "category",
        data: ordered.map((f) =>
          f.feature.length > 26 ? f.feature.slice(0, 24) + "…" : f.feature
        ),
      },
      series: [
        {
          type: "bar",
          data: ordered.map((f) => Number(f.importance.toFixed(4))),
          itemStyle: { color: SKILLBI_PALETTE.me, borderRadius: [0, 4, 4, 0] },
        },
      ],
    };
  }, [topFeatures]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[24px] font-semibold text-[var(--ink-primary)]">
            {locale === "th" ? "ML Lab — ห้องทดลองเปรียบเทียบโมเดล" : "ML Lab — Model Benchmark"}
          </h1>
          <p className="text-[13px] text-[var(--ink-secondary)]">
            {locale === "th"
              ? "ประเมิน 5 โมเดล + Baseline ด้วย GroupKFold(5, group=company_key) และ Nested CV · ระบบจริงใช้เฉพาะ Champion"
              : "5 models + Baseline evaluated with GroupKFold(5, group=company) + Nested CV. Only the Champion model is served in production."}
          </p>
        </div>

        <StatusChip
          variant="pending"
          label={locale === "th" ? "ระบบจริงใช้เฉพาะ Champion" : "Production uses Champion ONLY"}
        />
      </div>

      {/* Methodology & Fairness Box */}
      <section className="glass p-5">
        <div className="relative z-10 grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-4">
            <div className="flex items-center gap-2 text-[13px] font-semibold text-[var(--series-me)]">
              <ShieldCheck className="h-4 w-4" />
              <span>GroupKFold (5 folds, group = company)</span>
            </div>
            <p className="mt-1 text-[12px] text-[var(--ink-secondary)]">
              ป้องกันไม่ให้ประกาศจากบริษัทเดียวกันรั่วข้ามชุด Train/Test และจูน Hyperparameter ด้วย Nested GroupKFold(3) ชั้นใน
            </p>
          </div>
          <div className="rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-4">
            <div className="flex items-center gap-2 text-[13px] font-semibold text-[var(--series-market)]">
              <FlaskConical className="h-4 w-4" />
              <span>No Gender / Age / Company Features (D6)</span>
            </div>
            <p className="mt-1 text-[12px] text-[var(--ink-secondary)]">
              ตัดเพศ อายุ และชื่อบริษัทออกจาก feature ของโมเดลทั้งหมด พร้อมชุดทดสอบ unit test ป้องกัน feature leak
            </p>
          </div>
          <div className="rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-4">
            <div className="flex items-center gap-2 text-[13px] font-semibold text-[var(--series-compare)]">
              <Sparkles className="h-4 w-4" />
              <span>FastAPI Champion + Fallback</span>
            </div>
            <p className="mt-1 text-[12px] text-[var(--ink-secondary)]">
              เสิร์ฟเฉพาะ Champion บน FastAPI (`services/ml-api`) พร้อมตาราง `mart.salary_prediction` เป็น fallback
            </p>
          </div>
        </div>
      </section>

      {summaryWithSd.length === 0 ? (
        <EmptyState
          title={locale === "th" ? "กำลังรอผลการทดลอง ML จาก pipeline/ml/benchmark.py" : "Waiting for ML benchmark results"}
          description={
            locale === "th"
              ? "เมื่อรัน ml-service แล้ว ตารางเทียบ 5 โมเดล (Ridge, RandomForest, XGBoost, LightGBM, CatBoost) + Baseline จะปรากฏที่นี่"
              : "Run pipeline.ml.benchmark to populate 5-model + baseline results into seed_marts.json."
          }
          action={
            <Link
              href="/salary"
              className="inline-flex min-h-[40px] items-center rounded-xl bg-[var(--series-me)] px-4 text-[13px] font-semibold text-white"
            >
              {locale === "th" ? "ไปหน้าประมาณเงินเดือน →" : "Open Salary Estimator →"}
            </Link>
          }
        />
      ) : (
        <>
          {champion ? (
            <ChampionCard
              badge={locale === "th" ? "Selected Champion Model" : "Selected Champion"}
              title={champion.model_name}
              footer={`Dataset: ${champion.dataset_version || "v1"} · Training rows: ${
                champion.n_rows ?? publicSummary.n_with_salary
              } · Target: log(salary_mid)`}
            >
              <div className="flex flex-wrap gap-6 text-white">
                <div>
                  <div className="text-[12px] text-white/80">RMSE (Mean ± SD)</div>
                  <div className="tabular-nums text-[24px] font-bold">
                    {formatBaht(champion.rmse)} ± {formatBaht(champion.rmse_sd ?? 0)}
                  </div>
                </div>
                <div>
                  <div className="text-[12px] text-white/80">MAE</div>
                  <div className="tabular-nums text-[24px] font-bold">
                    {formatBaht(champion.mae)}
                  </div>
                </div>
                <div>
                  <div className="text-[12px] text-white/80">R² / MAPE</div>
                  <div className="tabular-nums text-[24px] font-bold">
                    {champion.r2.toFixed(3)} / {champion.mape.toFixed(1)}%
                  </div>
                </div>
              </div>
            </ChampionCard>
          ) : null}

          <GlassCard
            title={locale === "th" ? "Leaderboard: 5 โมเดล + Baseline" : "ML Model Leaderboard"}
            icon={<Award className="h-5 w-5" />}
            provenance={{ source: "ML Pipeline", n: champion?.n_rows ?? publicSummary.n_with_salary }}
          >
            <DataTable
              columns={[
                { key: "model_name", label: locale === "th" ? "โมเดล" : "Model" },
                { key: "role", label: locale === "th" ? "สถานะ" : "Role" },
                { key: "r2", label: "R² (±SD)", numeric: true },
                { key: "rmse", label: "RMSE (±SD)", numeric: true },
                { key: "mae", label: "MAE (±SD)", numeric: true },
                { key: "mape", label: "MAPE %", numeric: true },
                { key: "fit_seconds", label: "Fit (s)", numeric: true },
              ]}
              data={summaryWithSd.map((r) => ({
                model_name: r.model_name,
                role: r.is_champion ? "★ Champion (Production)" : "Benchmark Only",
                r2: `${r.r2.toFixed(3)} ± ${(r.r2_sd ?? 0).toFixed(3)}`,
                rmse: `${formatBaht(r.rmse)} ± ${formatBaht(r.rmse_sd ?? 0)}`,
                mae: `${formatBaht(r.mae)} ± ${formatBaht(r.mae_sd ?? 0)}`,
                mape: `${r.mape.toFixed(1)}%`,
                fit_seconds: r.fit_seconds.toFixed(2),
              }))}
            />
          </GlassCard>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
            <div className="lg:col-span-6">
              <GlassCard
                title={locale === "th" ? "RMSE เฉลี่ย ± SD ข้าม Fold" : "RMSE Mean ± SD"}
                icon={<BarChart3 className="h-5 w-5" />}
                provenance={{ source: "Nested GroupKFold(5)", n: champion?.n_rows }}
              >
                <EChartBox option={rmseBarOption} height={280} ariaLabel="Model RMSE with SD error bars" />
              </GlassCard>
            </div>
            <div className="lg:col-span-6">
              <GlassCard
                title={locale === "th" ? "การกระจาย RMSE ราย Fold (Strip Plot)" : "Per-Fold RMSE Strip Plot"}
                icon={<FlaskConical className="h-5 w-5" />}
                provenance={{ source: "GroupKFold(5)", n: foldRows.length }}
              >
                <EChartBox option={stripPlotOption} height={280} ariaLabel="Per-fold RMSE strip plot" />
              </GlassCard>
            </div>
          </div>

          {topFeatures.length > 0 ? (
            <GlassCard
              title={locale === "th" ? "Champion Feature Importance (Top 15)" : "Champion Feature Importance"}
              icon={<Sparkles className="h-5 w-5" />}
              provenance={{ source: champion?.model_name || "Champion", n: champion?.n_rows }}
              tableData={{
                columns: [
                  { key: "feature", label: "Feature" },
                  { key: "importance", label: "Importance", numeric: true },
                ],
                rows: topFeatures.map((f) => ({
                  feature: f.feature,
                  importance: f.importance.toFixed(4),
                })),
              }}
            >
              <EChartBox option={fiOption} height={360} ariaLabel="Champion feature importance bars" />
            </GlassCard>
          ) : null}
        </>
      )}
    </div>
  );
}
