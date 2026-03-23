"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { STATUS_META } from "@/lib/graph-styles";
import type { FlowStatusOverview } from "@/types";

export default function StatusBar() {
  const [data, setData] = useState<FlowStatusOverview | null>(null);

  useEffect(() => {
    api.status.overview().then(setData).catch(() => {});
  }, []);

  if (!data) return null;

  return (
    <div className="flex items-center gap-3">
      {data.summary.map((s) => {
        const meta = STATUS_META[s.status];
        const pct = ((s.count / data.total_items) * 100).toFixed(0);
        return (
          <div
            key={s.status}
            className="flex items-center gap-1.5"
            title={`${meta?.label || s.status}: ${s.count} items (${pct}%)`}
          >
            <span
              className="w-2 h-2 rounded-full"
              style={{ background: meta?.color || "#94a3b8" }}
            />
            <span className="text-xs text-neutral-500">
              {s.count}
            </span>
          </div>
        );
      })}
      <span className="text-xs text-neutral-300">|</span>
      <span className="text-xs text-neutral-400">{data.total_items} items</span>
    </div>
  );
}
