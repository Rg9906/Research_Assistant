import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { processPaper, chatWithWorkspace, fetchSummaryLevels, summarizePaper } from '../api/client';
import type { Paper, SummaryLevel } from '../api/client';
import { useAgentActivity } from '../context/AgentActivityContext';
import AnswerMessage from './AnswerMessage';
import type { AgentMessage } from './AnswerMessage';

const LOADING_MESSAGES = [
  "Brewing coffee for the AI...",
  "Looking up papers...",
  "Finding more info about the author...",
  "Learning context...",
  "Learning to reason...",
  "Getting inferences...",
  "Almost there..."
];

// The abstract is shown verbatim from search metadata — no LLM call, and it is
// available before the paper has been indexed. Every other tab comes from the
// backend's summary-level catalogue (/api/summary-levels).
const ABSTRACT_TAB = { id: 'abstract', label: 'Abstract', difficulty: '' };

const PaperSummary: React.FC = () => {
  const { state } = useLocation();
  const navigate = useNavigate();
  const paper = state?.paper as Paper | undefined;
  const { withActivity } = useAgentActivity();

  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processError, setProcessError] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [loadingMsgIndex, setLoadingMsgIndex] = useState(0);

  const [levels, setLevels] = useState<SummaryLevel[]>([]);
  const [activeTab, setActiveTab] = useState(ABSTRACT_TAB.id);
  const [tabContent, setTabContent] = useState<Record<string, string>>({});
  const [tabLoading, setTabLoading] = useState(false);

  // Tabs are whatever the backend offers, so adding a summary level is a
  // backend-only change. A failure here just leaves the abstract tab.
  useEffect(() => {
    fetchSummaryLevels()
      .then(setLevels)
      .catch((err) => console.error('Could not load summary levels', err));
  }, []);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (isProcessing) {
      setLoadingMsgIndex(0);
      interval = setInterval(() => {
        setLoadingMsgIndex(prev => (prev < LOADING_MESSAGES.length - 1 ? prev + 1 : prev));
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [isProcessing]);

  if (!paper) {
    return (
      <div className="flex flex-col items-center justify-center pt-24 pb-32">
        <h2 className="text-xl text-primary font-bold">Paper not found</h2>
        <button onClick={() => navigate('/')} className="mt-4 text-secondary hover:underline">
          Go back to Discovery Feed
        </button>
      </div>
    );
  }

  const handleProcessPaper = async () => {
    setIsProcessing(true);
    setProcessError(null);
    try {
      const wId = await withActivity('Reading and indexing paper...', () => processPaper(paper));
      setWorkspaceId(wId);
      setChatOpen(true);
      setMessages([{ role: 'agent', content: `Hello! I've read "${paper.title}". What would you like to know about it?` }]);
    } catch (err) {
      console.error(err);
      // Surface the backend's reason. "Failed to process, please try again"
      // is actively misleading for the common permanent failures (no
      // open-access PDF, paywalled link) where retrying can never work.
      setProcessError(
        err instanceof Error && err.message
          ? err.message
          : 'Failed to process this paper for chat. Please try again.'
      );
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || !workspaceId) return;

    const userMessage = inputValue;
    setInputValue('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsTyping(true);

    try {
      const result = await withActivity('Answering from paper...', () => chatWithWorkspace(workspaceId, userMessage));
      setMessages(prev => [...prev, {
        role: 'agent',
        content: result.answer,
        citations: result.citations,
        approved: result.approved,
        refused: result.refused,
      }]);
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: 'agent', content: 'Sorry, I encountered an error answering your question.' }]);
    } finally {
      setIsTyping(false);
    }
  };

  const loadSummary = async (tabId: string, regenerate = false) => {
    const tab = levels.find(t => t.id === tabId);
    if (!tab || !workspaceId) return;

    setTabLoading(true);
    try {
      // Summaries are cached server-side per paper+level, so revisiting a tab
      // is instant and costs nothing; `regenerate` is the deliberate opt-out.
      const result = await withActivity(`Generating ${tab.label.toLowerCase()} view...`, () =>
        summarizePaper(paper.paper_id, tabId, regenerate)
      );
      setTabContent(prev => ({ ...prev, [tabId]: result.summary }));
    } catch (err) {
      console.error(err);
      // Surface the backend's actual reason (e.g. "the link did not return a
      // valid PDF") rather than a blanket "try again" — for a paper whose PDF
      // can't be fetched, retrying can never succeed.
      const reason =
        err instanceof Error && err.message
          ? err.message
          : 'Could not generate this view.';
      setTabContent(prev => ({ ...prev, [tabId]: reason }));
    } finally {
      setTabLoading(false);
    }
  };

  const handleTabClick = async (tabId: string) => {
    setActiveTab(tabId);
    if (tabId === ABSTRACT_TAB.id || tabContent[tabId]) return;
    await loadSummary(tabId);
  };

  const allTabs = [ABSTRACT_TAB, ...levels];
  const activeTabMeta = allTabs.find(t => t.id === activeTab);

  return (
    <div className="min-h-screen bg-background text-on-background font-body-ui">
      <main className="px-margin-mobile md:px-margin-desktop max-w-max-width mx-auto grid grid-cols-1 lg:grid-cols-12 gap-gutter">
        {/* Back to the previous page (the Discovery Feed / Library the user came from). */}
        <button
          onClick={() => navigate(-1)}
          className="lg:col-span-12 flex items-center gap-2 w-fit text-on-surface-variant hover:text-primary transition-colors active:scale-95"
        >
          <span className="material-symbols-outlined">arrow_back</span>
          <span className="font-medium text-sm">Back</span>
        </button>

        {/* Left Column: Summary Content */}
        <div className="lg:col-span-8 space-y-8">

          {/* Paper Header Information */}
          <div className="space-y-4 pb-6 border-b border-outline-variant/30">
            <h1 className="font-h2 text-2xl md:text-3xl font-bold text-primary leading-tight">{paper.title}</h1>
            <p className="text-sm md:text-base text-on-surface-variant font-medium">
              {paper.authors.join(', ')} ({paper.publication_year})
            </p>
            {paper.pdf_url && (
              <a href={paper.pdf_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 bg-primary text-white px-5 py-2.5 rounded-lg font-medium text-sm transition-transform active:scale-95 whitespace-nowrap">
                <span className="material-symbols-outlined text-sm">download</span>
                <span>Download PDF</span>
              </a>
            )}
          </div>

          {/* Tab Selector */}
          <div className="flex gap-2 p-1 bg-surface-container rounded-xl overflow-x-auto scrollbar-hide">
            {allTabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => handleTabClick(tab.id)}
                className={`whitespace-nowrap px-5 py-2.5 rounded-lg font-bold shadow-sm transition-all text-sm ${
                  activeTab === tab.id
                    ? 'text-primary bg-primary-container'
                    : 'text-on-surface-variant hover:bg-surface-container-high/50'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Content Area */}
          <section className="space-y-6">
            <article className="font-body-reading text-body-reading text-on-surface leading-relaxed max-w-[800px]">
              {activeTab === ABSTRACT_TAB.id ? (
                <p className="mb-6 whitespace-pre-wrap">{paper.abstract}</p>
              ) : !workspaceId ? (
                <p className="text-on-surface-variant italic">
                  {paper.pdf_url
                    ? `Click "Chat with Paper" below to unlock the AI-generated ${activeTabMeta?.label.toLowerCase()} view.`
                    : `This paper has no open-access PDF, so the ${activeTabMeta?.label.toLowerCase()} view can't be generated — summaries are written only from the paper's own text.`}
                </p>
              ) : tabLoading && !tabContent[activeTab] ? (
                <p className="text-on-surface-variant italic flex items-center gap-2">
                  <span className="material-symbols-outlined animate-spin text-sm">sync</span>
                  Generating {activeTabMeta?.label.toLowerCase()} view...
                </p>
              ) : (
                <>
                  <p className="mb-4 whitespace-pre-wrap">{tabContent[activeTab]}</p>
                  {tabContent[activeTab] && (
                    <button
                      onClick={() => loadSummary(activeTab, true)}
                      disabled={tabLoading}
                      className="flex items-center gap-1.5 text-xs font-bold text-secondary hover:underline disabled:opacity-50"
                    >
                      <span className={`material-symbols-outlined text-sm ${tabLoading ? 'animate-spin' : ''}`}>refresh</span>
                      Regenerate
                    </button>
                  )}
                </>
              )}
            </article>
          </section>
        </div>

        {/* Right Column: HUD & Glossary */}
        <aside className="lg:col-span-4 space-y-gutter">
          <div className="glass-panel p-6 rounded-xl space-y-4 sticky top-24 shadow-sm border border-outline-variant/30">
            <div className="flex items-center justify-between mb-2">
              <span className="font-label-caps text-label-caps text-on-surface-variant">AGENT HUD</span>
              <div className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${isProcessing ? 'bg-secondary animate-pulse' : (workspaceId ? 'bg-emerald-500' : 'bg-outline')}`}></span>
                <span className="text-[10px] font-bold text-secondary tracking-widest">{isProcessing ? 'ANALYZING' : (workspaceId ? 'READY' : 'IDLE')}</span>
              </div>
            </div>

            <div className="space-y-4">
              {isProcessing ? (
                <div className="p-3 bg-surface rounded-lg border border-outline-variant/20">
                  <p className="text-[11px] font-mono-technical text-on-surface-variant uppercase mb-2">Current Operation</p>
                  <p className="text-sm font-medium text-primary flex items-center gap-2">
                    <span className="material-symbols-outlined animate-spin text-sm">sync</span>
                    <span className="animate-pulse">{LOADING_MESSAGES[loadingMsgIndex]}</span>
                  </p>
                </div>
              ) : (
                <div className="p-3 bg-surface rounded-lg border border-outline-variant/20">
                  <p className="text-sm font-medium text-on-surface-variant">
                    {workspaceId ? 'Paper embedded successfully. Ready for questions.' : 'Click "Chat with Paper" to analyze.'}
                  </p>
                </div>
              )}
            </div>
          </div>
        </aside>
      </main>

      {/* Full-screen overlay for the "prepare paper" step. It stays up for BOTH
          the in-progress state AND a failure, so a fast failure (e.g. a paywalled
          or dead PDF link that 403s) no longer flashes and vanishes — the reason
          stays on screen with a way to retry or dismiss. */}
      {(isProcessing || processError) && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-background/80 backdrop-blur-sm animate-fade-in p-4">
          <div className="bg-surface-container-lowest p-8 rounded-2xl shadow-2xl border border-outline-variant/30 max-w-sm w-full text-center space-y-6">
            {isProcessing ? (
              <>
                <div className="relative w-24 h-24 mx-auto flex items-center justify-center">
                  <div className="absolute inset-0 border-4 border-primary/20 rounded-full"></div>
                  <div className="absolute inset-0 border-4 border-primary rounded-full border-t-transparent animate-spin"></div>
                  <span className="material-symbols-outlined text-primary text-4xl animate-pulse">auto_awesome</span>
                </div>
                <div className="space-y-2">
                  <h3 className="font-h2 text-2xl text-primary font-bold">Preparing Paper...</h3>
                  <p className="text-on-surface-variant font-body-ui h-12 flex items-center justify-center transition-all animate-fade-in text-sm">
                    {LOADING_MESSAGES[loadingMsgIndex]}
                  </p>
                </div>
                <div className="flex justify-center gap-1.5 mt-4">
                  {LOADING_MESSAGES.map((_, i) => (
                    <div key={i} className={`h-1.5 rounded-full transition-all duration-500 ${i === loadingMsgIndex ? 'w-4 bg-primary' : (i < loadingMsgIndex ? 'w-1.5 bg-primary/50' : 'w-1.5 bg-outline-variant')}`}></div>
                  ))}
                </div>
                <p className="text-[11px] text-on-surface-variant/70">
                  Indexing the full PDF can take a little while on the first run.
                </p>
              </>
            ) : (
              <>
                <div className="relative w-20 h-20 mx-auto flex items-center justify-center">
                  <div className="absolute inset-0 border-4 border-error/20 rounded-full"></div>
                  <span className="material-symbols-outlined text-error text-4xl">error</span>
                </div>
                <div className="space-y-2">
                  <h3 className="font-h2 text-2xl text-error font-bold">Couldn't prepare this paper</h3>
                  <p className="text-on-surface-variant text-sm leading-relaxed">{processError}</p>
                </div>
                <div className="flex gap-3 justify-center pt-1">
                  <button
                    onClick={() => setProcessError(null)}
                    className="px-5 py-2.5 rounded-lg border border-outline-variant text-on-surface-variant text-sm font-medium hover:bg-surface-container transition-colors"
                  >
                    Dismiss
                  </button>
                  <button
                    onClick={handleProcessPaper}
                    className="px-5 py-2.5 rounded-lg bg-primary text-white text-sm font-bold hover:opacity-90 active:scale-95 transition-all"
                  >
                    Try Again
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Floating Action Button.
          Chat requires indexing the PDF, so a paper with no open-access PDF
          can never be chatted with. Say that up front instead of offering a
          button whose only possible outcome is an error. */}
      {!chatOpen && !isProcessing && (
        paper.pdf_url ? (
          <button
            onClick={workspaceId ? () => setChatOpen(true) : handleProcessPaper}
            className="fixed bottom-24 right-6 md:right-12 z-50 text-white flex items-center gap-3 px-6 py-4 rounded-full shadow-2xl hover:scale-105 active:scale-95 transition-all group bg-primary"
          >
            <span className="material-symbols-outlined group-hover:rotate-12 transition-transform">
              forum
            </span>
            <span className="font-bold text-sm tracking-wide">
              {workspaceId ? 'Open Chat' : 'Chat with Paper'}
            </span>
          </button>
        ) : (
          <div className="fixed bottom-24 right-6 md:right-12 z-50 max-w-[280px] flex items-start gap-2.5 px-5 py-4 rounded-2xl shadow-2xl bg-surface-container-high border border-outline-variant/30">
            <span className="material-symbols-outlined text-on-surface-variant text-[20px] shrink-0">
              lock
            </span>
            <p className="text-xs text-on-surface-variant leading-relaxed">
              No open-access PDF is available for this paper, so it can't be
              indexed for chat. The abstract above is all we have.
            </p>
          </div>
        )
      )}

      {/* Chat Interface Overlay */}
      {chatOpen && (
        <div className="fixed bottom-0 right-0 md:bottom-6 md:right-6 w-full h-[500px] md:w-[400px] bg-surface-container-lowest shadow-2xl md:rounded-xl border border-outline-variant/30 flex flex-col z-50 animate-fade-in overflow-hidden">
          {/* Header */}
          <div className="bg-primary text-on-primary p-4 flex justify-between items-center shrink-0">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined">smart_toy</span>
              <span className="font-bold">PaperPilot Chat</span>
            </div>
            <button onClick={() => setChatOpen(false)} className="text-on-primary/80 hover:text-white transition-colors">
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
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

          {/* Input */}
          <form onSubmit={handleSendMessage} className="p-3 bg-surface-container-lowest border-t border-outline-variant/20 shrink-0">
            <div className="relative flex items-center">
              <input
                type="text"
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                placeholder="Ask about this paper..."
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
      )}
    </div>
  );
};

export default PaperSummary;
