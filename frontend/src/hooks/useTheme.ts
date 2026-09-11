import { useEffect, useState } from 'react';

export type Theme = 'light' | 'dark';

function prefersDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function initialTheme(): Theme {
  const params = new URLSearchParams(window.location.search);
  const qt = params.get('systemTheme');
  const saved = localStorage.getItem('bimos-theme');
  if (saved === 'dark' || saved === 'light') return saved;
  if (qt === 'dark' || qt === 'light') return qt as Theme;
  return prefersDark() ? 'dark' : 'light';
}

/**
 * Theme precedence (matches the bootstrap script in index.html):
 * localStorage override → ?systemTheme (Qt desktop) → OS media query.
 */
export function useTheme(): Theme {
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) => {
      const params = new URLSearchParams(window.location.search);
      const qt = params.get('systemTheme');
      const saved = localStorage.getItem('bimos-theme');
      // Follow live OS changes only when neither an override nor a desktop
      // theme is explicitly forcing the value.
      if (saved !== 'dark' && saved !== 'light' && qt !== 'dark' && qt !== 'light') {
        setTheme(e.matches ? 'dark' : 'light');
      }
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  return theme;
}