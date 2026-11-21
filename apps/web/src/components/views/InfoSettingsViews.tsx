"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { BookOpen, Info, Languages, ShieldAlert, SlidersHorizontal, Trash2 } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { useRegisterPageContext } from "@/components/chat/PageContextProvider";
import type { PublicSummary, UserSession } from "@/types/marts";

export function SettingsView({ session }: { session: UserSession }) {
  const router = useRouter();
  const { locale, setLocale, glassOff, setGlassOff } = useI18n();
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  useRegisterPageContext({
    page: "settings",
    route: "/settings",
    title: locale === "th" ? "ตั้งค่าและจัดการข้อมูลส่วนตัว" : "Settings & Account Data",
    kpis: [{ label: "Role", value: session.role }],
  });

  const handleClearSkills = async () => {
    await fetch("/api/user-state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "clear_skills" }),
    });
    setStatusMsg(locale === "th" ? "ลบทักษะทั้งหมดของคุณเรียบร้อยแล้ว" : "All personal skills cleared.");
    router.refresh();
  };

  const handleDeleteAccount = async () => {
    await fetch("/api/user-state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "delete_account" }),
    });
    router.push("/login");
    router.refresh();
  };

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <section className="glass p-6">
        <div className="relative z-10 space-y-5">
          <h1 className="text-[22px] font-semibold text-[var(--ink-primary)]">
            {locale === "th" ? "ตั้งค่าระบบและข้อมูลส่วนตัว" : "Settings & Privacy Controls"}
          </h1>

          {statusMsg ? (
            <div className="rounded-xl border border-[#138A4B]/30 bg-[#138A4B]/10 p-3 text-[13px] text-[#0F6E3B]">
              {statusMsg}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-4">
            <div className="flex items-center gap-3">
              <Languages className="h-5 w-5 text-[var(--series-me)]" aria-hidden="true" />
              <div>
                <div className="text-[14px] font-semibold text-[var(--ink-primary)]">
                  {locale === "th" ? "ภาษาแสดงผล (TH / EN)" : "Display Language (TH / EN)"}
                </div>
                <div className="text-[12px] text-[var(--ink-muted)]">
                  {locale === "th" ? "ภาษาไทยแสดงปี พ.ศ., อังกฤษแสดง ค.ศ." : "Thai uses Buddhist Era (พ.ศ.), English uses CE"}
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setLocale("th")}
                className={`min-h-[40px] rounded-xl px-4 text-[13px] font-semibold ${
                  locale === "th" ? "bg-[var(--series-me)] text-white" : "bg-[var(--surface-sunken)]"
                }`}
              >
                ไทย (พ.ศ.)
              </button>
              <button
                type="button"
                onClick={() => setLocale("en")}
                className={`min-h-[40px] rounded-xl px-4 text-[13px] font-semibold ${
                  locale === "en" ? "bg-[var(--series-me)] text-white" : "bg-[var(--surface-sunken)]"
                }`}
              >
                English (CE)
              </button>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-4">
            <div className="flex items-center gap-3">
              <SlidersHorizontal className="h-5 w-5 text-[var(--series-compare)]" aria-hidden="true" />
              <div>
                <div className="text-[14px] font-semibold text-[var(--ink-primary)]">
                  {locale === "th" ? "โหมดพื้นผิวการ์ด (Liquid Glass / Solid)" : "Surface Mode (Liquid Glass / Solid)"}
                </div>
                <div className="text-[12px] text-[var(--ink-muted)]">
                  {locale === "th"
                    ? "สลับเป็นพื้นทึบเพื่อความคมชัดสูงสุดหรือประหยัดพลังงานบนอุปกรณ์มือถือ"
                    : "Switch to solid cards for maximum contrast or mobile GPU efficiency"}
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setGlassOff(!glassOff)}
              className="min-h-[40px] rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-sunken)] px-4 text-[13px] font-semibold text-[var(--ink-primary)]"
            >
              {glassOff
                ? locale === "th"
                  ? "กำลังใช้: โหมดทึบ (สลับเป็น Glass)"
                  : "Active: Solid (Switch to Glass)"
                : locale === "th"
                ? "กำลังใช้: Liquid Glass (สลับเป็นทึบ)"
                : "Active: Glass (Switch to Solid)"}
            </button>
          </div>

          <div className="rounded-2xl border border-[#C92A2A]/25 bg-[var(--surface-solid)] p-4 space-y-3">
            <div className="flex items-center gap-2 text-[14px] font-semibold text-[#A82020]">
              <ShieldAlert className="h-5 w-5" aria-hidden="true" />
              <span>{locale === "th" ? "ลบข้อมูลส่วนบุคคล (PDPA)" : "Delete Personal Data (PDPA)"}</span>
            </div>
            <div className="flex flex-wrap gap-2.5">
              <button
                type="button"
                onClick={handleClearSkills}
                className="inline-flex min-h-[40px] items-center gap-1.5 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-sunken)] px-4 text-[13px] font-medium text-[var(--ink-primary)] hover:bg-[var(--tint-market)]"
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
                <span>{locale === "th" ? "ลบทักษะของฉันทั้งหมด" : "Clear All My Skills"}</span>
              </button>
              <button
                type="button"
                onClick={handleDeleteAccount}
                className="inline-flex min-h-[40px] items-center gap-1.5 rounded-xl bg-[#C92A2A] px-4 text-[13px] font-semibold text-white hover:opacity-90"
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
                <span>{locale === "th" ? "ลบบัญชีและออกจากระบบ" : "Delete Account & Sign Out"}</span>
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

export function PrivacyView() {
  const { locale } = useI18n();
  useRegisterPageContext({
    page: "privacy",
    route: "/privacy",
    title: locale === "th" ? "นโยบายความเป็นส่วนตัวและ PDPA" : "Privacy & PDPA Notice",
    kpis: [],
    dataNotes: [
      "ไม่เก็บข้อมูลติดต่อ HR (ชื่อ/เบอร์โทร/อีเมล/LINE)",
      "คำถามแชทส่งเฉพาะ pageContext สรุปหน้าเว็บให้ Google Gemini",
    ],
  });

  return (
    <article className="glass mx-auto max-w-3xl p-6 sm:p-8">
      <div className="relative z-10 space-y-4">
        <div className="flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-[var(--series-me)]" aria-hidden="true" />
          <h1 className="text-[22px] font-semibold text-[var(--ink-primary)]">
            {locale === "th" ? "ความเป็นส่วนตัวและ PDPA" : "Privacy Notice & PDPA Compliance"}
          </h1>
        </div>
        <div className="space-y-3 rounded-2xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-5 text-[14px] leading-relaxed text-[var(--ink-secondary)]">
          <p>
            <strong className="text-[var(--ink-primary)]">1. ข้อมูลประกาศงานและผู้ติดต่อ:</strong>{" "}
            ระบบตัดข้อมูลผู้ติดต่อฝ่ายบุคคล (ชื่อผู้ติดต่อ เบอร์โทรศัพท์ อีเมล และ LINE ID) ออกตั้งแต่ขั้นตอน parse ก่อนบันทึกเข้าสู่คลังข้อมูล และแสดงบนเว็บไซต์เฉพาะค่าสถิติรวม (n ≥ 5) พร้อมลิงก์กลับไปยังประกาศต้นฉบับเท่านั้น
          </p>
          <p>
            <strong className="text-[var(--ink-primary)]">2. ข้อมูลผู้ใช้และสิทธิ์ RLS:</strong>{" "}
            ข้อมูลทักษะส่วนตัว (`app_user_skill`) และหลักสูตรของสถาบัน (`app_curriculum`) ถูกป้องกันด้วย Row Level Security (RLS) มองเห็นและแก้ไขได้เฉพาะเจ้าของบัญชีเท่านั้น และผู้ใช้สามารถลบข้อมูลตนเองได้ที่หน้า Settings
          </p>
          <p>
            <strong className="text-[var(--ink-primary)]">3. การใช้งานผู้ช่วยแชท Gemini:</strong>{" "}
            เมื่อผู้ใช้ส่งคำถามในหน้าต่างแชท ระบบจะส่งเฉพาะสรุปตัวเลขรวมบนหน้าปัจจุบัน (`pageContext`) ไปประมวลผลที่ Google Gemini API โดยไม่มีข้อมูลส่วนบุคคล ข้อความประกาศ หรือคำสั่ง SQL
          </p>
          <p>
            <strong className="text-[var(--ink-primary)]">4. ความเป็นธรรมของโมเดล ML:</strong>{" "}
            แบบจำลองประมาณเงินเดือนไม่ใช้เพศ อายุ หรือชื่อบริษัทเป็นตัวแปรทำนาย (D6)
          </p>
        </div>
      </div>
    </article>
  );
}

export function AboutView({ publicSummary }: { publicSummary: PublicSummary }) {
  const { locale } = useI18n();
  useRegisterPageContext({
    page: "about",
    route: "/about",
    title: locale === "th" ? "เกี่ยวกับระบบและข้อจำกัดข้อมูล" : "About & Data Limitations",
    kpis: [{ label: "Analyzed Postings", value: publicSummary.n_postings }],
    dataNotes: [
      "ตัวอย่างไม่ใช่สำมะโนทั้งตลาด",
      "เงินเดือนที่ประกาศมีความเอนเอียง (selection bias) และไม่ใช่เงินเดือนที่ได้รับจริง",
      "แนวโน้มครอบคลุมช่วงเวลาเก็บข้อมูล 3-4 เดือน",
    ],
  });

  return (
    <article className="glass mx-auto max-w-3xl p-6 sm:p-8">
      <div className="relative z-10 space-y-4">
        <div className="flex items-center gap-2">
          <Info className="h-5 w-5 text-[var(--series-me)]" aria-hidden="true" />
          <h1 className="text-[22px] font-semibold text-[var(--ink-primary)]">
            {locale === "th" ? "เกี่ยวกับ Skill Demand Intelligence (E′)" : "About Skill Demand Intelligence"}
          </h1>
        </div>
        <div className="space-y-3 rounded-2xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-5 text-[14px] leading-relaxed text-[var(--ink-secondary)]">
          <p>
            โครงงานสาขาคอมพิวเตอร์ธุรกิจ: พัฒนากระบวนการเก็บข้อมูลประกาศงานอย่างสุภาพ (Polite Scraping) คลังข้อมูล Star/Galaxy, Taxonomy ทักษะภาษาไทย-อังกฤษอ้างอิง O*NET/ESCO และเปรียบเทียบโมเดล Machine Learning 5 โมเดล + Baseline สำหรับประมาณช่วงเงินเดือน
          </p>
          <h2 className="pt-2 text-[16px] font-semibold text-[var(--ink-primary)]">
            ข้อจำกัดของข้อมูลที่ต้องทราบ
          </h2>
          <ul className="list-disc space-y-1.5 pl-5">
            <li>
              <strong>ตัวอย่างไม่ใช่ Census:</strong> ข้อมูลสุ่มแบบแบ่งชั้นจังหวัด × หมวดงานจาก JobThai และถ่วงน้ำหนักด้วย `sample_weight` ในชั้น mart
            </li>
            <li>
              <strong>อคติของการระบุเงินเดือน (Selection Bias):</strong> ประมาณ 56% ของประกาศระบุตัวเลขเงินเดือน มักเอนไปทางตำแหน่งระดับต้นหรือองค์กรที่เปิดเผยฐานเงินเดือน และเงินเดือนที่ประกาศ ≠ เงินเดือนที่ตกลงจ้างจริง
            </li>
            <li>
              <strong>กรอบเวลา Snapshot:</strong> แนวโน้มทักษะเป็นรายสัปดาห์ในช่วงที่เก็บข้อมูล (~3–4 เดือน) ไม่ใช่การพยากรณ์ตลาดแรงงานในอนาคต
            </li>
            <li>
              <strong>กฎการแสดงผล ToS:</strong> ไม่เผยแพร่ข้อความรายละเอียดประกาศ แสดงเฉพาะค่าสถิติรวมเมื่อ `n ≥ 5` และลิงก์ไปยังหน้าประกาศต้นฉบับ
            </li>
          </ul>
        </div>
      </div>
    </article>
  );
}
