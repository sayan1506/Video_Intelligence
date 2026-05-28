import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';

export default function ThemeToggle() {
  const { mode, toggle } = useTheme();

  return (
    <button
      onClick={toggle}
      aria-label={mode === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
      className="w-11 h-11 flex items-center justify-center rounded-md
                 text-gold-light-text-primary dark:text-gold-text-primary
                 hover:bg-gold-light-bg-tertiary dark:hover:bg-gold-bg-tertiary
                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-accent
                 transition-colors"
    >
      {mode === 'light' ? <Sun size={20} /> : <Moon size={20} />}
    </button>
  );
}
