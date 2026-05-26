import { useState } from 'react';
import { Copy, Check, AlertCircle } from 'lucide-react';

export default function CopyLinkButton({ shareUrl, isPublic }) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(false);

  if (!isPublic) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setError(false);
      setTimeout(() => setCopied(false), 3000);
    } catch {
      setError(true);
      setCopied(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={handleCopy}
        disabled={copied}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:text-white bg-white/5 hover:bg-white/10 border border-dark-border hover:border-slate-500 transition-all disabled:opacity-60 disabled:cursor-default"
        aria-label="Copy Link"
      >
        {copied ? (
          <>
            <Check className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-emerald-400">Copied!</span>
          </>
        ) : (
          <>
            <Copy className="w-3.5 h-3.5" />
            <span>Copy Link</span>
          </>
        )}
      </button>

      {error && (
        <div className="flex items-center gap-2">
          <AlertCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />
          <span className="text-xs text-red-400">Copy failed —</span>
          <input
            type="text"
            readOnly
            value={shareUrl}
            onClick={(e) => e.target.select()}
            className="text-xs bg-white/5 border border-white/10 rounded px-2 py-1 text-slate-300 select-all w-64 focus:outline-none focus:border-violet-500"
            aria-label="Share URL"
          />
        </div>
      )}
    </div>
  );
}
