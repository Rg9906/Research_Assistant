import React from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { useAgentActivity } from '../context/AgentActivityContext';
import { useTheme } from '../context/ThemeContext';
import { RETURN_HOME_EVENT } from '../App';

const Layout: React.FC = () => {
  const location = useLocation();
  const { isActive, label } = useAgentActivity();
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';

  // Return to the landing / splash page (handled in App, which replays the intro).
  const returnToLanding = () => window.dispatchEvent(new Event(RETURN_HOME_EVENT));

  return (
    <>
      <nav className="fixed top-0 w-full z-50 bg-surface/70 backdrop-blur-md border-b border-outline-variant/30 shadow-sm h-16">
        <div className="flex justify-between items-center px-margin-mobile h-16 w-full max-w-max-width mx-auto">
          <Link to="/" className="flex items-center gap-3">
            <span className="material-symbols-outlined text-primary text-2xl">hub</span>
            <h1 className="font-h2 text-h2 font-bold text-primary">PaperPilot AI</h1>
          </Link>
          <div className="flex items-center gap-4">
            <div className={`hidden md:flex items-center bg-surface-container-low px-3 py-1.5 rounded-full border border-outline-variant/20 ${isActive ? 'agent-glow' : ''}`}>
              <div className={`w-2 h-2 rounded-full mr-2 ${isActive ? 'bg-[#38B2AC] animate-pulse' : 'bg-outline-variant'}`}></div>
              <span className="font-mono-technical text-mono-technical text-on-surface-variant">
                Agent: <span className="font-bold">{isActive ? label : 'Idle'}</span>
              </span>
            </div>
            {/* Day / night theme toggle. Persists via ThemeContext and applies
                to every app page henceforth; the landing/splash keeps its own
                look and is unaffected. */}
            <button
              onClick={toggleTheme}
              title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              aria-pressed={isDark}
              className="flex items-center justify-center w-9 h-9 rounded-full text-on-surface-variant hover:text-primary hover:bg-surface-container-high transition-colors active:scale-90"
            >
              <span className="material-symbols-outlined text-xl">
                {isDark ? 'light_mode' : 'dark_mode'}
              </span>
            </button>
            <div className="w-8 h-8 rounded-full bg-primary-fixed flex items-center justify-center text-primary font-bold overflow-hidden border border-outline-variant">
              PA
            </div>
            <button
              onClick={returnToLanding}
              title="Log out — return to the landing page"
              aria-label="Log out and return to the landing page"
              className="flex items-center justify-center w-9 h-9 rounded-full text-on-surface-variant hover:text-primary hover:bg-surface-container-high transition-colors active:scale-90"
            >
              <span className="material-symbols-outlined text-xl">logout</span>
            </button>
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
