import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import SharePage from './SharePage';

// Mock the API service
vi.mock('../services/api.js', () => ({
  getResult: vi.fn(),
  getVideoUrl: vi.fn(),
}));

// Mock child components to isolate SharePage logic
vi.mock('../components/VideoPlayer', () => ({
  default: ({ videoUrl }) => <div data-testid="video-player">VideoPlayer: {videoUrl}</div>,
}));

vi.mock('../components/SummaryCard', () => ({
  default: ({ summary, hideExports }) => (
    <div data-testid="summary-card" data-hide-exports={hideExports}>
      SummaryCard: {summary}
    </div>
  ),
}));

vi.mock('../components/TranscriptPanel', () => ({
  default: ({ transcript, hideExports }) => (
    <div data-testid="transcript-panel" data-hide-exports={hideExports}>
      TranscriptPanel: {transcript?.length ?? 0} words
    </div>
  ),
}));

vi.mock('../components/ScenePanel', () => ({
  default: ({ scenes }) => (
    <div data-testid="scene-panel">ScenePanel: {scenes?.length ?? 0} scenes</div>
  ),
}));

import { getResult, getVideoUrl } from '../services/api.js';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderSharePage(jobId = 'test-job-123') {
  return render(
    <MemoryRouter initialEntries={[`/share/${jobId}`]}>
      <Routes>
        <Route path="/share/:jobId" element={<SharePage />} />
      </Routes>
    </MemoryRouter>
  );
}

// Full result data for a public job
const fullResult = {
  jobId: 'test-job-123',
  status: 'completed',
  isPublic: true,
  shareUrl: 'https://video-intelligence-v1.web.app/share/test-job-123',
  transcript: [
    { word: 'hello', startTime: 0, endTime: 0.5, speaker: 1 },
    { word: 'world', startTime: 0.5, endTime: 1.0, speaker: 1 },
  ],
  scenes: [
    { startTime: 0, endTime: 5, labels: ['intro'] },
  ],
  labels: ['intro'],
  summary: 'This is a test summary of the video content.',
  sentiment: 'positive',
  chapters: [{ title: 'Introduction', startTime: 0 }],
  highlights: [{ timestamp: 2, description: 'Key moment' }],
  actionItems: ['Follow up on topic'],
};

const mockVideoUrl = 'https://storage.googleapis.com/test-bucket/video.mp4';

describe('SharePage', () => {
  // --- Requirement 4.1: Renders all non-null sections for public job ---

  describe('renders all non-null sections for public job', () => {
    beforeEach(() => {
      getResult.mockResolvedValue(fullResult);
      getVideoUrl.mockResolvedValue(mockVideoUrl);
    });

    it('renders VideoPlayer with the fetched video URL', async () => {
      renderSharePage();

      await waitFor(() => {
        expect(screen.getByTestId('video-player')).toBeInTheDocument();
      });

      expect(screen.getByTestId('video-player')).toHaveTextContent(mockVideoUrl);
    });

    it('renders SummaryCard with summary data', async () => {
      renderSharePage();

      await waitFor(() => {
        expect(screen.getByTestId('summary-card')).toBeInTheDocument();
      });

      expect(screen.getByTestId('summary-card')).toHaveTextContent('This is a test summary');
    });

    it('renders TranscriptPanel with transcript data', async () => {
      renderSharePage();

      await waitFor(() => {
        expect(screen.getByTestId('transcript-panel')).toBeInTheDocument();
      });

      expect(screen.getByTestId('transcript-panel')).toHaveTextContent('2 words');
    });

    it('renders ScenePanel with scene data', async () => {
      renderSharePage();

      await waitFor(() => {
        expect(screen.getByTestId('scene-panel')).toBeInTheDocument();
      });

      expect(screen.getByTestId('scene-panel')).toHaveTextContent('1 scenes');
    });
  });

  // --- Requirement 4.9: Shows 404 for non-public jobs ---

  describe('shows 404 for non-public jobs', () => {
    it('displays Not Found page when API returns 404', async () => {
      const error404 = new Error('Not Found');
      error404.response = { status: 404 };
      getResult.mockRejectedValue(error404);
      getVideoUrl.mockRejectedValue(error404);

      renderSharePage();

      await waitFor(() => {
        expect(screen.getByText('Not Found')).toBeInTheDocument();
      });

      expect(screen.getByText(/no longer available or does not exist/i)).toBeInTheDocument();
    });

    it('does not render content sections on 404', async () => {
      const error404 = new Error('Not Found');
      error404.response = { status: 404 };
      getResult.mockRejectedValue(error404);
      getVideoUrl.mockRejectedValue(error404);

      renderSharePage();

      await waitFor(() => {
        expect(screen.getByText('Not Found')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('video-player')).not.toBeInTheDocument();
      expect(screen.queryByTestId('summary-card')).not.toBeInTheDocument();
      expect(screen.queryByTestId('transcript-panel')).not.toBeInTheDocument();
      expect(screen.queryByTestId('scene-panel')).not.toBeInTheDocument();
    });
  });

  // --- Requirements 4.4, 4.5, 4.6: Omits QAPanel, export buttons, ShareToggle ---

  describe('omits QAPanel, export buttons, ShareToggle', () => {
    beforeEach(() => {
      getResult.mockResolvedValue(fullResult);
      getVideoUrl.mockResolvedValue(mockVideoUrl);
    });

    it('does not render QAPanel', async () => {
      renderSharePage();

      await waitFor(() => {
        expect(screen.getByTestId('summary-card')).toBeInTheDocument();
      });

      // QAPanel should not be present anywhere in the page
      expect(screen.queryByText(/Ask a question/i)).not.toBeInTheDocument();
      expect(screen.queryByTestId('qa-panel')).not.toBeInTheDocument();
    });

    it('passes hideExports=true to SummaryCard (omits PDF export)', async () => {
      renderSharePage();

      await waitFor(() => {
        expect(screen.getByTestId('summary-card')).toBeInTheDocument();
      });

      expect(screen.getByTestId('summary-card')).toHaveAttribute('data-hide-exports', 'true');
    });

    it('passes hideExports=true to TranscriptPanel (omits SRT/VTT exports)', async () => {
      renderSharePage();

      await waitFor(() => {
        expect(screen.getByTestId('transcript-panel')).toBeInTheDocument();
      });

      expect(screen.getByTestId('transcript-panel')).toHaveAttribute('data-hide-exports', 'true');
    });

    it('does not render ShareToggle', async () => {
      renderSharePage();

      await waitFor(() => {
        expect(screen.getByTestId('video-player')).toBeInTheDocument();
      });

      // ShareToggle renders a switch role element
      expect(screen.queryByRole('switch')).not.toBeInTheDocument();
      expect(screen.queryByText('Private')).not.toBeInTheDocument();
      expect(screen.queryByText('Public')).not.toBeInTheDocument();
    });
  });

  // --- Requirement 4.8: Shows CTA with link to landing page ---

  describe('shows CTA with link to landing page', () => {
    beforeEach(() => {
      getResult.mockResolvedValue(fullResult);
      getVideoUrl.mockResolvedValue(mockVideoUrl);
    });

    it('displays "Sign in to analyse your own videos" CTA text', async () => {
      renderSharePage();

      await waitFor(() => {
        expect(screen.getByText('Sign in to analyse your own videos')).toBeInTheDocument();
      });
    });

    it('CTA links to the landing page ("/")', async () => {
      renderSharePage();

      await waitFor(() => {
        const ctaLink = screen.getByText('Sign in to analyse your own videos');
        expect(ctaLink.closest('a')).toHaveAttribute('href', '/');
      });
    });
  });

  // --- Requirement 4.7: Omits null sections without error ---

  describe('omits null sections without error', () => {
    it('renders without error when transcript is null', async () => {
      getResult.mockResolvedValue({ ...fullResult, transcript: null });
      getVideoUrl.mockResolvedValue(mockVideoUrl);

      renderSharePage();

      await waitFor(() => {
        expect(screen.getByTestId('video-player')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('transcript-panel')).not.toBeInTheDocument();
      // Other sections still render
      expect(screen.getByTestId('summary-card')).toBeInTheDocument();
      expect(screen.getByTestId('scene-panel')).toBeInTheDocument();
    });

    it('renders without error when summary is null', async () => {
      getResult.mockResolvedValue({ ...fullResult, summary: null });
      getVideoUrl.mockResolvedValue(mockVideoUrl);

      renderSharePage();

      await waitFor(() => {
        expect(screen.getByTestId('video-player')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('summary-card')).not.toBeInTheDocument();
      // Other sections still render
      expect(screen.getByTestId('transcript-panel')).toBeInTheDocument();
      expect(screen.getByTestId('scene-panel')).toBeInTheDocument();
    });

    it('renders without error when scenes is null', async () => {
      getResult.mockResolvedValue({ ...fullResult, scenes: null });
      getVideoUrl.mockResolvedValue(mockVideoUrl);

      renderSharePage();

      await waitFor(() => {
        expect(screen.getByTestId('video-player')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('scene-panel')).not.toBeInTheDocument();
      // Other sections still render
      expect(screen.getByTestId('summary-card')).toBeInTheDocument();
      expect(screen.getByTestId('transcript-panel')).toBeInTheDocument();
    });

    it('renders without error when all optional sections are null', async () => {
      getResult.mockResolvedValue({
        ...fullResult,
        transcript: null,
        summary: null,
        scenes: null,
      });
      getVideoUrl.mockResolvedValue(mockVideoUrl);

      renderSharePage();

      await waitFor(() => {
        expect(screen.getByTestId('video-player')).toBeInTheDocument();
      });

      // No content sections rendered
      expect(screen.queryByTestId('summary-card')).not.toBeInTheDocument();
      expect(screen.queryByTestId('transcript-panel')).not.toBeInTheDocument();
      expect(screen.queryByTestId('scene-panel')).not.toBeInTheDocument();

      // CTA still renders
      expect(screen.getByText('Sign in to analyse your own videos')).toBeInTheDocument();
    });
  });
});
