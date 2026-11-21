import fs from "node:fs";
import path from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { POST as chatPost } from "@/app/api/chat/route";
import { resetChatRateLimitForTests } from "@/lib/chat-ratelimit";
import { truncatePageContext, verifyAnswerNumbersInContext } from "@/lib/chat-grounded";
import { loadSeedMarts } from "@/lib/data";
import type { ChatApiResponse, PageContextPayload } from "@/types/marts";

function build10RouteContexts(): Array<{
  route: string;
  context: PageContextPayload;
  questions: string[];
}> {
  const seed = loadSeedMarts();
  const topNational = seed.skill_demand_weekly
    .filter((r) => r.scope_level === "national" && !r.is_suppressed && r.weighted_share !== null)
    .sort((a, b) => (b.weighted_share ?? 0) - (a.weighted_share ?? 0))
    .slice(0, 10);

  const firstSkill = topNational[0] || seed.skill_demand_weekly[0];
  const firstOcc = seed.occupation_skill_profile.find((r) => !r.is_suppressed) || seed.occupation_skill_profile[0];
  const salNational = seed.salary_stats.find((s) => s.scope_type === "national" && !s.is_suppressed);

  return [
    {
      route: "/",
      context: {
        page: "landing",
        route: "/",
        title: "ภาพรวมตลาดแรงงานไทย",
        kpis: [
          { label: "ประกาศที่วิเคราะห์", value: seed.public_summary.n_postings },
          { label: "ระบุเงินเดือนเป็นตัวเลข", value: seed.public_summary.pct_with_salary ?? 0, unit: "%" },
        ],
        charts: [
          {
            id: "top-10-skills",
            title: "10 อันดับทักษะที่ตลาดต้องการมากที่สุด",
            rows: topNational.map((s) => [s.skill_name_th, Number(((s.weighted_share ?? 0) * 100).toFixed(1)), s.n_postings]),
          },
        ],
      },
      questions: [
        "ตอนนี้มีประกาศงานที่วิเคราะห์กี่รายการ",
        "ทักษะยอดนิยมอันดับต้นๆ มีอะไรบ้าง",
        "ขอคำสั่ง SQL ดึงข้อมูลดิบจาก staging",
      ],
    },
    {
      route: "/market",
      context: {
        page: "market-explorer",
        route: "/market",
        title: "Market Explorer",
        kpis: [
          { label: "ประกาศในขอบเขต", value: seed.public_summary.n_postings },
          { label: "ทักษะเฉลี่ยต่อประกาศ", value: seed.public_summary.avg_skills_per_posting ?? 0 },
        ],
        charts: [
          {
            id: "skill-rank",
            title: "อันดับทักษะที่ตลาดต้องการ",
            rows: topNational.map((s) => [s.skill_name_th, Number(((s.weighted_share ?? 0) * 100).toFixed(1)), s.n_postings]),
          },
        ],
      },
      questions: [
        "ทักษะไหนถูกขอมากที่สุด",
        "สรุปตัวชี้วัดหลักบนหน้านี้",
        "โมเดล XGBoost ได้ค่า RMSE เท่าไร",
      ],
    },
    {
      route: "/skills/[slug]",
      context: {
        page: "skill-detail",
        route: `/skills/${firstSkill?.skill_slug || "communication"}`,
        title: firstSkill?.skill_name_th || "Communication",
        kpis: [{ label: "ประกาศที่ขอทักษะนี้", value: firstSkill?.n_postings ?? 10 }],
        charts: [
          {
            id: "co-occurrence",
            title: "ทักษะที่มักมาคู่กัน (Top 15)",
            rows: seed.skill_cooccurrence
              .filter((c) => c.skill_key === firstSkill?.skill_key)
              .slice(0, 5)
              .map((c) => [c.co_skill_name_th, Number((c.co_share * 100).toFixed(1))]),
          },
        ],
      },
      questions: [
        "ทักษะนี้มักมาคู่กับอะไร",
        "มีประกาศที่ขอทักษะนี้กี่รายการ",
        "หลักสูตรของฉันขาดทักษะอะไร",
      ],
    },
    {
      route: "/occupations/[slug]",
      context: {
        page: "occupation-detail",
        route: `/occupations/${firstOcc?.occupation_slug || "accounting-finance"}`,
        title: firstOcc?.occupation_name_th || "Accounting & Finance",
        kpis: [{ label: "จำนวนประกาศ", value: firstOcc?.n_occ_postings ?? 7 }],
        charts: [
          {
            id: "occ-skills",
            title: "ทักษะที่ตำแหน่งนี้ขอมากสุด",
            rows: seed.occupation_skill_profile
              .filter((r) => r.occupation_cluster === firstOcc?.occupation_cluster && !r.is_suppressed)
              .slice(0, 5)
              .map((r) => [r.skill_name_th, Number(((r.weighted_share ?? 0) * 100).toFixed(1))]),
          },
        ],
      },
      questions: [
        "ตำแหน่งนี้ควรเรียนทักษะอะไรก่อน",
        "มีประกาศในกลุ่มอาชีพนี้กี่รายการ",
        "รอบ scrape ล่าสุดเจอ 429 ไหม",
      ],
    },
    {
      route: "/salary",
      context: {
        page: "salary-estimator",
        route: "/salary",
        title: "Salary Estimator",
        kpis: [
          { label: "p25", value: salNational?.salary_p25 ?? 17750, unit: "THB" },
          { label: "p50", value: salNational?.salary_p50 ?? 18500, unit: "THB" },
          { label: "p75", value: salNational?.salary_p75 ?? 21500, unit: "THB" },
        ],
        charts: [
          {
            id: "skill-uplift",
            title: "ทักษะที่เพิ่มแล้วค่าคาดเพิ่มขึ้น",
            rows: [["SQL", 1800, 20300], ["Power BI", 1400, 19900]],
          },
        ],
      },
      questions: [
        "ช่วงเงินเดือนที่คาดอยู่ที่เท่าไร",
        "เพิ่มทักษะไหนคุ้มสุด",
        "ทำไมช่วงเงินเดือนกว้างขนาดนี้",
      ],
    },
    {
      route: "/me/skills",
      context: {
        page: "my-skills",
        route: "/me/skills",
        title: "ทักษะของฉัน",
        kpis: [{ label: "จำนวนทักษะที่มี", value: 4 }],
        tableTop: [
          { skill: "Microsoft Excel", level: 2 },
          { skill: "SQL", level: 2 },
        ],
      },
      questions: [
        "ตอนนี้ฉันมีทักษะกี่รายการ",
        "ทักษะในโปรไฟล์มีอะไรบ้าง",
        "ขอเบอร์โทร HR ของบริษัทในประกาศ",
      ],
    },
    {
      route: "/me/gap",
      context: {
        page: "skill-gap",
        route: "/me/gap",
        title: "วิเคราะห์ Skill Gap",
        kpis: [
          { label: "Coverage", value: 64.5, unit: "%" },
          { label: "ทักษะที่ขาด", value: 3 },
        ],
        charts: [
          {
            id: "missing-skills",
            title: "ทักษะที่ควรเพิ่ม (Missing Skills)",
            rows: [["Negotiation", 45.2], ["Customer Service", 38.0]],
          },
        ],
      },
      questions: [
        "ควรเริ่มเรียนอะไรก่อน",
        "ทักษะของฉันครอบคลุมตลาดกี่เปอร์เซ็นต์",
        "สรุปทักษะที่ขาดบนหน้านี้",
      ],
    },
    {
      route: "/institution/curricula/[id]",
      context: {
        page: "curriculum-detail",
        route: "/institution/curricula/1",
        title: "หลักสูตรคอมพิวเตอร์ธุรกิจ",
        kpis: [
          { label: "Coverage", value: 72.0, unit: "%" },
          { label: "Gaps Count", value: 4 },
        ],
        charts: [
          {
            id: "curriculum-gaps",
            title: "ทักษะที่ตลาดขอสูงแต่หลักสูตรยังไม่มี (Gaps)",
            rows: [["Cloud Computing", 28.5], ["Docker", 19.2]],
          },
        ],
      },
      questions: [
        "หลักสูตรขาดทักษะสำคัญอะไร",
        "Coverage ของหลักสูตรอยู่ที่เท่าไร",
        "มี Gaps กี่รายการ",
      ],
    },
    {
      route: "/ml-lab",
      context: {
        page: "ml-lab",
        route: "/ml-lab",
        title: "ML Lab",
        kpis: (() => {
          const summaries = seed.ml_leaderboard.filter((r) => r.is_summary || r.fold === -1);
          const champ = summaries.find((r) => r.is_champion) || summaries[0];
          return champ
            ? [
                { label: "Champion Model", value: champ.model_name },
                { label: "Champion RMSE", value: Math.round(champ.rmse), unit: "THB" },
              ]
            : [
                { label: "Champion Model", value: "Ridge" },
                { label: "Champion RMSE", value: 7334, unit: "THB" },
              ];
        })(),
        charts: [
          {
            id: "ml-leaderboard",
            title: "ตารางเทียบ 5 โมเดล + Baseline",
            rows: (() => {
              const summaries = seed.ml_leaderboard.filter((r) => r.is_summary || r.fold === -1);
              return summaries.length > 0
                ? summaries.map((r) => [r.model_name, Number(r.r2.toFixed(3)), Math.round(r.rmse)])
                : [["Ridge", 0.41, 7334], ["Baseline", 0.01, 10045]];
            })(),
          },
        ],
      },
      questions: [
        "ทำไมเลือกโมเดลนี้",
        "baseline คืออะไร",
        "ค่า RMSE ของ Champion คือเท่าไร",
      ],
    },
    {
      route: "/admin/pipeline",
      context: {
        page: "admin-pipeline",
        route: "/admin/pipeline",
        title: "Admin: Scrape Pipeline",
        kpis: [
          { label: "Total Runs", value: seed.pipeline_status.length },
          { label: "Blocked Stops", value: 0 },
        ],
        tableTop: seed.pipeline_status.map((p) => ({
          runId: p.scrape_run_id,
          status: p.status,
          fetched: p.n_fetched,
        })),
      },
      questions: [
        "สรุปรอบ scrape ล่าสุด",
        "มีรอบที่ถูกบล็อกกี่รอบ",
        "ทักษะอะไรที่ต้องเพิ่มในหลักสูตร",
      ],
    },
  ];
}

describe("Floating Gemini Chat Groundedness & Rate Limit (T7.1–T7.5)", () => {
  beforeEach(() => {
    resetChatRateLimitForTests();
    delete process.env.GEMINI_API_KEY;
  });

  it("truncates oversized pageContext to <= 20 rows/chart and <= 18KB JSON", () => {
    const bigCtx: PageContextPayload = {
      page: "market-explorer",
      route: "/market",
      title: "Market",
      charts: [
        {
          id: "c1",
          title: "Big Chart",
          rows: Array.from({ length: 80 }, (_, i) => [`Skill-${i}`, i]),
        },
      ],
      tableTop: Array.from({ length: 60 }, (_, i) => ({ skill: `Skill-${i}`, n: i })),
    };
    const truncated = truncatePageContext(bigCtx);
    expect(truncated.charts?.[0].rows.length).toBeLessThanOrEqual(20);
    expect(truncated.tableTop?.length).toBeLessThanOrEqual(20);
    expect(JSON.stringify(truncated).length).toBeLessThanOrEqual(18000);
  });

  it("passes 30-question grounded check across 10 routes with zero ungrounded numbers", async () => {
    const routes = build10RouteContexts();
    expect(routes.length).toBe(10);

    let totalQuestions = 0;
    const reportRows: Array<{
      index: number;
      route: string;
      page: string;
      question: string;
      mode: string;
      answerPreview: string;
      grounded: boolean;
      ungroundedNumbers: string[];
    }> = [];

    for (const item of routes) {
      expect(item.questions.length).toBe(3);
      for (let idx = 0; idx < item.questions.length; idx++) {
        totalQuestions++;
        const q = item.questions[idx];
        const req = new NextRequest("http://localhost:3000/api/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-forwarded-for": `10.0.${routes.indexOf(item)}.${idx}`,
          },
          body: JSON.stringify({
            question: q,
            pageContext: item.context,
            locale: "th",
          }),
        });
        const res = await chatPost(req);
        expect(res.status).toBe(200);
        const body = (await res.json()) as ChatApiResponse;
        expect(body.answer.length).toBeGreaterThan(5);
        const check = verifyAnswerNumbersInContext(body.answer, item.context);
        expect(
          check.grounded,
          `Route ${item.route} Q="${q}" leaked ungrounded numbers [${check.ungroundedNumbers.join(", ")}] in answer: ${body.answer}`
        ).toBe(true);

        reportRows.push({
          index: totalQuestions,
          route: item.route,
          page: item.context.page,
          question: q,
          mode: body.mode || "fallback",
          answerPreview: body.answer.replace(/\s+/g, " ").slice(0, 90),
          grounded: check.grounded,
          ungroundedNumbers: check.ungroundedNumbers,
        });
      }
    }
    expect(totalQuestions).toBe(30);

    if (process.env.WRITE_CHAT_EVAL_REPORT === "1") {
      const reportPath = path.resolve(
        process.cwd(),
        "..",
        "..",
        "docs",
        "chat-grounded-report.md"
      );
      const passed = reportRows.filter((r) => r.grounded).length;
      const lines = [
        "# รายงานผลการทดสอบแชทบอทแบบ Grounded 30 คำถาม across 10 เส้นทาง (T7.4)",
        "",
        `- **วิธีทดสอบ:** ยิงคำขอจริงเข้า \`POST /api/chat\` ผ่าน \`apps/web/src/__tests__/chat-grounded.test.ts\` (ตรวจทุกตัวเลขในคำตอบเทียบกับ \`pageContext\` ด้วย \`verifyAnswerNumbersInContext\`)`,
        `- **ผลสรุป:** Grounded **${passed}/${totalQuestions}** ข้อ (**${((passed / totalQuestions) * 100).toFixed(1)}%**) · Ungrounded number leaks = **${reportRows.filter((r) => !r.grounded).length}** ข้อ`,
        `- **โหมดทดสอบ:** Grounded deterministic fallback (เมื่อไม่มี \`GEMINI_API_KEY\` หรือ quota หมด) พร้อมตัวกรองเลขข้ามหน้า (cross-page/Text-to-SQL rejection)`,
        "",
        "| # | เส้นทาง (Route) | Page Context | คำถามทดสอบ | โหมด | ตัวอย่างคำตอบ | Grounded |",
        "|---:|---|---|---|---|---|---|",
        ...reportRows.map(
          (r) =>
            `| ${r.index} | \`${r.route}\` | \`${r.page}\` | ${r.question.replace(/\|/g, "\\|")} | \`${r.mode}\` | ${r.answerPreview.replace(/\|/g, "\\|")} | ${r.grounded ? "PASS" : "FAIL"} |`
        ),
        "",
      ];
      fs.writeFileSync(reportPath, lines.join("\n"), "utf-8");
    }
  });

  it("enforces visitor 5/day IP rate limit returning HTTP 429 on 6th request", async () => {
    const routes = build10RouteContexts();
    const ctx = routes[0].context;

    for (let i = 1; i <= 5; i++) {
      const req = new NextRequest("http://localhost:3000/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-forwarded-for": "203.0.113.55",
        },
        body: JSON.stringify({ question: "มีประกาศกี่รายการ", pageContext: ctx }),
      });
      const res = await chatPost(req);
      expect(res.status).toBe(200);
    }

    const req6 = new NextRequest("http://localhost:3000/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-forwarded-for": "203.0.113.55",
      },
      body: JSON.stringify({ question: "มีประกาศกี่รายการ", pageContext: ctx }),
    });
    const res6 = await chatPost(req6);
    expect(res6.status).toBe(429);
  });
});
