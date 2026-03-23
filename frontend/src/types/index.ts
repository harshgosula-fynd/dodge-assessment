export interface GraphNode {
  node_id: string;
  node_type: string;
  label: string;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  source_id: string;
  target_id: string;
  edge_type: string;
  properties: Record<string, unknown>;
}

export interface SubgraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface NodeSearchResult {
  node_id: string;
  node_type: string;
  label: string;
}

export interface FlowStatusSummary {
  status: string;
  count: number;
}

export interface FlowStatusOverview {
  total_items: number;
  summary: FlowStatusSummary[];
}

export interface BrokenFlowItem {
  sales_order_id: string;
  so_item_number: number;
  product_id: string;
  customer_id: string;
  order_amount: number | null;
  flow_status: string;
  delivery_id: string | null;
  active_billing_id: string | null;
}

export interface LineageStep {
  stage: string;
  document_id: string | null;
  item_number: number | null;
  amount: number | null;
  date: string | null;
  status: string | null;
}

export interface LineageItemFlow {
  so_item_number: number;
  product_id: string;
  order_amount: number | null;
  steps: LineageStep[];
  flow_status: string;
}

export interface LineageFlow {
  sales_order_id: string;
  customer_id: string;
  items: LineageItemFlow[];
}

export interface ChatResponse {
  answer: string;
  query_plan: Record<string, unknown> | null;
  executed_sql: string | null;
  data: Record<string, unknown>[] | null;
  result_count: number | null;
  highlighted_nodes: string[] | null;
  rejected: boolean;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  data?: Record<string, unknown>[] | null;
  queryPlan?: Record<string, unknown> | null;
  executedSql?: string | null;
  resultCount?: number | null;
  highlightedNodes?: string[] | null;
}
