import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';

/**
 * Utility: Parse a hex color string to RGB components.
 * Supports 6-digit hex format: #RRGGBB
 */
function hexToRgb(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return { r, g, b };
}

/**
 * Utility: Compute relative luminance per WCAG 2.1.
 * https://www.w3.org/TR/WCAG21/#dfn-relative-luminance
 */
function relativeLuminance({ r, g, b }) {
  const [rs, gs, bs] = [r, g, b].map((c) => {
    const sRGB = c / 255;
    return sRGB <= 0.03928
      ? sRGB / 12.92
      : Math.pow((sRGB + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

/**
 * Utility: Compute contrast ratio between two luminance values.
 * https://www.w3.org/TR/WCAG21/#dfn-contrast-ratio
 */
function contrastRatioFromLuminance(l1, l2) {
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Utility: Compute contrast ratio between two hex colors.
 */
function contrastRatio(color1, color2) {
  const l1 = relativeLuminance(hexToRgb(color1));
  const l2 = relativeLuminance(hexToRgb(color2));
  return contrastRatioFromLuminance(l1, l2);
}

/**
 * Utility: Composite an rgba foreground color over an opaque background.
 * Returns the effective RGB values (0-255).
 */
function compositeOver(fgR, fgG, fgB, fgA, bgR, bgG, bgB) {
  return {
    r: Math.round(fgR * fgA + bgR * (1 - fgA)),
    g: Math.round(fgG * fgA + bgG * (1 - fgA)),
    b: Math.round(fgB * fgA + bgB * (1 - fgA)),
  };
}

// Feature: gold-string-theme-redesign, Property 4: WCAG AA normal text contrast
describe('Color Contrast Property Tests', () => {
  /**
   * Property 4: WCAG AA contrast ratio for normal text
   *
   * For any pairing of a normal-text color token with its designated background
   * color token (dark mode: gold-text-primary on gold-bg-primary, gold-text-secondary
   * on gold-bg-primary, gold-text-secondary on gold-bg-secondary; light mode:
   * gold-light-text-primary on gold-light-bg-primary, gold-light-text-secondary on
   * gold-light-bg-primary, gold-light-text-secondary on gold-light-bg-secondary),
   * the computed contrast ratio SHALL be at least 4.5:1.
   *
   * **Validates: Requirements 7.6, 9.1**
   */
  it('Property 4: All normal text/background token pairs meet WCAG AA 4.5:1 contrast ratio', () => {
    const normalTextPairs = [
      // Dark mode pairs
      {
        name: 'Dark: gold-text-primary (#F5F5F0) on gold-bg-primary (#0C0C0C)',
        text: { r: 245, g: 245, b: 240, a: 1.0 },
        bg: { r: 12, g: 12, b: 12 },
      },
      {
        name: 'Dark: gold-text-secondary (rgba(245,245,240,0.7)) on gold-bg-primary (#0C0C0C)',
        text: { r: 245, g: 245, b: 240, a: 0.7 },
        bg: { r: 12, g: 12, b: 12 },
      },
      {
        name: 'Dark: gold-text-secondary (rgba(245,245,240,0.7)) on gold-bg-secondary (#141414)',
        text: { r: 245, g: 245, b: 240, a: 0.7 },
        bg: { r: 20, g: 20, b: 20 },
      },
      // Light mode pairs
      {
        name: 'Light: gold-light-text-primary (#0C0C0C) on gold-light-bg-primary (#FAFAF7)',
        text: { r: 12, g: 12, b: 12, a: 1.0 },
        bg: { r: 250, g: 250, b: 247 },
      },
      {
        name: 'Light: gold-light-text-secondary (rgba(12,12,12,0.7)) on gold-light-bg-primary (#FAFAF7)',
        text: { r: 12, g: 12, b: 12, a: 0.7 },
        bg: { r: 250, g: 250, b: 247 },
      },
      {
        name: 'Light: gold-light-text-secondary (rgba(12,12,12,0.7)) on gold-light-bg-secondary (#FFFFFF)',
        text: { r: 12, g: 12, b: 12, a: 0.7 },
        bg: { r: 255, g: 255, b: 255 },
      },
    ];

    fc.assert(
      fc.property(
        fc.constantFrom(...normalTextPairs),
        (pair) => {
          const { text, bg } = pair;

          // Composite the text color over the background if it has alpha < 1
          let effectiveColor;
          if (text.a < 1.0) {
            effectiveColor = compositeOver(text.r, text.g, text.b, text.a, bg.r, bg.g, bg.b);
          } else {
            effectiveColor = { r: text.r, g: text.g, b: text.b };
          }

          const textLuminance = relativeLuminance(effectiveColor);
          const bgLuminance = relativeLuminance(bg);
          const ratio = contrastRatioFromLuminance(textLuminance, bgLuminance);

          expect(ratio).toBeGreaterThanOrEqual(4.5);
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Property 5: WCAG AA contrast ratio for large text and UI boundaries
   *
   * For any pairing of a large-text/accent color token with its adjacent
   * background token, the computed contrast ratio SHALL be at least 3:1.
   *
   * **Validates: Requirements 9.2**
   */
  it('Property 5: All accent/background token pairs meet WCAG AA 3:1 contrast for large text and UI boundaries', () => {
    const largeTextUiPairs = [
      // Dark mode: gold-accent on backgrounds
      { foreground: '#D4AF37', background: '#0C0C0C', label: 'dark: gold-accent on gold-bg-primary' },
      { foreground: '#D4AF37', background: '#141414', label: 'dark: gold-accent on gold-bg-secondary' },
      { foreground: '#D4AF37', background: '#1C1C1C', label: 'dark: gold-accent on gold-bg-tertiary' },
      // Light mode: gold-light-accent on backgrounds
      { foreground: '#8B7209', background: '#FAFAF7', label: 'light: gold-light-accent on gold-light-bg-primary' },
      { foreground: '#8B7209', background: '#FFFFFF', label: 'light: gold-light-accent on gold-light-bg-secondary' },
      { foreground: '#8B7209', background: '#F5F5F0', label: 'light: gold-light-accent on gold-light-bg-tertiary' },
    ];

    fc.assert(
      fc.property(
        fc.constantFrom(...largeTextUiPairs),
        (pair) => {
          const ratio = contrastRatio(pair.foreground, pair.background);
          expect(ratio).toBeGreaterThanOrEqual(3.0);
        }
      ),
      { numRuns: 100 }
    );
  });
});
