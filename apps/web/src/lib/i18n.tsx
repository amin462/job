"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import thMessages from "../../messages/th.json";
import enMessages from "../../messages/en.json";
import type { Locale } from "@/types/marts";

const DICTIONARIES: Record<Locale, typeof thMessages> = {
  th: thMessages,
  en: enMessages,
};

interface I18nContextValue {
  locale: Locale;
  setLocale: (loc: Locale) => void;
  glassOff: boolean;
  setGlassOff: (off: boolean) => void;
  t: (path: string) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

const THAI_MONTHS_SHORT = [
  "ม.ค.",
  "ก.พ.",
  "มี.ค.",
  "เม.ย.",
  "พ.ค.",
  "มิ.ย.",
  "ก.ค.",
  "ส.ค.",
  "ก.ย.",
  "ต.ค.",
  "พ.ย.",
  "ธ.ค.",
];

const EN_MONTHS_SHORT = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

export function formatDateByLocale(dateStr: string | null | undefined, locale: Locale): string {
  if (!dateStr) return "—";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(dateStr));
  if (!match) return String(dateStr);
  const year = Number(match[1]);
  const monthIdx = Number(match[2]) - 1;
  const day = Number(match[3]);
  if (monthIdx < 0 || monthIdx > 11) return String(dateStr);
  if (locale === "th") {
    const beYear = year < 2400 ? year + 543 : year;
    return `${day} ${THAI_MONTHS_SHORT[monthIdx]} ${beYear}`;
  }
  const ceYear = year > 2400 ? year - 543 : year;
  return `${day} ${EN_MONTHS_SHORT[monthIdx]} ${ceYear}`;
}

export function formatBaht(val: number | null | undefined): string {
  if (val === null || val === undefined || Number.isNaN(val)) return "—";
  return `฿${Math.round(val).toLocaleString("en-US")}`;
}

export function formatPercent(share: number | null | undefined, isAlreadyPct = false): string {
  if (share === null || share === undefined || Number.isNaN(share)) return "—";
  const pct = isAlreadyPct ? share : share * 100;
  return `${pct.toFixed(1)}%`;
}

export function I18nProvider({
  children,
  initialLocale = "th",
}: {
  children: React.ReactNode;
  initialLocale?: Locale;
}) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);
  const [glassOff, setGlassOffState] = useState<boolean>(false);

  useEffect(() => {
    try {
      const savedLocale = localStorage.getItem("skillbi_locale") as Locale | null;
      if (savedLocale === "th" || savedLocale === "en") {
        setLocaleState(savedLocale);
        document.documentElement.lang = savedLocale;
      }
      const savedGlass = localStorage.getItem("skillbi_glass_off");
      if (savedGlass === "true") {
        setGlassOffState(true);
        document.documentElement.setAttribute("data-glass", "off");
      }
    } catch {
      // ignore storage errors in restricted environments
    }
  }, []);

  const setLocale = useCallback((loc: Locale) => {
    setLocaleState(loc);
    try {
      localStorage.setItem("skillbi_locale", loc);
      document.cookie = `skillbi_locale=${loc}; path=/; max-age=31536000; samesite=lax`;
      document.documentElement.lang = loc;
    } catch {
      // ignore
    }
  }, []);

  const setGlassOff = useCallback((off: boolean) => {
    setGlassOffState(off);
    try {
      localStorage.setItem("skillbi_glass_off", String(off));
      if (off) {
        document.documentElement.setAttribute("data-glass", "off");
      } else {
        document.documentElement.removeAttribute("data-glass");
      }
    } catch {
      // ignore
    }
  }, []);

  const t = useCallback(
    (path: string): string => {
      const parts = path.split(".");
      let cur: unknown = DICTIONARIES[locale];
      for (const p of parts) {
        if (cur && typeof cur === "object" && p in cur) {
          cur = (cur as Record<string, unknown>)[p];
        } else {
          return path;
        }
      }
      return typeof cur === "string" ? cur : path;
    },
    [locale]
  );

  return (
    <I18nContext.Provider value={{ locale, setLocale, glassOff, setGlassOff, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    return {
      locale: "th",
      setLocale: () => {},
      glassOff: false,
      setGlassOff: () => {},
      t: (path: string) => {
        const parts = path.split(".");
        let cur: unknown = thMessages;
        for (const p of parts) {
          if (cur && typeof cur === "object" && p in cur) {
            cur = (cur as Record<string, unknown>)[p];
          } else {
            return path;
          }
        }
        return typeof cur === "string" ? cur : path;
      },
    };
  }
  return ctx;
}
