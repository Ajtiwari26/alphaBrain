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
    },
  },
  plugins: [],
}
