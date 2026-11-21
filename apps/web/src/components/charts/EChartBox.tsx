"use client";

import dynamic from "next/dynamic";
import type { EChartInnerProps } from "./EChartInner";

const DynamicEChart = dynamic(() => import("./EChartInner"), {
  ssr: false,
  loading: () => (
    <div
      className="flex h-[280px] w-full items-center justify-center rounded-xl bg-[var(--surface-sunken)] text-sm text-[var(--ink-muted)]"
      aria-busy="true"
    >
      กำลังโหลดกราฟ...
    </div>
  ),
});

export function EChartBox(props: EChartInnerProps) {
  return <DynamicEChart {...props} />;
}
