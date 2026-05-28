import { useState } from 'react';
import { ChevronDown, ChevronRight, DollarSign, Cpu, Clock } from 'lucide-react';

const fmt = (val, decimals = 4) => {
  if (val == null || val === undefined) return '—';
  return `$${Number(val).toFixed(decimals)}`;
};

const fmtNum = (val) => {
  if (val == null || val === undefined) return '—';
  return Number(val).toLocaleString();
};

const fmtMin = (val) => {
  if (val == null || val === undefined) return '—';
  return `${Number(val).toFixed(2)} min`;
};

export default function ProcessingStats({ result }) {
  const [open, setOpen] = useState(false);

  // Only show if at least one cost field exists and is non-zero
  const hasCostData = [
    result?.sttEstimatedCostUsd,
    result?.viEstimatedCostUsd,
    result?.geminiEstimatedCostUsd,
    result?.totalEstimatedCostUsd,
  ].some((v) => v != null && v > 0);

  if (!hasCostData) return null;

  return (
    <div className="bg-gold-light-bg-secondary dark:bg-gold-bg-secondary border border-gold-light-border dark:border-gold-border rounded-2xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 text-sm font-medium text-gold-light-text-secondary dark:text-gold-text-secondary hover:text-gold-light-text-primary dark:hover:text-gold-text-primary hover:bg-gold-light-bg-tertiary dark:hover:bg-gold-bg-tertiary transition-colors"
      >
        <span className="flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-gold-light-accent dark:text-gold-accent" />
          Processing Stats & Cost
        </span>
        {open ? (
          <ChevronDown className="w-4 h-4 text-gold-light-text-muted dark:text-gold-text-muted" />
        ) : (
          <ChevronRight className="w-4 h-4 text-gold-light-text-muted dark:text-gold-text-muted" />
        )}
      </button>

      {open && (
        <div className="px-5 pb-5 pt-1 border-t border-gold-light-border dark:border-gold-border grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* Cost Breakdown */}
          <div className="bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border-subtle dark:border-gold-border-subtle rounded-xl p-4">
            <h4 className="text-xs font-semibold text-gold-light-text-muted dark:text-gold-text-muted uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <DollarSign className="w-3.5 h-3.5" /> AI Cost Breakdown
            </h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gold-light-text-secondary dark:text-gold-text-secondary">Speech-to-Text</span>
                <span className="text-gold-light-text-primary dark:text-gold-text-primary font-mono">{fmt(result?.sttEstimatedCostUsd)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gold-light-text-secondary dark:text-gold-text-secondary">Video Intelligence</span>
                <span className="text-gold-light-text-primary dark:text-gold-text-primary font-mono">{fmt(result?.viEstimatedCostUsd)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gold-light-text-secondary dark:text-gold-text-secondary">Gemini AI</span>
                <span className="text-gold-light-text-primary dark:text-gold-text-primary font-mono">{fmt(result?.geminiEstimatedCostUsd)}</span>
              </div>
              <div className="flex justify-between pt-2 border-t border-gold-light-border dark:border-gold-border">
                <span className="text-gold-light-text-primary dark:text-gold-text-primary font-semibold">Total</span>
                <span className="text-gold-light-accent dark:text-gold-accent font-mono font-bold">{fmt(result?.totalEstimatedCostUsd)}</span>
              </div>
            </div>
          </div>

          {/* Token Usage */}
          <div className="bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border-subtle dark:border-gold-border-subtle rounded-xl p-4">
            <h4 className="text-xs font-semibold text-gold-light-text-muted dark:text-gold-text-muted uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5" /> Gemini Token Usage
            </h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gold-light-text-secondary dark:text-gold-text-secondary">Input tokens</span>
                <span className="text-gold-light-text-primary dark:text-gold-text-primary font-mono">{fmtNum(result?.geminiInputTokens)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gold-light-text-secondary dark:text-gold-text-secondary">Output tokens</span>
                <span className="text-gold-light-text-primary dark:text-gold-text-primary font-mono">{fmtNum(result?.geminiOutputTokens)}</span>
              </div>
              <div className="flex justify-between pt-2 border-t border-gold-light-border dark:border-gold-border">
                <span className="text-gold-light-text-primary dark:text-gold-text-primary font-semibold">Total tokens</span>
                <span className="text-gold-light-accent dark:text-gold-accent font-mono font-bold">
                  {result?.geminiInputTokens != null && result?.geminiOutputTokens != null
                    ? fmtNum(result.geminiInputTokens + result.geminiOutputTokens)
                    : '—'}
                </span>
              </div>
            </div>
          </div>

          {/* Duration */}
          <div className="bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border-subtle dark:border-gold-border-subtle rounded-xl p-4">
            <h4 className="text-xs font-semibold text-gold-light-text-muted dark:text-gold-text-muted uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" /> Audio / Video Duration
            </h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gold-light-text-secondary dark:text-gold-text-secondary">STT audio</span>
                <span className="text-gold-light-text-primary dark:text-gold-text-primary font-mono">{fmtMin(result?.sttAudioMinutes)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gold-light-text-secondary dark:text-gold-text-secondary">VI video</span>
                <span className="text-gold-light-text-primary dark:text-gold-text-primary font-mono">{fmtMin(result?.viVideoMinutes)}</span>
              </div>
              {result?.processingTime && (
                <div className="flex justify-between pt-2 border-t border-gold-light-border dark:border-gold-border">
                  <span className="text-gold-light-text-primary dark:text-gold-text-primary font-semibold">Processing time</span>
                  <span className="text-gold-light-accent dark:text-gold-accent font-mono font-bold">{result.processingTime}s</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
