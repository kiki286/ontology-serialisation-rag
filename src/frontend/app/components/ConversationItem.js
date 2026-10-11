"use client";
import { useState } from "react";
import SourcesList from "./SourcesList";

export default function ConversationItem({ entry }) {
  const [showSources, setShowSources] = useState(false);

  return (
    <div className="mb-6">

      {/* USER MESSAGE (RIGHT BUBBLE) */}
      <div className="flex justify-end">
        <div className="max-w-[75%] bg-[#acc5dd] text-black p-3 rounded-xl rounded-br-none whitespace-pre-line">
          {entry.question}
        </div>
      </div>

      {/* ASSISTANT MESSAGE (LEFT, NO BUBBLE) */}
      <div className="flex justify-start mt-3">
        <div className="max-w-[75%] text-gray-900 dark:text-gray-100 whitespace-pre-line">
          {entry.pending ? (
            <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
              <div className="animate-spin h-4 w-4 border-2 border-gray-600 border-t-transparent rounded-full" />
              Thinking...
            </div>
          ) : (
            entry.answer
          )}
        </div>
      </div>

      {/* SOURCES DROPDOWN (LEFT, UNDER ASSISTANT) */}
      {entry.sources?.length > 0 && (
        <div className="mt-2 ml-0">

          <button
            onClick={() => setShowSources((s) => !s)}
            className="font-medium text-slate-500 dark:text-slate-400 hover:underline"
          >
            Sources {showSources ? "▲" : "▼"}
          </button>

          {showSources && (
            <div className="ml-4">
              <SourcesList sources={entry.sources} />
            </div>
          )}

        </div>
      )}

    </div>
  );
}
