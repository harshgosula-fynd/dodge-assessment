"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import dynamic from "next/dynamic";
import { api } from "@/lib/api";
import { NODE_TYPE_META } from "@/lib/graph-styles";
import SearchBar from "@/components/SearchBar";
import NodeDetail from "@/components/NodeDetail";
import ChatPanel from "@/components/ChatPanel";
import Legend from "@/components/Legend";
import ErrorBoundary from "@/components/ErrorBoundary";
import type { GraphNode, GraphEdge, FlowStatusOverview, ChatMessage } from "@/types";
import type { LayoutMode } from "@/components/GraphExplorer";

const INITIAL_MESSAGES: ChatMessage[] = [
  { role: "assistant", content: "Ask me about sales orders, deliveries, billing, payments, or flow status." },
];

const GraphExplorer = dynamic(() => import("@/components/GraphExplorer"), { ssr: false });

type ViewMode = "overview" | "explore" | "trace";

export default function Home() {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("overview");
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("explore");
  const [chatHighlightedIds, setChatHighlightedIds] = useState<string[]>([]);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<FlowStatusOverview | null>(null);
  const [activeFilters, setActiveFilters] = useState<Set<string>>(
    new Set(["customer", "sales_order", "delivery", "billing", "journal", "payment", "product", "plant"])
  );

  // ── Load overview on mount ──
  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.graph.getInitial(),
      api.status.overview(),
    ])
      .then(([sg, st]) => {
        setNodes(sg.nodes);
        setEdges(sg.edges);
        setStats(st);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // ── Graph data helpers ──
  const loadSubgraph = useCallback((sg: { nodes: GraphNode[]; edges: GraphEdge[] }, mode: ViewMode, layout: LayoutMode) => {
    setLoading(false);
    setNodes(sg.nodes);
    setEdges(sg.edges);
    setViewMode(mode);
    setLayoutMode(layout);
    setChatHighlightedIds([]);
  }, []);

  const mergeSubgraph = useCallback((sg: { nodes: GraphNode[]; edges: GraphEdge[] }) => {
    setNodes((prev) => {
      const existing = new Set(prev.map((n) => n.node_id));
      const added = sg.nodes.filter((n) => !existing.has(n.node_id));
      return added.length > 0 ? [...prev, ...added] : prev;
    });
    setEdges((prev) => {
      const existing = new Set(prev.map((e) => `${e.source_id}|${e.edge_type}|${e.target_id}`));
      const added = sg.edges.filter((e) => !existing.has(`${e.source_id}|${e.edge_type}|${e.target_id}`));
      return added.length > 0 ? [...prev, ...added] : prev;
    });
  }, []);

  // ── Handlers ──
  const handleNodeSelect = useCallback((nodeId: string | null) => {
    setSelectedNodeId(nodeId);
    if (nodeId) {
      setChatHighlightedIds([]);
      setChatOpen(false);
    }
  }, []);

  const handleSearchSelect = useCallback(async (nodeId: string) => {
    // Entity-type-aware focus: loads business-meaningful subgraph
    try {
      const [type] = nodeId.split(":");
      const sg = await api.graph.getFocus(nodeId);
      const layout: LayoutMode = (type === "customer" || type === "product") ? "explore" : "trace";
      loadSubgraph(sg, layout === "trace" ? "trace" : "explore", layout);
      setSelectedNodeId(nodeId);
      setChatOpen(false);
    } catch {
      // Fallback: just load neighbors
      try {
        const sg = await api.graph.getNeighbors(nodeId, 1);
        loadSubgraph(sg, "explore", "explore");
        setSelectedNodeId(nodeId);
      } catch { /* */ }
    }
  }, [loadSubgraph]);

  const handleExpandNeighbors = useCallback(async (nodeId: string) => {
    try {
      const [type] = nodeId.split(":");
      if (type === "customer") {
        // Customer: load all their orders
        const sg = await api.graph.getFocus(nodeId);
        mergeSubgraph(sg);
      } else {
        // For transactional nodes: load 2-hop neighbors including all types
        // plus the full focus context
        const [sg1, sg2] = await Promise.all([
          api.graph.getNeighbors(nodeId, 2, ""),
          api.graph.getFocus(nodeId),
        ]);
        mergeSubgraph(sg1);
        mergeSubgraph(sg2);
      }
    } catch { /* */ }
  }, [mergeSubgraph]);

  const handleTraceFlow = useCallback(async (nodeId: string) => {
    const [, id] = nodeId.split(":");
    if (!id) return;
    try {
      // Find the related SO
      const sg = await api.graph.getFocus(nodeId);
      loadSubgraph(sg, "trace", "trace");
      setSelectedNodeId(nodeId);
    } catch { /* */ }
  }, [loadSubgraph]);

  const handleNavigate = useCallback((nodeId: string) => {
    setSelectedNodeId(nodeId);
    setChatOpen(false);
  }, []);

  const resetToOverview = useCallback(() => {
    setSelectedNodeId(null);
    setChatHighlightedIds([]);
    setLoading(true);
    api.graph.getInitial()
      .then((sg) => loadSubgraph(sg, "overview", "explore"))
      .finally(() => setLoading(false));
  }, [loadSubgraph]);

  const handleChatHighlight = useCallback((nodeIds: string[]) => {
    setChatHighlightedIds(nodeIds);
    setSelectedNodeId(null);
  }, []);

  const handleChatNavigate = useCallback(async (nodeId: string) => {
    setChatHighlightedIds([]);
    setChatOpen(false);
    try {
      const sg = await api.graph.getFocus(nodeId);
      const [type] = nodeId.split(":");
      const layout: LayoutMode = (type === "customer" || type === "product") ? "explore" : "trace";
      loadSubgraph(sg, layout === "trace" ? "trace" : "explore", layout);
      setSelectedNodeId(nodeId);
    } catch {
      setSelectedNodeId(nodeId);
    }
  }, [loadSubgraph]);

  const handleFilterToggle = useCallback((type: string) => {
    setActiveFilters((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }, []);

  // ── Filtered data ──
  const filteredNodes = useMemo(
    () => nodes.filter((n) => activeFilters.has(n.node_type)),
    [nodes, activeFilters]
  );
  const filteredNodeIds = useMemo(
    () => new Set(filteredNodes.map((n) => n.node_id)),
    [filteredNodes]
  );
  const filteredEdges = useMemo(
    () => edges.filter((e) => filteredNodeIds.has(e.source_id) && filteredNodeIds.has(e.target_id)),
    [edges, filteredNodeIds]
  );

  return (
    <div className="h-screen flex flex-col bg-neutral-50">
      {/* ── Top bar ── */}
      <header className="h-11 bg-white border-b border-neutral-200 flex items-center px-4 shrink-0 z-20">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <h1 className="text-[13px] font-bold text-neutral-800 whitespace-nowrap">O2C Graph</h1>
          <div className="w-px h-4 bg-neutral-200" />
          <SearchBar onSelect={handleSearchSelect} />
          <div className="w-px h-4 bg-neutral-200" />
          <Legend activeFilters={activeFilters} onToggle={handleFilterToggle} />
        </div>

        <div className="flex items-center gap-2 shrink-0 ml-3">
          {/* Stats summary */}
          {stats && (
            <div className="hidden md:flex items-center gap-1.5 mr-1">
              {stats.summary.slice(0, 3).map((s) => (
                <span key={s.status} className="text-[10px] text-neutral-400 tabular-nums">
                  {s.count} {s.status.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}
          <button
            onClick={() => setChatOpen((o) => !o)}
            className={`h-7 px-3 text-[11px] font-medium rounded-md flex items-center gap-1.5 transition-colors
              ${chatOpen
                ? "bg-neutral-900 text-white"
                : "bg-blue-600 text-white hover:bg-blue-700"
              }`}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            Ask AI
          </button>
        </div>
      </header>

      {/* ── Main content ── */}
      <div className="flex-1 flex overflow-hidden">
        {/* Graph region */}
        <div className="flex-1 min-w-0 relative">
          {loading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-sm text-neutral-400">Loading graph...</div>
            </div>
          ) : (
            <ErrorBoundary
              fallback={
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-sm text-neutral-500">Graph error. Try resetting.</span>
                </div>
              }
            >
              <GraphExplorer
                nodes={filteredNodes}
                edges={filteredEdges}
                onNodeSelect={handleNodeSelect}
                selectedNodeId={selectedNodeId}
                chatHighlightedIds={chatHighlightedIds}
                layoutMode={layoutMode}
                onClearGraph={resetToOverview}
                onExpandNeighbors={handleExpandNeighbors}
              />
            </ErrorBoundary>
          )}

          {/* Navigation bar — shows mode + back action */}
          <div className="absolute top-0 left-0 right-0 h-8 bg-white/90 backdrop-blur-sm border-b border-neutral-100
                          flex items-center justify-between px-3 z-10">
            <div className="flex items-center gap-2">
              {viewMode !== "overview" && (
                <button
                  onClick={resetToOverview}
                  className="flex items-center gap-1 text-[11px] text-blue-600 hover:text-blue-700 font-medium"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="m15 18-6-6 6-6"/>
                  </svg>
                  Overview
                </button>
              )}
              <span className="text-[10px] text-neutral-400 font-medium uppercase tracking-wider">
                {viewMode === "overview" && "O2C Overview"}
                {viewMode === "explore" && "Focused view"}
                {viewMode === "trace" && "Flow trace"}
              </span>
            </div>
            <span className="text-[10px] text-neutral-400 tabular-nums">
              {filteredNodes.length} nodes &middot; {filteredEdges.length} edges
            </span>
          </div>
        </div>

        {/* ── Detail panel (always visible when node selected) ── */}
        {selectedNodeId && (
          <div className="w-[340px] shrink-0 bg-white border-l border-neutral-200 overflow-y-auto">
            <ErrorBoundary
              key={selectedNodeId}
              fallback={<div className="p-4 text-sm text-neutral-500">Could not load details.</div>}
            >
              <NodeDetail
                nodeId={selectedNodeId}
                onClose={() => setSelectedNodeId(null)}
                onNavigate={handleNavigate}
                onExpandNeighbors={viewMode === "trace" ? handleExpandNeighbors : undefined}
                onTraceFlow={handleTraceFlow}
              />
            </ErrorBoundary>
          </div>
        )}

        {/* ── Chat panel (opens on Ask AI click) ── */}
        {chatOpen && (
          <div className="w-[380px] shrink-0 bg-white border-l border-neutral-200 flex flex-col">
            <ErrorBoundary fallback={<div className="p-4 text-sm text-neutral-500">Chat error.</div>}>
              <ChatPanel
                onClose={() => setChatOpen(false)}
                onHighlightNodes={handleChatHighlight}
                onNavigateNode={handleChatNavigate}
                messages={chatMessages}
                onMessagesChange={setChatMessages}
              />
            </ErrorBoundary>
          </div>
        )}
      </div>
    </div>
  );
}
