import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import DiscoveryFeed from './components/DiscoveryFeed';
import ResearchLibrary from './components/ResearchLibrary';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<DiscoveryFeed />} />
          <Route path="library" element={<ResearchLibrary />} />
          {/* We will add PaperSummary and Chat here as needed */}
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
