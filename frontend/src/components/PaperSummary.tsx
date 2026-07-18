import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { processPaper, chatWithWorkspace } from '../api/client';
import type { Paper } from '../api/client';
import { useAgentActivity } from '../context/AgentActivityContext';

const LOADING_MESSAGES = [
  "Brewing coffee for the AI...",
  "Looking up papers...",
  "Finding more info about the author...",
  "Learning context...",
  "Learning to reason...",
  "Getting inferences...",
  "Almost there..."
];

interface SummaryTab {
  id: string;
  label: string;
  prompt: string;
}

const SUMMARY_TABS: SummaryTab[] = [
  { id: 'quick', label: 'Quick', prompt: 'Summarize this paper in five clear sentences.' },
  { id: 'beginner', label: 'Beginner', prompt: "Explain this paper as if I'm an undergraduate student, avoiding heavy jargon and defining any technical terms you use." },
  { id: 'technical', label: 'Technical', prompt: 'Give a graduate/researcher-level technical explanation of this paper, focusing on the methodology.' },
  { id: 'contribution', label: 'Contribution', prompt: "List this paper's key contributions as concise bullet points." },
  { id: 'limitations', label: 'Limitations', prompt: 'What are the limitations and weaknesses of this paper?' },
];

const PaperSummary: React.FC = () => {
  const { state } = useLocation();
  const navigate = useNavigate();
  const paper = state?.paper as Paper | undefined;
  const { withActivity } = useAgentActivity();

  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processError, setProcessError] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [messages, setMessages] = useState<{ role: 'user' | 'agent'; content: string }[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [loadingMsgIndex, setLoadingMsgIndex] = useState(0);

  const [activeTab, setActiveTab] = useState('quick');
  const [tabContent, setTabContent] = useState<Record<string, string>>({});
  const [tabLoading, setTabLoading] = useState(false);

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
      setProcessError('Failed to process this paper for chat. Please try again.');
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
      const answer = await withActivity('Answering from paper...', () => chatWithWorkspace(workspaceId, userMessage));
      setMessages(prev => [...prev, { role: 'agent', content: answer }]);
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: 'agent', content: 'Sorry, I encountered an error answering your question.' }]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleTabClick = async (tabId: string) => {
    setActiveTab(tabId);
    if (tabId === 'quick' || tabContent[tabId] || !workspaceId) return;

    const tab = SUMMARY_TABS.find(t => t.id === tabId);
    if (!tab) return;

    setTabLoading(true);
    try {
      const answer = await withActivity(`Generating ${tab.label.toLowerCase()} view...`, () =>
        chatWithWorkspace(workspaceId, tab.prompt)
      );
      setTabContent(prev => ({ ...prev, [tabId]: answer }));
    } catch (err) {
      console.error(err);
      setTabContent(prev => ({ ...prev, [tabId]: 'Sorry, could not generate this view. Please try again.' }));
    } finally {
      setTabLoading(false);
    }
  };

  const activeTabMeta = SUMMARY_TABS.find(t => t.id === activeTab);

  return (
    <div className="min-h-screen bg-background text-on-background font-body-ui">
      <main className="px-margin-mobile md:px-margin-desktop max-w-max-width mx-auto grid grid-cols-1 lg:grid-cols-12 gap-gutter">
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

          {processError && (
            <div className="bg-error-container text-on-error-container rounded-lg p-4 text-sm flex items-center gap-2">
              <span className="material-symbols-outlined text-sm">error</span>
              {processError}
            </div>
          )}

          {/* Tab Selector */}
          <div className="flex gap-2 p-1 bg-surface-container rounded-xl overflow-x-auto scrollbar-hide">
            {SUMMARY_TABS.map(tab => (
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
              {activeTab === 'quick' ? (
                <p className="mb-6 whitespace-pre-wrap">{paper.abstract}</p>
              ) : !workspaceId ? (
                <p className="text-on-surface-variant italic">
                  Click "Chat with Paper" below to unlock the AI-generated {activeTabMeta?.label.toLowerCase()} view.
                </p>
              ) : tabLoading && !tabContent[activeTab] ? (
                <p className="text-on-surface-variant italic flex items-center gap-2">
                  <span className="material-symbols-outlined animate-spin text-sm">sync</span>
                  Generating {activeTabMeta?.label.toLowerCase()} view...
                </p>
              ) : (
                <p className="mb-6 whitespace-pre-wrap">{tabContent[activeTab]}</p>
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

      {/* Full Screen Loading Overlay */}
      {isProcessing && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-background/80 backdrop-blur-sm animate-fade-in">
          <div className="bg-surface-container-lowest p-8 rounded-2xl shadow-2xl border border-outline-variant/30 max-w-sm w-full text-center space-y-6">
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
          </div>
        </div>
      )}

      {/* Floating Action Button */}
      {!chatOpen && !isProcessing && (
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
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] p-3 rounded-lg text-sm ${msg.role === 'user' ? 'bg-primary-container text-on-primary-container rounded-tr-none' : 'bg-surface-container text-on-surface rounded-tl-none border border-outline-variant/20'}`}>
                  {msg.content}
                </div>
              </div>
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
