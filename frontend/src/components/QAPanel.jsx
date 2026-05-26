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
    <div className="rounded-2xl border border-white/10 bg-white/5 mt-4">
      {/* Header — always visible */}
      <button
        onClick={() => setIsOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-4 text-left"
        aria-expanded={isOpen}
      >
        <span className="font-semibold text-slate-200 flex items-center gap-2">
          <span>💬</span> Ask about this video
          <span className="text-xs font-normal text-violet-400 border border-violet-400/40 rounded px-1.5 py-0.5">
            Pro
          </span>
        </span>
        <span className="text-slate-500 text-sm">{isOpen ? '▲' : '▼'}</span>
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
              className="flex-1 rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-violet-500 transition-colors"
              disabled={loading}
              aria-label="Ask a question about this video"
            />
            <button
              onClick={handleSubmit}
              disabled={loading || !question.trim()}
              className="px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
            >
              {loading ? '…' : 'Ask'}
            </button>
          </div>

          {/* Error states */}
          {error && error !== 'upgrade' && (
            <p className="text-sm text-red-400">{error}</p>
          )}

          {error === 'upgrade' && (
            <div className="text-sm text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
              Q&A is a Pro feature.{' '}
              <a
                href="/billing"
                className="underline text-violet-400 hover:text-violet-300"
              >
                Upgrade your plan
              </a>{' '}
              to use it.
            </div>
          )}

          {/* Answer */}
          {answer && (
            <div className="space-y-3">
              <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                {answer}
              </div>

              {/* Sources */}
              {sources.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-xs text-slate-500 font-medium uppercase tracking-wide">
                    Sources
                  </p>
                  {sources.map((src, i) => (
                    <button
                      key={i}
                      onClick={() => onSeek?.(src.startTime)}
                      className="w-full text-left rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-xs text-slate-400 hover:border-violet-500/50 hover:text-slate-300 transition-colors"
                    >
                      <span className="text-violet-400 font-mono mr-2">
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
