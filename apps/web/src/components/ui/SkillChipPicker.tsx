"use client";

import React, { useMemo, useState } from "react";
import { Plus, Search, X } from "lucide-react";
import type { DimSkill } from "@/types/marts";
import { useI18n } from "@/lib/i18n";

export function SkillChipPicker({
  skillsCatalog,
  selectedKeys,
  onAdd,
  onRemove,
  placeholder,
  maxItems,
}: {
  skillsCatalog: DimSkill[];
  selectedKeys: number[];
  onAdd: (skill: DimSkill) => void;
  onRemove: (skillKey: number) => void;
  placeholder?: string;
  maxItems?: number;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const { locale } = useI18n();

  const selectedSet = useMemo(() => new Set(selectedKeys), [selectedKeys]);
  const selectedSkills = useMemo(
    () =>
      selectedKeys
        .map((k) => skillsCatalog.find((s) => s.skill_key === k))
        .filter((s): s is DimSkill => Boolean(s)),
    [selectedKeys, skillsCatalog]
  );

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const available = skillsCatalog.filter((s) => !selectedSet.has(s.skill_key));
    if (!q) return available.slice(0, 10);
    return available
      .filter((s) => {
        if (s.skill_canonical.toLowerCase().includes(q)) return true;
        if (s.skill_name_th.toLowerCase().includes(q)) return true;
        if (s.skill_group.toLowerCase().includes(q)) return true;
        return (s.aliases || []).some((al) => al.toLowerCase().includes(q));
      })
      .slice(0, 12);
  }, [query, selectedSet, skillsCatalog]);

  const atLimit = Boolean(maxItems && selectedKeys.length >= maxItems);

  return (
    <div className="space-y-2.5">
      <div className="relative">
        <div className="flex items-center rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] px-3">
          <Search className="h-4 w-4 shrink-0 text-[var(--ink-muted)]" aria-hidden="true" />
          <input
            type="text"
            value={query}
            disabled={atLimit}
            onFocus={() => setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), 180)}
            onChange={(e) => {
              setQuery(e.target.value);
              setOpen(true);
            }}
            placeholder={
              placeholder ||
              (locale === "th"
                ? "ค้นหาทักษะ (เช่น Excel, เอ็กเซล, SQL, ภาษี)..."
                : "Search skills by Thai or English alias...")
            }
            aria-label={locale === "th" ? "ค้นหาทักษะ" : "Search skills"}
            className="min-h-[42px] w-full bg-transparent px-2.5 text-[14px] text-[var(--ink-primary)] placeholder:text-[var(--ink-muted)] focus:outline-none"
          />
        </div>
        {open && matches.length > 0 && !atLimit ? (
          <ul
            role="listbox"
            className="absolute z-30 mt-1 max-h-60 w-full overflow-y-auto rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-1.5 shadow-lg"
          >
            {matches.map((sk) => (
              <li key={sk.skill_key}>
                <button
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    onAdd(sk);
                    setQuery("");
                  }}
                  className="flex min-h-[40px] w-full items-center justify-between gap-2 rounded-lg px-3 py-1.5 text-left text-[13px] hover:bg-[var(--tint-me)]"
                >
                  <div>
                    <span className="font-medium text-[var(--ink-primary)]">
                      {locale === "th" ? sk.skill_name_th : sk.skill_canonical}
                    </span>
                    <span className="ml-2 text-[12px] text-[var(--ink-muted)]">
                      {locale === "th" ? sk.skill_canonical : sk.skill_name_th}
                    </span>
                  </div>
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--series-me)]">
                    <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                    <span>{sk.skill_type}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      {selectedSkills.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {selectedSkills.map((sk) => (
            <span
              key={sk.skill_key}
              className="inline-flex min-h-[34px] items-center gap-1.5 rounded-full border border-[#6C5CE7]/30 bg-[var(--tint-me)] px-3 py-1 text-[13px] font-medium text-[#2F2680]"
            >
              <span>{locale === "th" ? sk.skill_name_th : sk.skill_canonical}</span>
              <button
                type="button"
                onClick={() => onRemove(sk.skill_key)}
                aria-label={`Remove ${sk.skill_canonical}`}
                className="rounded-full p-0.5 hover:bg-[#6C5CE7]/20"
              >
                <X className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
