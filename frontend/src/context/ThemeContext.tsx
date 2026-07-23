import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';

/**
 * Light/dark theme, applied by toggling a single `.dark` class on <html>.
 *
 * The whole Material-3 token set is CSS-variable driven (see src/index.css +
 * tailwind.config.js), so that one class re-themes every token-based component
 * at once — no per-component wiring. The preference is persisted to
 * localStorage under {@link STORAGE_KEY}, so the chosen mode sticks across
 * navigations and reloads ("henceforth").
 *
 * The landing/splash screen has its own hardcoded styling (splash.css) and does
 * not use these tokens, so it is intentionally unaffected. This provider also
 * only wraps the mounted app tree, and its cleanup strips the class on unmount,
 * so returning to the landing page never leaves the app's dark class behind.
 */

export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'pp_theme';

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

function readStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
  } catch {
    // localStorage can throw in private-mode / sandboxed contexts — fall through.
  }
  return 'light';
}

/**
 * Apply the theme class to <html>. When `animate` is set, a short-lived
 * `.theme-transition` class crossfades colors; it is removed after the
 * transition so ordinary state changes elsewhere stay instant.
 */
function applyThemeClass(theme: Theme, animate: boolean): void {
  const root = document.documentElement;
  if (animate) {
    root.classList.add('theme-transition');
    window.setTimeout(() => root.classList.remove('theme-transition'), 320);
  }
  root.classList.toggle('dark', theme === 'dark');
}

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme, setThemeState] = useState<Theme>(readStoredTheme);

  // Sync the class + persistence whenever the theme changes. Runs on mount too,
  // so the app reflects the stored preference as soon as it is shown.
  useEffect(() => {
    applyThemeClass(theme, false);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // Ignore persistence failures; the in-session theme still works.
    }
  }, [theme]);

  // On unmount (e.g. returning to the landing page, which unmounts the app),
  // drop the dark class so the splash is never rendered under it.
  useEffect(() => {
    return () => document.documentElement.classList.remove('dark');
  }, []);

  const setTheme = useCallback((next: Theme) => {
    applyThemeClass(next, true);
    setThemeState(next);
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => {
      const next: Theme = prev === 'dark' ? 'light' : 'dark';
      applyThemeClass(next, true);
      return next;
    });
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within a ThemeProvider');
  return ctx;
}
