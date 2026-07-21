import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { fetchWorkspacePapers, chatWithWorkspace } from '../api/client';
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
  }, [workspaceId]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || !workspaceId) return;

    const userMessage = inputValue;
    setInputValue('');
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setIsTyping(true);

    try {
      const result = await withActivity('Answering from workspace papers...', () =>
        chatWithWorkspace(workspaceId, userMessage)
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

  return (
    <div className="lg:col-span-8 space-y-8 px-margin-mobile md:px-margin-desktop max-w-max-width mx-auto">
      <button onClick={() => navigate('/library')} className="flex items-center gap-1 text-on-surface-variant hover:text-primary text-sm mb-2">
        <span className="material-symbols-outlined text-sm">arrow_back</span>
        Back to Library
      </button>

      <section className="space-y-4">
        <h2 className="font-h2 text-h2 text-primary">Workspace Papers</h2>

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
            <div key={paper.paper_id} className="bg-surface-container-lowest border border-outline-variant/20 rounded-xl p-6">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="bg-surface-container-high text-on-surface-variant text-[10px] font-bold px-2 py-0.5 rounded uppercase">{paper.venue || 'ARXIV'}</span>
                  <span className="text-xs text-outline font-mono-technical">Published {paper.publication_year}</span>
                </div>
                <h4 className="font-h2 text-xl text-on-surface leading-tight">{paper.title}</h4>
                <p className="text-on-surface-variant text-sm italic">{paper.authors?.join(', ')}</p>
              </div>
            </div>
          ))
        )}
      </section>

      {papers.length > 0 && (
        <section className="space-y-4">
          <h2 className="font-h2 text-h2 text-primary">Chat with this Workspace</h2>
          <p className="text-on-surface-variant text-sm">
            Questions are grounded across all {papers.length} paper{papers.length > 1 ? 's' : ''} in this workspace.
          </p>

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
