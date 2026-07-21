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

export interface Citation {
  rank: number;
  score: number;
  text: string;
  page_number: string;
  paper_id: string | null;
  filename: string;
}

/**
 * A chat answer plus the evidence and audit result behind it. The backend
 * routes chat through the Tutor/Critic contract, so an answer can come back
 * flagged (`approved: false`) or refused — the UI shows both rather than
 * presenting an unverified answer as if it were verified.
 */
export interface ChatAnswer {
  answer: string;
  citations: Citation[];
  approved: boolean;
  refused: boolean;
  attempts: number;
  critique: string | null;
}

export const chatWithWorkspace = async (
  workspaceId: string,
  query: string,
  difficulty: string = 'graduate/expert',
): Promise<ChatAnswer> => {
  const res = await fetch(`${API_BASE_URL}/workspaces/${workspaceId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, difficulty }),
  });
  if (!res.ok) throw new Error('Failed to chat');
  return res.json();
};

export interface SummaryLevel {
  id: string;
  label: string;
  difficulty: string;
}

export const fetchSummaryLevels = async (): Promise<SummaryLevel[]> => {
  const res = await fetch(`${API_BASE_URL}/summary-levels`);
  if (!res.ok) throw new Error('Failed to fetch summary levels');
  const data = await res.json();
  return data.levels;
};

export interface SummaryResult {
  paper_id: string;
  level_id: string;
  summary: string;
  from_cache: boolean;
}

/** Generated summaries are cached server-side per paper+level; `regenerate` forces a fresh one. */
export const summarizePaper = async (
  paperId: string,
  levelId: string,
  regenerate: boolean = false,
): Promise<SummaryResult> => {
  const res = await fetch(
    `${API_BASE_URL}/papers/${paperId}/summary/${levelId}?regenerate=${regenerate}`,
    { method: 'POST' },
  );
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to generate summary');
  }
  return res.json();
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
