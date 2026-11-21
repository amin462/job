import { describe, expect, it } from "vitest";

function hexToRgb(hex: string): [number, number, number] {
  const clean = hex.replace("#", "");
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  return [r, g, b];
}

function blendRgba(
  fg: [number, number, number],
  alpha: number,
  bg: [number, number, number]
): [number, number, number] {
  return [
    Math.round(fg[0] * alpha + bg[0] * (1 - alpha)),
    Math.round(fg[1] * alpha + bg[1] * (1 - alpha)),
    Math.round(fg[2] * alpha + bg[2] * (1 - alpha)),
  ];
}

function relativeLuminance([r, g, b]: [number, number, number]): number {
  const channel = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrastRatio(
  c1: [number, number, number],
  c2: [number, number, number]
): number {
  const l1 = relativeLuminance(c1);
  const l2 = relativeLuminance(c2);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

describe("WCAG AA Contrast Audit (DESIGN_SYSTEM.md §3.2 & §8)", () => {
  const meshWorstPoints = [
    { name: "Mesh Purple (#E4DEFF)", rgb: hexToRgb("#E4DEFF") },
    { name: "Mesh Peach (#FFE3D8)", rgb: hexToRgb("#FFE3D8") },
    { name: "Mesh Cyan (#D8F0F5)", rgb: hexToRgb("#D8F0F5") },
  ];

  const inks = [
    { name: "--ink-primary (#1B1A2E)", rgb: hexToRgb("#1B1A2E") },
    { name: "--ink-secondary (#4A4963)", rgb: hexToRgb("#4A4963") },
    { name: "--ink-muted (#6B6A82)", rgb: hexToRgb("#6B6A82") },
  ];

  const white: [number, number, number] = [255, 255, 255];

  it("ensures all --ink-* tokens pass WCAG AA >= 4.5:1 on solid white and --surface-chart (0.94)", () => {
    for (const ink of inks) {
      expect(contrastRatio(ink.rgb, white)).toBeGreaterThanOrEqual(4.5);
      for (const mesh of meshWorstPoints) {
        const chartBg = blendRgba(white, 0.94, mesh.rgb);
        const ratio = contrastRatio(ink.rgb, chartBg);
        expect(
          ratio,
          `${ink.name} on chart-surface over ${mesh.name} was ${ratio.toFixed(2)}`
        ).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it("ensures all --ink-* tokens pass WCAG AA >= 4.5:1 on .glass (0.62) and .glass-strong (0.78) over worst-case mesh points", () => {
    for (const ink of inks) {
      for (const mesh of meshWorstPoints) {
        const glassBg = blendRgba(white, 0.62, mesh.rgb);
        const glassStrongBg = blendRgba(white, 0.78, mesh.rgb);
        expect(
          contrastRatio(ink.rgb, glassBg),
          `${ink.name} on .glass over ${mesh.name}`
        ).toBeGreaterThanOrEqual(4.5);
        expect(
          contrastRatio(ink.rgb, glassStrongBg),
          `${ink.name} on .glass-strong over ${mesh.name}`
        ).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it("ensures status text tokens pass >= 4.5:1 on white surface", () => {
    expect(contrastRatio(hexToRgb("#0F6E3B"), white)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(hexToRgb("#734A00"), white)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(hexToRgb("#A82020"), white)).toBeGreaterThanOrEqual(4.5);
  });

  it("ensures white bold/large text (>=16px) on AI Champion card with scrim passes >= 3.0:1 across gradient stops", () => {
    const scrimColor = hexToRgb("#1B1A2E");
    const stops = ["#6C5CE7", "#A77BE8", "#F0A58C"];
    for (const stop of stops) {
      const scrimmed = blendRgba(scrimColor, 0.36, hexToRgb(stop));
      expect(contrastRatio(white, scrimmed)).toBeGreaterThanOrEqual(3.0);
    }
  });
});
