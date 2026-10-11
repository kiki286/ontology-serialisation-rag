"use client";
import { useState } from "react";
import QueryForm from "./components/QueryForm";
import ConversationList from "./components/ConversationList";
import ResetButton from "./components/ResetButton";

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [conversation, setConversation] = useState([]); // stores { question, answer, sources }
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (maybeEvent) => {
    if (maybeEvent && maybeEvent.preventDefault) maybeEvent.preventDefault();
    if (!query.trim()) return;

    const userQuestion = query;
    // clear input immediately so user can continue typing
    setQuery("");

    // optimistic entry appended immediately so user's message appears
    const optimisticEntry = {
      id: Date.now(),
      question: userQuestion,
      answer: "", // will populate when response arrives
      sources: [],
      pending: true,
    };

    setConversation((prev) => [...prev, optimisticEntry]);
    setLoading(true);

    try {
      const res = await fetch("/api/answer_query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userQuestion }),
      });

      const data = await res.json();

      const updatedEntry = {
        ...optimisticEntry,
        answer: data.answer || data.response || "No answer found",
        sources: data.sources || [],
        pending: false,
      };

      setConversation((prev) => prev.map((e) => (e.id === optimisticEntry.id ? updatedEntry : e)));
    } catch (err) {
      const failedEntry = {
        ...optimisticEntry,
        answer: "Error: failed to fetch response",
        pending: false,
      };
      setConversation((prev) => prev.map((e) => (e.id === optimisticEntry.id ? failedEntry : e)));
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex flex-col items-center bg-white dark:bg-neutral-900 text-foreground">
      
      <div
        className="
          sticky top-0 left-0 z-50 
          w-full px-4 py-3 
          text-xl font-semibold 
          bg-white dark:bg-neutral-900 
          border-b border-gray-200 dark:border-gray-700 
          flex items-center justify-between
        "
      >
        <div>ido:assistant</div>

        <ResetButton onReset={() => setConversation([])} />
      </div>

      <div className="w-full max-w-3xl h-full flex flex-col min-h-screen bg-white dark:bg-neutral-900 shadow-lg pt-16">
        
        {/* Scrollable conversation */}
        <div className="flex-1 p-6">
          <ConversationList conversation={conversation} />
        </div>

        {/* Fixed bottom input */}
        <div className="border-t p-4 sticky bottom-0 bg-white/90 dark:bg-neutral-900/90 backdrop-blur">
          <QueryForm
            query={query}
            setQuery={setQuery}
            onSubmit={handleSubmit}
            loading={loading}
          />
        </div>

      </div>

    </main>
  );
}
