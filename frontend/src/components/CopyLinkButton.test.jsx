import { render, screen, cleanup, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import CopyLinkButton from './CopyLinkButton';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('CopyLinkButton', () => {
  const shareUrl = 'https://video-intelligence-v1.web.app/share/abc-123';

  describe('visibility based on isPublic prop', () => {
    it('renders the Copy Link button when isPublic is true', () => {
      render(<CopyLinkButton shareUrl={shareUrl} isPublic={true} />);
      expect(screen.getByRole('button', { name: /copy share link/i })).toBeInTheDocument();
    });

    it('renders nothing when isPublic is false', () => {
      const { container } = render(<CopyLinkButton shareUrl={shareUrl} isPublic={false} />);
      expect(container).toBeEmptyDOMElement();
    });
  });

  describe('copies correct URL to clipboard', () => {
    it('copies shareUrl to clipboard on click', async () => {
      const writeText = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, { clipboard: { writeText } });

      render(<CopyLinkButton shareUrl={shareUrl} isPublic={true} />);
      const button = screen.getByRole('button', { name: /copy share link/i });

      await act(async () => {
        fireEvent.click(button);
      });

      expect(writeText).toHaveBeenCalledWith(shareUrl);
    });
  });

  describe('shows confirmation for 3 seconds', () => {
    it('shows "Copied!" text after successful copy', async () => {
      const writeText = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, { clipboard: { writeText } });

      render(<CopyLinkButton shareUrl={shareUrl} isPublic={true} />);
      const button = screen.getByRole('button', { name: /copy share link/i });

      await act(async () => {
        fireEvent.click(button);
      });

      expect(screen.getByText('Copied!')).toBeInTheDocument();
    });

    it('reverts back to "Copy Link" after 3 seconds', async () => {
      const writeText = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, { clipboard: { writeText } });

      render(<CopyLinkButton shareUrl={shareUrl} isPublic={true} />);
      const button = screen.getByRole('button', { name: /copy share link/i });

      await act(async () => {
        fireEvent.click(button);
      });

      expect(screen.getByText('Copied!')).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(3000);
      });

      expect(screen.queryByText('Copied!')).not.toBeInTheDocument();
      expect(screen.getByText('Copy Link')).toBeInTheDocument();
    });

    it('does not revert before 3 seconds', async () => {
      const writeText = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, { clipboard: { writeText } });

      render(<CopyLinkButton shareUrl={shareUrl} isPublic={true} />);

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /copy share link/i }));
      });

      act(() => {
        vi.advanceTimersByTime(2999);
      });

      expect(screen.getByText('Copied!')).toBeInTheDocument();
    });
  });

  describe('handles clipboard failure gracefully', () => {
    it('shows error message and selectable URL on clipboard failure', async () => {
      const writeText = vi.fn().mockRejectedValue(new Error('Clipboard write failed'));
      Object.assign(navigator, { clipboard: { writeText } });

      render(<CopyLinkButton shareUrl={shareUrl} isPublic={true} />);

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /copy share link/i }));
      });

      expect(screen.getByText(/copy failed/i)).toBeInTheDocument();
      const urlInput = screen.getByLabelText('Share URL');
      expect(urlInput).toBeInTheDocument();
      expect(urlInput).toHaveValue(shareUrl);
      expect(urlInput).toHaveAttribute('readOnly');
    });

    it('does not show "Copied!" on clipboard failure', async () => {
      const writeText = vi.fn().mockRejectedValue(new Error('Clipboard write failed'));
      Object.assign(navigator, { clipboard: { writeText } });

      render(<CopyLinkButton shareUrl={shareUrl} isPublic={true} />);

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /copy share link/i }));
      });

      expect(screen.queryByText('Copied!')).not.toBeInTheDocument();
    });
  });
});
