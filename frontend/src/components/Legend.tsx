"use client";

import { NODE_TYPE_META } from "@/lib/graph-styles";

interface Props {
  activeFilters: Set<string>;
  onToggle: (type: string) => void;
}

export default function Legend({ activeFilters, onToggle }: Props) {
  return (
    <div className="flex items-center gap-1">
      {Object.entries(NODE_TYPE_META).map(([type, meta]) => {
        const active = activeFilters.has(type);
        return (
          <button
            key={type}
            onClick={() => onToggle(type)}
            className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-xs transition-colors
              ${active
                ? "bg-white border border-neutral-200 text-neutral-700 shadow-sm"
                : "text-neutral-400 hover:text-neutral-500"
              }`}
          >
            <span
              className="w-2 h-2 rounded-full"
              style={{ background: meta.color, opacity: active ? 1 : 0.4 }}
            />
            {meta.label}
          </button>
        );
      })}
    </div>
  );
}
