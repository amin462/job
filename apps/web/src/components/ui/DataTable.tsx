"use client";

import React, { useMemo, useState } from "react";
import { flexRender } from "@tanstack/react-table";
import {
  getCoreRowModel,
  getSortedRowModel,
  useLegacyTable,
  type LegacyColumnDef,
} from "@tanstack/react-table/legacy";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

export interface SimpleColumn<T extends Record<string, unknown>> {
  key: keyof T & string;
  label: string;
  numeric?: boolean;
  render?: (row: T) => React.ReactNode;
}

interface DataTableProps<T extends Record<string, unknown>> {
  columns: SimpleColumn<T>[];
  data: T[];
  caption?: string;
  maxRows?: number;
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  caption,
  maxRows,
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState<Array<{ id: string; desc: boolean }>>([]);

  const visibleData = useMemo(
    () => (maxRows ? data.slice(0, maxRows) : data),
    [data, maxRows]
  );

  const columnDefs = useMemo<LegacyColumnDef<T>[]>(
    () =>
      columns.map((col) => ({
        id: col.key,
        accessorKey: col.key,
        header: col.label,
        cell: (info) =>
          col.render ? col.render(info.row.original) : String(info.getValue() ?? "—"),
      })),
    [columns]
  );

  const table = useLegacyTable({
    data: visibleData,
    columns: columnDefs,
    state: { sorting },
    onSortingChange: setSorting as never,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const colMetaMap = useMemo(
    () => new Map(columns.map((c) => [c.key, c])),
    [columns]
  );

  if (visibleData.length === 0) {
    return (
      <div className="rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)] p-6 text-center text-sm text-[var(--ink-muted)]">
        ไม่มีข้อมูลในตาราง
      </div>
    );
  }

  return (
    <div className="w-full overflow-x-auto rounded-xl border border-[var(--border-hairline)] bg-[var(--surface-solid)]">
      <table className="w-full border-collapse text-left text-[13px]">
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead className="border-b border-[var(--border-hairline)] bg-[var(--surface-sunken)] text-[12px] font-semibold text-[var(--ink-secondary)]">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((header) => {
                const meta = colMetaMap.get(header.id);
                const sorted = header.column.getIsSorted();
                return (
                  <th
                    key={header.id}
                    scope="col"
                    className={`px-3 py-2.5 whitespace-nowrap ${
                      meta?.numeric ? "text-right" : "text-left"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={header.column.getToggleSortingHandler()}
                      className="inline-flex items-center gap-1 rounded px-1 py-0.5 hover:text-[var(--ink-primary)]"
                    >
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                      {sorted === "asc" ? (
                        <ArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
                      ) : sorted === "desc" ? (
                        <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
                      ) : (
                        <ArrowUpDown className="h-3 w-3 opacity-50" aria-hidden="true" />
                      )}
                    </button>
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody className="divide-y divide-[var(--border-hairline)]">
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              className="transition-colors hover:bg-[var(--surface-sunken)]/70"
            >
              {row.getVisibleCells().map((cell) => {
                const meta = colMetaMap.get(cell.column.id);
                return (
                  <td
                    key={cell.id}
                    className={`px-3 py-2.5 text-[var(--ink-primary)] ${
                      meta?.numeric ? "text-right tabular-nums" : "text-left"
                    }`}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
