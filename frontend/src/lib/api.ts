import type {
  SubgraphResponse,
  NodeSearchResult,
  GraphNode,
  FlowStatusOverview,
  BrokenFlowItem,
  LineageFlow,
  ChatResponse,
} from "@/types";

const BASE = "/api";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  graph: {
    getInitial: () =>
      fetchJSON<SubgraphResponse>(`${BASE}/graph/initial`),
    getSampleFlow: () =>
      fetchJSON<SubgraphResponse>(`${BASE}/graph/sample-flow`),
    getFlow: (salesOrderId: string) =>
      fetchJSON<SubgraphResponse>(`${BASE}/graph/flow/${salesOrderId}`),
    getFocus: (nodeId: string) =>
      fetchJSON<SubgraphResponse>(`${BASE}/graph/focus/${nodeId}`),
    getNode: (nodeId: string) =>
      fetchJSON<GraphNode>(`${BASE}/graph/node/${nodeId}`),
    getNeighbors: (nodeId: string, depth = 1, excludeTypes = "product,plant") =>
      fetchJSON<SubgraphResponse>(
        `${BASE}/graph/neighbors/${nodeId}?depth=${depth}&exclude_types=${excludeTypes}`
      ),
    search: (q: string, nodeType?: string, limit = 20) => {
      const params = new URLSearchParams({ q, limit: String(limit) });
      if (nodeType) params.set("node_type", nodeType);
      return fetchJSON<NodeSearchResult[]>(
        `${BASE}/graph/search?${params}`
      );
    },
  },
  lineage: {
    getOrder: (salesOrderId: string) =>
      fetchJSON<LineageFlow>(`${BASE}/lineage/order/${salesOrderId}`),
    trace: (docType: string, docId: string) =>
      fetchJSON<LineageFlow>(`${BASE}/lineage/trace/${docType}/${docId}`),
  },
  status: {
    overview: () => fetchJSON<FlowStatusOverview>(`${BASE}/status/overview`),
    broken: (status?: string, limit = 50) => {
      const params = new URLSearchParams({ limit: String(limit) });
      if (status) params.set("status", status);
      return fetchJSON<BrokenFlowItem[]>(`${BASE}/status/broken?${params}`);
    },
  },
  chat: (message: string) =>
    fetchJSON<ChatResponse>(`${BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    }),
};
