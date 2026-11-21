"use client";

import React from "react";
import Link from "next/link";
import { AlertTriangle, RotateCcw } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-lg items-center justify-center px-4 py-12">
      <div className="surface-solid w-full space-y-4 rounded-3xl border border-[var(--border-hairline)] p-6 text-center shadow-sm">
        <AlertTriangle
          className="mx-auto h-9 w-9 text-[var(--status-warning)]"
          aria-hidden="true"
        />
        <h1 className="text-[20px] font-semibold text-[var(--ink-primary)]">
          ไม่สามารถโหลดข้อมูลหน้านี้ได้ชั่วคราว
        </h1>
        <p className="text-[13px] text-[var(--ink-secondary)]">
          {error.message || "เกิดข้อผิดพลาดในการเชื่อมต่อแหล่งข้อมูล กรุณาลองใหม่อีกครั้ง"}
        </p>
        <div className="flex flex-wrap justify-center gap-3 pt-2">
          <button
            type="button"
            onClick={reset}
            className="inline-flex min-h-[42px] items-center gap-2 rounded-xl bg-[var(--series-me)] px-4 text-[13px] font-semibold text-white hover:opacity-95"
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            <span>ลองใหม่</span>
          </button>
          <Link
            href="/"
            className="inline-flex min-h-[42px] items-center rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-sunken)] px-4 text-[13px] font-medium text-[var(--ink-primary)]"
          >
            กลับหน้าหลัก
          </Link>
        </div>
      </div>
    </div>
  );
}
