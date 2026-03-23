"use client";

import { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import { NODE_TYPE_META } from "@/lib/graph-styles";
import type { NodeSearchResult } from "@/types";

interface Props {
  onSelect: (nodeId: string) => void;
}

export default function SearchBar({ onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<NodeSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [noResults, setNoResults] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => {
      document.removeEventListener("mousedown", handler);
      clearTimeout(timerRef.current);
    };
  }, []);

  const search = (q: string) => {
    if (q.length < 1) {
      setResults([]);
      setOpen(false);
      setNoResults(false);
      return;
    }
    setLoading(true);
    setNoResults(false);
    api.graph
      .search(q, undefined, 15)
      .then((r) => {
        setResults(r);
        setNoResults(r.length === 0);
        setOpen(true);
      })
      .catch(() => {
        setResults([]);
        setNoResults(true);
        setOpen(true);
      })
      .finally(() => setLoading(false));
  };

  const handleChange = (val: string) => {
    setQuery(val);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => search(val), 200);
  };

  const handleSelect = (nodeId: string) => {
    setOpen(false);
    setQuery("");
    setNoResults(false);
    onSelect(nodeId);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setOpen(false);
      (e.target as HTMLInputElement).blur();
    }
  };

  return (
    <div ref={wrapperRef} className="relative">
      <div className="relative">
        <svg
          className="absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400"
          width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        >
          <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
        </svg>
        <input
          type="text"
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => query.length > 0 && (results.length > 0 || noResults) && setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search entities..."
          className="w-64 h-8 pl-8 pr-3 text-[13px] bg-neutral-50 border border-neutral-200
                     rounded-lg focus:outline-none focus:border-neutral-400 focus:bg-white
                     placeholder:text-neutral-400 transition-colors"
        />
        {loading && (
          <div className="absolute right-2.5 top-1/2 -translate-y-1/2">
            <div className="w-3 h-3 border-2 border-neutral-300 border-t-neutral-500 rounded-full animate-spin" />
          </div>
        )}
      </div>

      {open && (
        <div className="absolute top-9 left-0 w-80 bg-white border border-neutral-200
                        rounded-lg shadow-lg z-50 max-h-80 overflow-y-auto">
          {noResults && results.length === 0 ? (
            <div className="px-3 py-4 text-center">
              <p className="text-xs text-neutral-400">No entities found for &quot;{query}&quot;</p>
              <p className="text-[10px] text-neutral-300 mt-1">Try a sales order number, customer name, or product ID</p>
            </div>
          ) : (
            results.map((r) => {
              const meta = NODE_TYPE_META[r.node_type];
              const idPart = r.node_id.split(":").slice(1).join(":");
              return (
                <button
                  key={r.node_id}
                  onClick={() => handleSelect(r.node_id)}
                  className="w-full text-left px-3 py-2 hover:bg-neutral-50
                             flex items-center gap-2.5 border-b border-neutral-100
                             last:border-b-0 transition-colors"
                >
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ background: meta?.color || "#94a3b8" }}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] text-neutral-800 truncate">{r.label}</div>
                    <div className="text-[10px] text-neutral-400 font-mono truncate">{idPart}</div>
                  </div>
                  <span className="text-[10px] text-neutral-400 bg-neutral-50 px-1.5 py-0.5 rounded shrink-0">
                    {meta?.label || r.node_type}
                  </span>
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
