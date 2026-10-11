"use client";
import { useRef, useEffect } from "react";

export default function QueryForm({ query, setQuery, onSubmit, loading }) {
  const textareaRef = useRef(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;

    el.style.height = "0px";
    el.style.height = el.scrollHeight + "px";
  }, [query]);

  return (
    <form onSubmit={onSubmit} className="flex items-end gap-2 w-full">
      
      {/* AUTO-GROW TEXTAREA */}
      <textarea
        ref={textareaRef}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            // call parent submit handler; handle both event-taking and no-event variants
            if (typeof onSubmit === "function") {
              try {
                onSubmit();
              } catch (err) {
                // fallback: pass the event if parent expects it
                onSubmit(e);
              }
            }
          }
        }}
        placeholder="Type your question..."
        rows={1}
        className="
          flex-1 resize-none overflow-hidden 
          border border-gray-300 dark:border-gray-700 
          rounded-md p-2 
          bg-background text-foreground 
          focus:outline-none focus:ring-2 focus:ring-blue-500
        "
      />

      {/* ARROW BUTTON */}
      <button
        type="submit"
        disabled={loading}
        className="
          p-2 rounded-full 
          bg-[#acc5dd] text-gray-900 
          hover:bg-[#8aa9c9]
          disabled:bg-gray-400 disabled:cursor-not-allowed
          flex items-center justify-center
          w-10 h-10
        "
      >
        {loading ? (
          <div className="animate-spin h-5 w-5 border-2 border-gray-600 border-t-transparent rounded-full" />
        ) : (
          "➤"
        )}
      </button>


    </form>
  );
}
