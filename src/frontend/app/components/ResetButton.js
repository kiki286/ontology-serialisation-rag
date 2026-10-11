"use client";

export default function ResetButton({ onReset }) {
  const handleReset = async () => {
    try {
      await fetch("/api/clear_rag_memory/", {
        method: "POST",
      });

      if (onReset) onReset(); // resets UI conversation state
    } catch (err) {
      console.error("Failed to reset RAG memory:", err);
    }
  };

  return (
    <button
      onClick={handleReset}
      className="
        text-sm font-normal
        text-gray-600 dark:text-gray-300 
        hover:text-black dark:hover:text-white
        transition-colors cursor-pointer
      "
    >
      ↻
    </button>
  );
}
