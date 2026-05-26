import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import TranscriptPanel from './TranscriptPanel';

vi.mock('../lib/exporters.js', () => ({
  exportSrt: vi.fn(),
  exportVtt: vi.fn(),
}));

afterEach(() => {
  cleanup();
});

describe('TranscriptPanel', () => {
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
