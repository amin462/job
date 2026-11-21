"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  Award,
  BarChart2,
  BookOpen,
  Compass,
  Database,
  Filter,
  FlaskConical,
  GraduationCap,
  Home,
  Info,
  Languages,
  Layers,
  LogIn,
  LogOut,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  UserCheck,
  Wallet,
  X,
} from "lucide-react";
import { useI18n, formatDateByLocale } from "@/lib/i18n";
import { useGlobalFilters } from "@/components/context/FilterContext";
import { ChatWidget } from "@/components/chat/ChatWidget";
import type { DimLocation, DimOccupation, PublicSummary, UserSession } from "@/types/marts";

interface AppShellProps {
  children: React.ReactNode;
  session: UserSession | null;
  publicSummary: PublicSummary;
  locations?: DimLocation[];
  occupations?: DimOccupation[];
  showContextBar?: boolean;
}

export function AppShell({
  children,
  session,
  publicSummary,
  locations = [],
  occupations = [],
  showContextBar = false,
}: AppShellProps) {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const { locale, setLocale, glassOff, setGlassOff, t } = useI18n();
  const { filters, setFilters, resetFilters } = useGlobalFilters();
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);

  const role = session?.role || "visitor";

  const mainNav = [
    { href: "/", label: t("nav.landing"), icon: Home, show: true },
    { href: "/market", label: t("nav.market"), icon: BarChart2, show: true },
    { href: "/salary", label: t("nav.salary"), icon: Wallet, show: true },
    {
      href: "/me/skills",
      label: t("nav.mySkills"),
      icon: Award,
      show: role === "student" || role === "admin",
    },
    {
      href: "/me/gap",
      label: t("nav.skillGap"),
      icon: Compass,
      show: role === "student" || role === "admin",
    },
    {
      href: "/institution/curricula",
      label: t("nav.curricula"),
      icon: GraduationCap,
      show: role === "institution" || role === "admin",
    },
    { href: "/ml-lab", label: t("nav.mlLab"), icon: FlaskConical, show: true },
  ];

  const adminNav = [
    { href: "/admin/pipeline", label: t("nav.adminPipeline"), icon: Activity },
    { href: "/admin/quality", label: t("nav.adminQuality"), icon: ShieldCheck },
    { href: "/admin/taxonomy", label: t("nav.adminTaxonomy"), icon: Layers },
    { href: "/admin/sources", label: t("nav.adminSources"), icon: Database },
  ];

  const footerNav = [
    ...(session ? [{ href: "/settings", label: t("nav.settings"), icon: Settings }] : []),
    { href: "/privacy", label: t("nav.privacy"), icon: BookOpen },
    { href: "/about", label: t("nav.about"), icon: Info },
  ];

  const handleLogout = async () => {
    await fetch("/api/demo", { method: "DELETE" });
    router.push("/login");
    router.refresh();
  };

  const regionList = ["กลาง", "ตะวันออก", "ใต้", "อีสาน", "เหนือ", "ตะวันตก"];

  const renderFilterControls = () => (
    <div className="flex flex-wrap items-center gap-2.5">
      <label className="flex items-center gap-1.5 text-[12px]">
        <span className="font-medium text-[var(--ink-secondary)]">
          {t("filters.province")}
        </span>
        <select
          value={filters.provinceOrRegion}
          onChange={(e) =>
            setFilters((f) => ({ ...f, provinceOrRegion: e.target.value }))
          }
          className="min-h-[38px] rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-2.5 text-[13px] text-[var(--ink-primary)]"
        >
          <option value="ALL">{t("filters.allCountry")}</option>
          <option value="SOUTH14">{t("filters.south14")}</option>
          <optgroup label={locale === "th" ? "รายภาค" : "By Region"}>
            {regionList.map((r) => (
              <option key={r} value={`REGION:${r}`}>
                {locale === "th" ? `ภาค${r}` : r}
              </option>
            ))}
          </optgroup>
          {locations.length > 0 ? (
            <optgroup label={locale === "th" ? "รายจังหวัด" : "By Province"}>
              {locations.map((loc) => (
                <option key={loc.location_key} value={loc.province_th}>
                  {locale === "th" ? loc.province_th : loc.province_en}
                </option>
              ))}
            </optgroup>
          ) : null}
        </select>
      </label>

      <label className="flex items-center gap-1.5 text-[12px]">
        <span className="font-medium text-[var(--ink-secondary)]">
          {t("filters.occupation")}
        </span>
        <select
          value={filters.occupationCluster}
          onChange={(e) =>
            setFilters((f) => ({ ...f, occupationCluster: e.target.value }))
          }
          className="min-h-[38px] max-w-[210px] rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-2.5 text-[13px] text-[var(--ink-primary)]"
        >
          <option value="ALL">{t("filters.allOccupations")}</option>
          {occupations.map((occ) => (
            <option key={occ.occupation_slug} value={occ.occupation_cluster}>
              {locale === "th" ? occ.occupation_name_th : occ.occupation_cluster}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-1.5 text-[12px]">
        <span className="font-medium text-[var(--ink-secondary)]">
          {t("filters.skillType")}
        </span>
        <select
          value={filters.skillType}
          onChange={(e) =>
            setFilters((f) => ({ ...f, skillType: e.target.value }))
          }
          className="min-h-[38px] rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-2.5 text-[13px] text-[var(--ink-primary)]"
        >
          <option value="ALL">{t("filters.allSkillTypes")}</option>
          <option value="technical">Technical</option>
          <option value="tool">Tool / Software</option>
          <option value="soft">Soft Skill</option>
          <option value="language">Language</option>
          <option value="licence">Licence</option>
        </select>
      </label>

      {(filters.provinceOrRegion !== "ALL" ||
        filters.occupationCluster !== "ALL" ||
        filters.skillType !== "ALL") && (
        <button
          type="button"
          onClick={resetFilters}
          className="min-h-[36px] rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-2.5 text-[12px] font-medium text-[var(--series-me)] hover:bg-[var(--tint-me)]"
        >
          {locale === "th" ? "ล้างตัวกรอง" : "Reset"}
        </button>
      )}
    </div>
  );

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      {/* Desktop/Tablet Sidebar */}
      <aside className="no-print glass-strong glass hidden w-64 shrink-0 flex-col justify-between rounded-none border-y-0 border-l-0 p-4 md:sticky md:top-0 md:flex md:h-screen">
        <div className="relative z-10 flex flex-col gap-5 overflow-y-auto">
          <Link href="/" className="flex items-center gap-2.5 px-1">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[linear-gradient(135deg,#6C5CE7_0%,#E0623F_100%)] text-white shadow-sm">
              <Sparkles className="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <div className="text-[15px] leading-tight font-semibold text-[var(--ink-primary)]">
                Skill Demand BI
              </div>
              <div className="text-[11px] text-[var(--ink-muted)]">
                Thailand Job Intelligence
              </div>
            </div>
          </Link>

          <nav aria-label="Main navigation" className="space-y-1">
            {mainNav
              .filter((item) => item.show)
              .map((item) => {
                const Icon = item.icon;
                const active =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex min-h-[40px] items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] font-medium transition ${
                      active
                        ? "bg-[var(--series-me)] text-white shadow-xs"
                        : "text-[var(--ink-secondary)] hover:bg-[var(--surface-solid)] hover:text-[var(--ink-primary)]"
                    }`}
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
          </nav>

          {role === "admin" ? (
            <div className="space-y-1 border-t border-[var(--border-hairline)] pt-3">
              <div className="px-3 text-[11px] font-semibold uppercase tracking-wider text-[var(--ink-muted)]">
                Admin
              </div>
              {adminNav.map((item) => {
                const Icon = item.icon;
                const active = pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex min-h-[40px] items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] font-medium transition ${
                      active
                        ? "bg-[var(--series-me)] text-white"
                        : "text-[var(--ink-secondary)] hover:bg-[var(--surface-solid)] hover:text-[var(--ink-primary)]"
                    }`}
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>
          ) : null}
        </div>

        <div className="relative z-10 space-y-2 border-t border-[var(--border-hairline)] pt-3">
          {footerNav.map((item) => {
            const Icon = item.icon;
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex min-h-[38px] items-center gap-2.5 rounded-xl px-3 py-1.5 text-[12px] font-medium ${
                  active
                    ? "bg-[var(--tint-me)] text-[#2F2680]"
                    : "text-[var(--ink-secondary)] hover:bg-[var(--surface-solid)]"
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span>{item.label}</span>
              </Link>
            );
          })}

          {session ? (
            <div className="rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-2.5">
              <div className="flex items-center gap-2 text-[12px] font-semibold text-[var(--ink-primary)]">
                <UserCheck className="h-4 w-4 shrink-0 text-[var(--series-me)]" aria-hidden="true" />
                <span className="truncate">{session.display_name}</span>
              </div>
              <div className="mt-0.5 text-[11px] text-[var(--ink-muted)]">
                Role: {session.role}
                {session.is_demo ? " · Demo" : ""}
              </div>
              <button
                type="button"
                onClick={handleLogout}
                className="mt-2 inline-flex min-h-[34px] w-full items-center justify-center gap-1.5 rounded-lg bg-[var(--surface-sunken)] px-2.5 text-[12px] font-medium text-[var(--ink-secondary)] hover:bg-[var(--tint-market)] hover:text-[#9E2A0B]"
              >
                <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
                <span>{t("nav.logout")}</span>
              </button>
            </div>
          ) : (
            <Link
              href="/login"
              className="flex min-h-[42px] items-center justify-center gap-2 rounded-xl bg-[var(--series-me)] px-3 py-2 text-[13px] font-semibold text-white hover:opacity-95"
            >
              <LogIn className="h-4 w-4" aria-hidden="true" />
              <span>{t("nav.login")}</span>
            </Link>
          )}
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex min-w-0 flex-1 flex-col pb-20 md:pb-6">
        {/* Top Bar / Global Context Bar */}
        <header className="no-print glass-strong glass sticky top-0 z-30 rounded-none border-x-0 border-t-0 px-4 py-2.5 sm:px-6">
          <div className="relative z-10 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 md:hidden">
              <Link href="/" className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[linear-gradient(135deg,#6C5CE7_0%,#E0623F_100%)] text-white">
                  <Sparkles className="h-4 w-4" aria-hidden="true" />
                </span>
                <span className="text-[14px] font-semibold text-[var(--ink-primary)]">
                  Skill BI
                </span>
              </Link>
            </div>

            {showContextBar ? (
              <div className="hidden flex-1 items-center md:flex">
                {renderFilterControls()}
              </div>
            ) : (
              <div className="hidden text-[12px] text-[var(--ink-secondary)] md:flex md:items-center md:gap-2">
                <span className="font-medium text-[var(--ink-primary)]">
                  {t("app.provenancePrefix")}
                </span>
                <span>·</span>
                <span className="tabular-nums">
                  {locale === "th" ? "ตัวอย่าง" : "Sample"} n ={" "}
                  {publicSummary.n_postings.toLocaleString("en-US")}
                </span>
                {publicSummary.last_updated_at ? (
                  <>
                    <span>·</span>
                    <span>
                      {t("app.updatedLabel")}{" "}
                      {formatDateByLocale(publicSummary.last_updated_at, locale)}
                    </span>
                  </>
                ) : null}
              </div>
            )}

            <div className="flex items-center gap-2">
              {showContextBar ? (
                <button
                  type="button"
                  onClick={() => setMobileFilterOpen(true)}
                  className="inline-flex min-h-[40px] items-center gap-1.5 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3 text-[12px] font-medium text-[var(--ink-primary)] md:hidden"
                >
                  <Filter className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>{t("filters.openFilters")}</span>
                </button>
              ) : null}

              <button
                type="button"
                onClick={() => setLocale(locale === "th" ? "en" : "th")}
                aria-label="Switch language TH/EN"
                className="inline-flex min-h-[40px] items-center gap-1.5 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-2.5 text-[12px] font-semibold text-[var(--ink-primary)] hover:bg-[var(--tint-me)]"
              >
                <Languages className="h-3.5 w-3.5 text-[var(--series-me)]" aria-hidden="true" />
                <span>{locale === "th" ? "TH / EN" : "EN / TH"}</span>
              </button>

              <button
                type="button"
                onClick={() => setGlassOff(!glassOff)}
                aria-label="Toggle Liquid Glass / Solid mode"
                title={glassOff ? "Glass: OFF (Solid)" : "Glass: ON"}
                className="hidden min-h-[40px] items-center gap-1.5 rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-2.5 text-[12px] font-medium text-[var(--ink-secondary)] hover:bg-[var(--tint-me)] sm:inline-flex"
              >
                <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
                <span>{glassOff ? "Solid" : "Glass"}</span>
              </button>

              {!session ? (
                <Link
                  href="/login"
                  className="inline-flex min-h-[40px] items-center gap-1.5 rounded-xl bg-[var(--series-me)] px-3 text-[12px] font-semibold text-white md:hidden"
                >
                  <LogIn className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>{locale === "th" ? "เข้าใช้" : "Login"}</span>
                </Link>
              ) : null}
            </div>
          </div>

          {showContextBar ? (
            <div className="relative z-10 mt-1.5 hidden text-[11px] text-[var(--ink-muted)] md:flex md:items-center md:justify-between">
              <span>
                {t("app.provenancePrefix")} ({t("app.sampleBadge")} n ={" "}
                {publicSummary.n_postings.toLocaleString("en-US")}) ·{" "}
                {t("app.updatedLabel")}{" "}
                {formatDateByLocale(publicSummary.last_updated_at, locale)}
              </span>
            </div>
          ) : null}
        </header>

        {/* Mobile Filters Bottom Sheet */}
        {mobileFilterOpen && showContextBar ? (
          <div className="fixed inset-0 z-50 flex items-end bg-black/30 md:hidden">
            <div className="glass-strong glass w-full rounded-t-[24px] rounded-b-none p-5">
              <div className="relative z-10 flex items-center justify-between border-b border-[var(--border-hairline)] pb-3">
                <h2 className="text-[16px] font-semibold text-[var(--ink-primary)]">
                  {t("filters.openFilters")}
                </h2>
                <button
                  type="button"
                  onClick={() => setMobileFilterOpen(false)}
                  className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--surface-solid)]"
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
              <div className="relative z-10 mt-4 space-y-3">
                {renderFilterControls()}
              </div>
              <button
                type="button"
                onClick={() => setMobileFilterOpen(false)}
                className="relative z-10 mt-5 min-h-[44px] w-full rounded-xl bg-[var(--series-me)] text-[14px] font-semibold text-white"
              >
                {locale === "th" ? "ใช้ตัวกรอง" : "Apply Filters"}
              </button>
            </div>
          </div>
        ) : null}

        <main className="mx-auto w-full max-w-[1360px] flex-1 px-4 py-5 sm:px-6">
          {children}
        </main>
      </div>

      {/* Mobile Bottom Tab Bar (< 768px, >= 40px hit targets) */}
      <nav
        aria-label="Mobile navigation"
        className="no-print glass-strong glass fixed inset-x-0 bottom-0 z-30 flex items-center justify-around rounded-none border-x-0 border-b-0 px-1 py-1 md:hidden"
      >
        {[
          { href: "/market", label: "Market", icon: BarChart2 },
          { href: "/ml-lab", label: "ML Lab", icon: FlaskConical },
          { href: "/salary", label: "Salary", icon: Wallet },
          {
            href:
              role === "institution"
                ? "/institution/curricula"
                : role === "admin"
                ? "/admin/pipeline"
                : role === "student"
                ? "/me/gap"
                : "/login",
            label: locale === "th" ? "ฉัน" : "Me",
            icon: role === "visitor" ? LogIn : UserCheck,
          },
        ].map((tab) => {
          const Icon = tab.icon;
          const active = pathname.startsWith(tab.href);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`relative z-10 flex min-h-[44px] min-w-[64px] flex-col items-center justify-center gap-0.5 rounded-xl px-2 text-[11px] font-medium ${
                active ? "text-[var(--series-me)]" : "text-[var(--ink-secondary)]"
              }`}
            >
              <Icon className="h-5 w-5" aria-hidden="true" />
              <span>{tab.label}</span>
            </Link>
          );
        })}
      </nav>

      <ChatWidget />
    </div>
  );
}
