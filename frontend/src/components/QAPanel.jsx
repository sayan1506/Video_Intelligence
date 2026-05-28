import { useState } from 'react';
import { askQuestion } from '../services/api';

export default function QAPanel({ jobId, onSeek }) {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState(null);
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isOpen, setIsOpen] = useState(false);

  const handleSubmit = async () => {
    if (!question.trim() || loading) return;
    setLoading(true);
    setError(null);
    setAnswer(null);
    setSources([]);
    try {
      const data = await askQuestion(jobId, question.trim());
      setAnswer(data.answer);
      setSources(data.sources || []);
    } catch (err) {
      if (err.response?.status === 402) {
        setError('upgrade');
      } else if (err.response?.status === 409) {
        setError('Video is still processing — please wait for it to complete.');
      } else {
        setError('Something went wrong. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (seconds) => {
    const s = Math.floor(seconds);
    const m = Math.floor(s / 60);
    return `${m}:${String(s % 60).padStart(2, '0')}`;
  };

  return (
    <div className="rounded-lg border-t-2 border-t-gold-light-accent dark:border-t-gold-accent border border-gold-light-border dark:border-gold-border bg-gold-light-bg-secondary dark:bg-gold-bg-secondary mt-4">
      {/* Header — always visible */}
      <button
        onClick={() => setIsOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-4 text-left"
        aria-expanded={isOpen}
      >
        <span className="font-semibold text-gold-light-text-primary dark:text-gold-text-primary flex items-center gap-2">
          <span>💬</span> Ask about this video
          <span className="text-xs font-normal text-gold-light-accent dark:text-gold-accent border border-gold-light-accent/40 dark:border-gold-accent/40 rounded px-1.5 py-0.5">
            Pro
          </span>
        </span>
        <span className="text-gold-light-text-muted dark:text-gold-text-muted text-sm">{isOpen ? '▲' : '▼'}</span>
      </button>

      {/* Collapsible body */}
      {isOpen && (
        <div className="px-5 pb-5 space-y-4">
          {/* Input row */}
          <div className="flex gap-2">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
              placeholder="e.g. What did the speaker say about pricing?"
              className="flex-1 rounded-lg bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border dark:border-gold-border px-3 py-2 text-sm text-gold-light-text-primary dark:text-gold-text-primary placeholder-gold-light-text-muted dark:placeholder-gold-text-muted focus:outline-none focus:border-gold-light-accent dark:focus:border-gold-accent transition-colors"
              disabled={loading}
              aria-label="Ask a question about this video"
            />
            <button
              onClick={handleSubmit}
              disabled={loading || !question.trim()}
              className="px-4 py-2 rounded-lg bg-gold-light-accent dark:bg-gold-accent hover:bg-gold-light-accent-hover dark:hover:bg-gold-accent-hover disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
            >
              {loading ? '…' : 'Ask'}
            </button>
          </div>

          {/* Error states */}
          {error && error !== 'upgrade' && (
            <p className="text-sm text-red-400">{error}</p>
          )}

          {error === 'upgrade' && (
            <div className="text-sm text-gold-light-accent dark:text-gold-accent bg-gold-accent-muted border border-gold-light-border dark:border-gold-border rounded-lg px-3 py-2">
              Q&A is a Pro feature.{' '}
              <a
                href="/billing"
                className="underline text-gold-light-accent dark:text-gold-accent hover:text-gold-light-accent-hover dark:hover:text-gold-accent-hover"
              >
                Upgrade your plan
              </a>{' '}
              to use it.
            </div>
          )}

          {/* Answer */}
          {answer && (
            <div className="space-y-3">
              <div className="text-sm text-gold-light-text-secondary dark:text-gold-text-secondary leading-relaxed whitespace-pre-wrap">
                {answer}
              </div>

              {/* Sources */}
              {sources.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-xs text-gold-light-text-muted dark:text-gold-text-muted font-medium uppercase tracking-wide">
                    Sources
                  </p>
                  {sources.map((src, i) => (
                    <button
                      key={i}
                      onClick={() => onSeek?.(src.startTime)}
                      className="w-full text-left rounded-lg bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border dark:border-gold-border px-3 py-2 text-xs text-gold-light-text-secondary dark:text-gold-text-secondary hover:border-gold-light-accent/50 dark:hover:border-gold-accent/50 hover:text-gold-light-text-primary dark:hover:text-gold-text-primary transition-colors"
                    >
                      <span className="text-gold-light-accent dark:text-gold-accent font-mono mr-2">
                        {formatTime(src.startTime)} – {formatTime(src.endTime)}
                      </span>
                      {src.snippet}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
