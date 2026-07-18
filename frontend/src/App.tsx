import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import DiscoveryFeed from './components/DiscoveryFeed';
import ResearchLibrary from './components/ResearchLibrary';
import PaperSummary from './components/PaperSummary';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<DiscoveryFeed />} />
          <Route path="library" element={<ResearchLibrary />} />
          <Route path="paper/:paperId" element={<PaperSummary />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
