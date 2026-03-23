// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Stylesheet = { selector: string; style: Record<string, any> };

const NODE_COLORS: Record<string, string> = {
  customer: "#2563eb",
  sales_order: "#7c3aed",
  delivery: "#0891b2",
  billing: "#059669",
  journal: "#d97706",
  payment: "#16a34a",
  product: "#ef4444",
  plant: "#64748b",
};

const NODE_SHAPES: Record<string, string> = {
  customer: "ellipse",
  sales_order: "round-rectangle",
  delivery: "round-rectangle",
  billing: "round-rectangle",
  journal: "round-rectangle",
  payment: "diamond",
  product: "round-triangle",
  plant: "round-hexagon",
};

export const cytoscapeStyles: Stylesheet[] = [
  // ── Base node ──
  {
    selector: "node",
    style: {
      label: "",
      "text-valign": "bottom",
      "text-halign": "center",
      "font-size": "8px",
      "font-family": "Inter, sans-serif",
      "font-weight": 500,
      color: "#525252",
      "text-margin-y": 4,
      "background-color": "#a3a3a3",
      "background-opacity": 0.85,
      width: 16,
      height: 16,
      "border-width": 1.5,
      "border-color": "#ffffff",
      "text-max-width": "80px",
      "text-wrap": "ellipsis",
      "overlay-opacity": 0,
    },
  },
  // Node type colors + shapes
  ...Object.entries(NODE_COLORS).map(
    ([type, color]): Stylesheet => ({
      selector: `node[node_type = "${type}"]`,
      style: {
        "background-color": color,
        shape: NODE_SHAPES[type] || "ellipse",
      },
    })
  ),
  // Customer nodes: always show label, larger
  {
    selector: 'node[node_type = "customer"]',
    style: {
      label: "data(label)",
      width: 26,
      height: 26,
      "font-size": "10px",
      "font-weight": 600,
      color: "#171717",
    },
  },
  // Product/plant nodes: smaller, more transparent
  {
    selector: 'node[node_type = "product"], node[node_type = "plant"]',
    style: {
      width: 12,
      height: 12,
      "background-opacity": 0.5,
    },
  },
  // ── Highlighted nodes: show label, larger, ring ──
  {
    selector: "node.highlighted",
    style: {
      label: "data(label)",
      "border-width": 2.5,
      "border-color": "#2563eb",
      opacity: 1,
      width: 22,
      height: 22,
      "font-size": "9px",
      "font-weight": 600,
      color: "#171717",
    },
  },
  // Selected node
  {
    selector: "node:selected",
    style: {
      label: "data(label)",
      "border-width": 3,
      "border-color": "#171717",
      width: 26,
      height: 26,
      "font-size": "9px",
      "font-weight": 600,
    },
  },
  // Faded
  { selector: "node.faded", style: { opacity: 0.08 } },

  // ── Edges ──
  {
    selector: "edge",
    style: {
      width: 1,
      "line-color": "#d4d4d4",
      "target-arrow-color": "#d4d4d4",
      "target-arrow-shape": "triangle",
      "arrow-scale": 0.5,
      "curve-style": "bezier",
      opacity: 0.35,
      label: "",
    },
  },
  // Edge type tints (subtle in default state)
  { selector: 'edge[edge_type = "PLACED_ORDER"]', style: { "line-color": "#93c5fd", "target-arrow-color": "#93c5fd", opacity: 0.35 } },
  { selector: 'edge[edge_type = "FULFILLED_BY"]', style: { "line-color": "#67e8f9", "target-arrow-color": "#67e8f9", opacity: 0.3 } },
  { selector: 'edge[edge_type = "BILLED_AS"]', style: { "line-color": "#6ee7b7", "target-arrow-color": "#6ee7b7", opacity: 0.3 } },
  { selector: 'edge[edge_type = "POSTED_AS"]', style: { "line-color": "#fcd34d", "target-arrow-color": "#fcd34d", opacity: 0.3 } },
  { selector: 'edge[edge_type = "CLEARED_BY"]', style: { "line-color": "#86efac", "target-arrow-color": "#86efac", opacity: 0.3 } },
  { selector: 'edge[edge_type = "CANCELLED_BY"]', style: { "line-color": "#fca5a5", "target-arrow-color": "#fca5a5", "line-style": "dashed", opacity: 0.3 } },
  { selector: 'edge[edge_type = "CONTAINS_PRODUCT"]', style: { opacity: 0.1, width: 0.5 } },
  { selector: 'edge[edge_type = "SHIPS_FROM"]', style: { opacity: 0.1, width: 0.5 } },
  // Highlighted edges — strong, prominent
  {
    selector: "edge.highlighted",
    style: {
      width: 2.5,
      "line-color": "#3b82f6",
      "target-arrow-color": "#3b82f6",
      opacity: 0.9,
      "arrow-scale": 0.7,
    },
  },
  { selector: "edge.faded", style: { opacity: 0.03 } },
];

export const NODE_TYPE_META: Record<string, { label: string; color: string }> = {
  customer: { label: "Customer", color: "#2563eb" },
  sales_order: { label: "Sales Order", color: "#7c3aed" },
  delivery: { label: "Delivery", color: "#0891b2" },
  billing: { label: "Billing", color: "#059669" },
  journal: { label: "Journal Entry", color: "#d97706" },
  payment: { label: "Payment", color: "#16a34a" },
  product: { label: "Product", color: "#ef4444" },
  plant: { label: "Plant", color: "#64748b" },
};

export const STATUS_META: Record<string, { label: string; color: string; bg: string }> = {
  complete: { label: "Complete", color: "#16a34a", bg: "#f0fdf4" },
  ordered_only: { label: "Ordered Only", color: "#d97706", bg: "#fffbeb" },
  delivered_not_billed: { label: "Not Billed", color: "#dc2626", bg: "#fef2f2" },
  billed_no_posting: { label: "No Posting", color: "#d97706", bg: "#fffbeb" },
  posted_not_paid: { label: "Unpaid", color: "#ea580c", bg: "#fff7ed" },
  cancelled: { label: "Cancelled", color: "#64748b", bg: "#f8fafc" },
};

export const TRACE_LAYOUT = {
  name: "breadthfirst",
  directed: true,
  padding: 40,
  spacingFactor: 1.5,
  animate: false,
  avoidOverlap: true,
};

export const EXPLORE_LAYOUT = {
  name: "cose",
  animate: false,
  randomize: true,
  nodeRepulsion: () => 8000,
  idealEdgeLength: () => 100,
  edgeElasticity: () => 80,
  gravity: 0.3,
  numIter: 400,
  padding: 40,
  componentSpacing: 80,
};
