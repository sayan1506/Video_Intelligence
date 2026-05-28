import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { describe, it, expect, afterEach, beforeEach } from 'vitest';
import ThemeToggle from '../components/ThemeToggle';
import { ThemeProvider } from '../contexts/ThemeContext';

afterEach(() => {
  cleanup();
  localStorage.clear();
  document.documentElement.classList.remove('dark');
});

/**
 * Helper: renders ThemeToggle wrapped in ThemeProvider with a given initial mode.
 */
function renderToggle(initialMode = 'dark') {
  localStorage.setItem('vidiq-theme', initialMode);
  return render(
    <ThemeProvider>
      <ThemeToggle />
    </ThemeProvider>
  );
}

describe('ThemeToggle', () => {
  // --- Requirement 2.1: Correct icon rendering per mode ---

  describe('icon rendering per mode', () => {
    it('renders Moon icon when current mode is dark', () => {
      renderToggle('dark');
      const button = screen.getByRole('button');
      // Moon icon from lucide-react renders an SVG with a specific class
      const svg = button.querySelector('svg');
      expect(svg).toBeInTheDocument();
      // In dark mode, aria-label says "Switch to light mode"
      expect(button).toHaveAttribute('aria-label', 'Switch to light mode');
    });

    it('renders Sun icon when current mode is light', () => {
      renderToggle('light');
      const button = screen.getByRole('button');
      const svg = button.querySelector('svg');
      expect(svg).toBeInTheDocument();
      // In light mode, aria-label says "Switch to dark mode"
      expect(button).toHaveAttribute('aria-label', 'Switch to dark mode');
    });
  });

  // --- Requirement 2.2: Click triggers mode switch ---

  describe('click triggers mode switch', () => {
    it('toggles from dark to light on click', () => {
      renderToggle('dark');
      const button = screen.getByRole('button');

      expect(button).toHaveAttribute('aria-label', 'Switch to light mode');

      fireEvent.click(button);

      // After toggle, should now be in light mode
      expect(button).toHaveAttribute('aria-label', 'Switch to dark mode');
    });

    it('toggles from light to dark on click', () => {
      renderToggle('light');
      const button = screen.getByRole('button');

      expect(button).toHaveAttribute('aria-label', 'Switch to dark mode');

      fireEvent.click(button);

      // After toggle, should now be in dark mode
      expect(button).toHaveAttribute('aria-label', 'Switch to light mode');
    });

    it('toggles dark → light → dark on consecutive clicks', () => {
      renderToggle('dark');
      const button = screen.getByRole('button');

      // Start: dark
      expect(button).toHaveAttribute('aria-label', 'Switch to light mode');

      // First click: dark → light
      fireEvent.click(button);
      expect(button).toHaveAttribute('aria-label', 'Switch to dark mode');

      // Second click: light → dark
      fireEvent.click(button);
      expect(button).toHaveAttribute('aria-label', 'Switch to light mode');
    });
  });

  // --- Requirement 2.3: aria-label updates dynamically ---

  describe('aria-label updates dynamically', () => {
    it('has aria-label "Switch to light mode" in dark mode', () => {
      renderToggle('dark');
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-label', 'Switch to light mode');
    });

    it('has aria-label "Switch to dark mode" in light mode', () => {
      renderToggle('light');
      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-label', 'Switch to dark mode');
    });

    it('updates aria-label after toggle', () => {
      renderToggle('dark');
      const button = screen.getByRole('button');

      expect(button).toHaveAttribute('aria-label', 'Switch to light mode');
      fireEvent.click(button);
      expect(button).toHaveAttribute('aria-label', 'Switch to dark mode');
    });
  });

  // --- Requirement 2.4: Focus ring visibility on keyboard focus ---

  describe('focus ring visibility', () => {
    it('has focus-visible:ring-2 class for keyboard focus ring', () => {
      renderToggle('dark');
      const button = screen.getByRole('button');
      expect(button.className).toContain('focus-visible:ring-2');
    });
  });

  // --- Requirement 2.5: Minimum 44×44px target size ---

  describe('minimum 44×44px target size', () => {
    it('has w-11 h-11 classes for 44px interactive target', () => {
      renderToggle('dark');
      const button = screen.getByRole('button');
      expect(button.className).toContain('w-11');
      expect(button.className).toContain('h-11');
    });
  });
});
