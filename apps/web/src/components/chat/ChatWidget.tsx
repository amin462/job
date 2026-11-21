"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  AlertCircle,
  MessageSquareText,
  RefreshCw,
  Send,
  Sparkles,
  X,
} from "lucide-react";
import { usePageContext } from "./PageContextProvider";
import { useI18n } from "@/lib/i18n";
import type { ChatApiResponse } from "@/types/marts";

interface ChatItem {
  id: string;
  role: "user" | "assistant" | "notice";
  text: string;
  citedCards?: string[];
  suggestedPages?: Array<{ label: string; href: string }>;
  error?: boolean;
}

function getSuggestedQuestions(pathname: string, locale: "th" | "en"): string[] {
  if (pathname.startsWith("/market")) {
    return locale === "th"
      ? ["ทักษะไหนโตเร็วสุดในช่วงนี้", "ภาคใต้ต่างจากทั้งประเทศอย่างไร", "สรุปตัวชี้วัดหลักบนหน้านี้"]
      : ["Which skills have the highest share right now?", "How do metrics differ by region?", "Summarize the key KPIs on this page"];
  }
  if (pathname.startsWith("/occupations")) {
    return locale === "th"
      ? ["ตำแหน่งนี้ควรเรียนทักษะอะไรก่อน", "ช่วงเงินเดือนของตำแหน่งนี้อยู่ที่เท่าไร"]
      : ["Which top skills should I learn first for this role?", "What is the salary range shown for this role?"];
  }
  if (pathname.startsWith("/skills")) {
    return locale === "th"
      ? ["ทักษะนี้มักมาคู่กับอะไร", "กลุ่มอาชีพไหนขอทักษะนี้มากที่สุด"]
      : ["Which skills co-occur most with this skill?", "Which occupations request this skill most?"];
  }
  if (pathname.startsWith("/salary")) {
    return locale === "th"
      ? ["ทำไมช่วงเงินเดือนกว้างขนาดนี้", "เพิ่มทักษะไหนคุ้มสุด"]
      : ["Why is the salary range this wide?", "Which skill gives the largest uplift?"];
  }
  if (pathname.startsWith("/me/gap") || pathname.startsWith("/me/skills")) {
    return locale === "th"
      ? ["ควรเริ่มเรียนอะไรก่อน", "ทักษะของฉันครอบคลุมตลาดกี่เปอร์เซ็นต์"]
      : ["What missing skill should I learn first?", "What is my current market coverage?"];
  }
  if (pathname.startsWith("/institution/curricula")) {
    return locale === "th"
      ? ["หลักสูตรขาดทักษะสำคัญอะไร", "ทักษะใดที่สอนแต่ตลาดขอน้อย"]
      : ["Which high-demand market skills are missing?", "Which taught skills have lower market demand?"];
  }
  if (pathname.startsWith("/ml-lab")) {
    return locale === "th"
      ? ["ทำไมเลือกโมเดลนี้", "baseline คืออะไร"]
      : ["Why was the champion model selected?", "What is the baseline model?"];
  }
  if (pathname.startsWith("/admin")) {
    return locale === "th"
      ? ["check ไหนไม่ผ่าน", "สรุปรอบ scrape ล่าสุด"]
      : ["Which data quality checks failed?", "Summarize the latest scrape run"];
  }
  return locale === "th"
    ? ["ตอนนี้มีประกาศงานกี่รายการ", "ทักษะยอดนิยมอันดับต้นๆ มีอะไรบ้าง"]
    : ["How many postings are analyzed?", "What are the top requested skills?"];
}

export function ChatWidget() {
  const pathname = usePathname() || "/";
  const { pageContext } = usePageContext();
  const { locale, t } = useI18n();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatItem[]>([]);
  const [lastQuestion, setLastQuestion] = useState<string | null>(null);
  const prevPathRef = useRef<string>(pathname);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const suggestions = useMemo(
    () => getSuggestedQuestions(pathname, locale),
    [pathname, locale]
  );

  // Notice when switching routes so context boundaries stay clear
  useEffect(() => {
    if (prevPathRef.current !== pathname) {
      prevPathRef.current = pathname;
      setMessages((prev) =>
        prev.length > 0
          ? [
              ...prev,
              {
                id: `notice-${Date.now()}`,
                role: "notice",
                text: t("chat.routeChanged"),
              },
            ]
          : prev
      );
    }
  }, [pathname, t]);

  // Close on Esc
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  const sendQuestion = async (questionText: string) => {
    const trimmed = questionText.trim();
    if (!trimmed || loading) return;

    const userMsg: ChatItem = {
      id: `u-${Date.now()}`,
      role: "user",
      text: trimmed,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLastQuestion(trimmed);
    setLoading(true);

    try {
      const ctxToSend = pageContext ?? {
        page: pathname,
        route: pathname,
        title: document.title || "Skill Demand Intelligence",
        kpis: [],
        charts: [],
        dataNotes: ["ตัวอย่างจากประกาศงาน JobThai"],
      };

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: trimmed,
          pageContext: ctxToSend,
          locale,
        }),
      });

      if (res.status === 429) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        setMessages((prev) => [
          ...prev,
          {
            id: `a-${Date.now()}`,
            role: "assistant",
            text: body.error || t("chat.quotaExceeded"),
            error: true,
          },
        ]);
        return;
      }

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = (await res.json()) as ChatApiResponse;
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          text: data.answer,
          citedCards: data.citedCards,
          suggestedPages: data.suggestedPages,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          text: t("chat.errorReply"),
          error: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="no-print">
      {!open ? (
        <button
          type="button"
          onClick={() => {
            setOpen(true);
            setTimeout(() => inputRef.current?.focus(), 60);
          }}
          aria-label={t("chat.title")}
          className="fixed right-4 bottom-20 z-40 flex h-13 w-13 items-center justify-center rounded-full bg-[linear-gradient(135deg,#6C5CE7_0%,#A77BE8_55%,#F0A58C_100%)] text-white shadow-lg transition hover:scale-105 md:right-6 md:bottom-6"
        >
          <Sparkles className="h-6 w-6" aria-hidden="true" />
        </button>
      ) : (
        <aside
          role="dialog"
          aria-label={t("chat.title")}
          className="glass-strong glass fixed inset-x-0 bottom-0 z-50 flex h-[88dvh] flex-col rounded-t-[24px] rounded-b-none p-4 shadow-2xl md:inset-x-auto md:right-6 md:bottom-6 md:h-[560px] md:w-[400px] md:rounded-[20px]"
        >
          <header className="relative z-10 flex items-center justify-between gap-2 border-b border-[var(--border-hairline)] pb-3">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[linear-gradient(135deg,#6C5CE7_0%,#E0623F_100%)] text-white">
                <MessageSquareText className="h-4 w-4" aria-hidden="true" />
              </span>
              <div>
                <h2 className="text-[14px] font-semibold text-[var(--ink-primary)]">
                  {t("chat.title")}
                </h2>
                <p className="text-[11px] text-[var(--ink-muted)]">
                  {pageContext?.title || pathname}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label={t("chat.close")}
              className="flex h-10 w-10 items-center justify-center rounded-xl text-[var(--ink-secondary)] hover:bg-[var(--surface-solid)]"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </header>

          <div className="relative z-10 mt-2 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)]/90 px-3 py-2 text-[11px] leading-relaxed text-[var(--ink-secondary)]">
            {t("chat.disclaimer")}
          </div>

          <div
            aria-live="polite"
            className="relative z-10 mt-3 flex-1 space-y-3 overflow-y-auto pr-1"
          >
            {messages.length === 0 ? (
              <div className="space-y-2">
                <p className="text-[12px] font-medium text-[var(--ink-secondary)]">
                  {locale === "th" ? "คำถามแนะนำสำหรับหน้านี้:" : "Suggested questions:"}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {suggestions.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => sendQuestion(q)}
                      className="min-h-[36px] rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3 py-1.5 text-left text-[12px] font-medium text-[var(--ink-primary)] hover:border-[var(--series-me)] hover:bg-[var(--tint-me)]/50"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {messages.map((m) => {
              if (m.role === "notice") {
                return (
                  <div
                    key={m.id}
                    className="my-2 flex items-center justify-center text-[11px] font-medium text-[var(--ink-muted)]"
                  >
                    <span className="rounded-full bg-[var(--surface-solid)] px-3 py-0.5">
                      — {m.text} —
                    </span>
                  </div>
                );
              }
              if (m.role === "user") {
                return (
                  <div key={m.id} className="flex justify-end">
                    <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-[var(--series-me)] px-3.5 py-2 text-[13px] text-white">
                      {m.text}
                    </div>
                  </div>
                );
              }
              return (
                <div key={m.id} className="flex justify-start">
                  <div className="max-w-[92%] space-y-2 rounded-2xl rounded-bl-sm border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3.5 py-2.5 text-[13px] text-[var(--ink-primary)] shadow-xs">
                    {m.error ? (
                      <div className="flex items-center gap-1.5 font-medium text-[var(--status-critical)]">
                        <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
                        <span>{m.text}</span>
                      </div>
                    ) : (
                      <p className="whitespace-pre-line">{m.text}</p>
                    )}

                    {m.citedCards && m.citedCards.length > 0 ? (
                      <div className="flex flex-wrap gap-1 pt-1">
                        {m.citedCards.map((c) => (
                          <span
                            key={c}
                            className="rounded-md bg-[var(--tint-me)] px-2 py-0.5 text-[11px] font-medium text-[#2F2680]"
                          >
                            {c}
                          </span>
                        ))}
                      </div>
                    ) : null}

                    {m.suggestedPages && m.suggestedPages.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {m.suggestedPages.map((sp) => (
                          <Link
                            key={sp.href}
                            href={sp.href}
                            className="inline-flex items-center rounded-lg border border-[var(--series-me)]/40 px-2.5 py-1 text-[11px] font-semibold text-[var(--series-me)] hover:bg-[var(--tint-me)]"
                          >
                            {sp.label} →
                          </Link>
                        ))}
                      </div>
                    ) : null}

                    {m.error && lastQuestion ? (
                      <button
                        type="button"
                        onClick={() => sendQuestion(lastQuestion)}
                        className="inline-flex items-center gap-1 text-[12px] font-semibold text-[var(--series-me)] hover:underline"
                      >
                        <RefreshCw className="h-3 w-3" aria-hidden="true" />
                        <span>{t("chat.retry")}</span>
                      </button>
                    ) : null}
                  </div>
                </div>
              );
            })}

            {loading ? (
              <div className="flex justify-start">
                <div className="rounded-2xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3.5 py-2 text-[12px] text-[var(--ink-muted)]">
                  {locale === "th" ? "กำลังสรุปจากข้อมูลบนหน้า..." : "Reading page context..."}
                </div>
              </div>
            ) : null}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              sendQuestion(input);
            }}
            className="relative z-10 mt-3 flex items-center gap-2 border-t border-[var(--border-hairline)] pt-2.5"
          >
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t("chat.placeholder")}
              aria-label={t("chat.placeholder")}
              className="min-h-[42px] flex-1 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3 text-[13px] text-[var(--ink-primary)] placeholder:text-[var(--ink-muted)]"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              aria-label={t("chat.send")}
              className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-xl bg-[var(--series-me)] text-white transition hover:opacity-90 disabled:opacity-40"
            >
              <Send className="h-4 w-4" aria-hidden="true" />
            </button>
          </form>
        </aside>
      )}
    </div>
  );
}
