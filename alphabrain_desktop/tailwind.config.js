/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dmRed: '#E6391E',
        dmBlack: '#0A0A0A',
        dmBorder: '#0A0A0A',
        dmWhite: '#FFFFFF',
        background: '#FFFFFF',
        card: '#FFFFFF',
        'card-border': '#0A0A0A',
        accent: '#E6391E',
        'accent-cyan': '#0A0A0A',
        'accent-emerald': '#0A0A0A',
        'accent-amber': '#E6391E',
        muted: '#52525b',
      },
      fontFamily: {
        headline: ['"Space Grotesk"', 'sans-serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"Fira Code"', 'monospace'],
        display: ['"Space Grotesk"', 'sans-serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      transitionTimingFunction: {
        'spring': 'cubic-bezier(0.16, 1, 0.3, 1)',
        'smooth': 'cubic-bezier(0.4, 0, 0.2, 1)',
        'bounce': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      animation: {
        'shimmer': 'skeleton-shimmer 1.8s infinite ease-in-out',
        'spin-smooth': 'smooth-spin 0.8s cubic-bezier(0.4, 0, 0.2, 1) infinite',
        'screen-enter': 'screen-fade-in 0.22s cubic-bezier(0.16, 1, 0.3, 1) forwards',
      },
    },
  },
  plugins: [],
};
