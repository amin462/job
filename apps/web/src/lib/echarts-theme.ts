import type * as echarts from "echarts/core";

export const SKILLBI_PALETTE = {
  me: "#6C5CE7",
  market: "#E0623F",
  compare: "#0E9AAE",
  context: "#B4B3C6",
  inkPrimary: "#1B1A2E",
  inkSecondary: "#4A4963",
  inkMuted: "#6B6A82",
  hairline: "#E8E8F0",
  seq: ["#F1EFFD", "#D9D3FA", "#B7ACF4", "#9384EE", "#6C5CE7", "#4B3DBF", "#2F2680"],
};

let themeRegistered = false;

export function registerSkillBiTheme(echartsInstance: typeof echarts): void {
  if (themeRegistered) return;

  echartsInstance.registerTheme("skillbi", {
    color: [
      SKILLBI_PALETTE.me,
      SKILLBI_PALETTE.market,
      SKILLBI_PALETTE.compare,
      SKILLBI_PALETTE.context,
      "#4B3DBF",
      "#9384EE",
    ],
    backgroundColor: "transparent",
    textStyle: {
      fontFamily: '"Inter", "IBM Plex Sans Thai", system-ui, sans-serif',
      color: SKILLBI_PALETTE.inkPrimary,
      fontSize: 12,
    },
    title: {
      textStyle: {
        color: SKILLBI_PALETTE.inkPrimary,
        fontSize: 15,
        fontWeight: 600,
      },
      subtextStyle: {
        color: SKILLBI_PALETTE.inkMuted,
        fontSize: 12,
      },
    },
    legend: {
      textStyle: {
        color: SKILLBI_PALETTE.inkSecondary,
        fontSize: 12,
      },
      itemWidth: 12,
      itemHeight: 8,
    },
    tooltip: {
      backgroundColor: "#FFFFFF",
      borderColor: SKILLBI_PALETTE.hairline,
      borderWidth: 1,
      textStyle: {
        color: SKILLBI_PALETTE.inkPrimary,
        fontSize: 12,
      },
      extraCssText:
        "border-radius: 12px; box-shadow: 0 8px 24px rgba(27,26,46,0.10);",
    },
    categoryAxis: {
      axisLine: { lineStyle: { color: SKILLBI_PALETTE.hairline } },
      axisTick: { show: false },
      axisLabel: {
        color: SKILLBI_PALETTE.inkSecondary,
        fontSize: 12,
      },
      splitLine: { show: false },
    },
    valueAxis: {
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: SKILLBI_PALETTE.inkSecondary,
        fontSize: 12,
      },
      splitLine: {
        show: true,
        lineStyle: { color: SKILLBI_PALETTE.hairline, type: "solid" },
      },
    },
    bar: {
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
      },
    },
    line: {
      lineStyle: {
        width: 2,
      },
      symbolSize: 6,
    },
  });

  themeRegistered = true;
}
