import { render, screen, cleanup, act } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import ShareToggle from './ShareToggle';

vi.mock('../services/api.js', () => ({
  toggleJobShare: vi.fn(),
}));

import { toggleJobShare } from '../services/api.js';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('ShareToggle', () => {
  const defaultProps = {
    jobId: 'test-job-123',
    isPublic: false,
    onToggle: vi.fn(),
  };

  // --- Requirement 2.1: Renders correct state based on isPublic prop ---

  describe('renders correct state based on isPublic prop', () => {
    it('shows "Private" label and Lock icon when isPublic is false', () => {
      render(<ShareToggle {...defaultProps} isPublic={false} />);

      expect(screen.getByText('Private')).toBeInTheDocument();
      expect(screen.queryByText('Public')).not.toBeInTheDocument();

      const toggle = screen.getByRole('switch');
      expect(toggle).toHaveAttribute('aria-checked', 'false');
      expect(toggle).toHaveAttribute('aria-label', 'Private');
    });

    it('shows "Public" label and Globe icon when isPublic is true', () => {
      render(<ShareToggle {...defaultProps} isPublic={true} />);

      expect(screen.getByText('Public')).toBeInTheDocument();
      expect(screen.queryByText('Private')).not.toBeInTheDocument();

      const toggle = screen.getByRole('switch');
      expect(toggle).toHaveAttribute('aria-checked', 'true');
      expect(toggle).toHaveAttribute('aria-label', 'Public');
    });
  });

  // --- Requirements 2.2, 2.3, 2.5: Disables during API call ---

  describe('disables during API call', () => {
    it('disables toggle while API request is in-flight', async () => {
      let resolveApi;
      toggleJobShare.mockImplementation(
        () => new Promise((resolve) => { resolveApi = resolve; })
      );

      render(<ShareToggle {...defaultProps} isPublic={false} />);
      const toggle = screen.getByRole('switch');

      expect(toggle).not.toBeDisabled();

      // Click to trigger API call
      await act(async () => {
        toggle.click();
      });

      // Toggle should be disabled while request is in-flight
      expect(toggle).toBeDisabled();

      // Resolve the API call
      await act(async () => {
        resolveApi({ jobId: 'test-job-123', isPublic: true, shareUrl: 'http://example.com/share/test-job-123' });
      });

      // Toggle should be re-enabled after API completes
      expect(toggle).not.toBeDisabled();
    });

    it('calls onToggle with new value on successful API call', async () => {
      toggleJobShare.mockResolvedValue({
        jobId: 'test-job-123',
        isPublic: true,
        shareUrl: 'http://example.com/share/test-job-123',
      });

      const onToggle = vi.fn();
      render(<ShareToggle {...defaultProps} isPublic={false} onToggle={onToggle} />);

      const toggle = screen.getByRole('switch');
      await act(async () => {
        toggle.click();
      });

      expect(toggleJobShare).toHaveBeenCalledWith('test-job-123', true);
      expect(onToggle).toHaveBeenCalledWith(true);
    });

    it('calls toggleJobShare with false when toggling from public to private', async () => {
      toggleJobShare.mockResolvedValue({
        jobId: 'test-job-123',
        isPublic: false,
        shareUrl: null,
      });

      const onToggle = vi.fn();
      render(<ShareToggle {...defaultProps} isPublic={true} onToggle={onToggle} />);

      const toggle = screen.getByRole('switch');
      await act(async () => {
        toggle.click();
      });

      expect(toggleJobShare).toHaveBeenCalledWith('test-job-123', false);
      expect(onToggle).toHaveBeenCalledWith(false);
    });
  });

  // --- Requirement 2.4: Reverts on API failure ---

  describe('reverts on API failure', () => {
    it('does not call onToggle when API fails', async () => {
      toggleJobShare.mockRejectedValue(new Error('Network error'));

      const onToggle = vi.fn();
      render(<ShareToggle {...defaultProps} isPublic={false} onToggle={onToggle} />);

      const toggle = screen.getByRole('switch');
      await act(async () => {
        toggle.click();
      });

      // onToggle should NOT be called — state reverts
      expect(onToggle).not.toHaveBeenCalled();
    });

    it('shows error toast on API failure', async () => {
      toggleJobShare.mockRejectedValue(new Error('Network error'));

      render(<ShareToggle {...defaultProps} isPublic={false} />);

      const toggle = screen.getByRole('switch');
      await act(async () => {
        toggle.click();
      });

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Failed to update share setting. Please try again.')).toBeInTheDocument();
    });

    it('re-enables toggle after API failure', async () => {
      toggleJobShare.mockRejectedValue(new Error('Network error'));

      render(<ShareToggle {...defaultProps} isPublic={false} />);

      const toggle = screen.getByRole('switch');
      await act(async () => {
        toggle.click();
      });

      // Toggle should be re-enabled after failure
      expect(toggle).not.toBeDisabled();
    });

    it('auto-dismisses error toast after 5 seconds', async () => {
      vi.useFakeTimers();
      toggleJobShare.mockRejectedValue(new Error('Network error'));

      render(<ShareToggle {...defaultProps} isPublic={false} />);

      const toggle = screen.getByRole('switch');
      await act(async () => {
        toggle.click();
      });

      expect(screen.getByRole('alert')).toBeInTheDocument();

      // Advance time by 5 seconds
      await act(async () => {
        vi.advanceTimersByTime(5000);
      });

      expect(screen.queryByRole('alert')).not.toBeInTheDocument();

      vi.useRealTimers();
    });
  });
});
