import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle, Loader2 } from 'lucide-react';
import { getBillingStatus } from '../services/api';

const POLL_INTERVAL_MS = 2000;
const MAX_POLLS = 20;

export default function BillingSuccessPage() {
  const navigate = useNavigate();
  const [confirmed, setConfirmed] = useState(false);
  const [pollCount, setPollCount] = useState(0);

  useEffect(() => {
    if (confirmed || pollCount >= MAX_POLLS) return;

    const timer = setTimeout(async () => {
      try {
        const { plan } = await getBillingStatus();
        if (plan === 'pro') {
          setConfirmed(true);
          setTimeout(() => navigate('/dashboard'), 2500);
        } else {
          setPollCount((n) => n + 1);
        }
      } catch {
        setPollCount((n) => n + 1);
      }
    }, POLL_INTERVAL_MS);

    return () => clearTimeout(timer);
  }, [confirmed, pollCount, navigate]);

  return (
    <div className="min-h-screen bg-dark-base text-slate-100 font-sans flex items-center justify-center px-6">
      <div className="text-center max-w-sm">
        {confirmed ? (
          <>
            <CheckCircle className="w-16 h-16 text-emerald-400 mx-auto mb-6" />
            <h1 className="text-2xl font-bold mb-2">You're on Pro!</h1>
            <p className="text-slate-400 text-sm">Redirecting to your dashboard…</p>
          </>
        ) : pollCount >= MAX_POLLS ? (
          <>
            <h1 className="text-2xl font-bold mb-2">Payment received</h1>
            <p className="text-slate-400 text-sm mb-4">
              Your plan will update in a moment. Refresh your dashboard if it doesn't.
            </p>
            <button
              onClick={() => navigate('/dashboard')}
              className="bg-violet-600 hover:brightness-110 text-white px-6 py-2 rounded-xl text-sm font-medium transition-all"
            >
              Go to Dashboard
            </button>
          </>
        ) : (
          <>
            <Loader2 className="w-10 h-10 text-violet-500 animate-spin mx-auto mb-6" />
            <h1 className="text-2xl font-bold mb-2">Confirming your payment…</h1>
            <p className="text-slate-400 text-sm">This takes a few seconds.</p>
          </>
        )}
      </div>
    </div>
  );
}
