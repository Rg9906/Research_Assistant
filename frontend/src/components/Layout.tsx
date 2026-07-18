import React from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';

const Layout: React.FC = () => {
  const location = useLocation();

  return (
    <>
      <nav className="fixed top-0 w-full z-50 bg-surface/70 backdrop-blur-md border-b border-outline-variant/30 shadow-sm h-16">
        <div className="flex justify-between items-center px-margin-mobile h-16 w-full max-w-max-width mx-auto">
          <Link to="/" className="flex items-center gap-3">
            <span className="material-symbols-outlined text-primary text-2xl">hub</span>
            <h1 className="font-h2 text-h2 font-bold text-primary">PaperPilot AI</h1>
          </Link>
          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center bg-surface-container-low px-3 py-1.5 rounded-full border border-outline-variant/20 agent-glow">
              <div className="w-2 h-2 rounded-full bg-[#38B2AC] mr-2 animate-pulse"></div>
              <span className="font-mono-technical text-mono-technical text-on-surface-variant">Planner Agent: <span className="font-bold">Thinking...</span></span>
            </div>
            <div className="w-8 h-8 rounded-full bg-primary-fixed flex items-center justify-center text-primary font-bold overflow-hidden border border-outline-variant">
              PA
            </div>
          </div>
        </div>
      </nav>

      <div className="pt-24 pb-32 md:pl-[72px]">
        <Outlet />
      </div>

      <nav className="fixed bottom-0 left-0 w-full flex justify-around items-center h-20 pb-safe px-4 bg-surface border-t border-outline-variant/20 z-50 md:hidden">
        <Link to="/library" className={`flex flex-col items-center justify-center px-4 py-1 hover:text-primary transition-all active:scale-90 duration-200 ${location.pathname === '/library' ? 'bg-primary-container text-on-primary-container rounded-full' : 'text-on-surface-variant'}`}>
          <span className="material-symbols-outlined">library_books</span>
          <span className="font-label-caps text-label-caps mt-1">Library</span>
        </Link>
        <Link to="/" className={`flex flex-col items-center justify-center px-4 py-1 hover:text-primary transition-all active:scale-90 duration-200 ${location.pathname === '/' ? 'bg-primary-container text-on-primary-container rounded-full' : 'text-on-surface-variant'}`}>
          <span className="material-symbols-outlined" style={location.pathname === '/' ? { fontVariationSettings: "'FILL' 1" } : {}}>explore</span>
          <span className="font-label-caps text-label-caps mt-1">Discover</span>
        </Link>
      </nav>
      
      {/* Desktop Sidebar Rail */}
      <nav className="hidden md:flex fixed left-0 top-0 h-full w-[72px] flex-col items-center py-20 bg-surface border-r border-outline-variant/10 z-40">
        <div className="flex flex-col gap-8 w-full">
            <Link to="/library" className={`w-full flex flex-col items-center justify-center py-2 border-r-2 ${location.pathname === '/library' ? 'border-primary text-primary bg-surface-container-high' : 'border-transparent text-on-surface-variant hover:bg-surface-container'}`}>
                <span className="material-symbols-outlined mb-1">library_books</span>
                <span className="text-[10px] font-bold uppercase">Library</span>
            </Link>
            <Link to="/" className={`w-full flex flex-col items-center justify-center py-2 border-r-2 ${location.pathname === '/' ? 'border-primary text-primary bg-surface-container-high' : 'border-transparent text-on-surface-variant hover:bg-surface-container'}`}>
                <span className="material-symbols-outlined mb-1" style={location.pathname === '/' ? { fontVariationSettings: "'FILL' 1" } : {}}>explore</span>
                <span className="text-[10px] font-bold uppercase">Discover</span>
            </Link>
        </div>
      </nav>
    </>
  );
};

export default Layout;
