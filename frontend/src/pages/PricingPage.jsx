import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Check, Zap, Loader2 } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { createCheckoutSession } from '../services/api';
import ThemeToggle from '../components/ThemeToggle';

const FREE_FEATURES = [
  '5 videos per month',
  'Max 10 minutes per video',
  'AI transcript with word timestamps',
  'Auto-generated chapters',
  'Highlights and sentiment analysis',
];

const PRO_FEATURES = [
  '50 videos per month',
  'Max 120 minutes per video',
  'Everything in Free',
  'Speaker diarization (who said what)',
  'Export transcript as SRT/VTT',
  'Export summary as PDF',
  'Public share links',
  'Priority processing',
];

export default function PricingPage() {
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleUpgrade = async () => {
    if (!user) {
      await signIn();
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { subscriptionId, keyId } = await createCheckoutSession();

      const options = {
        key: keyId,
        subscription_id: subscriptionId,
        name: 'VidIQ',
        description: 'Pro Plan — ₹9/month',
        prefill: {
          email: user.email,
          name: user.displayName || '',
        },
        theme: { color: '#7c3aed' },
        handler: function () {
          navigate('/billing/success');
        },
        modal: {
          ondismiss: function () {
            setLoading(false);
          },
        },
      };

      const rzp = new window.Razorpay(options);
      rzp.open();
    } catch (err) {
      console.error('Checkout failed:', err);
      setError('Could not start checkout. Please try again.');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gold-light-bg-primary dark:bg-gold-bg-primary text-gold-light-text-primary dark:text-gold-text-primary font-sans px-6 py-16 transition-colors">
      <div className="max-w-4xl mx-auto">
        {/* Page header with brand wordmark and ThemeToggle */}
        <header className="flex items-center justify-between mb-12">
          <Link to="/" className="inline-flex items-center gap-2">
            <Zap className="w-6 h-6 text-gold-light-accent dark:text-gold-accent" fill="currentColor" />
            <span className="font-display text-2xl font-bold tracking-tight">VidIQ</span>
          </Link>
          <ThemeToggle />
        </header>

        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold tracking-tight">Simple, transparent pricing</h1>
          <p className="text-gold-light-text-secondary dark:text-gold-text-secondary mt-3 text-lg">Start free. Upgrade when you need more.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Free tier card */}
          <div className="bg-gold-light-bg-secondary dark:bg-gold-bg-secondary border-t-2 border-t-gold-light-accent dark:border-t-gold-accent border border-gold-light-border dark:border-gold-border rounded-2xl p-8">
            <h2 className="text-xl font-bold mb-1">Free</h2>
            <p className="text-4xl font-bold mt-4 text-gold-light-accent dark:text-gold-accent">₹0<span className="text-lg text-gold-light-text-secondary dark:text-gold-text-secondary font-normal">/month</span></p>
            <ul className="mt-6 space-y-3">
              {FREE_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-3 text-sm text-gold-light-text-secondary dark:text-gold-text-secondary">
                  <Check className="w-4 h-4 text-gold-light-accent dark:text-gold-accent shrink-0 mt-0.5" />
                  {f}
                </li>
              ))}
            </ul>
            <Link
              to="/dashboard"
              className="mt-8 block text-center border border-gold-light-border dark:border-gold-border hover:border-gold-light-accent dark:hover:border-gold-accent text-gold-light-text-primary dark:text-gold-text-primary px-4 py-3 rounded-xl text-sm font-medium transition-colors"
            >
              Get started free
            </Link>
          </div>

          {/* Pro tier card — recommended */}
          <div className="bg-gold-accent-muted dark:bg-gold-accent-muted border-2 border-gold-light-accent dark:border-gold-accent rounded-2xl p-8 relative">
            <div className="absolute top-4 right-4 bg-gold-accent-muted text-gold-light-accent dark:text-gold-accent text-xs font-semibold px-3 py-1 rounded-full border border-gold-light-accent dark:border-gold-accent">
              Most popular
            </div>
            <h2 className="text-xl font-bold mb-1">Pro</h2>
            <p className="text-4xl font-bold mt-4 text-gold-light-accent dark:text-gold-accent">₹9<span className="text-lg text-gold-light-text-secondary dark:text-gold-text-secondary font-normal">/month</span></p>
            <ul className="mt-6 space-y-3">
              {PRO_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-3 text-sm text-gold-light-text-secondary dark:text-gold-text-secondary">
                  <Check className="w-4 h-4 text-gold-light-accent dark:text-gold-accent shrink-0 mt-0.5" />
                  {f}
                </li>
              ))}
            </ul>
            {error && <p className="mt-4 text-red-400 text-sm">{error}</p>}
            <button
              onClick={handleUpgrade}
              disabled={loading}
              className="mt-8 w-full flex items-center justify-center gap-2 bg-gold-light-accent dark:bg-gold-accent hover:bg-gold-light-accent-hover dark:hover:bg-gold-accent-hover active:scale-95 transition-all text-white px-4 py-3 rounded-xl text-sm font-semibold disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              {user ? 'Upgrade to Pro' : 'Sign in to upgrade'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
