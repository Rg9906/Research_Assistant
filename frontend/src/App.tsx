import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import DiscoveryFeed from './components/DiscoveryFeed';
import ResearchLibrary from './components/ResearchLibrary';
import PaperSummary from './components/PaperSummary';
import WorkspaceDetail from './components/WorkspaceDetail';
import { AgentActivityProvider } from './context/AgentActivityContext';

function App() {
  return (
    <AgentActivityProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<DiscoveryFeed />} />
            <Route path="library" element={<ResearchLibrary />} />
            <Route path="paper/:paperId" element={<PaperSummary />} />
            <Route path="workspace/:workspaceId" element={<WorkspaceDetail />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AgentActivityProvider>
  );
}

export default App;
