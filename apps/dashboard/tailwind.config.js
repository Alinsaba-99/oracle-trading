/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(240 5% 14%)',
        background: 'hsl(240 10% 4%)',
        foreground: 'hsl(240 10% 90%)',
        muted: {
          DEFAULT: 'hsl(240 5% 12%)',
          foreground: 'hsl(240 5% 45%)',
        },
        card: {
          DEFAULT: 'hsl(240 5% 8%)',
          foreground: 'hsl(240 10% 90%)',
        },
        accent: {
          DEFAULT: 'hsl(240 5% 16%)',
          foreground: 'hsl(240 10% 90%)',
        },
        destructive: {
          DEFAULT: 'hsl(0 62% 30%)',
          foreground: 'hsl(0 62% 90%)',
        },
        ring: 'hsl(240 5% 65%)',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        lg: '0.5rem',
        md: 'calc(0.5rem - 2px)',
        sm: 'calc(0.5rem - 4px)',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
}
