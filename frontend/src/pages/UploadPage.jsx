export default function UploadPage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-slate-950 text-slate-100 flex items-center justify-center px-6 py-12">
      <style>{`
        @keyframes orbFloatA {
          0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
          50% { transform: translate3d(28px, -20px, 0) scale(1.08); }
        }

        @keyframes orbFloatB {
          0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
          50% { transform: translate3d(-24px, 18px, 0) scale(1.06); }
        }

        @keyframes orbFloatC {
          0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
          50% { transform: translate3d(16px, 24px, 0) scale(1.05); }
        }

        @keyframes wrenchWiggle {
          0%, 100% { transform: rotate(-3deg); }
          50% { transform: rotate(3deg); }
        }

        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translate3d(0, 14px, 0);
          }
          to {
            opacity: 1;
            transform: translate3d(0, 0, 0);
          }
        }

        .orb-a { animation: orbFloatA 14s ease-in-out infinite; }
        .orb-b { animation: orbFloatB 17s ease-in-out infinite; }
        .orb-c { animation: orbFloatC 20s ease-in-out infinite; }
        .wrench-wiggle {
          display: inline-block;
          transform-origin: 58% 78%;
          animation: wrenchWiggle 2.8s ease-in-out infinite;
        }
        .fade-in-heading {
          opacity: 0;
          animation: fadeInUp 700ms ease forwards;
        }
        .fade-in-paragraph {
          opacity: 0;
          animation: fadeInUp 700ms ease forwards;
          animation-delay: 220ms;
        }
      `}</style>

      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_25%_20%,rgba(99,102,241,0.26),transparent_56%),radial-gradient(circle_at_80%_75%,rgba(139,92,246,0.22),transparent_58%),linear-gradient(160deg,#020617_0%,#0b1120_52%,#09091a_100%)]" />
      <div className="orb-a pointer-events-none absolute -top-20 left-6 h-72 w-72 rounded-full bg-indigo-500/24 blur-3xl" />
      <div className="orb-b pointer-events-none absolute right-8 top-1/3 h-80 w-80 rounded-full bg-violet-500/24 blur-3xl" />
      <div className="orb-c pointer-events-none absolute -bottom-24 left-1/3 h-72 w-72 rounded-full bg-purple-400/18 blur-3xl" />

      <section className="relative z-10 w-full max-w-xl rounded-2xl border border-indigo-200/20 bg-slate-900/35 p-8 sm:p-10 text-center shadow-[0_24px_80px_rgba(15,23,42,0.75),0_0_0_1px_rgba(129,140,248,0.08),0_0_42px_rgba(139,92,246,0.18)] backdrop-blur-xl">
        <div className="text-5xl mb-5 wrench-wiggle" role="img" aria-label="Wrench">
          🔧
        </div>
        <h1 className="fade-in-heading text-2xl sm:text-3xl font-semibold tracking-tight text-slate-50">
          VidIQ v1.1 maintenance in progress
        </h1>
        <p className="fade-in-paragraph mt-4 text-base sm:text-lg text-slate-300 leading-relaxed">
          Uploads are temporarily disabled.
        </p>
      </section>
    </main>
  );
}