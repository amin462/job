import { NextResponse, type NextRequest } from "next/server";
import { loadSeedMarts } from "@/lib/data";
import { FORBIDDEN_ML_FAIRNESS_KEYS } from "@/lib/compliance";
import type {
  SalaryEstimateResponse,
  SalaryPredictionRow,
  SalaryStatsRow,
  SkillUpliftItem,
} from "@/types/marts";

const ML_TIMEOUT_MS = 8000;
const DISCLAIMER_TH = "ประมาณการจากประกาศที่ระบุเงินเดือน ไม่ใช่เงินเดือนจริง";

function getMlConfig() {
  const url = process.env.ML_API_URL?.trim()?.replace(/\/+$/, "");
  const key = process.env.ML_API_KEY?.trim() || "";
  const valid = Boolean(
    url && (url.startsWith("https://") || url.startsWith("http://"))
  );
  return { url: url || "", key, valid };
}

export async function GET(request: NextRequest) {
  const warm = request.nextUrl.searchParams.get("warm");
  const { url, valid } = getMlConfig();

  if (!valid) {
    return NextResponse.json({
      warmed: false,
      configured: false,
      status: "fallback-ready",
    });
  }

  if (warm === "1") {
    try {
      const res = await fetch(`${url}/health`, {
        method: "GET",
        signal: AbortSignal.timeout(ML_TIMEOUT_MS),
        cache: "no-store",
      });
      const data = res.ok ? await res.json().catch(() => null) : null;
      return NextResponse.json({
        warmed: res.ok,
        configured: true,
        status: res.ok ? "ok" : `http-${res.status}`,
        health: data,
      });
    } catch {
      return NextResponse.json({
        warmed: false,
        configured: true,
        status: "cold-starting-or-unreachable",
      });
    }
  }

  return NextResponse.json({ warmed: false, configured: true });
}

function findBestPredictionFallback(
  preds: SalaryPredictionRow[],
  occ: string,
  province: string,
  region: string,
  exp: string,
  edu: string
): SalaryPredictionRow | null {
  if (!preds || preds.length === 0) return null;
  return (
    preds.find(
      (p) =>
        p.occupation_cluster === occ &&
        p.province_th === province &&
        p.experience_band === exp &&
        p.education_level === edu
    ) ||
    preds.find(
      (p) =>
        p.occupation_cluster === occ &&
        p.province_th === province &&
        p.experience_band === exp
    ) ||
    preds.find(
      (p) =>
        p.occupation_cluster === occ &&
        p.province_th === "ทั้งประเทศ" &&
        p.experience_band === exp &&
        p.education_level === edu
    ) ||
    preds.find(
      (p) =>
        p.occupation_cluster === occ &&
        p.province_th === "ทั้งประเทศ" &&
        p.experience_band === exp
    ) ||
    preds.find(
      (p) =>
        p.occupation_cluster === occ &&
        p.province_th === "ทั้งหมดในภาค" &&
        p.region === region
    ) ||
    preds.find((p) => p.occupation_cluster === occ && p.province_th === province) ||
    preds.find((p) => p.occupation_cluster === occ && p.region === region) ||
    preds.find((p) => p.occupation_cluster === occ) ||
    null
  );
}

function findBestSalaryStats(
  stats: SalaryStatsRow[],
  occ: string,
  province: string,
  region: string,
  exp: string
): SalaryStatsRow | null {
  const valid = stats.filter(
    (s) => !s.is_suppressed && s.salary_p50 !== null && s.n_postings >= 5
  );
  return (
    valid.find(
      (s) =>
        s.occupation_cluster === occ &&
        s.province_th === province &&
        s.experience_band === exp
    ) ||
    valid.find(
      (s) =>
        s.occupation_cluster === occ &&
        s.region === region &&
        s.experience_band === exp
    ) ||
    valid.find(
      (s) => s.occupation_cluster === occ && s.experience_band === exp
    ) ||
    valid.find((s) => s.occupation_cluster === occ && s.region === region) ||
    valid.find((s) => s.occupation_cluster === occ) ||
    valid.find((s) => s.scope_type === "reg" && s.region === region) ||
    valid.find((s) => s.scope_type === "national") ||
    null
  );
}

export async function POST(request: NextRequest) {
  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return NextResponse.json({ error: "Invalid JSON payload" }, { status: 400 });
  }

  // Enforce D6 fairness rule: NEVER accept gender, age, or company_name
  for (const forbidden of FORBIDDEN_ML_FAIRNESS_KEYS) {
    if (forbidden in body && body[forbidden] !== undefined) {
      return NextResponse.json(
        {
          error: `Fairness policy violation (D6): '${forbidden}' must not be sent or used as a salary estimation feature.`,
        },
        { status: 400 }
      );
    }
  }

  const occupation_cluster = String(body.occupation_cluster || "").trim();
  const province_th = String(body.province_th || "ทั้งประเทศ").trim();
  const experience_band = String(
    body.experience_band || "ไม่ระบุ/ไม่จำเป็น"
  ).trim();
  const education_level = String(body.education_level || "ไม่ระบุ").trim();
  const employment_type = String(body.employment_type || "FULL_TIME").trim();
  const skills = Array.isArray(body.skills)
    ? body.skills.map((s) => String(s))
    : [];
  const candidate_skills = Array.isArray(body.candidate_skills)
    ? body.candidate_skills
        .map((s) => String(s))
        .filter((s) => !skills.includes(s))
        .slice(0, 6)
    : [];

  if (!occupation_cluster) {
    return NextResponse.json(
      { error: "occupation_cluster is required" },
      { status: 400 }
    );
  }

  const seed = loadSeedMarts();
  const locMeta = seed.dim_locations.find((l) => l.province_th === province_th);
  const region = String(body.region || locMeta?.region || "ทั้งประเทศ");

  const { url, key, valid } = getMlConfig();
  const championRow = seed.ml_leaderboard.find(
    (r) => r.is_summary && r.is_champion
  );

  // Try live FastAPI Champion service (timeout 8s)
  if (valid) {
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (key) headers["X-ML-Key"] = key;

      const baseFeature = {
        occupation_cluster,
        province_th,
        region,
        experience_band,
        education_level,
        employment_type,
        skills,
      };

      const predRes = await fetch(`${url}/predict`, {
        method: "POST",
        headers,
        body: JSON.stringify(baseFeature),
        signal: AbortSignal.timeout(ML_TIMEOUT_MS),
        cache: "no-store",
      });

      if (predRes.ok) {
        const pred = (await predRes.json()) as {
          p25: number;
          p50: number;
          p75: number;
          model_name?: string;
          mae?: number;
          mape?: number;
          cv_mae?: number;
          cv_mape?: number;
          n_support?: number;
          out_of_domain?: boolean;
        };

        let uplifts: SkillUpliftItem[] = [];
        if (candidate_skills.length > 0) {
          try {
            const batchPayload = {
              items: candidate_skills.map((cs) => ({
                ...baseFeature,
                skills: [...skills, cs],
              })),
            };
            const batchRes = await fetch(`${url}/predict/batch`, {
              method: "POST",
              headers,
              body: JSON.stringify(batchPayload),
              signal: AbortSignal.timeout(ML_TIMEOUT_MS),
              cache: "no-store",
            });
            if (batchRes.ok) {
              const batchData = (await batchRes.json()) as {
                predictions?: Array<{ p50: number }>;
              };
              const list = batchData.predictions || [];
              uplifts = candidate_skills.map((sk, idx) => {
                const newP50 = Math.round(list[idx]?.p50 ?? pred.p50);
                return {
                  skill: sk,
                  new_p50: newP50,
                  delta_p50: newP50 - Math.round(pred.p50),
                };
              });
            }
          } catch {
            // Optional uplift batch fallback handled gracefully
          }
        }

        const nSupport = pred.n_support ?? null;
        const responseBody: SalaryEstimateResponse = {
          p25: Math.round(pred.p25),
          p50: Math.round(pred.p50),
          p75: Math.round(pred.p75),
          model_name:
            pred.model_name || championRow?.model_name || "Champion Model",
          cv_mae: pred.cv_mae ?? pred.mae ?? championRow?.mae ?? null,
          cv_mape: pred.cv_mape ?? pred.mape ?? championRow?.mape ?? null,
          source: "ml-api",
          badge: "คำนวณสดจากโมเดล Champion",
          disclaimer: DISCLAIMER_TH,
          n_support: nSupport,
          low_support_warning: Boolean(pred.out_of_domain) || (nSupport !== null && nSupport < 10),
          uplifts,
        };
        return NextResponse.json(responseBody);
      }
    } catch {
      // Fall through to mart.salary_prediction / mart.salary_stats fallback
    }
  }

  // Fallback 1: mart.salary_prediction (precomputed Champion predictions)
  const predRow = findBestPredictionFallback(
    seed.salary_prediction || [],
    occupation_cluster,
    province_th,
    region,
    experience_band,
    education_level
  );

  if (predRow) {
    const baseP50 = Math.round(predRow.pred_p50);
    const uplifts: SkillUpliftItem[] = candidate_skills.map((sk, idx) => {
      const occSkill = seed.occupation_skill_profile.find(
        (r) =>
          r.occupation_cluster === occupation_cluster &&
          r.skill_canonical === sk
      );
      const bump = Math.round(
        baseP50 * Math.max(0.015, Math.min(0.08, (occSkill?.weighted_share ?? 0.2) * 0.12 - idx * 0.005))
      );
      return {
        skill: sk,
        delta_p50: bump,
        new_p50: baseP50 + bump,
      };
    });

    const responseBody: SalaryEstimateResponse = {
      p25: Math.round(predRow.pred_p25),
      p50: baseP50,
      p75: Math.round(predRow.pred_p75),
      model_name:
        predRow.model_name || championRow?.model_name || "Champion (Precomputed)",
      cv_mae: predRow.mae_cv ?? championRow?.mae ?? null,
      cv_mape: predRow.mape_cv ?? championRow?.mape ?? null,
      source: "fallback_prediction",
      badge: "ค่าประมาณที่คำนวณล่วงหน้า (บริการโมเดลกำลังเริ่มต้น)",
      disclaimer: DISCLAIMER_TH,
      n_support: predRow.n_train_support ?? null,
      low_support_warning: (predRow.n_train_support ?? 20) < 10,
      uplifts,
    };
    return NextResponse.json(responseBody);
  }

  // Fallback 2: mart.salary_stats median
  const statRow = findBestSalaryStats(
    seed.salary_stats || [],
    occupation_cluster,
    province_th,
    region,
    experience_band
  );

  const p25 = Math.round(statRow?.salary_p25 ?? 15000);
  const p50 = Math.round(statRow?.salary_p50 ?? 18500);
  const p75 = Math.round(statRow?.salary_p75 ?? 23000);

  const uplifts: SkillUpliftItem[] = candidate_skills.map((sk, idx) => {
    const occSkill = seed.occupation_skill_profile.find(
      (r) =>
        r.occupation_cluster === occupation_cluster && r.skill_canonical === sk
    );
    const bump = Math.round(
      p50 * Math.max(0.015, Math.min(0.07, (occSkill?.weighted_share ?? 0.2) * 0.1 - idx * 0.004))
    );
    return {
      skill: sk,
      delta_p50: bump,
      new_p50: p50 + bump,
    };
  });

  const responseBody: SalaryEstimateResponse = {
    p25,
    p50,
    p75,
    model_name: championRow?.model_name || "Statistical Median Fallback",
    cv_mae: championRow?.mae ?? null,
    cv_mape: championRow?.mape ?? null,
    source: "fallback_median",
    badge: "ค่าสถิติ ไม่ใช่ค่าจากโมเดล (บริการโมเดลยังไม่เชื่อมต่อ)",
    disclaimer: DISCLAIMER_TH,
    n_support: statRow?.n_postings ?? null,
    low_support_warning: (statRow?.n_postings ?? 0) < 10,
    uplifts,
  };

  return NextResponse.json(responseBody);
}
