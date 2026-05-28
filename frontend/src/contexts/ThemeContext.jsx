import { createContext, useContext, useState, useEffect } from 'react';

/**
 * ThemeContext — global light/dark mode state for VidIQ.
 *
 * Provides:
 *   mode    — "light" or "dark"
 *   toggle  — flips the mode, persists to localStorage, and updates <html> class
 */
const ThemeContext = createContext(undefined);

const STORAGE_KEY = 'vidiq-theme';

/**
 * Safely reads the stored theme from localStorage.
 * Returns "dark" if the value is missing, invalid, or localStorage is unavailable.
 */
function getStoredTheme() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'light' || stored === 'dark') {
      return stored;
    }
  } catch {
    // localStorage unavailable (private browsing, storage quota, etc.)
  }
  return 'dark';
}

/**
 * Synchronizes the "dark" class on <html> with the current mode.
 */
function applyModeToDocument(mode) {
  if (typeof document === 'undefined') return;
  if (mode === 'dark') {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
}

export function ThemeProvider({ children }) {
  // Initialize from localStorage synchronously to prevent FOUC.
  // The lazy initializer runs during the first render, before paint.
  const [mode, setMode] = useState(() => {
    const initial = getStoredTheme();
    applyModeToDocument(initial);
    return initial;
  });

  // Keep document class in sync whenever mode changes (covers hydration edge case)
  useEffect(() => {
    applyModeToDocument(mode);
  }, [mode]);

  const toggle = () => {
    setMode((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark';
      // Persist to localStorage
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        // localStorage unavailable — toggle still works in-memory for the session
      }
      // Update document root class immediately
      applyModeToDocument(next);
      return next;
    });
  };

  return (
    <ThemeContext.Provider value={{ mode, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

/**
 * useTheme — convenience hook for consuming ThemeContext.
 *
 * Usage:
 *   const { mode, toggle } = useTheme();
 *
 * Throws if used outside of a ThemeProvider.
 */
export function useTheme() {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
