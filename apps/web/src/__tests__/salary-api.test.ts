import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET as salaryGet, POST as salaryPost } from "@/app/api/salary/estimate/route";
import type { SalaryEstimateResponse } from "@/types/marts";

describe("/api/salary/estimate Proxy, Fairness & Fallback (T5.12, D6, D19)", () => {
  afterEach(() => {
    delete process.env.ML_API_URL;
    delete process.env.ML_API_KEY;
    vi.restoreAllMocks();
  });

  it("rejects HTTP 400 when forbidden gender, age, or company_name fields are sent", async () => {
    for (const forbidden of ["gender", "age", "company_name"]) {
      const req = new NextRequest("http://localhost:3000/api/salary/estimate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          occupation_cluster: "Sales & Business Development",
          province_th: "กรุงเทพมหานคร",
          experience_band: "1-2 ปี",
          education_level: "ปริญญาตรี",
          employment_type: "FULL_TIME",
          skills: ["Microsoft Excel"],
          [forbidden]: "invalid",
        }),
      });
      const res = await salaryPost(req);
      expect(res.status).toBe(400);
    }
  });

  it("handles GET ?warm=1 pre-warm cleanly when ML_API_URL is unset or reachable", async () => {
    const req = new NextRequest("http://localhost:3000/api/salary/estimate?warm=1");
    const res = await salaryGet(req);
    expect(res.status).toBe(200);
    const body = (await res.json()) as { configured: boolean };
    expect(body.configured).toBe(false);
  });

  it("falls back automatically to mart median/prediction when ML_API_URL is unset", async () => {
    const req = new NextRequest("http://localhost:3000/api/salary/estimate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        occupation_cluster: "Sales & Business Development",
        province_th: "กรุงเทพมหานคร",
        experience_band: "1-2 ปี",
        education_level: "ปริญญาตรี",
        employment_type: "FULL_TIME",
        skills: ["Communication"],
        candidate_skills: ["Microsoft Excel", "Negotiation"],
      }),
    });
    const res = await salaryPost(req);
    expect(res.status).toBe(200);
    const data = (await res.json()) as SalaryEstimateResponse;
    expect(data.p25).toBeGreaterThan(0);
    expect(data.p50).toBeGreaterThanOrEqual(data.p25);
    expect(data.p75).toBeGreaterThanOrEqual(data.p50);
    expect(data.source === "fallback_prediction" || data.source === "fallback_median").toBe(true);
    expect(data.uplifts.length).toBe(2);
  });

  it("proxies /predict and /predict/batch with X-ML-Key header when ML_API_URL is configured", async () => {
    process.env.ML_API_URL = "https://mock-ml-api.example.com";
    process.env.ML_API_KEY = "test-secret-key";

    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      const headers = init?.headers as Record<string, string> | undefined;
      expect(headers?.["X-ML-Key"]).toBe("test-secret-key");

      if (url.endsWith("/predict/batch")) {
        return new Response(
          JSON.stringify({ predictions: [{ p50: 27000 }, { p50: 26200 }] }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response(
        JSON.stringify({
          p25: 21000,
          p50: 24500,
          p75: 29000,
          model_name: "CatBoost",
          cv_mae: 3200,
          cv_mape: 14.2,
          n_support: 42,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    });

    const req = new NextRequest("http://localhost:3000/api/salary/estimate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        occupation_cluster: "Data & Analytics",
        province_th: "สงขลา",
        experience_band: "1-2 ปี",
        education_level: "ปริญญาตรี",
        employment_type: "FULL_TIME",
        skills: ["Microsoft Excel"],
        candidate_skills: ["SQL", "Python"],
      }),
    });
    const res = await salaryPost(req);
    expect(res.status).toBe(200);
    const data = (await res.json()) as SalaryEstimateResponse;
    expect(data.source).toBe("ml-api");
    expect(data.badge).toContain("คำนวณสดจากโมเดล Champion");
    expect(data.p50).toBe(24500);
    expect(data.uplifts).toEqual([
      { skill: "SQL", delta_p50: 2500, new_p50: 27000 },
      { skill: "Python", delta_p50: 1700, new_p50: 26200 },
    ]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
