"use client";
import ConversationItem from "./ConversationItem";

import { useEffect, useRef } from "react";

export default function ConversationList({ conversation }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    // scroll to bottom on new messages
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation]);

  return (
    <div className="flex flex-col gap-6">
      {conversation.map((entry, index) => (
        <ConversationItem key={index} entry={entry} />
      ))}

      <div ref={bottomRef} />
    </div>
  );
}
