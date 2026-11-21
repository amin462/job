"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Award,
  GraduationCap,
  LogIn,
  Shield,
  Sparkles,
  UserPlus,
} from "lucide-react";
import { DEMO_PERSONAS } from "@/lib/demo-personas";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import { isSupabaseConfigured } from "@/lib/supabase/config";
import { useI18n } from "@/lib/i18n";
import { useRegisterPageContext } from "@/components/chat/PageContextProvider";
import { SkillChipPicker } from "@/components/ui/SkillChipPicker";
import type {
  DemoPersonaKey,
  DimLocation,
  DimOccupation,
  DimSkill,
  UserSession,
} from "@/types/marts";

export function LoginView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextUrl = searchParams.get("next");
  const { locale } = useI18n();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loadingPersona, setLoadingPersona] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useRegisterPageContext({
    page: "login",
    route: "/login",
    title: locale === "th" ? "เข้าสู่ระบบและบัญชีเดโม" : "Sign In & Demo Personas",
    kpis: [{ label: locale === "th" ? "บัญชีเดโมพร้อมใช้" : "Demo Personas", value: 4 }],
    dataNotes: ["รองรับเข้าสู่ระบบคลิกเดียว 4 บทบาท: นักศึกษาสาย Data, นักศึกษาสายบัญชี, อาจารย์หลักสูตร, Admin"],
  });

  const handleDemoLogin = async (persona: DemoPersonaKey) => {
    setError(null);
    setLoadingPersona(persona);
    try {
      const res = await fetch("/api/demo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona }),
      });
      const data = (await res.json()) as { ok?: boolean; redirectTo?: string; error?: string };
      if (!res.ok || !data.ok) {
        setError(data.error || "Failed to activate demo persona");
        return;
      }
      router.push(nextUrl || data.redirectTo || "/market");
      router.refresh();
    } catch {
      setError("Network error while activating demo persona");
    } finally {
      setLoadingPersona(null);
    }
  };

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!isSupabaseConfigured()) {
      setError(
        locale === "th"
          ? "ยังไม่ได้เชื่อมต่อ Supabase จริงใน .env.local — กรุณาใช้ปุ่ม 'เดโมคลิกเดียว 4 บทบาท' ด้านขวา"
          : "Supabase keys are not configured yet — please use one of the 4 one-click Demo Persona buttons."
      );
      return;
    }
    const supabase = createSupabaseBrowserClient();
    if (!supabase) return;
    const { error: authErr } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    if (authErr) {
      setError(authErr.message);
      return;
    }
    router.push(nextUrl || "/market");
    router.refresh();
  };

  const personaIcons: Record<DemoPersonaKey, React.ReactNode> = {
    student_data: <Award className="h-5 w-5 text-[var(--series-me)]" />,
    student_acc: <Award className="h-5 w-5 text-[var(--series-market)]" />,
    institution: <GraduationCap className="h-5 w-5 text-[var(--series-compare)]" />,
    admin: <Shield className="h-5 w-5 text-[var(--ink-primary)]" />,
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* One-Click Demo Personas */}
        <section className="glass p-6 lg:col-span-7">
          <div className="relative z-10 space-y-4">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-[var(--tint-me)] px-3 py-1 text-[12px] font-semibold text-[#2F2680]">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              <span>{locale === "th" ? "เข้าใช้คลิกเดียวสำหรับกรรมการ / ทดสอบ" : "One-Click Demo Access"}</span>
            </div>
            <h1 className="text-[22px] font-semibold text-[var(--ink-primary)]">
              {locale === "th" ? "เลือกบทบาททดลองระบบ (4 Persona)" : "Choose a Demo Persona"}
            </h1>
            <p className="text-[13px] text-[var(--ink-secondary)]">
              {locale === "th"
                ? "เข้าใช้งานทันทีพร้อมทักษะและหลักสูตรตัวอย่างที่ seed ไว้ในระบบ"
                : "Sign in immediately with pre-seeded skills, sample curricula, or admin privileges."}
            </p>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {(Object.keys(DEMO_PERSONAS) as DemoPersonaKey[]).map((key) => {
                const p = DEMO_PERSONAS[key];
                const isLoading = loadingPersona === key;
                return (
                  <button
                    key={key}
                    type="button"
                    disabled={Boolean(loadingPersona)}
                    onClick={() => handleDemoLogin(key)}
                    className="flex min-h-[104px] flex-col items-start justify-between rounded-2xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-4 text-left transition hover:border-[var(--series-me)] hover:bg-[var(--tint-me)]/40 disabled:opacity-60"
                  >
                    <div className="flex w-full items-center justify-between">
                      {personaIcons[key]}
                      <span className="rounded-full bg-[var(--surface-sunken)] px-2 py-0.5 text-[11px] font-medium text-[var(--ink-secondary)]">
                        {p.role}
                      </span>
                    </div>
                    <div className="mt-2">
                      <div className="text-[14px] font-semibold text-[var(--ink-primary)]">
                        {isLoading
                          ? locale === "th"
                            ? "กำลังเข้าสู่ระบบ..."
                            : "Signing in..."
                          : locale === "th"
                          ? p.labelTh
                          : p.labelEn}
                      </div>
                      <div className="mt-0.5 text-[12px] text-[var(--ink-muted)]">
                        {locale === "th" ? p.descriptionTh : p.descriptionEn}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </section>

        {/* Email / Password Form */}
        <section className="glass p-6 lg:col-span-5">
          <div className="relative z-10 space-y-4">
            <div className="flex items-center gap-2">
              <LogIn className="h-5 w-5 text-[var(--series-me)]" aria-hidden="true" />
              <h2 className="text-[18px] font-semibold text-[var(--ink-primary)]">
                {locale === "th" ? "เข้าสู่ระบบด้วยอีเมล" : "Email Sign In"}
              </h2>
            </div>

            {error ? (
              <div
                role="alert"
                className="rounded-xl border border-[#C92A2A]/30 bg-[#C92A2A]/10 px-3.5 py-2.5 text-[13px] text-[#9E1C1C]"
              >
                {error}
              </div>
            ) : null}

            <form onSubmit={handleEmailLogin} className="space-y-3.5">
              <label className="block text-[13px]">
                <span className="font-medium text-[var(--ink-secondary)]">
                  {locale === "th" ? "อีเมล" : "Email"}
                </span>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3 text-[14px]"
                  placeholder="student@university.ac.th"
                />
              </label>

              <label className="block text-[13px]">
                <span className="font-medium text-[var(--ink-secondary)]">
                  {locale === "th" ? "รหัสผ่าน" : "Password"}
                </span>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3 text-[14px]"
                />
              </label>

              <button
                type="submit"
                className="min-h-[44px] w-full rounded-xl bg-[var(--series-me)] px-4 text-[14px] font-semibold text-white hover:opacity-95"
              >
                {locale === "th" ? "เข้าสู่ระบบ" : "Sign In"}
              </button>
            </form>

            <div className="border-t border-[var(--border-hairline)] pt-3 text-[13px] text-[var(--ink-secondary)]">
              {locale === "th" ? "ยังไม่มีบัญชี? " : "No account yet? "}
              <Link href="/signup" className="font-semibold text-[var(--series-me)] hover:underline">
                {locale === "th" ? "สมัครสมาชิก (Student / Institution)" : "Sign Up"}
              </Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

export function SignupView() {
  const router = useRouter();
  const { locale } = useI18n();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<"student" | "institution">("student");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useRegisterPageContext({
    page: "signup",
    route: "/signup",
    title: locale === "th" ? "สมัครสมาชิก" : "Sign Up",
    kpis: [],
    dataNotes: ["บทบาทที่สมัครได้: Student หรือ Institution เท่านั้น (ป้องกันยกระดับสิทธิ์ Admin ตาม RLS)"],
  });

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMessage(null);

    if (!isSupabaseConfigured()) {
      setError(
        locale === "th"
          ? "โหมดออฟไลน์ไม่มีฐานข้อมูล Supabase — กรุณากลับไปใช้ปุ่มเดโม 4 บทบาทที่หน้า /login"
          : "Supabase is not configured in offline mode — use the 4 Demo Personas on /login."
      );
      return;
    }

    const supabase = createSupabaseBrowserClient();
    if (!supabase) return;
    const { error: signErr } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          role, // trigger enforces ('student','institution') only
          display_name: displayName || email.split("@")[0],
        },
      },
    });
    if (signErr) {
      setError(signErr.message);
      return;
    }
    setMessage(
      locale === "th"
        ? "สร้างบัญชีสำเร็จ กรุณาตรวจสอบอีเมลหรือเข้าสู่ระบบเพื่อไปหน้า Onboarding"
        : "Account created! Check your email or sign in to continue onboarding."
    );
    setTimeout(() => router.push("/onboarding"), 1200);
  };

  return (
    <section className="glass mx-auto max-w-md p-6">
      <div className="relative z-10 space-y-4">
        <div className="flex items-center gap-2">
          <UserPlus className="h-5 w-5 text-[var(--series-me)]" aria-hidden="true" />
          <h1 className="text-[20px] font-semibold text-[var(--ink-primary)]">
            {locale === "th" ? "สมัครใช้งานระบบ" : "Create Account"}
          </h1>
        </div>
        <p className="text-[12px] text-[var(--ink-muted)]">
          {locale === "th"
            ? "เลือกบทบาท Student หรือ Institution เท่านั้น (สิทธิ์ Admin ถูกจำกัดด้วย RLS ตามมาตรฐานความปลอดภัย)"
            : "Select Student or Institution role (Admin self-registration is blocked by RLS)."}
        </p>

        {error ? (
          <div className="rounded-xl border border-[#C92A2A]/30 bg-[#C92A2A]/10 p-3 text-[13px] text-[#9E1C1C]">
            {error}
          </div>
        ) : null}
        {message ? (
          <div className="rounded-xl border border-[#138A4B]/30 bg-[#138A4B]/10 p-3 text-[13px] text-[#0F6E3B]">
            {message}
          </div>
        ) : null}

        <form onSubmit={handleSignup} className="space-y-3">
          <label className="block text-[13px]">
            <span className="font-medium text-[var(--ink-secondary)]">
              {locale === "th" ? "ชื่อแสดง" : "Display Name"}
            </span>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3"
              required
            />
          </label>
          <label className="block text-[13px]">
            <span className="font-medium text-[var(--ink-secondary)]">
              {locale === "th" ? "บทบาท" : "Role"}
            </span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as "student" | "institution")}
              className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3"
            >
              <option value="student">{locale === "th" ? "นักศึกษา / ผู้จบใหม่ (Student)" : "Student / Graduate"}</option>
              <option value="institution">{locale === "th" ? "อาจารย์ / สถานศึกษา (Institution)" : "Institution / Curriculum"}</option>
            </select>
          </label>
          <label className="block text-[13px]">
            <span className="font-medium text-[var(--ink-secondary)]">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3"
              required
            />
          </label>
          <label className="block text-[13px]">
            <span className="font-medium text-[var(--ink-secondary)]">
              {locale === "th" ? "รหัสผ่าน (≥ 6 ตัวอักษร)" : "Password (≥ 6 chars)"}
            </span>
            <input
              type="password"
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3"
              required
            />
          </label>
          <button
            type="submit"
            className="min-h-[44px] w-full rounded-xl bg-[var(--series-me)] font-semibold text-white"
          >
            {locale === "th" ? "สร้างบัญชี" : "Create Account"}
          </button>
        </form>

        <div className="text-center text-[13px]">
          <Link href="/login" className="font-medium text-[var(--series-me)] hover:underline">
            {locale === "th" ? "← กลับไปหน้าเข้าสู่ระบบ / เดโม" : "← Back to Login / Demo"}
          </Link>
        </div>
      </div>
    </section>
  );
}

export function OnboardingView({
  session,
  locations,
  occupations,
  skillsCatalog,
  initialSkillKeys,
}: {
  session: UserSession;
  locations: DimLocation[];
  occupations: DimOccupation[];
  skillsCatalog: DimSkill[];
  initialSkillKeys: number[];
}) {
  const router = useRouter();
  const { locale } = useI18n();
  const [role, setRole] = useState<"student" | "institution">(
    session.role === "institution" ? "institution" : "student"
  );
  const [province, setProvince] = useState(session.province_th || "สงขลา");
  const [targetOcc, setTargetOcc] = useState(
    session.target_occupation_cluster || occupations[0]?.occupation_cluster || "Data & Analytics"
  );
  const [selectedKeys, setSelectedKeys] = useState<number[]>(initialSkillKeys);
  const [saving, setSaving] = useState(false);

  useRegisterPageContext({
    page: "onboarding",
    route: "/onboarding",
    title: locale === "th" ? "ตั้งค่าเริ่มต้นโปรไฟล์" : "Profile Onboarding",
    kpis: [{ label: locale === "th" ? "ทักษะที่เลือก" : "Selected Skills", value: selectedKeys.length }],
  });

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await fetch("/api/user-state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "update_profile",
          role: session.role === "admin" ? "admin" : role,
          province_th: province,
          target_occupation_cluster: targetOcc,
        }),
      });
      for (const k of selectedKeys) {
        if (!initialSkillKeys.includes(k)) {
          await fetch("/api/user-state", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "upsert_skill", skill_key: k, level: 2 }),
          });
        }
      }
      router.push(role === "institution" ? "/institution/curricula" : "/me/gap");
      router.refresh();
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="glass mx-auto max-w-2xl p-6">
      <form onSubmit={handleSave} className="relative z-10 space-y-5">
        <div>
          <h1 className="text-[22px] font-semibold text-[var(--ink-primary)]">
            {locale === "th" ? "ตั้งค่าเป้าหมายและทักษะเริ่มต้น" : "Set Your Target Role & Starter Skills"}
          </h1>
          <p className="mt-1 text-[13px] text-[var(--ink-secondary)]">
            {locale === "th"
              ? "เลือกจังหวัด ตำแหน่งเป้าหมาย และทักษะพื้นฐานที่มี เพื่อเริ่มวิเคราะห์ Skill Gap"
              : "Choose your province, target occupation cluster, and initial skills."}
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {session.role !== "admin" ? (
            <label className="text-[13px]">
              <span className="font-medium text-[var(--ink-secondary)]">
                {locale === "th" ? "บทบาทของคุณ" : "Your Role"}
              </span>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as "student" | "institution")}
                className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3"
              >
                <option value="student">{locale === "th" ? "นักศึกษา / ผู้จบใหม่" : "Student / Graduate"}</option>
                <option value="institution">{locale === "th" ? "อาจารย์ / สถานศึกษา" : "Institution / Faculty"}</option>
              </select>
            </label>
          ) : null}

          <label className="text-[13px]">
            <span className="font-medium text-[var(--ink-secondary)]">
              {locale === "th" ? "จังหวัดที่สนใจ" : "Preferred Province"}
            </span>
            <select
              value={province}
              onChange={(e) => setProvince(e.target.value)}
              className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3"
            >
              {locations.map((loc) => (
                <option key={loc.location_key} value={loc.province_th}>
                  {locale === "th" ? loc.province_th : loc.province_en}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="block text-[13px]">
          <span className="font-medium text-[var(--ink-secondary)]">
            {locale === "th" ? "กลุ่มอาชีพเป้าหมาย" : "Target Occupation Cluster"}
          </span>
          <select
            value={targetOcc}
            onChange={(e) => setTargetOcc(e.target.value)}
            className="mt-1 min-h-[42px] w-full rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3"
          >
            {occupations.map((o) => (
              <option key={o.occupation_slug} value={o.occupation_cluster}>
                {locale === "th" ? o.occupation_name_th : o.occupation_cluster}
              </option>
            ))}
          </select>
        </label>

        {role === "student" ? (
          <div>
            <div className="mb-1.5 text-[13px] font-medium text-[var(--ink-secondary)]">
              {locale === "th" ? "ทักษะเริ่มต้นของคุณ" : "Starter Skills"}
            </div>
            <SkillChipPicker
              skillsCatalog={skillsCatalog}
              selectedKeys={selectedKeys}
              onAdd={(sk) => setSelectedKeys((prev) => [...prev, sk.skill_key])}
              onRemove={(k) => setSelectedKeys((prev) => prev.filter((x) => x !== k))}
            />
          </div>
        ) : null}

        <button
          type="submit"
          disabled={saving}
          className="min-h-[44px] rounded-xl bg-[var(--series-me)] px-6 text-[14px] font-semibold text-white"
        >
          {saving
            ? locale === "th"
              ? "กำลังบันทึก..."
              : "Saving..."
            : locale === "th"
            ? "บันทึกและเริ่มต้นใช้งาน →"
            : "Save & Continue →"}
        </button>
      </form>
    </section>
  );
}
