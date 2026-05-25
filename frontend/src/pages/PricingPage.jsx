import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Check, Zap, Loader2 } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { createCheckoutSession } from '../services/api';

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
    <div className="min-h-screen bg-dark-base text-slate-100 font-sans px-6 py-16">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-12">
          <Link to="/" className="inline-flex items-center gap-2 text-xl font-bold tracking-tight mb-8">
            <Zap className="w-6 h-6 text-violet-500" fill="currentColor" />
            <span>VidIQ</span>
          </Link>
          <h1 className="text-4xl font-bold tracking-tight mt-4">Simple, transparent pricing</h1>
          <p className="text-slate-400 mt-3 text-lg">Start free. Upgrade when you need more.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Free */}
          <div className="bg-dark-surface border border-dark-border rounded-2xl p-8">
            <h2 className="text-xl font-bold mb-1">Free</h2>
            <p className="text-4xl font-bold mt-4">₹0<span className="text-lg text-slate-400 font-normal">/month</span></p>
            <ul className="mt-6 space-y-3">
              {FREE_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-3 text-sm text-slate-300">
                  <Check className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  {f}
                </li>
              ))}
            </ul>
            <Link
              to="/dashboard"
              className="mt-8 block text-center border border-dark-border hover:border-violet-500/40 text-slate-300 px-4 py-3 rounded-xl text-sm font-medium transition-colors"
            >
              Get started free
            </Link>
          </div>

          {/* Pro */}
          <div className="bg-dark-surface border border-violet-500/40 rounded-2xl p-8 relative">
            <div className="absolute top-4 right-4 bg-violet-500/20 text-violet-400 text-xs font-semibold px-3 py-1 rounded-full border border-violet-500/30">
              Most popular
            </div>
            <h2 className="text-xl font-bold mb-1">Pro</h2>
            <p className="text-4xl font-bold mt-4">₹9<span className="text-lg text-slate-400 font-normal">/month</span></p>
            <ul className="mt-6 space-y-3">
              {PRO_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-3 text-sm text-slate-300">
                  <Check className="w-4 h-4 text-violet-400 shrink-0 mt-0.5" />
                  {f}
                </li>
              ))}
            </ul>
            {error && <p className="mt-4 text-red-400 text-sm">{error}</p>}
            <button
              onClick={handleUpgrade}
              disabled={loading}
              className="mt-8 w-full flex items-center justify-center gap-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:brightness-110 active:scale-95 transition-all text-white px-4 py-3 rounded-xl text-sm font-semibold disabled:opacity-60 disabled:cursor-not-allowed"
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
