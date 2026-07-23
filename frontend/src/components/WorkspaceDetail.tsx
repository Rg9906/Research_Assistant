import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  fetchWorkspacePapers,
  chatWithWorkspace,
  fetchChatHistory,
  clearChatHistory,
  fetchComparisonAxes,
  compareWorkspacePapers,
} from '../api/client';
import type { Paper } from '../api/client';
import { useAgentActivity } from '../context/AgentActivityContext';
import AnswerMessage from './AnswerMessage';
import type { AgentMessage } from './AnswerMessage';

const WorkspaceDetail: React.FC = () => {
  const { workspaceId } = useParams();
  const navigate = useNavigate();
  const { withActivity } = useAgentActivity();

  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  const [selectedPaperIds, setSelectedPaperIds] = useState<Set<string>>(new Set());
  const [comparisonAxes, setComparisonAxes] = useState<string[]>([]);
  const [showComparePicker, setShowComparePicker] = useState(false);
  const [customAxis, setCustomAxis] = useState('');

  useEffect(() => {
    if (!workspaceId) return;
    setLoading(true);
    setError(null);
    fetchWorkspacePapers(workspaceId)
      .then(setPapers)
      .catch((err) => {
        console.error(err);
        setError('Could not load this workspace. It may have been deleted.');
      })
      .finally(() => setLoading(false));

    // Restore any conversation the backend already remembers for this
    // workspace, so navigating away and back doesn't look like memory loss.
    fetchChatHistory(workspaceId)
      .then((history) =>
        setMessages(
          history.map((entry) => ({
            role: entry.role === 'user' ? 'user' : 'agent',
            content: entry.content,
          })),
        ),
      )
      .catch((err) => console.error('Could not restore chat history', err));

    fetchComparisonAxes()
      .then(setComparisonAxes)
      .catch((err) => console.error('Could not fetch comparison axes', err));
  }, [workspaceId]);

  const togglePaperSelection = (paperId: string) => {
    setSelectedPaperIds((prev) => {
      const next = new Set(prev);
      if (next.has(paperId)) next.delete(paperId);
      else next.add(paperId);
      return next;
    });
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || !workspaceId) return;

    const userMessage = inputValue;
    setInputValue('');
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setIsTyping(true);

    try {
      const paperIds = selectedPaperIds.size > 0 ? Array.from(selectedPaperIds) : undefined;
      const result = await withActivity('Answering from workspace papers...', () =>
        chatWithWorkspace(workspaceId, userMessage, 'graduate/expert', paperIds)
      );
      setMessages((prev) => [
        ...prev,
        {
          role: 'agent',
          content: result.answer,
          citations: result.citations,
          approved: result.approved,
          refused: result.refused,
        },
      ]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        { role: 'agent', content: 'Sorry, I encountered an error answering that question.' },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleCompare = async (axis: string) => {
    if (!workspaceId || !axis.trim() || selectedPaperIds.size < 2) return;
    const paperIds = Array.from(selectedPaperIds);
    setShowComparePicker(false);
    setCustomAxis('');
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: `Compare ${paperIds.length} papers on: ${axis}` },
    ]);
    setIsTyping(true);

    try {
      const result = await withActivity('Comparing selected papers...', () =>
        compareWorkspacePapers(workspaceId, axis, paperIds)
      );
      setMessages((prev) => [
        ...prev,
        {
          role: 'agent',
          content: result.synthesis,
          sections: result.sections,
          citations: result.citations,
          approved: result.approved,
          refused: result.refused,
        },
      ]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        { role: 'agent', content: 'Sorry, I encountered an error comparing those papers.' },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleClearConversation = async () => {
    if (!workspaceId) return;
    try {
      await clearChatHistory(workspaceId);
      setMessages([]);
    } catch (err) {
      console.error('Could not clear conversation', err);
    }
  };

  return (
    <div className="lg:col-span-8 space-y-8 px-margin-mobile md:px-margin-desktop max-w-max-width mx-auto">
      <button onClick={() => navigate('/library')} className="flex items-center gap-1 text-on-surface-variant hover:text-primary text-sm mb-2">
        <span className="material-symbols-outlined text-sm">arrow_back</span>
        Back to Library
      </button>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-h2 text-h2 text-primary">Workspace Papers</h2>
          {papers.length > 1 && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-on-surface-variant font-mono-technical">
                {selectedPaperIds.size > 0 ? `${selectedPaperIds.size} selected` : 'Select papers to compare'}
              </span>
              {selectedPaperIds.size > 0 && (
                <button
                  onClick={() => setSelectedPaperIds(new Set())}
                  className="text-xs text-secondary hover:underline"
                >
                  Clear selection
                </button>
              )}
            </div>
          )}
        </div>

        {error && (
          <div className="bg-error-container text-on-error-container rounded-lg p-4 text-sm flex items-center gap-2">
            <span className="material-symbols-outlined text-sm">error</span>
            {error}
          </div>
        )}

        {loading ? (
          <p className="text-on-surface-variant">Loading...</p>
        ) : papers.length === 0 ? (
          <p className="text-on-surface-variant italic">This workspace has no papers yet.</p>
        ) : (
          papers.map((paper) => (
            <div
              key={paper.paper_id}
              onClick={() => papers.length > 1 && togglePaperSelection(paper.paper_id)}
              className={`bg-surface-container-lowest border rounded-xl p-6 transition-colors ${
                selectedPaperIds.has(paper.paper_id)
                  ? 'border-primary ring-1 ring-primary'
                  : 'border-outline-variant/20'
              } ${papers.length > 1 ? 'cursor-pointer' : ''}`}
            >
              <div className="flex items-start gap-3">
                {papers.length > 1 && (
                  <input
                    type="checkbox"
                    checked={selectedPaperIds.has(paper.paper_id)}
                    onChange={() => togglePaperSelection(paper.paper_id)}
                    onClick={(e) => e.stopPropagation()}
                    className="mt-1.5 accent-primary"
                  />
                )}
                <div className="space-y-1 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="bg-surface-container-high text-on-surface-variant text-[10px] font-bold px-2 py-0.5 rounded uppercase">{paper.venue || 'ARXIV'}</span>
                    <span className="text-xs text-outline font-mono-technical">Published {paper.publication_year}</span>
                  </div>
                  <h4 className="font-h2 text-xl text-on-surface leading-tight">{paper.title}</h4>
                  <p className="text-on-surface-variant text-sm italic">{paper.authors?.join(', ')}</p>
                </div>
              </div>
            </div>
          ))
        )}
      </section>

      {selectedPaperIds.size >= 2 && (
        <section className="bg-surface-container-lowest border border-primary/30 rounded-xl p-4 space-y-3">
          {!showComparePicker ? (
            <button
              onClick={() => setShowComparePicker(true)}
              className="flex items-center gap-2 text-primary font-bold text-sm"
            >
              <span className="material-symbols-outlined text-[18px]">difference</span>
              Compare {selectedPaperIds.size} Selected Papers
            </button>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-on-surface-variant">Compare along:</p>
              <div className="flex flex-wrap gap-2">
                {comparisonAxes.map((axis) => (
                  <button
                    key={axis}
                    onClick={() => handleCompare(axis)}
                    className="bg-primary-container text-on-primary-container text-xs font-bold px-3 py-1.5 rounded-full uppercase tracking-wide hover:opacity-80"
                  >
                    {axis}
                  </button>
                ))}
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleCompare(customAxis);
                }}
                className="flex gap-2"
              >
                <input
                  type="text"
                  value={customAxis}
                  onChange={(e) => setCustomAxis(e.target.value)}
                  placeholder="Or type a custom axis..."
                  className="flex-1 bg-surface-container h-9 px-3 rounded-lg text-sm border border-outline-variant/30 focus:ring-1 focus:ring-primary"
                />
                <button
                  type="submit"
                  disabled={!customAxis.trim()}
                  className="bg-primary text-on-primary px-4 rounded-lg text-sm font-bold disabled:opacity-50"
                >
                  Compare
                </button>
              </form>
            </div>
          )}
        </section>
      )}

      {papers.length > 0 && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-h2 text-h2 text-primary">Chat with this Workspace</h2>
              <p className="text-on-surface-variant text-sm">
                Questions are grounded across{' '}
                {selectedPaperIds.size > 0
                  ? `${selectedPaperIds.size} selected paper${selectedPaperIds.size > 1 ? 's' : ''}`
                  : `all ${papers.length} paper${papers.length > 1 ? 's' : ''} in this workspace`}
                .
              </p>
            </div>
            {messages.length > 0 && (
              <button
                onClick={handleClearConversation}
                className="flex items-center gap-1 text-xs text-on-surface-variant hover:text-error shrink-0"
              >
                <span className="material-symbols-outlined text-sm">delete_sweep</span>
                Clear conversation
              </button>
            )}
          </div>

          <div className="bg-surface-container-lowest border border-outline-variant/30 rounded-xl flex flex-col h-[420px] overflow-hidden">
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 && (
                <p className="text-on-surface-variant text-sm italic">Ask a question to get started.</p>
              )}
              {messages.map((msg, idx) => (
                <AnswerMessage key={idx} message={msg} />
              ))}
              {isTyping && (
                <div className="flex justify-start">
                  <div className="max-w-[85%] p-3 rounded-lg text-sm bg-surface-container text-on-surface rounded-tl-none border border-outline-variant/20 flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-outline-variant animate-bounce"></span>
                    <span className="w-2 h-2 rounded-full bg-outline-variant animate-bounce delay-75"></span>
                    <span className="w-2 h-2 rounded-full bg-outline-variant animate-bounce delay-150"></span>
                  </div>
                </div>
              )}
            </div>

            <form onSubmit={handleSendMessage} className="p-3 bg-surface-container-lowest border-t border-outline-variant/20 shrink-0">
              <div className="relative flex items-center">
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder="Ask about these papers..."
                  className="w-full bg-surface-container h-10 pl-4 pr-10 rounded-full text-sm border-none focus:ring-1 focus:ring-primary"
                  disabled={isTyping}
                />
                <button
                  type="submit"
                  disabled={!inputValue.trim() || isTyping}
                  className="absolute right-1 w-8 h-8 flex items-center justify-center text-primary disabled:opacity-50"
                >
                  <span className="material-symbols-outlined text-[20px]">send</span>
                </button>
              </div>
            </form>
          </div>
        </section>
      )}
    </div>
  );
};

export default WorkspaceDetail;
