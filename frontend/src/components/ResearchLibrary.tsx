import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchWorkspaces, createWorkspace } from '../api/client';
import type { Workspace } from '../api/client';

const ResearchLibrary: React.FC = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [newWorkspaceName, setNewWorkspaceName] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const loadWorkspaces = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchWorkspaces();
      setWorkspaces(data);
    } catch (err) {
      console.error(err);
      setError('Could not load workspaces. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWorkspaces();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWorkspaceName.trim()) return;
    setError(null);
    try {
      await createWorkspace(newWorkspaceName);
      setNewWorkspaceName('');
      loadWorkspaces();
    } catch (err) {
      console.error(err);
      setError('Could not create workspace. Please try again.');
    }
  };

  return (
    <div className="lg:col-span-8 space-y-8 px-margin-mobile md:px-margin-desktop max-w-max-width mx-auto pb-24">
      
      {/* Header Section */}
      <section className="mt-8 mb-10 text-center md:text-left">
        <h2 className="font-h1 text-4xl md:text-5xl text-primary font-bold tracking-tight mb-4">Research Library</h2>
        <p className="text-on-surface-variant text-lg max-w-2xl font-body-ui">
          Manage your active research sessions, saved papers, and custom collections. Your AI-assisted knowledge base lives here.
        </p>
      </section>

      {/* Creation Form */}
      <section className="mb-12">
        <div className="glass-panel rounded-2xl p-6 relative overflow-hidden group border border-outline-variant/40 shadow-sm">
          <div className="absolute inset-0 bg-gradient-to-r from-primary/5 to-secondary/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
          <form onSubmit={handleCreate} className="relative flex flex-col md:flex-row gap-4 items-center z-10">
            <div className="relative flex-1 w-full">
              <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-outline-variant pointer-events-none">
                search
              </span>
              <input 
                type="text" 
                value={newWorkspaceName}
                onChange={(e) => setNewWorkspaceName(e.target.value)}
                placeholder="Name your new workspace..."
                className="w-full bg-surface-container-highest border border-outline-variant/30 focus:border-primary focus:ring-2 focus:ring-primary/20 h-14 pl-12 pr-4 rounded-xl font-body-ui text-body-ui text-on-surface transition-all placeholder:text-outline-variant outline-none"
              />
            </div>
            <button 
              type="submit" 
              disabled={!newWorkspaceName.trim()}
              className="w-full md:w-auto h-14 bg-primary hover:bg-primary-container text-on-primary px-8 rounded-xl font-bold flex items-center justify-center gap-2 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-primary/20 disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:shadow-none font-label-caps tracking-wider"
            >
              <span className="material-symbols-outlined text-[20px]">add</span>
              CREATE WORKSPACE
            </button>
          </form>
        </div>
      </section>

      {/* Error Message */}
      {error && (
        <div className="bg-error-container border border-error/20 text-on-error-container rounded-xl p-4 text-sm flex items-center gap-3 mb-8">
          <span className="material-symbols-outlined">error</span>
          <p className="font-body-ui font-medium">{error}</p>
        </div>
      )}

      {/* Workspaces Grid */}
      <section>
        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 text-outline-variant animate-pulse">
            <span className="material-symbols-outlined text-4xl mb-4">hourglass_empty</span>
            <p className="font-body-ui font-medium">Loading your workspaces...</p>
          </div>
        ) : workspaces.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 px-4 text-center glass-panel rounded-3xl border-dashed border-2 border-outline-variant/50">
            <div className="w-20 h-20 bg-surface-container rounded-full flex items-center justify-center mb-6 shadow-inner">
              <span className="material-symbols-outlined text-4xl text-primary/40">library_books</span>
            </div>
            <h3 className="text-2xl font-h2 text-on-surface mb-3 font-semibold">Your library is empty</h3>
            <p className="text-on-surface-variant max-w-md mb-8 font-body-ui">
              Create a workspace above to start organizing your papers, generating summaries, and interacting with the AI.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {workspaces.map((w) => (
              <div
                key={w.workspace_id}
                onClick={() => navigate(`/workspace/${w.workspace_id}`)}
                className="group relative bg-surface-container-lowest rounded-2xl p-6 cursor-pointer transition-all duration-300 hover:-translate-y-1.5 hover:shadow-xl border border-outline-variant/30 hover:border-primary/40 flex flex-col h-full min-h-[200px] overflow-hidden"
              >
                {/* Decorative Top Gradient Line */}
                <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-primary to-secondary opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
                
                <div className="flex justify-between items-start mb-6 z-10">
                  <div className="bg-primary-container/20 text-primary-container px-3 py-1.5 rounded-full text-xs font-bold tracking-widest flex items-center gap-1.5 font-label-caps">
                    <span className="material-symbols-outlined text-[14px]">folder_open</span>
                    WORKSPACE
                  </div>
                  <div className="w-8 h-8 rounded-full bg-surface-container flex items-center justify-center text-outline group-hover:bg-primary group-hover:text-on-primary transition-colors duration-300 shadow-sm">
                    <span className="material-symbols-outlined text-sm transition-transform duration-300 group-hover:translate-x-0.5">arrow_forward</span>
                  </div>
                </div>
                
                <h3 className="font-h2 text-xl text-on-surface mb-4 line-clamp-2 leading-snug group-hover:text-primary transition-colors duration-300 z-10">
                  {w.name}
                </h3>
                
                <div className="mt-auto pt-4 border-t border-outline-variant/20 flex items-center justify-between z-10">
                  <div className="flex items-center gap-2 text-on-surface-variant group-hover:text-primary-container transition-colors duration-300">
                    <span className="material-symbols-outlined text-[18px]">description</span>
                    <span className="text-sm font-body-ui font-medium">
                      {w.paper_count} {w.paper_count === 1 ? 'Paper' : 'Papers'}
                    </span>
                  </div>
                </div>
                
                {/* Subtle Background Glow on Hover */}
                <div className="absolute -bottom-16 -right-16 w-40 h-40 bg-primary/5 rounded-full blur-3xl group-hover:bg-primary/15 transition-all duration-700 pointer-events-none"></div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};

export default ResearchLibrary;
