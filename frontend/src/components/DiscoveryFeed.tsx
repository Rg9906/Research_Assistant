import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { searchPapers } from '../api/client';
import type { Paper } from '../api/client';

const DiscoveryFeed: React.FC = () => {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Paper[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const navigate = useNavigate();

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;
    
    setLoading(true);
    setHasSearched(true);
    try {
      const data = await searchPapers(query);
      setResults(data);
    } catch (err) {
      console.error(err);
      alert('Error searching papers.');
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestedClick = (suggestedQuery: string) => {
    setQuery(suggestedQuery);
    
    setLoading(true);
    setHasSearched(true);
    // we cant reliably call handleSearch immediately because state update is async
    searchPapers(suggestedQuery)
      .then((data) => {
          setResults(data);
      })
      .catch((err) => {
          console.error(err);
          alert('Error searching papers.');
      })
      .finally(() => {
          setLoading(false);
      });
  };

  const handleReadSummary = (paper: Paper, e: React.MouseEvent) => {
    e.stopPropagation();
    navigate(`/paper/${paper.paper_id}`, { state: { paper } });
  };

  return (
    <div className="lg:col-span-8 space-y-12 px-margin-mobile md:px-margin-desktop max-w-max-width mx-auto">
      {/* Agent-Guided Search */}
      <section className="relative">
        <div className="glass-panel p-6 rounded-xl shadow-sm space-y-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="material-symbols-outlined text-secondary">auto_awesome</span>
            <span className="font-label-caps text-label-caps text-secondary uppercase tracking-widest">Agent-Guided Synthesis</span>
          </div>
          <form onSubmit={handleSearch} className="relative group">
            <input 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full bg-surface-container-lowest border-outline-variant focus:border-primary focus:ring-1 focus:ring-primary h-14 pl-12 rounded-lg font-body-ui text-body-ui transition-all pr-6" 
              placeholder="Explore complex topics, e.g., 'Evolution of Vision Transformers in Medical Imaging'" 
              type="text" 
            />
            <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-outline">search</span>
          </form>
          <div className="flex flex-wrap gap-2 pt-2">
            <span className="text-xs font-mono-technical text-on-surface-variant">Suggested:</span>
            <button onClick={() => handleSuggestedClick('Cross-modal Attention')} className="text-xs font-mono-technical text-primary hover:underline transition-all px-2">Cross-modal Attention</button>
            <span className="text-xs text-outline-variant">•</span>
            <button onClick={() => handleSuggestedClick('Few-shot prompting')} className="text-xs font-mono-technical text-primary hover:underline transition-all px-2">Few-shot prompting</button>
            <span className="text-xs text-outline-variant">•</span>
            <button onClick={() => handleSuggestedClick('RAG Latency')} className="text-xs font-mono-technical text-primary hover:underline transition-all px-2">RAG Latency</button>
          </div>
        </div>
      </section>

      {/* Suggested Roadmaps */}
      <section>
        <div className="flex justify-between items-end mb-4">
          <h2 className="font-h2 text-h2 text-primary">Suggested Roadmaps</h2>
          <a className="font-label-caps text-label-caps text-on-surface-variant hover:text-primary transition-colors" href="#">VIEW ALL</a>
        </div>
        <div className="flex gap-4 overflow-x-auto pb-4 -mx-margin-mobile px-margin-mobile md:mx-0 md:px-0 md:px-4 scrollbar-hide">
          <div className="min-w-[280px] md:min-w-[320px] bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-5 hover:shadow-md transition-shadow cursor-pointer group">
            <div className="flex justify-between items-start mb-4">
              <span className="bg-primary-container text-on-primary-container px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider">AI FOUNDATIONS</span>
              <span className="material-symbols-outlined text-outline group-hover:text-primary transition-colors">map</span>
            </div>
            <h3 className="font-h2 text-lg text-on-surface mb-2">Vision Transformers</h3>
            <p className="text-on-surface-variant text-sm line-clamp-2 mb-4">From original ViT architectures to modern Swin and MAE breakthroughs.</p>
          </div>
        </div>
      </section>

      {/* Discoveries */}
      <section className="space-y-4">
        <div className="flex justify-between items-end">
          <h2 className="font-h2 text-h2 text-primary">Recent Discoveries {loading && <span className="text-sm">(Searching...)</span>}</h2>
        </div>
        {results.map((paper) => {
          return (
            <div key={paper.paper_id} className="group bg-surface-container-lowest border border-outline-variant/20 rounded-xl p-6 hover:border-primary/40 transition-all cursor-pointer">
              <div className="flex justify-between items-start gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="bg-surface-container-high text-on-surface-variant text-[10px] font-bold px-2 py-0.5 rounded uppercase">{paper.venue || 'ARXIV'}</span>
                    <span className="text-xs text-outline font-mono-technical">Published {paper.publication_year}</span>
                  </div>
                  <h4 className="font-h2 text-xl text-on-surface group-hover:text-primary transition-colors leading-tight">{paper.title}</h4>
                  <p className="text-on-surface-variant text-sm italic">{paper.authors.join(', ')}</p>
                </div>
              </div>
              <div className="mt-4 pt-4 border-t border-outline-variant/10 flex justify-between items-center">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-1 text-on-surface-variant">
                    <span className="material-symbols-outlined text-sm">format_quote</span>
                    <span className="text-xs font-mono-technical">{paper.citation_count} Citations</span>
                  </div>
                </div>
                <button 
                  onClick={(e) => handleReadSummary(paper, e)}
                  className="flex items-center gap-1 text-primary text-xs font-bold hover:gap-2 transition-all"
                >
                  READ SUMMARY 
                  <span className="material-symbols-outlined text-sm text-secondary">
                    arrow_forward
                  </span>
                </button>
              </div>
            </div>
          );
        })}
        {results.length === 0 && !loading && !hasSearched && (
            <p className="text-on-surface-variant italic">No recent discoveries yet. Try searching!</p>
        )}
        {results.length === 0 && !loading && hasSearched && (
            <p className="text-on-surface-variant italic">No papers found for your search. Try different keywords.</p>
        )}
      </section>
    </div>
  );
};

export default DiscoveryFeed;
