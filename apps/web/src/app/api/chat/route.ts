import { NextResponse, type NextRequest } from "next/server";
import { getCurrentSession, getDemoStore } from "@/lib/auth";
import {
  buildGeminiSystemPrompt,
  generateGroundedFallback,
  truncatePageContext,
  verifyAnswerNumbersInContext,
} from "@/lib/chat-grounded";
import { checkAndConsumeChatQuota } from "@/lib/chat-ratelimit";
import { isSupabaseConfigured } from "@/lib/supabase/config";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import type { ChatApiResponse, Locale, PageContextPayload } from "@/types/marts";

function getGeminiConfig() {
  const apiKey = process.env.GEMINI_API_KEY?.trim() || "";
  const model = process.env.GEMINI_MODEL?.trim() || "gemini-2.5-flash";
  const valid = Boolean(apiKey && !apiKey.includes("your-gemini-api-key"));
  return { apiKey, model, valid };
}

async function logChatQuestion(params: {
  userId: string | null;
  page: string;
  question: string;
  answered: boolean;
}) {
  if (isSupabaseConfigured()) {
    try {
      const supabase = await createSupabaseServerClient();
      if (supabase) {
        await supabase.from("app_chat_log").insert({
          user_id: params.userId,
          page: params.page,
          question: params.question.slice(0, 400),
          answered: params.answered,
        });
        return;
      }
    } catch {
      // fall through to demo store log
    }
  }

  const store = getDemoStore();
  store.chatLogs.unshift({
    chat_id: Date.now(),
    user_id: params.userId,
    page: params.page,
    question: params.question.slice(0, 400),
    answered: params.answered,
    created_at: new Date().toISOString(),
  });
  store.chatLogs = store.chatLogs.slice(0, 100);
}

export async function POST(request: NextRequest) {
  let body: {
    question?: string;
    pageContext?: PageContextPayload;
    locale?: Locale;
  };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const question = String(body.question || "").trim();
  if (!question) {
    return NextResponse.json({ error: "Question is required" }, { status: 400 });
  }
  if (!body.pageContext || typeof body.pageContext !== "object") {
    return NextResponse.json(
      { error: "pageContext is required" },
      { status: 400 }
    );
  }

  const locale: Locale = body.locale === "en" ? "en" : "th";
  const session = await getCurrentSession();

  const forwarded = request.headers.get("x-forwarded-for");
  const ip =
    forwarded?.split(",")[0]?.trim() ||
    request.headers.get("x-real-ip") ||
    "127.0.0.1";

  const quotaKey = session ? `user:${session.user_id}` : `ip:${ip}`;
  const quota = checkAndConsumeChatQuota({
    key: quotaKey,
    isAuthenticated: Boolean(session),
  });

  if (!quota.allowed) {
    return NextResponse.json(
      {
        error:
          locale === "th"
            ? `ใช้โควตาวันนี้ครบแล้ว (${quota.limit} ครั้ง/วัน)`
            : `Daily chat quota reached (${quota.limit} questions/day)`,
      },
      { status: 429 }
    );
  }

  const safeContext = truncatePageContext(body.pageContext);
  const { apiKey, model, valid } = getGeminiConfig();

  let result: ChatApiResponse | null = null;

  if (valid) {
    try {
      const systemPrompt = buildGeminiSystemPrompt(locale);
      const userPrompt = `pageContext:\n${JSON.stringify(safeContext)}\n\nQuestion: ${question}\nReturn JSON with keys: {"answer": string, "citedCards": string[], "suggestedPages": [{"label": string, "href": string}]}`;

      const res = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(
          model
        )}:generateContent?key=${encodeURIComponent(apiKey)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            systemInstruction: { parts: [{ text: systemPrompt }] },
            contents: [{ role: "user", parts: [{ text: userPrompt }] }],
            generationConfig: {
              temperature: 0.1,
              responseMimeType: "application/json",
            },
          }),
          signal: AbortSignal.timeout(9000),
          cache: "no-store",
        }
      );

      if (res.ok) {
        const json = (await res.json()) as {
          candidates?: Array<{
            content?: { parts?: Array<{ text?: string }> };
          }>;
        };
        const rawText = json.candidates?.[0]?.content?.parts?.[0]?.text || "";
        const parsed = JSON.parse(rawText) as {
          answer?: string;
          citedCards?: string[];
          suggestedPages?: Array<{ label: string; href: string }>;
        };
        if (parsed.answer) {
          const check = verifyAnswerNumbersInContext(parsed.answer, safeContext);
          if (check.grounded) {
            result = {
              answer: parsed.answer,
              citedCards: Array.isArray(parsed.citedCards)
                ? parsed.citedCards
                : [],
              suggestedPages: Array.isArray(parsed.suggestedPages)
                ? parsed.suggestedPages
                : [],
              mode: "gemini",
            };
          }
        }
      }
    } catch {
      // Fall back deterministically when Gemini errors, times out, or quota is exhausted (T7.5)
    }
  }

  if (!result) {
    result = generateGroundedFallback(question, safeContext, locale);
  }

  await logChatQuestion({
    userId: session?.user_id ?? null,
    page: safeContext.page,
    question,
    answered: Boolean(result.answer),
  });

  return NextResponse.json(result);
}
