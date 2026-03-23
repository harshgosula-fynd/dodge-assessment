"use client";

import { useEffect, useRef, useCallback, useMemo, useState } from "react";
import cytoscape from "cytoscape";
import { cytoscapeStyles, EXPLORE_LAYOUT, TRACE_LAYOUT, NODE_TYPE_META } from "@/lib/graph-styles";
import type { GraphNode, GraphEdge } from "@/types";

export type LayoutMode = "overview" | "explore" | "trace";

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeSelect: (nodeId: string | null) => void;
  selectedNodeId: string | null;
  chatHighlightedIds?: string[];
  layoutMode?: LayoutMode;
  onClearGraph?: () => void;
  onExpandNeighbors?: (nodeId: string) => void;
}

// Lane order and headers for overview mode
const LANES = [
  { type: "customer", label: "Customers" },
  { type: "sales_order", label: "Sales Orders" },
  { type: "delivery", label: "Deliveries" },
  { type: "billing", label: "Billings" },
  { type: "journal", label: "Journal Entries" },
  { type: "payment", label: "Payments" },
];

// Seeded pseudo-random for consistent jitter
function jitter(seed: number, range: number): number {
  const x = Math.sin(seed * 9301 + 49297) * 49297;
  return (x - Math.floor(x) - 0.5) * range;
}

export default function GraphExplorer({
  nodes,
  edges,
  onNodeSelect,
  selectedNodeId,
  chatHighlightedIds,
  layoutMode = "explore",
  onClearGraph,
  onExpandNeighbors,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const prevFingerprintRef = useRef("");
  const destroyedRef = useRef(false);
  const selectRef = useRef(onNodeSelect);
  selectRef.current = onNodeSelect;
  const expandRef = useRef(onExpandNeighbors);
  expandRef.current = onExpandNeighbors;

  // Tooltip state
  const [tooltip, setTooltip] = useState<{
    x: number; y: number; label: string; type: string; props: Record<string, unknown>;
  } | null>(null);

  // Lane header positions (computed after layout)
  const [laneHeaders, setLaneHeaders] = useState<{ label: string; pct: number; color: string }[]>([]);

  // ── Initialize Cytoscape ──
  useEffect(() => {
    if (!containerRef.current || cyRef.current) return;
    destroyedRef.current = false;

    const cy = cytoscape({
      container: containerRef.current,
      style: cytoscapeStyles as cytoscape.StylesheetStyle[],
      minZoom: 0.1,
      maxZoom: 3,
      boxSelectionEnabled: false,
    });

    // Click handlers
    cy.on("tap", "node", (evt) => {
      if (!destroyedRef.current) selectRef.current(evt.target.id());
    });
    cy.on("tap", (evt) => {
      if (!destroyedRef.current && evt.target === cy) selectRef.current(null);
    });

    // Double-click: expand neighbors
    cy.on("dbltap", "node", (evt) => {
      if (!destroyedRef.current && expandRef.current) {
        expandRef.current(evt.target.id());
      }
    });

    // Hover: show label + tooltip
    cy.on("mouseover", "node", (evt) => {
      const n = evt.target;
      n.style("label", n.data("label"));
      const rp = n.renderedPosition();
      const container = containerRef.current;
      if (container) {
        const rect = container.getBoundingClientRect();
        setTooltip({
          x: rp.x + rect.left,
          y: rp.y + rect.top - 40,
          label: n.data("label"),
          type: n.data("node_type"),
          props: {},
        });
      }
    });
    cy.on("mouseout", "node", (evt) => {
      const n = evt.target;
      if (!n.hasClass("highlighted") && n.data("node_type") !== "customer") {
        n.style("label", "");
      }
      setTooltip(null);
    });

    cyRef.current = cy;
    return () => {
      destroyedRef.current = true;
      cyRef.current = null;
      try { cy.destroy(); } catch { /* */ }
    };
  }, []);

  // ── Data fingerprint ──
  const fingerprint = useMemo(() => {
    const nk = nodes.map((n) => n.node_id).sort().join(",");
    const ek = edges.map((e) => `${e.source_id}>${e.target_id}`).sort().join(",");
    return `${nk}|${ek}|${layoutMode}`;
  }, [nodes, edges, layoutMode]);

  // ── Sync data + layout ──
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || destroyedRef.current) return;
    if (fingerprint === prevFingerprintRef.current) return;
    prevFingerprintRef.current = fingerprint;

    const nodeSet = new Set(nodes.map((n) => n.node_id));
    cy.elements().remove();
    setLaneHeaders([]);
    if (nodes.length === 0) return;

    cy.add(nodes.map((n) => ({
      group: "nodes" as const,
      data: { id: n.node_id, label: n.label, node_type: n.node_type },
    })));

    cy.add(
      edges
        .filter((e) => nodeSet.has(e.source_id) && nodeSet.has(e.target_id))
        .map((e, i) => ({
          group: "edges" as const,
          data: { id: `e-${i}`, source: e.source_id, target: e.target_id, edge_type: e.edge_type },
        }))
    );

    try {
      if (layoutMode === "overview") {
        runOverviewLayout(cy);
      } else if (layoutMode === "trace") {
        cy.layout(TRACE_LAYOUT).run();
        cy.fit(undefined, 40);
      } else {
        cy.layout(EXPLORE_LAYOUT).run();
        cy.fit(undefined, 40);
      }
    } catch { /* */ }
  }, [fingerprint, nodes, edges, layoutMode]);

  // ── Overview swimlane layout ──
  const runOverviewLayout = useCallback((cy: cytoscape.Core) => {
    const W = cy.width();
    const H = cy.height();
    const margin = 80;
    const usableW = W - margin * 2;
    const usableH = H - margin * 2 - 30; // 30px for headers

    // Count nodes per lane
    const laneCounts: Record<string, number> = {};
    const laneNodes: Record<string, cytoscape.NodeSingular[]> = {};
    LANES.forEach((l) => { laneCounts[l.type] = 0; laneNodes[l.type] = []; });

    cy.nodes().forEach((n) => {
      const t = n.data("node_type") as string;
      if (laneNodes[t]) {
        laneNodes[t].push(n);
        laneCounts[t]++;
      }
    });

    const activeLanes = LANES.filter((l) => laneCounts[l.type] > 0);
    const laneSpacing = activeLanes.length > 1 ? usableW / (activeLanes.length - 1) : 0;

    // Position each node
    activeLanes.forEach((lane, laneIdx) => {
      const x = margin + laneIdx * laneSpacing;
      const nodesInLane = laneNodes[lane.type];
      const count = nodesInLane.length;
      const vSpacing = Math.min(60, (usableH) / Math.max(count, 1));
      const startY = margin + 30 + (usableH - count * vSpacing) / 2;

      nodesInLane.forEach((n, i) => {
        const j = jitter(i * 31 + laneIdx * 7, laneSpacing * 0.12);
        n.position({
          x: x + j,
          y: startY + i * vSpacing + jitter(i * 17 + laneIdx * 3, vSpacing * 0.3),
        });
      });
    });

    cy.fit(undefined, 40);

    // Lane headers as percentage positions (stable across zoom/pan)
    const headers = activeLanes.map((lane, laneIdx) => {
      const pct = activeLanes.length > 1
        ? 5 + (laneIdx / (activeLanes.length - 1)) * 90  // 5% to 95%
        : 50;
      return {
        label: lane.label,
        pct,
        color: NODE_TYPE_META[lane.type]?.color || "#737373",
      };
    });
    setLaneHeaders(headers);
  }, []);

  // ── Highlighting ──
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || destroyedRef.current) return;

    cy.elements().removeClass("highlighted faded");
    cy.nodes().forEach((n) => {
      if (n.data("node_type") !== "customer") n.style("label", "");
    });

    if (selectedNodeId) {
      const sel = cy.getElementById(selectedNodeId);
      if (sel.length > 0) {
        const hood = sel.neighborhood().add(sel);
        hood.addClass("highlighted");
        cy.elements().not(hood).addClass("faded");
        try { cy.center(sel); } catch { /* */ }
      }
      return;
    }

    if (chatHighlightedIds && chatHighlightedIds.length > 0) {
      let matched = cy.collection();
      for (const nid of chatHighlightedIds) {
        const el = cy.getElementById(nid);
        if (el.length > 0) matched = matched.add(el);
      }
      if (matched.length > 0) {
        const withEdges = matched.add(matched.edgesWith(matched));
        withEdges.addClass("highlighted");
        cy.elements().not(withEdges).addClass("faded");
        try { cy.fit(matched, 60); } catch { /* */ }
      }
    }
  }, [selectedNodeId, chatHighlightedIds]);

  // ── Controls ──
  const handleFit = useCallback(() => {
    cyRef.current?.fit(undefined, 40);
  }, []);

  const handleZoom = useCallback((dir: number) => {
    const cy = cyRef.current;
    if (!cy || destroyedRef.current) return;
    cy.zoom({
      level: cy.zoom() * (dir > 0 ? 1.3 : 1 / 1.3),
      renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
    });
  }, []);

  return (
    <div className="relative w-full h-full overflow-hidden">
      {/* Cytoscape canvas */}
      <div ref={containerRef} className="w-full h-full" />

      {/* Lane headers (overview mode) — percentage positioned, stable */}
      {layoutMode === "overview" && laneHeaders.length > 0 && (
        <div className="absolute top-9 left-0 right-0 h-6 pointer-events-none flex items-center">
          {laneHeaders.map((h) => (
            <div
              key={h.label}
              className="absolute flex items-center gap-1.5 -translate-x-1/2"
              style={{ left: `${h.pct}%` }}
            >
              <span className="w-2 h-2 rounded-full shrink-0" style={{ background: h.color }} />
              <span className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider whitespace-nowrap">
                {h.label}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 pointer-events-none px-2.5 py-1.5 bg-neutral-900 text-white
                     text-[11px] rounded-md shadow-lg whitespace-nowrap"
          style={{ left: tooltip.x, top: tooltip.y, transform: "translateX(-50%)" }}
        >
          <span className="font-medium">{tooltip.label}</span>
          <span className="text-neutral-400 ml-1.5">{NODE_TYPE_META[tooltip.type]?.label || tooltip.type}</span>
        </div>
      )}

      {/* Controls */}
      <div className="absolute bottom-4 left-4 flex items-center gap-1">
        {[
          { ch: "+", t: "Zoom in", fn: () => handleZoom(1) },
          { ch: "−", t: "Zoom out", fn: () => handleZoom(-1) },
          { ch: "⊡", t: "Fit to view", fn: handleFit },
        ].map((b) => (
          <button
            key={b.t} onClick={b.fn} title={b.t}
            className="w-7 h-7 bg-white border border-neutral-200 rounded text-xs
                       hover:bg-neutral-50 flex items-center justify-center shadow-sm
                       text-neutral-500 hover:text-neutral-700"
          >
            {b.ch}
          </button>
        ))}
      </div>

      {/* Mode badge */}
      {layoutMode === "trace" && (
        <div className="absolute top-3 right-3 text-[10px] px-2 py-1 bg-blue-50 text-blue-600
                        border border-blue-200 rounded font-medium">
          Flow trace
        </div>
      )}
    </div>
  );
}
