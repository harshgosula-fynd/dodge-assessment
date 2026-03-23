"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { STATUS_META } from "@/lib/graph-styles";
import type { FlowStatusOverview } from "@/types";

interface Props {
  onLoadSampleFlow: () => void;
  onSearch: (query: string) => void;
  onAskAI: () => void;
}

const SAMPLE_QUERIES = [
  { label: "Trace a complete order flow", action: "sample-flow" },
  { label: "Find incomplete flows", action: "ask:Identify orders with broken or incomplete flows" },
  { label: "Top products by billing", action: "ask:Which products have the most billing documents?" },
  { label: "Unpaid invoices", action: "ask:How many items are still awaiting payment?" },
];

export default function EmptyState({ onLoadSampleFlow, onSearch, onAskAI }: Props) {
  const [stats, setStats] = useState<FlowStatusOverview | null>(null);

  useEffect(() => {
    api.status.overview().then(setStats).catch(() => {});
  }, []);

  const handleAction = (action: string) => {
    if (action === "sample-flow") {
      onLoadSampleFlow();
    } else if (action.startsWith("ask:")) {
      onAskAI();
    }
  };

  return (
    <div className="absolute inset-0 flex items-center justify-center bg-white">
      <div className="max-w-lg w-full px-6">
        {/* Title */}
        <div className="text-center mb-8">
          <h2 className="text-xl font-semibold text-neutral-800 mb-1">
            O2C Context Graph
          </h2>
          <p className="text-sm text-neutral-400">
            Explore SAP Order-to-Cash data as an interactive graph
          </p>
        </div>

        {/* Search */}
        <div className="mb-6">
          <div className="relative">
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400"
              width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
            >
              <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
            </svg>
            <input
              type="text"
              placeholder="Search by customer name, order number, product ID..."
              className="w-full h-10 pl-10 pr-4 text-sm border border-neutral-200 rounded-lg
                         focus:outline-none focus:border-neutral-400 placeholder:text-neutral-400"
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.target as HTMLInputElement).value.trim()) {
                  onSearch((e.target as HTMLInputElement).value.trim());
                }
              }}
            />
          </div>
        </div>

        {/* Quick actions */}
        <div className="mb-6">
          <div className="text-[11px] font-medium text-neutral-400 uppercase tracking-wider mb-2">
            Quick start
          </div>
          <div className="grid grid-cols-2 gap-2">
            {SAMPLE_QUERIES.map((sq) => (
              <button
                key={sq.label}
                onClick={() => handleAction(sq.action)}
                className="text-left px-3 py-2.5 rounded-lg border border-neutral-200
                           hover:bg-neutral-50 hover:border-neutral-300 transition-colors"
              >
                <div className="text-[13px] text-neutral-700">{sq.label}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Dataset summary */}
        {stats && (
          <div>
            <div className="text-[11px] font-medium text-neutral-400 uppercase tracking-wider mb-2">
              Dataset overview
            </div>
            <div className="grid grid-cols-5 gap-2">
              {stats.summary.map((s) => {
                const meta = STATUS_META[s.status];
                return (
                  <div
                    key={s.status}
                    className="text-center px-2 py-2 rounded-lg border border-neutral-100"
                  >
                    <div className="text-lg font-semibold text-neutral-800">{s.count}</div>
                    <div
                      className="text-[10px] font-medium"
                      style={{ color: meta?.color || "#737373" }}
                    >
                      {meta?.label || s.status}
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="text-center mt-2 text-[11px] text-neutral-400">
              {stats.total_items} order items &middot; 8 customers &middot; 69 products
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
