"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { NODE_TYPE_META, STATUS_META } from "@/lib/graph-styles";
import type { GraphNode, LineageFlow } from "@/types";

interface Props {
  nodeId: string;
  onClose: () => void;
  onNavigate: (nodeId: string) => void;
  onExpandNeighbors?: (nodeId: string) => void;
  onTraceFlow?: (nodeId: string) => void;
}

export default function NodeDetail({ nodeId, onClose, onNavigate, onExpandNeighbors, onTraceFlow }: Props) {
  const [node, setNode] = useState<GraphNode | null>(null);
  const [lineage, setLineage] = useState<LineageFlow | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLineage(null);
    setNode(null);

    api.graph
      .getNode(nodeId)
      .then((n) => { if (!cancelled) setNode(n); })
      .catch(() => { if (!cancelled) setNode(null); })
      .finally(() => { if (!cancelled) setLoading(false); });

    // Load lineage for transactional nodes
    const parts = nodeId.split(":");
    const type = parts[0];
    const id = parts.slice(1).join(":");
    if (id && ["sales_order", "delivery", "billing", "journal", "payment"].includes(type)) {
      api.lineage.trace(type, id).then((l) => { if (!cancelled) setLineage(l); }).catch(() => {});
    }

    return () => { cancelled = true; };
  }, [nodeId]);

  if (loading) {
    return (
      <Shell onClose={onClose}>
        <div className="p-5 text-sm text-neutral-400">Loading...</div>
      </Shell>
    );
  }

  if (!node) {
    return (
      <Shell onClose={onClose}>
        <div className="p-5 text-sm text-neutral-400">Node not found</div>
      </Shell>
    );
  }

  const meta = NODE_TYPE_META[node.node_type];

  return (
    <Shell onClose={onClose}>
      {/* Header */}
      <div className="px-5 pt-5 pb-4">
        <div className="flex items-center gap-2 mb-1.5">
          <span
            className="w-2.5 h-2.5 rounded-full shrink-0"
            style={{ background: meta?.color || "#94a3b8" }}
          />
          <span className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
            {meta?.label || node.node_type}
          </span>
        </div>
        <h3 className="text-[15px] font-semibold text-neutral-900 leading-snug">
          {node.label}
        </h3>
        <p className="text-[11px] text-neutral-400 mt-1 font-mono">{nodeId}</p>
      </div>

      {/* Properties */}
      <div className="border-t border-neutral-100">
        <div className="px-5 pt-3 pb-1">
          <h4 className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider mb-2">
            Properties
          </h4>
        </div>
        <div className="px-5 pb-4 space-y-2">
          {Object.entries(node.properties)
            .filter(([, v]) => v !== null && v !== undefined && v !== "")
            .map(([key, value]) => (
              <div key={key} className="flex items-start justify-between gap-3">
                <span className="text-xs text-neutral-500 shrink-0">{fmtKey(key)}</span>
                <span className="text-xs text-neutral-900 font-medium text-right break-all">
                  {fmtVal(value)}
                </span>
              </div>
            ))}
          {Object.entries(node.properties).filter(([, v]) => v !== null && v !== undefined && v !== "").length === 0 && (
            <p className="text-xs text-neutral-400 italic">No properties</p>
          )}
        </div>
      </div>

      {/* Actions */}
      {(onExpandNeighbors || onTraceFlow) && (
        <div className="border-t border-neutral-100 px-5 py-3 flex gap-2">
          {onExpandNeighbors && (
            <button
              onClick={() => onExpandNeighbors(nodeId)}
              className="flex-1 h-7 text-[11px] font-medium border border-neutral-200 rounded-md
                         text-neutral-600 hover:bg-neutral-50 transition-colors"
            >
              Expand neighbors
            </button>
          )}
          {onTraceFlow && ["sales_order", "delivery", "billing", "journal", "payment"].includes(node.node_type) && (
            <button
              onClick={() => onTraceFlow(nodeId)}
              className="flex-1 h-7 text-[11px] font-medium border border-blue-200 rounded-md
                         text-blue-600 hover:bg-blue-50 transition-colors"
            >
              Trace flow
            </button>
          )}
        </div>
      )}

      {/* Lineage flow */}
      {lineage && lineage.items.length > 0 && (
        <div className="border-t border-neutral-100">
          <div className="px-5 pt-3 pb-1">
            <h4 className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider mb-2">
              Order Flow
            </h4>
          </div>
          <div className="px-5 pb-4">
            {lineage.items.map((item) => {
              const sMeta = STATUS_META[item.flow_status];
              return (
                <div key={item.so_item_number} className="mb-4 last:mb-0">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[11px] text-neutral-500 font-medium">
                      Item {item.so_item_number} &middot; {item.product_id}
                    </span>
                    {sMeta && (
                      <span
                        className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                        style={{ color: sMeta.color, background: sMeta.bg }}
                      >
                        {sMeta.label}
                      </span>
                    )}
                  </div>
                  {/* Step timeline */}
                  <div className="ml-1">
                    {item.steps.map((step, i) => {
                      const stepColor = NODE_TYPE_META[step.stage]?.color || "#94a3b8";
                      return (
                        <div key={i} className="flex items-start gap-2.5">
                          <div className="flex flex-col items-center pt-[5px]">
                            <div className="w-[7px] h-[7px] rounded-full shrink-0" style={{ background: stepColor }} />
                            {i < item.steps.length - 1 && <div className="w-px h-5 bg-neutral-200 mt-0.5" />}
                          </div>
                          <div className="flex-1 pb-1.5 min-w-0">
                            <div className="flex items-center gap-1.5">
                              <button
                                onClick={() => {
                                  if (step.document_id) {
                                    const t = step.stage === "journal_entry" ? "journal" : step.stage;
                                    onNavigate(`${t}:${step.document_id}`);
                                  }
                                }}
                                className="text-[11px] font-medium text-neutral-800 hover:text-blue-600 transition-colors"
                              >
                                {fmtKey(step.stage)}
                              </button>
                              <span className="text-[10px] text-neutral-400 font-mono truncate">
                                {step.document_id}
                              </span>
                            </div>
                            {step.amount !== null && (
                              <span className="text-[10px] text-neutral-500">
                                {fmtCurrency(step.amount)}
                              </span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Shell>
  );
}

function Shell({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="w-80 h-full bg-white border-l border-neutral-200 overflow-y-auto shrink-0">
      <div className="flex items-center justify-between px-5 pt-4 pb-0">
        <span className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider">
          Details
        </span>
        <button
          onClick={onClose}
          className="w-5 h-5 flex items-center justify-center rounded text-neutral-400
                     hover:text-neutral-600 hover:bg-neutral-100 transition-colors text-sm"
        >
          &times;
        </button>
      </div>
      {children}
    </div>
  );
}

function fmtKey(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function fmtVal(val: unknown): string {
  if (typeof val === "boolean") return val ? "Yes" : "No";
  if (typeof val === "number") return val.toLocaleString();
  return String(val);
}

function fmtCurrency(val: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(val);
}
