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
      // Fallback for browsers that block clipboard on non-HTTPS
      try {
        const input = document.createElement('input');
        input.value = shareUrl;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
        setCopied(true);
        setError(false);
        setTimeout(() => setCopied(false), 3000);
      } catch {
        setError(true);
        setCopied(false);
      }
    }
  };

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={handleCopy}
        disabled={copied}
        className="flex items-center gap-1.5 px-3 min-h-[44px] rounded-lg text-xs font-medium text-gold-light-text-secondary dark:text-gold-text-secondary hover:text-gold-light-accent dark:hover:text-gold-accent bg-gold-light-bg-tertiary dark:bg-gold-accent-muted border border-gold-light-border dark:border-gold-border hover:border-gold-light-accent dark:hover:border-gold-accent transition-all disabled:opacity-60 disabled:cursor-default focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-light-accent dark:focus-visible:ring-gold-accent"
        aria-label={copied ? 'Link copied' : 'Copy share link'}
      >
        {copied ? (
          <>
            <Check className="w-3.5 h-3.5 text-gold-light-accent dark:text-gold-accent" />
            <span className="text-gold-light-accent dark:text-gold-accent">Copied!</span>
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
            className="text-xs bg-gold-light-bg-tertiary dark:bg-gold-bg-tertiary border border-gold-light-border dark:border-gold-border rounded px-2 py-1 text-gold-light-text-secondary dark:text-gold-text-secondary select-all w-64 focus:outline-none focus:border-gold-light-accent dark:focus:border-gold-accent"
            aria-label="Share URL"
          />
        </div>
      )}
    </div>
  );
}
