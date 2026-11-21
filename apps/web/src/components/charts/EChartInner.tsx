"use client";

import React, { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import {
  BarChart,
  LineChart,
  SankeyChart,
  RadarChart,
  HeatmapChart,
  ScatterChart,
  GaugeChart,
  CustomChart,
  BoxplotChart,
} from "echarts/charts";
import {
  CalendarComponent,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  VisualMapComponent,
  MarkPointComponent,
  MarkLineComponent,
  MarkAreaComponent,
  TitleComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { registerSkillBiTheme } from "@/lib/echarts-theme";

echarts.use([
  BarChart,
  LineChart,
  SankeyChart,
  RadarChart,
  HeatmapChart,
  ScatterChart,
  GaugeChart,
  CustomChart,
  BoxplotChart,
  CalendarComponent,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  VisualMapComponent,
  MarkPointComponent,
  MarkLineComponent,
  MarkAreaComponent,
  TitleComponent,
  CanvasRenderer,
]);

export interface EChartInnerProps {
  option: Record<string, unknown>;
  ariaLabel: string;
  height?: number;
  className?: string;
  onItemClick?: (params: unknown) => void;
}

export default function EChartInner({
  option,
  ariaLabel,
  height = 300,
  className = "",
  onItemClick,
}: EChartInnerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    registerSkillBiTheme(echarts);
    const chart = echarts.init(el, "skillbi", { renderer: "canvas" });
    chartRef.current = chart;

    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;

    chart.setOption({
      animation: !prefersReducedMotion,
      ...option,
    });

    if (onItemClick) {
      chart.on("click", onItemClick);
    }

    const observer = new ResizeObserver(() => {
      chart.resize();
    });
    observer.observe(el);

    return () => {
      observer.disconnect();
      if (onItemClick) {
        chart.off("click", onItemClick);
      }
      chart.dispose();
      chartRef.current = null;
    };
  }, [option, onItemClick]);

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label={ariaLabel}
      tabIndex={0}
      style={{ height: `${height}px`, width: "100%" }}
      className={`rounded-xl focus-visible:outline-none ${className}`}
    />
  );
}
