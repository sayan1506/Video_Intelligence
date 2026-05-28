import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fc from 'fast-check';
import { render, act } from '@testing-library/react';
import { ThemeProvider, useTheme } from '../contexts/ThemeContext';

const STORAGE_KEY = 'vidiq-theme';

/**
 * Helper component that exposes ThemeContext values for testing.
 */
function ThemeConsumer({ onRender }) {
  const { mode, toggle } = useTheme();
  onRender({ mode, toggle });
  return null;
}

describe('ThemeContext Properties', () => {
  let originalLocalStorage;

  beforeEach(() => {
    // Clear localStorage and document classes before each test
    localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  afterEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  // Feature: gold-string-theme-redesign, Property 2: Toggle round-trip persistence
  // **Validates: Requirements 1.3, 1.4**
  it('toggle round-trip persistence: toggling N times yields correct final mode, persists to localStorage, and re-initialization restores it', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('light', 'dark'),
        fc.integer({ min: 1, max: 20 }),
        (initialMode, toggleCount) => {
          // Setup: clear state and set localStorage to initial mode
          localStorage.clear();
          document.documentElement.classList.remove('dark');
          localStorage.setItem(STORAGE_KEY, initialMode);

          // Step 1: Render ThemeProvider and capture context
          let themeRef = {};
          const { unmount } = render(
            <ThemeProvider>
              <ThemeConsumer onRender={(ctx) => { themeRef = ctx; }} />
            </ThemeProvider>
          );

          // Verify initial mode is read from localStorage
          expect(themeRef.mode).toBe(initialMode);

          // Step 2: Call toggle N times
          for (let i = 0; i < toggleCount; i++) {
            act(() => {
              themeRef.toggle();
            });
          }

          // Step 3: Compute expected final mode
          // Each toggle flips the mode. Odd number of toggles = opposite of initial.
          const expectedMode = toggleCount % 2 === 1
            ? (initialMode === 'dark' ? 'light' : 'dark')
            : initialMode;

          // Step 4: Verify final mode is correct
          expect(themeRef.mode).toBe(expectedMode);

          // Step 5: Verify localStorage has the final mode
          expect(localStorage.getItem(STORAGE_KEY)).toBe(expectedMode);

          // Cleanup first render
          unmount();

          // Step 6: Re-render a fresh ThemeProvider and verify it reads the persisted mode
          let freshThemeRef = {};
          const { unmount: unmount2 } = render(
            <ThemeProvider>
              <ThemeConsumer onRender={(ctx) => { freshThemeRef = ctx; }} />
            </ThemeProvider>
          );

          expect(freshThemeRef.mode).toBe(expectedMode);

          // Cleanup
          unmount2();
        }
      ),
      { numRuns: 100 }
    );
  });
});
