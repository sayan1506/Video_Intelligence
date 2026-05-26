import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import SummaryCard from './SummaryCard';

vi.mock('../lib/exporters.js', () => ({
  exportPdf: vi.fn(),
}));

afterEach(() => {
  cleanup();
});

describe('SummaryCard', () => {
  it('renders PDF button when summary is present', () => {
    render(
      <SummaryCard
        summary="Test summary"
        filenameBase="test"
        seekTo={() => {}}
      />
    );

    expect(screen.getByTitle('Export PDF summary')).toBeInTheDocument();
  });

  it('hides PDF button when summary is null', () => {
    render(
      <SummaryCard
        summary={null}
        filenameBase="test"
        seekTo={() => {}}
      />
    );

    expect(screen.queryByTitle('Export PDF summary')).not.toBeInTheDocument();
  });

  it('hides PDF button when summary is undefined', () => {
    render(
      <SummaryCard
        filenameBase="test"
        seekTo={() => {}}
      />
    );

    expect(screen.queryByTitle('Export PDF summary')).not.toBeInTheDocument();
  });

  it('hides PDF button when summary is empty string', () => {
    render(
      <SummaryCard
        summary=""
        filenameBase="test"
        seekTo={() => {}}
      />
    );

    expect(screen.queryByTitle('Export PDF summary')).not.toBeInTheDocument();
  });

  it('PDF button has correct accessible title attribute', () => {
    render(
      <SummaryCard
        summary="Test summary content"
        filenameBase="test"
        seekTo={() => {}}
      />
    );

    const pdfButton = screen.getByTitle('Export PDF summary');
    expect(pdfButton).toBeInTheDocument();
    expect(pdfButton.tagName).toBe('BUTTON');
  });
});
