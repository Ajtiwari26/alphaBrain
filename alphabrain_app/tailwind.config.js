/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#090a0f',
        card: '#11131a',
        'card-border': '#222634',
        accent: '#f97316',
        'accent-cyan': '#06b6d4',
        'accent-emerald': '#10b981',
        'accent-amber': '#f59e0b',
        muted: '#94a3b8',
      },
      fontFamily: {
        mono: ['"Fira Code"', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['"Space Grotesk"', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
