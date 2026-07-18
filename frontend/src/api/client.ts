export const API_BASE_URL = 'http://localhost:8000/api';

export interface Paper {
  paper_id: string;
  title: string;
  authors: string[];
  publication_year: number;
  citation_count: number;
  abstract: string;
  doi: string;
  pdf_url: string;
  venue: string;
}

export interface Workspace {
  workspace_id: string;
  name: string;
  paper_count: number;
}

export const fetchWorkspaces = async (): Promise<Workspace[]> => {
  const res = await fetch(`${API_BASE_URL}/workspaces`);
  if (!res.ok) throw new Error('Failed to fetch workspaces');
  return res.json();
};

export const createWorkspace = async (name: string): Promise<Workspace> => {
  const res = await fetch(`${API_BASE_URL}/workspaces`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error('Failed to create workspace');
  return res.json();
};

export const searchPapers = async (query: string, limit: number = 5): Promise<Paper[]> => {
  const res = await fetch(`${API_BASE_URL}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, limit }),
  });
  if (!res.ok) throw new Error('Failed to search papers');
  const data = await res.json();
  return data.results;
};

export const fetchWorkspacePapers = async (workspaceId: string): Promise<Paper[]> => {
  const res = await fetch(`${API_BASE_URL}/workspaces/${workspaceId}/papers`);
  if (!res.ok) throw new Error('Failed to fetch workspace papers');
  return res.json();
};

export const chatWithWorkspace = async (workspaceId: string, query: string): Promise<string> => {
  const res = await fetch(`${API_BASE_URL}/workspaces/${workspaceId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) throw new Error('Failed to chat');
  const data = await res.json();
  return data.answer;
};

export const processPaper = async (paper: Paper): Promise<string> => {
  const res = await fetch(`${API_BASE_URL}/papers/process`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(paper),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to process paper');
  }
  const data = await res.json();
  return data.workspace_id;
};
