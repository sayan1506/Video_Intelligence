import { Zap } from 'lucide-react';

/**
 * ComingSoonPage — static maintenance screen shown when the app is gated
 * behind the COMING_SOON flag in App.jsx. Purely presentational: no buttons,
 * links, forms, or anything clickable. Matches the dark gold theme.
 */
export default function ComingSoonPage() {
  return (
    <div className="min-h-screen bg-gold-light-bg-primary dark:bg-gold-bg-primary text-gold-light-text-primary dark:text-gold-text-primary font-sans flex flex-col items-center justify-center px-6 text-center relative overflow-hidden">
      {/* Background glow orb */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-gold-accent-muted dark:bg-gold-accent-muted rounded-full blur-[120px] pointer-events-none animate-pulse-slow -z-10" />

      {/* Brand */}
      <div className="flex items-center gap-2 text-2xl font-bold tracking-tight mb-12">
        <Zap className="w-7 h-7 text-gold-light-accent dark:text-gold-accent" fill="currentColor" />
        <span className="font-display">VidIQ</span>
      </div>

      {/* Headline */}
      <h1 className="font-display text-4xl md:text-5xl font-bold tracking-tight mb-6 max-w-2xl">
        We're Working on Something <span className="text-gold-light-accent dark:text-gold-accent">Great</span>
      </h1>

      {/* Subtext */}
      <p className="text-lg md:text-xl text-gold-light-text-secondary dark:text-gold-text-secondary max-w-xl leading-relaxed">
        VidIQ is currently under maintenance. We'll be back soon.
      </p>

      {/* Gold string accent */}
      <div className="h-px w-24 bg-gold-light-accent dark:bg-gold-accent mt-12" />
    </div>
  );
}
