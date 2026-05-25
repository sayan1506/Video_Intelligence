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
    <div className="bg-dark-surface border border-dark-border rounded-2xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 text-sm font-medium text-slate-300 hover:text-white hover:bg-white/5 transition-colors"
      >
        <span className="flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-violet-400" />
          Processing Stats & Cost
        </span>
        {open ? (
          <ChevronDown className="w-4 h-4 text-slate-500" />
        ) : (
          <ChevronRight className="w-4 h-4 text-slate-500" />
        )}
      </button>

      {open && (
        <div className="px-5 pb-5 pt-1 border-t border-dark-border grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* Cost Breakdown */}
          <div className="bg-black/20 border border-white/5 rounded-xl p-4">
            <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <DollarSign className="w-3.5 h-3.5" /> AI Cost Breakdown
            </h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-400">Speech-to-Text</span>
                <span className="text-slate-200 font-mono">{fmt(result?.sttEstimatedCostUsd)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Video Intelligence</span>
                <span className="text-slate-200 font-mono">{fmt(result?.viEstimatedCostUsd)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Gemini AI</span>
                <span className="text-slate-200 font-mono">{fmt(result?.geminiEstimatedCostUsd)}</span>
              </div>
              <div className="flex justify-between pt-2 border-t border-white/10">
                <span className="text-slate-200 font-semibold">Total</span>
                <span className="text-violet-400 font-mono font-bold">{fmt(result?.totalEstimatedCostUsd)}</span>
              </div>
            </div>
          </div>

          {/* Token Usage */}
          <div className="bg-black/20 border border-white/5 rounded-xl p-4">
            <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5" /> Gemini Token Usage
            </h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-400">Input tokens</span>
                <span className="text-slate-200 font-mono">{fmtNum(result?.geminiInputTokens)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Output tokens</span>
                <span className="text-slate-200 font-mono">{fmtNum(result?.geminiOutputTokens)}</span>
              </div>
              <div className="flex justify-between pt-2 border-t border-white/10">
                <span className="text-slate-200 font-semibold">Total tokens</span>
                <span className="text-slate-200 font-mono font-bold">
                  {result?.geminiInputTokens != null && result?.geminiOutputTokens != null
                    ? fmtNum(result.geminiInputTokens + result.geminiOutputTokens)
                    : '—'}
                </span>
              </div>
            </div>
          </div>

          {/* Duration */}
          <div className="bg-black/20 border border-white/5 rounded-xl p-4">
            <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" /> Audio / Video Duration
            </h4>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-400">STT audio</span>
                <span className="text-slate-200 font-mono">{fmtMin(result?.sttAudioMinutes)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">VI video</span>
                <span className="text-slate-200 font-mono">{fmtMin(result?.viVideoMinutes)}</span>
              </div>
              {result?.processingTime && (
                <div className="flex justify-between pt-2 border-t border-white/10">
                  <span className="text-slate-200 font-semibold">Processing time</span>
                  <span className="text-slate-200 font-mono font-bold">{result.processingTime}s</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
