import React, { useState } from 'react';
import type { Citation } from '../api/client';

export interface AgentMessage {
  role: 'user' | 'agent';
  content: string;
  citations?: Citation[];
  approved?: boolean;
  refused?: boolean;
}

/**
 * Renders one chat message, including the evidence behind an agent answer.
 *
 * The backend answers through the Tutor/Critic contract, so every agent reply
 * carries citations and an audit verdict. Showing them is the product promise —
 * an answer the user can trace back to a page of the paper — and a flagged
 * answer is labelled rather than rendered as if it had passed review.
 *
 * Shared by PaperSummary and WorkspaceDetail so both chat surfaces present
 * evidence identically.
 */
const AnswerMessage: React.FC<{ message: AgentMessage }> = ({ message }) => {
  const [showSources, setShowSources] = useState(false);
  const isUser = message.role === 'user';
  const citations = message.citations ?? [];

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] p-3 rounded-lg text-sm bg-primary-container text-on-primary-container rounded-tr-none">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] space-y-2">
        <div className="p-3 rounded-lg text-sm bg-surface-container text-on-surface rounded-tl-none border border-outline-variant/20 whitespace-pre-wrap">
          {message.content}
        </div>

        {message.refused && (
          <p className="flex items-center gap-1.5 text-[11px] text-on-surface-variant italic">
            <span className="material-symbols-outlined text-[13px]">search_off</span>
            Not found in the paper — the assistant declined rather than guess.
          </p>
        )}

        {message.approved === false && !message.refused && (
          <p className="flex items-center gap-1.5 text-[11px] text-on-surface-variant">
            <span className="material-symbols-outlined text-[13px]">warning</span>
            This answer did not pass the grounding review — verify against the sources.
          </p>
        )}

        {citations.length > 0 && (
          <div className="space-y-2">
            <button
              onClick={() => setShowSources((prev) => !prev)}
              className="flex items-center gap-1 text-[11px] font-bold text-secondary hover:underline tracking-wide"
            >
              <span className="material-symbols-outlined text-[13px]">
                {showSources ? 'expand_less' : 'expand_more'}
              </span>
              {showSources ? 'Hide' : 'Show'} {citations.length} source
              {citations.length > 1 ? 's' : ''}
            </button>

            {showSources && (
              <ol className="space-y-2">
                {citations.map((citation) => (
                  <li
                    key={`${citation.rank}-${citation.filename}`}
                    className="bg-surface rounded-lg border border-outline-variant/20 p-2.5 space-y-1"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] font-mono-technical text-on-surface-variant uppercase truncate">
                        {citation.filename} · Page {citation.page_number}
                      </span>
                      {/* Lead chunks (the paper's intro) have no similarity
                          score — they're always included as context. Label
                          them rather than showing a misleading "0.00". */}
                      {citation.score === null ? (
                        <span className="text-[10px] font-bold text-secondary uppercase tracking-wide shrink-0">
                          Intro
                        </span>
                      ) : (
                        <span className="text-[10px] font-mono-technical text-outline shrink-0">
                          {citation.score.toFixed(2)}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-on-surface-variant leading-relaxed line-clamp-4">
                      {citation.text}
                    </p>
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default AnswerMessage;
