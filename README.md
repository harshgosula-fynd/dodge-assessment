# O2C Context Graph

A full-stack system that ingests SAP Order-to-Cash data, models it as an interconnected graph of business entities, and provides an AI-powered natural language query interface for exploring and analyzing the data.

## Architecture

```
User
 │
 ├── Graph Explorer (Cytoscape.js)
 │     click node → detail panel with metadata + flow timeline
 │     search → find any entity by name/ID
 │     expand → load connected neighbors on demand
 │
 └── Chat Interface (Ask AI)
       │
       ▼
   ┌─────────────────┐
   │  Guardrail       │  keyword pre-filter + LLM domain classifier
   │  (reject off-    │  rejects questions not about O2C data
   │   topic prompts) │
   └────────┬────────┘
            ▼
   ┌─────────────────┐
   │  Query Planner   │  LLM maps natural language → structured JSON plan
   │  (LLM)           │  constrained to fixed set of intents + entity types
   └────────┬────────┘
            ▼
   ┌─────────────────┐
   │  SQL Compiler    │  deterministic: plan → parameterized SQL
   │  (no LLM)        │  queries only curated semantic views, never raw tables
   └────────┬────────┘
            ▼
   ┌─────────────────┐
   │  DuckDB          │  execute SQL, return rows
   └────────┬────────┘
            ▼
   ┌─────────────────┐
   │  Summarizer      │  LLM turns result rows into human-readable answer
   │  (LLM)           │  instructed to state only facts from the data
   └─────────────────┘
```

### Why this architecture?

The LLM never writes SQL and never sees raw data tables. Instead:

1. **Query Planner** produces a constrained JSON plan with a fixed intent vocabulary
2. **SQL Compiler** deterministically maps the plan to parameterized SQL over curated semantic views
3. **Summarizer** receives actual query results and is instructed to only state facts present in the data

This design prevents SQL injection, hallucination, and ensures every answer is grounded in an executed query.

## Data Model

### Dataset

19 SAP tables covering the Order-to-Cash flow:
- **Core flow**: Sales Orders → Deliveries → Billing → Journal Entries → Payments
- **Master data**: Customers, Products, Plants
- **Supporting**: Schedule lines, addresses, sales area assignments

### Layered Processing

| Layer | Purpose |
|-------|---------|
| **Raw** | 19 JSONL folders → DuckDB tables, all fields preserved as strings |
| **Link tables** | Validated pairwise joins between adjacent flow stages |
| **Dimensions** | Curated customer, product, plant tables with human-readable labels |
| **Flow status** | Per-item boolean indicators + derived status label |
| **Lineage** | End-to-end item-level flow composed from validated links |
| **Graph** | Materialized nodes + edges for visualization |

### Key Data Findings

- **167 order items** across 100 sales orders and 8 customers
- **80/83 original invoices were cancelled** and re-billed as S1 type documents
- **3 invoices remain unpaid** (open accounts receivable)
- **14 orders have no delivery** (status: ordered_only)
- **13 delivered items have no billing** (status: delivered_not_billed)

### Flow Status Distribution

| Status | Count | Meaning |
|--------|-------|---------|
| Complete | 90 | Full O2C cycle |
| Billed, no posting | 31 | Replacement invoice without own JE |
| Ordered only | 30 | No delivery created |
| Delivered, not billed | 13 | Shipped but not invoiced |
| Posted, not paid | 3 | AR posted, awaiting payment |

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Backend | FastAPI (Python) | Async, typed, auto-docs |
| Database | DuckDB | Embedded analytical DB, no infra needed, SQL on JSONL |
| Frontend | Next.js + React | SSR, API proxying, fast dev |
| Graph viz | Cytoscape.js | Mature, performant, handles 600+ nodes |
| LLM | OpenAI (gpt-4o-mini) | Reliable, fast, cost-effective |
| Styling | Tailwind CSS | Utility-first, consistent design |

### Why DuckDB over Neo4j?

- The graph is materialized from relational data — it doesn't need a native graph DB
- DuckDB runs embedded (no server process), making deployment trivial
- DuckDB's analytical query engine handles the aggregation/join workloads well
- The graph tables (nodes + edges) are queryable with standard SQL
- For a dataset this size, DuckDB is faster to set up and simpler to deploy

## Guardrail Design

The system prevents hallucination and off-topic responses through multiple layers:

1. **Keyword pre-filter**: Fast substring check for O2C-related terms. Rejects clearly unrelated questions without calling the LLM.
2. **LLM domain classifier**: For ambiguous questions, asks the LLM "is this about O2C data?" with a binary YES/NO response.
3. **Constrained intent set**: The query planner must choose from 5 fixed intents. Unknown intents are rejected.
4. **No raw SQL from LLM**: The LLM produces a structured JSON plan, never SQL. A deterministic compiler generates parameterized queries.
5. **Result grounding**: The summarizer receives actual query results and is instructed: "Only state facts present in the data. Do not speculate."
6. **Empty result handling**: If a query returns no rows, the system says so clearly instead of fabricating results.

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- An OpenAI API key

### Installation

```bash
# Clone the repo
git clone <repo-url>
cd dodge-assessment

# Install dependencies
make setup

# Set your API key
echo "OPENAI_API_KEY=sk-your-key" > .env

# Ingest data + build semantic layer
make seed

# Start backend (terminal 1)
make backend

# Start frontend (terminal 2)
make frontend
```

Open http://localhost:3001

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/graph/initial` | Starting graph view |
| GET | `/api/graph/node/{id}` | Node details |
| GET | `/api/graph/neighbors/{id}?depth=N` | Local subgraph |
| GET | `/api/graph/search?q=...` | Search nodes |
| GET | `/api/lineage/order/{id}` | Full O2C flow |
| GET | `/api/lineage/trace/{type}/{id}` | Trace any document |
| GET | `/api/status/overview` | Flow status summary |
| GET | `/api/status/broken` | Incomplete flows |
| POST | `/api/chat` | Natural language query |

## Sample Queries

Try these in the chat interface:

- "Which products are associated with the highest number of billing documents?"
- "Show me all orders that were delivered but not billed"
- "Trace the full flow of billing document 90504248"
- "What is the total billed amount per customer?"
- "How many items are still awaiting payment?"
- "How many customers are there?"
- "Trace sales order 740509"

Off-topic queries like "What is the weather?" are rejected with a clear explanation.

## Design Decisions

### Item-level lineage, header-level graph

The lineage table tracks flow at the **item level** (one row per sales order item) for correctness — a single order can have items at different stages. The graph visualization shows **header-level** edges (one edge per document relationship) for readability.

### Cancellation handling

80 of 83 original invoices (type F2) were cancelled and replaced with S1 documents. The system:
- Pairs cancelled → replacement via shared delivery item reference
- Filters to active billing documents for flow analysis
- Shows cancellation edges in the graph as dashed red lines

### Payment semantics

The `payments_accounts_receivable` table is a filtered subset of `journal_entry_items_accounts_receivable` (same keys, same amounts). The 120 rows with `clearingAccountingDocument` are cleared/paid; 3 remain open.

## Known Limitations

- Graph layout may be dense for customers with many orders — use type filters to manage
- Free-tier LLM APIs may hit rate limits — the system retries with exponential backoff
- No authentication — designed for local/demo use
- The chat system handles a fixed set of query patterns; very complex multi-hop questions may not compile correctly

## Project Structure

```
dodge-assessment/
├── README.md
├── Makefile
├── .env                          # API keys (not committed)
├── .gitignore
├── sap-o2c-data/                 # Raw JSONL dataset
├── backend/
│   ├── main.py                   # FastAPI app
│   ├── config.py                 # Paths
│   ├── seed.py                   # Data pipeline runner
│   ├── db/
│   │   ├── ingest.py             # JSONL → raw DuckDB tables
│   │   ├── semantic.py           # Link tables, dimensions, graph
│   │   └── connection.py         # DuckDB connection
│   ├── routers/                  # API endpoints
│   ├── services/                 # Business logic
│   ├── llm/
│   │   ├── client.py             # OpenAI/Gemini/Groq client
│   │   ├── prompts.py            # System prompts
│   │   ├── guardrails.py         # Domain classifier
│   │   ├── query_planner.py      # NL → structured plan
│   │   └── sql_compiler.py       # Plan → parameterized SQL
│   └── models/schemas.py         # Pydantic models
├── frontend/
│   ├── src/
│   │   ├── app/page.tsx          # Main page
│   │   ├── components/           # React components
│   │   ├── lib/api.ts            # API client
│   │   └── types/                # TypeScript types
│   └── next.config.ts            # API proxy config
└── docs/                         # Additional documentation
```
