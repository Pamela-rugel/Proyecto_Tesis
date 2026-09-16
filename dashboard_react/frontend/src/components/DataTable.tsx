import type { ReactNode } from "react";

interface Column {
  key: string;
  label: string;
  render?: (row: Record<string, unknown>) => ReactNode;
}

interface Props {
  columns: Column[];
  rows: Record<string, unknown>[];
  maxHeight?: number;
}

function fmt(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "boolean") return value ? "Sí" : "No";
  return String(value);
}

export default function DataTable({ columns, rows, maxHeight }: Props) {
  if (rows.length === 0) {
    return <p className="text-sm text-slate-400">Sin registros.</p>;
  }
  return (
    <div className="overflow-auto rounded-lg border border-slate-200" style={maxHeight ? { maxHeight } : undefined}>
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 sticky top-0">
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className="text-left px-3 py-2 font-medium text-xs uppercase tracking-wide text-slate-500 whitespace-nowrap"
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-slate-100 hover:bg-slate-50/70 transition-colors">
              {columns.map((c) => (
                <td key={c.key} className="px-3 py-2 text-slate-700 whitespace-nowrap">
                  {c.render ? c.render(row) : fmt(row[c.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
