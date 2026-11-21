import type { ChatApiResponse, Locale, PageContextPayload } from "@/types/marts";

const MAX_CHART_ROWS = 20;
const MAX_TABLE_ROWS = 20;
const MAX_JSON_CHARS = 18000; // <= ~6,000 tokens conservative budget

export function truncatePageContext(ctx: PageContextPayload): PageContextPayload {
  const charts = (ctx.charts || []).map((ch) => ({
    id: ch.id,
    title: ch.title,
    rows: (ch.rows || []).slice(0, MAX_CHART_ROWS),
  }));
  let tableTop = (ctx.tableTop || []).slice(0, MAX_TABLE_ROWS);

  const result: PageContextPayload = {
    page: ctx.page,
    route: ctx.route,
    title: ctx.title,
    filters: ctx.filters ?? {},
    kpis: (ctx.kpis || []).slice(0, 12),
    charts,
    tableTop,
    asOf: ctx.asOf,
    dataNotes: (ctx.dataNotes || []).slice(0, 8),
  };

  let json = JSON.stringify(result);
  while (json.length > MAX_JSON_CHARS && result.charts && result.charts.length > 0) {
    const longest = result.charts.reduce((best, cur) =>
      cur.rows.length > best.rows.length ? cur : best
    );
    if (longest.rows.length > 5) {
      longest.rows = longest.rows.slice(0, Math.floor(longest.rows.length * 0.75));
    } else if (tableTop.length > 5) {
      tableTop = tableTop.slice(0, Math.floor(tableTop.length * 0.75));
      result.tableTop = tableTop;
    } else {
      break;
    }
    json = JSON.stringify(result);
  }

  return result;
}

export function buildGeminiSystemPrompt(locale: Locale): string {
  if (locale === "en") {
    return [
      "You are the Skill Demand Intelligence data assistant.",
      "STRICT RULES:",
      "1. Answer ONLY using facts and numbers explicitly present in the provided pageContext JSON.",
      "2. ALWAYS cite the card titles or KPI labels from pageContext that support your answer.",
      "3. NEVER invent, extrapolate, estimate, or compute new numbers that are not explicitly in pageContext.",
      "4. NEVER generate SQL (no Text-to-SQL) and NEVER reveal raw job descriptions or personal/HR contacts.",
      "5. If the question cannot be answered from the current pageContext, clearly say the information is not on this page and suggest the appropriate page route (e.g. /market, /salary, /me/gap, /ml-lab, /institution/curricula).",
      "6. Keep answers concise, clear, and polite in English.",
    ].join("\n");
  }

  return [
    "คุณคือผู้ช่วยอธิบายข้อมูลของระบบ Skill Demand Intelligence",
    "กติกาบังคับ (ห้ามฝ่าฝืน):",
    "1. ตอบเป็นภาษาไทยโดยใช้ข้อมูลและตัวเลขที่ปรากฏอยู่ใน pageContext JSON ของหน้าปัจจุบันเท่านั้น",
    "2. อ้างถึงชื่อการ์ดหรือหัวข้อ KPI จาก pageContext ที่ใช้ประกอบคำตอบเสมอ",
    "3. ห้ามแต่งตัวเลขใหม่ ห้ามคำนวณหรือคาดเดาตัวเลขที่ไม่มีอยู่ใน pageContext โดยเด็ดขาด",
    "4. ห้ามเขียนคำสั่ง SQL (ไม่มี Text-to-SQL) และห้ามตอบข้อมูลรายบุคคล/HR/เนื้อหาประกาศ",
    "5. หากข้อมูลที่ถามไม่ได้แสดงอยู่บนหน้านี้ ให้แจ้งอย่างสุภาพว่าหน้านี้ไม่มีข้อมูลดังกล่าว พร้อมแนะนำหน้าที่เกี่ยวข้อง (เช่น /market, /salary, /me/gap, /ml-lab, /institution/curricula)",
    "6. ตอบกระชับ ชัดเจน และเป็นมิตร",
  ].join("\n");
}

function getSuggestedRedirect(
  q: string,
  currentPage: string,
  locale: Locale
): { label: string; href: string } | null {
  const lower = q.toLowerCase();

  if (
    (lower.includes("เงินเดือน") || lower.includes("salary") || lower.includes("ประมาณ") || lower.includes("ค่าคาด")) &&
    !currentPage.includes("salary") &&
    !currentPage.includes("skill") &&
    !currentPage.includes("occupation")
  ) {
    return {
      label: locale === "th" ? "ไปยังหน้าประมาณเงินเดือน (/salary)" : "Go to Salary Estimator (/salary)",
      href: "/salary",
    };
  }
  if (
    (lower.includes("ขาดทักษะ") || lower.includes("skill gap") || lower.includes("ทักษะของฉัน") || lower.includes("my skill")) &&
    !currentPage.includes("gap") &&
    !currentPage.includes("my-skills")
  ) {
    return {
      label: locale === "th" ? "ไปยังหน้าวิเคราะห์ Skill Gap (/me/gap)" : "Go to Skill Gap (/me/gap)",
      href: "/me/gap",
    };
  }
  if (
    (lower.includes("หลักสูตร") || lower.includes("รายวิชา") || lower.includes("curriculum")) &&
    !currentPage.includes("curric")
  ) {
    return {
      label: locale === "th" ? "ไปยังหน้าเทียบหลักสูตร (/institution/curricula)" : "Go to Curriculum Alignment (/institution/curricula)",
      href: "/institution/curricula",
    };
  }
  if (
    (lower.includes("xgboost") || lower.includes("lightgbm") || lower.includes("catboost") || lower.includes("leaderboard") || lower.includes("baseline") || lower.includes("groupkfold") || lower.includes("โมเดล")) &&
    !currentPage.includes("ml-lab") &&
    !currentPage.includes("salary")
  ) {
    return {
      label: locale === "th" ? "ไปยังหน้า ML Lab (/ml-lab)" : "Go to ML Lab (/ml-lab)",
      href: "/ml-lab",
    };
  }
  if (
    (lower.includes("scrape") || lower.includes("dq") || lower.includes("quality") || lower.includes("alias") || lower.includes("403") || lower.includes("429")) &&
    !currentPage.includes("admin")
  ) {
    return {
      label: locale === "th" ? "ไปยังหน้า Admin Pipeline (/admin/pipeline)" : "Go to Admin Pipeline (/admin/pipeline)",
      href: "/admin/pipeline",
    };
  }
  if (
    (lower.includes("ตลาด") || lower.includes("ภาคใต้") || lower.includes("จังหวัด") || lower.includes("market")) &&
    !currentPage.includes("market") &&
    !currentPage.includes("landing") &&
    !currentPage.includes("salary")
  ) {
    return {
      label: locale === "th" ? "ไปยังหน้า Market Explorer (/market)" : "Go to Market Explorer (/market)",
      href: "/market",
    };
  }

  return null;
}

export function generateGroundedFallback(
  question: string,
  rawCtx: PageContextPayload,
  locale: Locale = "th"
): ChatApiResponse {
  const ctx = truncatePageContext(rawCtx);
  const q = question.trim();
  const qLower = q.toLowerCase();

  // Block SQL / raw text / PII requests explicitly
  if (
    qLower.includes("select ") ||
    qLower.includes("sql") && qLower.includes("query") ||
    qLower.includes("เบอร์โทร") ||
    qLower.includes("อีเมล hr") ||
    qLower.includes("ข้อความประกาศเต็ม")
  ) {
    return {
      answer:
        locale === "th"
          ? "ระบบไม่รองรับการสร้างคำสั่ง SQL (Text-to-SQL) และไม่แสดงข้อความประกาศเต็มหรือข้อมูลผู้ติดต่อ HR เพื่อปฏิบัติตาม ToS และ PDPA ครับ สามารถดูสถิติรวมได้จากการ์ดบนหน้านี้"
          : "Text-to-SQL, full posting descriptions, and HR contact details are strictly disabled under ToS/PDPA rules. Please refer to the aggregate cards on this page.",
      citedCards: [],
      suggestedPages: [{ label: locale === "th" ? "ความเป็นส่วนตัว (/privacy)" : "Privacy (/privacy)", href: "/privacy" }],
      mode: "grounded-fallback",
    };
  }

  // Redirect if clearly asking about another page's domain
  const redirect = getSuggestedRedirect(q, ctx.page, locale);
  const hasRelevantChart = (ctx.charts || []).some((c) => {
    const t = c.title.toLowerCase();
    return (
      (qLower.includes("เงินเดือน") && t.includes("เงินเดือน")) ||
      (qLower.includes("โมเดล") && (t.includes("โมเดล") || t.includes("champion") || t.includes("leaderboard"))) ||
      (qLower.includes("ทักษะ") && t.includes("ทักษะ"))
    );
  });

  if (redirect && !hasRelevantChart && !qLower.includes("ทั้งหมด") && !qLower.includes("ภาพรวม")) {
    return {
      answer:
        locale === "th"
          ? `หน้านี้ (${ctx.title}) ไม่ได้แสดงรายละเอียดดังกล่าวโดยตรง แนะนำให้เปิดดูข้อมูลเพิ่มเติมที่ ${redirect.label}`
          : `This page (${ctx.title}) does not directly display that breakdown. Please check ${redirect.label}.`,
      citedCards: [],
      suggestedPages: [redirect],
      mode: "grounded-fallback",
    };
  }

  const citedCards: string[] = [];
  const parts: string[] = [];

  if (ctx.kpis && ctx.kpis.length > 0) {
    const kpiSummary = ctx.kpis
      .slice(0, 4)
      .filter((k) => k.value !== null && k.value !== undefined)
      .map((k) => `${k.label}: ${k.value}${k.unit ? ` ${k.unit}` : ""}`)
      .join(" · ");
    if (kpiSummary) {
      parts.push(
        locale === "th"
          ? `จากตัวชี้วัดหลักบนหน้า "${ctx.title}": ${kpiSummary}`
          : `From key metrics on "${ctx.title}": ${kpiSummary}`
      );
      citedCards.push(ctx.title);
    }
  }

  const charts = ctx.charts || [];
  if (charts.length > 0) {
    // Score charts by token overlap with question
    const scored = charts.map((ch) => {
      const titleLower = ch.title.toLowerCase();
      let score = 0;
      for (const word of qLower.split(/\s+/)) {
        if (word.length >= 2 && titleLower.includes(word)) score += 3;
      }
      if (qLower.includes("แนวโน้ม") || qLower.includes("trend") || qLower.includes("โต")) {
        if (ch.id.includes("trend") || ch.id.includes("volume") || titleLower.includes("แนวโน้ม")) score += 4;
      }
      if (qLower.includes("คู่") || qLower.includes("co-occur")) {
        if (ch.id.includes("co") || titleLower.includes("คู่")) score += 4;
      }
      if (qLower.includes("ขาด") || qLower.includes("gap")) {
        if (ch.id.includes("gap") || ch.id.includes("missing") || titleLower.includes("ขาด")) score += 4;
      }
      if (qLower.includes("เงินเดือน") || qLower.includes("salary") || qLower.includes("คุ้ม")) {
        if (ch.id.includes("salary") || ch.id.includes("uplift") || titleLower.includes("เงินเดือน")) score += 4;
      }
      if (qLower.includes("check") || qLower.includes("ผ่าน") || qLower.includes("dq")) {
        if (ch.id.includes("dq") || titleLower.includes("คุณภาพ")) score += 4;
      }
      return { ch, score };
    });

    scored.sort((a, b) => b.score - a.score);
    const topCharts = scored.slice(0, 2).map((s) => s.ch);

    for (const ch of topCharts) {
      if (ch.rows.length === 0) continue;
      citedCards.push(ch.title);
      const previewRows = ch.rows
        .slice(0, 5)
        .map((r) => r.filter((cell) => cell !== null && cell !== undefined).join(": "))
        .join(" | ");
      parts.push(
        locale === "th"
          ? `การ์ด "${ch.title}" แสดง: ${previewRows}`
          : `Card "${ch.title}" shows: ${previewRows}`
      );
    }
  }

  if (parts.length === 0 && ctx.tableTop && ctx.tableTop.length > 0) {
    const rowsText = ctx.tableTop
      .slice(0, 3)
      .map((row) =>
        Object.entries(row)
          .filter(([, v]) => v !== null && v !== undefined)
          .slice(0, 4)
          .map(([k, v]) => `${k}=${v}`)
          .join(", ")
      )
      .join(" | ");
    parts.push(
      locale === "th"
        ? `ข้อมูลตารางบนหน้า "${ctx.title}": ${rowsText}`
        : `Table summary on "${ctx.title}": ${rowsText}`
    );
    citedCards.push(ctx.title);
  }

  if (ctx.dataNotes && ctx.dataNotes.length > 0) {
    parts.push(
      locale === "th"
        ? `หมายเหตุข้อมูล: ${ctx.dataNotes[0]}`
        : `Data note: ${ctx.dataNotes[0]}`
    );
  }

  if (parts.length === 0) {
    return {
      answer:
        locale === "th"
          ? `หน้านี้ (${ctx.title}) ยังไม่มีตัวเลขสรุปเพียงพอสำหรับตอบคำถามนี้ (อาจถูกซ่อนเนื่องจาก n < 5 หรือยังไม่ได้คำนวณ)`
          : `This page (${ctx.title}) does not currently display enough aggregate rows to answer this question (n < 5 suppression or empty state).`,
      citedCards: [],
      suggestedPages: [{ label: locale === "th" ? "ตลาดทักษะ (/market)" : "Market Explorer (/market)", href: "/market" }],
      mode: "grounded-fallback",
    };
  }

  return {
    answer: parts.join("\n"),
    citedCards: Array.from(new Set(citedCards)),
    suggestedPages: redirect ? [redirect] : [],
    mode: "grounded-fallback",
  };
}

/**
 * Extracts all numeric tokens from text (ignoring dates formatted YYYY-MM-DD or common Thai/EN numbers)
 * and checks whether each number appears in the serialized pageContext.
 */
export function verifyAnswerNumbersInContext(
  answer: string,
  ctx: PageContextPayload
): { grounded: boolean; ungroundedNumbers: string[] } {
  const ctxString = JSON.stringify(ctx);
  // Extract numbers inside ctxString as normalized strings (remove commas)
  const ctxNumbers = new Set<string>();
  const ctxMatches = ctxString.match(/-?\d+(?:\.\d+)?/g) || [];
  for (const m of ctxMatches) {
    ctxNumbers.add(m);
    ctxNumbers.add(String(Number(m)));
    const num = Number(m);
    if (!Number.isNaN(num)) {
      // Also allow percentage representation of share (e.g. 0.4755 -> 47.6 or 47.55)
      if (num > 0 && num <= 1) {
        ctxNumbers.add((num * 100).toFixed(1));
        ctxNumbers.add((num * 100).toFixed(0));
      }
    }
  }

  // Also check Buddhist Era equivalents of CE years in ctxString
  for (const m of ctxMatches) {
    const n = Number(m);
    if (n >= 2020 && n <= 2035) {
      ctxNumbers.add(String(n + 543));
    }
  }

  // Standard policy constants explicitly in system messages (n < 5, 20/day, 5/day)
  const policyConstants = new Set(["5", "20", "403", "429"]);

  const answerClean = answer.replace(/(\d),(\d)/g, "$1$2");
  const ansMatches = answerClean.match(/(?<!\d)-?\d+(?:\.\d+)?/g) || [];
  const ungrounded: string[] = [];

  for (const raw of ansMatches) {
    const normalized = String(Number(raw));
    if (ctxNumbers.has(raw) || ctxNumbers.has(normalized) || policyConstants.has(raw)) {
      continue;
    }
    ungrounded.push(raw);
  }

  return {
    grounded: ungrounded.length === 0,
    ungroundedNumbers: ungrounded,
  };
}
