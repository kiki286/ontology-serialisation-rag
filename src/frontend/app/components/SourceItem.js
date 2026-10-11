"use client";
import { useState } from "react";

export default function SourceItem({ src }) {
  const [expanded, setExpanded] = useState(false);

  // Destructure fields from Document structure
  const { metadata = {}, page_content } = src;
  const { type, source, subject, title, description } = metadata;

  // Determine display title
  let displayTitle = source || "Unknown source";

  if (type === "webpage" && title) displayTitle = title;
  if (type === "turtle" && subject) displayTitle = subject;

  if (type === "markdown") {
    const headers = Object.keys(metadata)
      .filter((k) => k.toLowerCase().startsWith("header"))
      .sort(
        (a, b) =>
          parseInt(a.replace(/\D/g, ""), 10) -
          parseInt(b.replace(/\D/g, ""), 10)
      )
      .map((h) => metadata[h]);
    if (headers.length) displayTitle = `${headers.join(" › ")}`;
  }

  return (
    <li className="mb-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left font-medium text-slate-500 dark:text-slate-400 hover:underline"
      >
        {displayTitle}
      </button>

      {expanded && (
        <div className="mt-2 p-3 bg-gray-50 dark:bg-neutral-800 rounded-md max-h-60 overflow-y-auto text-sm text-gray-700 dark:text-gray-300">

          {/* Markdown */}
          {type === "markdown" && (
            <div>
              <div className="text-sm text-gray-500 mb-1">Markdown Source:</div>
              <div className="font-semibold">{source}</div>

              {page_content && (
                <pre className="mt-2 text-xs whitespace-pre-wrap">{page_content}</pre>
              )}
            </div>
          )}

          {/* Turtle */}
          {type === "turtle" && (
            <div>
              <div className="text-sm text-gray-500 mb-1">Turtle Source:</div>
              <div className="font-semibold">{source}</div>
              {subject && <div className="ml-2">{subject}</div>}
              {page_content && (
                <pre className="mt-2 text-xs whitespace-pre-wrap">{page_content}</pre>
              )}
            </div>
          )}

          {/* Webpage */}
          {type === "webpage" && (
            <div>
              <div className="text-sm text-gray-500 mb-1">Webpage:</div>
              <a
                href={source}
                target="_blank"
                rel="noopener noreferrer"
                className="font-semibold text-blue-600 dark:text-blue-400 hover:underline break-all"
              >
                {source}
              </a>
              {page_content && (
                <pre className="mt-2 text-xs whitespace-pre-wrap">{page_content}</pre>
              )}
            </div>
          )}

          {/* LaTeX */}
          {type === "latex" && (
            <div>
              <div className="text-sm text-gray-500 mb-1">LaTeX Source:</div>
              <div className="font-semibold">{source}</div>

              {page_content && (
                <pre className="mt-2 text-xs whitespace-pre-wrap">{page_content}</pre>
              )}
            </div>
          )}

          {/* Text (.txt) */}
          {type === "txt" && (
            <div>
              <div className="text-sm text-gray-500 mb-1">Text File:</div>
              <div className="font-semibold">{source}</div>

              {page_content && (
                <pre className="mt-2 text-xs whitespace-pre-wrap">{page_content}</pre>
              )}
            </div>
          )}

          {/* Other/unknown but present type: show source and page content */}
          {type && !["markdown", "turtle", "webpage", "latex", "txt"].includes(type) && (
            <div>
              <div className="text-sm text-gray-500 mb-1">Source ({type}):</div>
              <div className="font-semibold">{source || "Unknown source"}</div>

              {page_content && (
                <pre className="mt-2 text-xs whitespace-pre-wrap">{page_content}</pre>
              )}
            </div>
          )}

          {/* Fallback */}
          {!type && (
            <div className="italic text-gray-500">
              Unknown type — raw data:
              <pre className="mt-1 text-xs whitespace-pre-wrap">
                {JSON.stringify(src, null, 2)}
              </pre>
            </div>
          )}

        </div>
      )}
    </li>
  );
}
