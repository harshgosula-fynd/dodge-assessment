# LLM Guardrail Design

## Problem

LLMs can hallucinate, generate unsafe SQL, or answer questions outside the dataset's scope. The system must ensure every answer is grounded in actual query results.

## Solution: 5-Layer Safety Architecture

### Layer 1: Keyword Pre-Filter
**Purpose**: Quickly reject obviously off-topic questions without calling the LLM.

Checks if the question contains any O2C-related keyword as a substring. Handles plurals (e.g., "customers" matches "customer"). Questions with at least 1 match proceed; very short questions with 0 matches are rejected immediately.

### Layer 2: LLM Domain Classifier
**Purpose**: For ambiguous questions, use the LLM as a binary classifier.

A dedicated prompt asks: "Is this question about O2C data? Reply YES or NO." Only YES responses proceed. This is a separate LLM call with temperature=0 for determinism.

### Layer 3: Constrained Intent Vocabulary
**Purpose**: The query planner can only produce plans with known intents.

Valid intents: `trace_flow`, `list_entities`, `aggregate`, `find_broken`, `describe_entity`. Any unknown intent is rejected at the validation layer, even if the LLM outputs it.

### Layer 4: Deterministic SQL Compilation
**Purpose**: The LLM never writes SQL.

The query planner outputs a structured JSON plan. A deterministic Python function compiles it into parameterized SQL (`?` placeholders). Column names and table names come from a fixed allowlist (TABLE_MAP). User values are always passed as parameters.

### Layer 5: Result Grounding
**Purpose**: The summarizer can only state facts from the data.

The summarizer prompt explicitly instructs: "Only state facts present in the data below. Do not speculate or add information not shown. If the data is empty, say so clearly."

## Rejection Behavior

Off-topic questions receive a clear, consistent message:

> "I can only answer questions about the Order-to-Cash dataset, including sales orders, deliveries, billing documents, payments, customers, products, and business flow analysis."

## Example Flows

**Valid**: "Which products have the most billing documents?"
→ keyword match → plan: aggregate/lineage/count → SQL over lineage_item_flow → summarize results

**Invalid**: "What is the capital of France?"
→ no keyword match, short question → rejected without LLM call

**Ambiguous**: "Tell me about the data"
→ keyword match → LLM classifier → YES → plan: describe_entity → results
