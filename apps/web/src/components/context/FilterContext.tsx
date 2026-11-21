"use client";

import React, { createContext, useContext, useState } from "react";

export interface GlobalFilters {
  provinceOrRegion: string; // "ALL" | "SOUTH14" | region name | province_th
  occupationCluster: string; // "ALL" | occupation_cluster
  period: string; // "ALL" | week_start ISO
  skillType: string; // "ALL" | "tool" | "technical" | "soft" | "language" | "licence"
  activeMode: "active" | "new";
}

const DEFAULT_FILTERS: GlobalFilters = {
  provinceOrRegion: "ALL",
  occupationCluster: "ALL",
  period: "ALL",
  skillType: "ALL",
  activeMode: "active",
};

interface FilterContextValue {
  filters: GlobalFilters;
  setFilters: React.Dispatch<React.SetStateAction<GlobalFilters>>;
  resetFilters: () => void;
}

const FilterContext = createContext<FilterContextValue | null>(null);

export function FilterProvider({ children }: { children: React.ReactNode }) {
  const [filters, setFilters] = useState<GlobalFilters>(DEFAULT_FILTERS);
  const resetFilters = () => setFilters(DEFAULT_FILTERS);

  return (
    <FilterContext.Provider value={{ filters, setFilters, resetFilters }}>
      {children}
    </FilterContext.Provider>
  );
}

export function useGlobalFilters(): FilterContextValue {
  const ctx = useContext(FilterContext);
  if (!ctx) {
    return {
      filters: DEFAULT_FILTERS,
      setFilters: () => {},
      resetFilters: () => {},
    };
  }
  return ctx;
}
