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
    <div className="lg:col-span-8 space-y-12 px-margin-mobile md:px-margin-desktop max-w-max-width mx-auto">
      <section>
        <h2 className="font-h2 text-h2 text-primary mb-6">Research Library</h2>
        
        <form onSubmit={handleCreate} className="mb-8 flex gap-4">
          <input 
            type="text" 
            value={newWorkspaceName}
            onChange={(e) => setNewWorkspaceName(e.target.value)}
            placeholder="New Workspace Name..."
            className="flex-1 bg-surface-container-lowest border-outline-variant focus:border-primary focus:ring-1 focus:ring-primary h-12 px-4 rounded-lg font-body-ui text-body-ui transition-all"
          />
          <button type="submit" className="bg-primary text-on-primary px-6 rounded-lg font-bold">
            CREATE
          </button>
        </form>

        {error && (
          <div className="bg-error-container text-on-error-container rounded-lg p-4 text-sm flex items-center gap-2 mb-6">
            <span className="material-symbols-outlined text-sm">error</span>
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {loading ? (
            <p className="text-on-surface-variant">Loading...</p>
          ) : workspaces.length === 0 ? (
            <p className="text-on-surface-variant">No workspaces found.</p>
          ) : (
            workspaces.map(w => (
              <div
                key={w.workspace_id}
                onClick={() => navigate(`/workspace/${w.workspace_id}`)}
                className="bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-5 hover:shadow-md transition-shadow cursor-pointer group"
              >
                <div className="flex justify-between items-start mb-4">
                  <span className="bg-primary-container text-on-primary-container px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider">WORKSPACE</span>
                  <span className="material-symbols-outlined text-outline group-hover:text-primary transition-colors">folder_open</span>
                </div>
                <h3 className="font-h2 text-lg text-on-surface mb-2">{w.name}</h3>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono-technical text-outline">{w.paper_count} Papers</span>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
};

export default ResearchLibrary;
