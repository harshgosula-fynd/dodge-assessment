"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "@/lib/api";
import { NODE_TYPE_META } from "@/lib/graph-styles";
import type { ChatMessage } from "@/types";

interface Props {
  onClose?: () => void;
  onHighlightNodes: (nodeIds: string[]) => void;
  onNavigateNode: (nodeId: string) => void;
  messages: ChatMessage[];
  onMessagesChange: (msgs: ChatMessage[]) => void;
}

const SUGGESTIONS = [
  "Which products have the most billing documents?",
  "Show orders delivered but not billed",
  "Total billed amount per customer?",
  "Trace sales order 740509",
  "How many items are awaiting payment?",
  "Identify broken or incomplete flows",
];

export default function ChatPanel({ onClose, onHighlightNodes, onNavigateNode, messages, onMessagesChange }: Props) {
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  const setMessages = useCallback((updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => {
    if (typeof updater === "function") {
      onMessagesChange(updater(messagesRef.current));
    } else {
      onMessagesChange(updater);
    }
  }, [onMessagesChange]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    setInput("");
    setMessages((m: ChatMessage[]) => [...m, { role: "user", content: trimmed }]);
    setLoading(true);

    try {
      const res = await api.chat(trimmed);
      setMessages((m: ChatMessage[]) => [
        ...m,
        {
          role: "assistant",
          content: res.answer,
          data: res.data,
          queryPlan: res.query_plan,
          executedSql: res.executed_sql,
          resultCount: res.result_count,
          highlightedNodes: res.highlighted_nodes,
        },
      ]);
      // Highlight referenced nodes in graph
      if (res.highlighted_nodes && res.highlighted_nodes.length > 0) {
        onHighlightNodes(res.highlighted_nodes);
      }
    } catch {
      setMessages((m: ChatMessage[]) => [
        ...m,
        { role: "assistant", content: "Something went wrong. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  return (
    <div className="w-full h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-neutral-100 shrink-0">
        <div>
          <h3 className="text-sm font-semibold text-neutral-800">Ask AI</h3>
          <p className="text-[10px] text-neutral-400">Grounded answers from O2C data</p>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="w-5 h-5 flex items-center justify-center rounded text-neutral-400
                       hover:text-neutral-600 hover:bg-neutral-100 transition-colors text-sm"
          >
            &times;
          </button>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {messages.map((msg, i) => (
          <div key={i}>
            {msg.role === "user" ? (
              <div className="flex justify-end">
                <div className="bg-neutral-900 text-white text-[13px] px-3 py-2 rounded-xl rounded-br-sm max-w-[85%] leading-relaxed">
                  {msg.content}
                </div>
              </div>
            ) : (
              <div className="flex justify-start">
                <div className="max-w-[95%] space-y-2">
                  {/* Answer text */}
                  <div className="text-[13px] text-neutral-700 leading-relaxed prose prose-sm prose-neutral max-w-none">
                    <ReactMarkdown
                      components={{
                        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                        strong: ({ children }) => <strong className="font-semibold text-neutral-800">{children}</strong>,
                        ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-0.5">{children}</ul>,
                        ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-0.5">{children}</ol>,
                        li: ({ children }) => <li className="text-neutral-700">{children}</li>,
                        code: ({ children }) => (
                          <code className="bg-neutral-100 px-1 py-0.5 rounded text-[12px] font-mono text-neutral-800">
                            {children}
                          </code>
                        ),
                        pre: ({ children }) => (
                          <pre className="bg-neutral-100 p-2 rounded overflow-x-auto text-[11px] font-mono mb-2">
                            {children}
                          </pre>
                        ),
                        h1: ({ children }) => <h1 className="font-semibold text-base mb-2 text-neutral-800">{children}</h1>,
                        h2: ({ children }) => <h2 className="font-semibold text-sm mb-1.5 text-neutral-800">{children}</h2>,
                        h3: ({ children }) => <h3 className="font-medium text-sm mb-1 text-neutral-800">{children}</h3>,
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>

                  {/* Entity chips — clickable graph links */}
                  {msg.highlightedNodes && msg.highlightedNodes.length > 0 && (
                    <EntityChips nodes={msg.highlightedNodes.slice(0, 12)} onNavigate={onNavigateNode} />
                  )}

                  {/* Evidence card */}
                  {(msg.queryPlan || msg.executedSql || msg.resultCount !== undefined) && (
                    <EvidenceCard
                      queryPlan={msg.queryPlan}
                      executedSql={msg.executedSql}
                      resultCount={msg.resultCount}
                    />
                  )}

                  {/* Data table */}
                  {msg.data && msg.data.length > 0 && <DataTable data={msg.data} />}
                </div>
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex gap-1 py-1">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="w-1.5 h-1.5 bg-neutral-300 rounded-full animate-bounce"
                style={{ animationDelay: `${i * 0.12}s` }}
              />
            ))}
          </div>
        )}
      </div>

      {/* Suggestions */}
      {messages.length <= 1 && (
        <div className="px-4 pb-2 flex flex-wrap gap-1.5 shrink-0">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              className="text-[11px] px-2 py-1 rounded-md border border-neutral-200
                         text-neutral-500 hover:bg-neutral-50 hover:border-neutral-300 transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="border-t border-neutral-100 p-3 shrink-0">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the data..."
            rows={1}
            className="flex-1 resize-none text-[13px] px-3 py-2 border border-neutral-200
                       rounded-lg focus:outline-none focus:border-neutral-400
                       placeholder:text-neutral-400 max-h-20"
          />
          <button
            onClick={() => send(input)}
            disabled={!input.trim() || loading}
            className="h-[34px] px-3 bg-neutral-900 text-white text-xs rounded-lg
                       hover:bg-neutral-800 disabled:opacity-30 disabled:cursor-not-allowed
                       transition-colors shrink-0"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Entity chips: clickable links to graph nodes ── */

function EntityChips({ nodes, onNavigate }: { nodes: string[]; onNavigate: (id: string) => void }) {
  return (
    <div className="flex flex-wrap gap-1">
      {nodes.map((nid) => {
        const [type] = nid.split(":");
        const meta = NODE_TYPE_META[type];
        return (
          <button
            key={nid}
            onClick={() => onNavigate(nid)}
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px]
                       border border-neutral-200 hover:bg-neutral-50 text-neutral-600 transition-colors"
            title={`View ${nid} in graph`}
          >
            <span
              className="w-1.5 h-1.5 rounded-full shrink-0"
              style={{ background: meta?.color || "#94a3b8" }}
            />
            {nid.split(":").slice(1).join(":")}
          </button>
        );
      })}
    </div>
  );
}

/* ── Evidence card: query plan + SQL + result count ── */

function EvidenceCard({
  queryPlan,
  executedSql,
  resultCount,
}: {
  queryPlan?: Record<string, unknown> | null;
  executedSql?: string | null;
  resultCount?: number | null;
}) {
  const [expanded, setExpanded] = useState(false);
  const intent = queryPlan?.intent as string | undefined;
  const entityType = queryPlan?.entity_type as string | undefined;

  return (
    <div className="bg-neutral-50 border border-neutral-100 rounded-lg overflow-hidden text-[11px]">
      {/* Summary row — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-2.5 py-1.5 hover:bg-neutral-100/50 transition-colors"
      >
        <div className="flex items-center gap-2 text-neutral-500">
          {intent && (
            <span className="px-1.5 py-0.5 bg-white border border-neutral-200 rounded font-medium text-neutral-600">
              {intent.replace(/_/g, " ")}
            </span>
          )}
          {entityType && (
            <span className="text-neutral-400">{entityType.replace(/_/g, " ")}</span>
          )}
          {resultCount !== null && resultCount !== undefined && (
            <span className="text-neutral-400">&middot; {resultCount} row{resultCount !== 1 ? "s" : ""}</span>
          )}
        </div>
        <span
          className="text-neutral-400 text-[9px] transition-transform"
          style={{ transform: expanded ? "rotate(90deg)" : "rotate(0)" }}
        >
          &#9654;
        </span>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="border-t border-neutral-100 px-2.5 py-2 space-y-2">
          {queryPlan && (
            <div>
              <div className="text-[10px] font-medium text-neutral-400 mb-1">Query Plan</div>
              <pre className="text-[10px] text-neutral-500 bg-white border border-neutral-100 rounded p-1.5 overflow-x-auto leading-relaxed">
                {JSON.stringify(queryPlan, null, 2)}
              </pre>
            </div>
          )}
          {executedSql && (
            <div>
              <div className="text-[10px] font-medium text-neutral-400 mb-1">Executed SQL</div>
              <pre className="text-[10px] text-neutral-500 bg-white border border-neutral-100 rounded p-1.5 overflow-x-auto leading-relaxed font-mono">
                {executedSql}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Data table ── */

function DataTable({ data }: { data: Record<string, unknown>[] }) {
  const [expanded, setExpanded] = useState(false);
  if (!data || data.length === 0 || !data[0]) return null;
  const cols = Object.keys(data[0]);
  const shown = expanded ? data.slice(0, 20) : data.slice(0, 5);

  return (
    <div className="overflow-x-auto rounded border border-neutral-100">
      <table className="text-[11px] border-collapse w-full">
        <thead>
          <tr className="bg-neutral-50">
            {cols.map((c) => (
              <th key={c} className="text-left px-2 py-1.5 text-neutral-500 font-medium whitespace-nowrap border-b border-neutral-100">
                {c.replace(/_/g, " ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((row, i) => (
            <tr key={i} className="hover:bg-neutral-50/50">
              {cols.map((c) => (
                <td key={c} className="px-2 py-1 text-neutral-700 whitespace-nowrap border-b border-neutral-50">
                  {row[c] === null ? "—" : String(row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length > 5 && (
        <button onClick={() => setExpanded(!expanded)} className="text-[10px] text-neutral-400 hover:text-neutral-600 px-2 py-1 w-full text-left">
          {expanded ? "Show less" : `Show all ${data.length} rows`}
        </button>
      )}
    </div>
  );
}
