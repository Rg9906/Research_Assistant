import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import DiscoveryFeed from './components/DiscoveryFeed';
import ResearchLibrary from './components/ResearchLibrary';
import PaperSummary from './components/PaperSummary';
import WorkspaceDetail from './components/WorkspaceDetail';
import { AgentActivityProvider } from './context/AgentActivityContext';
import SplashScreen from './components/splash/SplashScreen';

// Shown once per browser session, so navigating routes or refreshing mid-session
// doesn't replay the intro.
const SPLASH_KEY = 'pp_splash_seen';

// Any part of the app can ask to return to the landing splash (e.g. the navbar
// "Log out" control) by dispatching this event — App replays the intro.
export const RETURN_HOME_EVENT = 'pp:return-home';

// Handoff stages. The application is deliberately NOT mounted while the splash is
// up ('splash'), so the app's own navbar logo can never coexist with the splash
// wordmark. On BEGIN the splash dissolves its ribbons + wordmark first, then fires
// onExitStart → we mount + fade the app in ('reveal') as the (now logo-less) splash
// background fades out, and finally onExited → we drop the splash ('done').
type Stage = 'splash' | 'reveal' | 'done';

function App() {
  const [stage, setStage] = useState<Stage>(() =>
    sessionStorage.getItem(SPLASH_KEY) === '1' ? 'done' : 'splash',
  );

  // Returning to the landing page: clear the "seen" flag and replay the splash
  // from the top (this unmounts the app tree, so the app + splash logos never
  // coexist — same guarantee as the first load).
  useEffect(() => {
    const returnHome = () => {
      sessionStorage.removeItem(SPLASH_KEY);
      setStage('splash');
    };
    window.addEventListener(RETURN_HOME_EVENT, returnHome);
    return () => window.removeEventListener(RETURN_HOME_EVENT, returnHome);
  }, []);

  const appMounted = stage !== 'splash';

  return (
    <>
      {stage !== 'done' && (
        <SplashScreen
          onExitStart={() => {
            sessionStorage.setItem(SPLASH_KEY, '1');
            setStage('reveal');
          }}
          onExited={() => setStage('done')}
        />
      )}
      {appMounted && (
        <div
          className={stage === 'reveal' ? 'pp-app-enter' : undefined}
          style={stage === 'reveal' ? { pointerEvents: 'none' } : undefined}
        >
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
        </div>
      )}
    </>
  );
}

export default App;
