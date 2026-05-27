import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import TranscriptPanel from './TranscriptPanel';
import { exportSrt, exportVtt } from '../lib/exporters.js';

vi.mock('../lib/exporters.js', () => ({
  exportSrt: vi.fn(),
  exportVtt: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const originalTranscript = [
  { word: 'namaste', startTime: 0, endTime: 0.5, speaker: 1 },
  { word: 'duniya', startTime: 0.5, endTime: 1.0, speaker: 1 },
];

const translatedTranscript = [
  { word: 'hello', startTime: 0, endTime: 0.5, speaker: 1 },
  { word: 'world', startTime: 0.5, endTime: 1.0, speaker: 1 },
];

describe('TranscriptPanel', () => {
  describe('export buttons', () => {
    const validTranscript = [
      { word: 'hello', startTime: 0, endTime: 0.5, speaker: 1 },
    ];

    it('renders SRT and VTT buttons when transcript has data', () => {
      render(
        <TranscriptPanel
          transcript={validTranscript}
          filenameBase="test"
          currentTime={0}
          seekTo={() => {}}
        />
      );

      expect(screen.getByTitle('Download SRT subtitles')).toBeInTheDocument();
      expect(screen.getByTitle('Download VTT subtitles')).toBeInTheDocument();
    });

    it('hides export buttons when transcript is empty array', () => {
      render(
        <TranscriptPanel
          transcript={[]}
          filenameBase="test"
          currentTime={0}
          seekTo={() => {}}
        />
      );

      expect(screen.queryByTitle('Download SRT subtitles')).not.toBeInTheDocument();
      expect(screen.queryByTitle('Download VTT subtitles')).not.toBeInTheDocument();
    });

    it('hides export buttons when transcript is null', () => {
      render(
        <TranscriptPanel
          transcript={null}
          filenameBase="test"
          currentTime={0}
          seekTo={() => {}}
        />
      );

      expect(screen.queryByTitle('Download SRT subtitles')).not.toBeInTheDocument();
      expect(screen.queryByTitle('Download VTT subtitles')).not.toBeInTheDocument();
    });

    it('buttons have correct accessible title attributes', () => {
      render(
        <TranscriptPanel
          transcript={validTranscript}
          filenameBase="test"
          currentTime={0}
          seekTo={() => {}}
        />
      );

      const srtButton = screen.getByTitle('Download SRT subtitles');
      const vttButton = screen.getByTitle('Download VTT subtitles');

      expect(srtButton).toBeInTheDocument();
      expect(vttButton).toBeInTheDocument();
      expect(srtButton.tagName).toBe('BUTTON');
      expect(vttButton.tagName).toBe('BUTTON');
    });
  });

  describe('language toggle visibility (Req 5.1, 5.4)', () => {
    it('shows toggle when translatedTranscript is present', () => {
      render(
        <TranscriptPanel
          transcript={originalTranscript}
          translatedTranscript={translatedTranscript}
          currentTime={0}
          seekTo={() => {}}
          filenameBase="test"
        />
      );

      expect(screen.getByText('Original')).toBeInTheDocument();
      expect(screen.getByText('English')).toBeInTheDocument();
    });

    it('hides toggle when translatedTranscript is null', () => {
      render(
        <TranscriptPanel
          transcript={originalTranscript}
          translatedTranscript={null}
          currentTime={0}
          seekTo={() => {}}
          filenameBase="test"
        />
      );

      expect(screen.queryByText('English')).not.toBeInTheDocument();
    });

    it('hides toggle when translatedTranscript is undefined', () => {
      render(
        <TranscriptPanel
          transcript={originalTranscript}
          currentTime={0}
          seekTo={() => {}}
          filenameBase="test"
        />
      );

      expect(screen.queryByText('English')).not.toBeInTheDocument();
    });

    it('hides toggle when translatedTranscript is empty array', () => {
      render(
        <TranscriptPanel
          transcript={originalTranscript}
          translatedTranscript={[]}
          currentTime={0}
          seekTo={() => {}}
          filenameBase="test"
        />
      );

      expect(screen.queryByText('English')).not.toBeInTheDocument();
    });
  });

  describe('default view (Req 5.5)', () => {
    it('defaults to "Original" view showing original transcript words', () => {
      render(
        <TranscriptPanel
          transcript={originalTranscript}
          translatedTranscript={translatedTranscript}
          currentTime={0}
          seekTo={() => {}}
          filenameBase="test"
        />
      );

      // Original transcript words should be visible
      expect(screen.getByText('namaste')).toBeInTheDocument();
      expect(screen.getByText('duniya')).toBeInTheDocument();

      // Translated words should NOT be visible
      expect(screen.queryByText('hello')).not.toBeInTheDocument();
      expect(screen.queryByText('world')).not.toBeInTheDocument();
    });
  });

  describe('search cleared on toggle switch (Req 5.6)', () => {
    it('clears search input when switching from Original to English', () => {
      render(
        <TranscriptPanel
          transcript={originalTranscript}
          translatedTranscript={translatedTranscript}
          currentTime={0}
          seekTo={() => {}}
          filenameBase="test"
        />
      );

      const searchInput = screen.getByPlaceholderText('Search transcript...');

      // Type a search query
      fireEvent.change(searchInput, { target: { value: 'namaste' } });
      expect(searchInput).toHaveValue('namaste');

      // Click "English" toggle
      fireEvent.click(screen.getByText('English'));

      // Search should be cleared
      expect(searchInput).toHaveValue('');
    });

    it('clears search input when switching from English to Original', () => {
      render(
        <TranscriptPanel
          transcript={originalTranscript}
          translatedTranscript={translatedTranscript}
          currentTime={0}
          seekTo={() => {}}
          filenameBase="test"
        />
      );

      const searchInput = screen.getByPlaceholderText('Search transcript...');

      // Switch to English first
      fireEvent.click(screen.getByText('English'));

      // Type a search query
      fireEvent.change(searchInput, { target: { value: 'hello' } });
      expect(searchInput).toHaveValue('hello');

      // Switch back to Original
      fireEvent.click(screen.getByText('Original'));

      // Search should be cleared
      expect(searchInput).toHaveValue('');
    });
  });

  describe('export uses active transcript (Req 5.7)', () => {
    it('exports original transcript when Original view is active', () => {
      render(
        <TranscriptPanel
          transcript={originalTranscript}
          translatedTranscript={translatedTranscript}
          currentTime={0}
          seekTo={() => {}}
          filenameBase="test-file"
        />
      );

      // Click SRT export (default is Original view)
      fireEvent.click(screen.getByTitle('Download SRT subtitles'));
      expect(exportSrt).toHaveBeenCalledWith(originalTranscript, 'test-file');

      // Click VTT export
      fireEvent.click(screen.getByTitle('Download VTT subtitles'));
      expect(exportVtt).toHaveBeenCalledWith(originalTranscript, 'test-file');
    });

    it('exports translated transcript when English view is active', () => {
      render(
        <TranscriptPanel
          transcript={originalTranscript}
          translatedTranscript={translatedTranscript}
          currentTime={0}
          seekTo={() => {}}
          filenameBase="test-file"
        />
      );

      // Switch to English view
      fireEvent.click(screen.getByText('English'));

      // Click SRT export
      fireEvent.click(screen.getByTitle('Download SRT subtitles'));
      expect(exportSrt).toHaveBeenCalledWith(translatedTranscript, 'test-file');

      // Click VTT export
      fireEvent.click(screen.getByTitle('Download VTT subtitles'));
      expect(exportVtt).toHaveBeenCalledWith(translatedTranscript, 'test-file');
    });
  });
});
