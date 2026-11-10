/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // Ignara Design System Tokens
        bg: 'var(--bg)',
        side: 'var(--side)',
        card: 'var(--card)',
        card2: 'var(--card2)',
        line: 'var(--line)',
        tx: 'var(--tx)',
        mu: 'var(--mu)',
        dim: 'var(--dim)',
        ember: {
          1: 'var(--o1)',
          2: 'var(--o2)',
          DEFAULT: 'var(--o1)',
        },
        igGreen: 'var(--g)',
        igRose: 'var(--r)',
        igYellow: 'var(--y)',
        inv: 'var(--inv)',
        invt: 'var(--invt)',

        // Backward compatibility mappings
        ink: {
          DEFAULT: "var(--tx)",
          950: "var(--bg)",
          900: "var(--bg)",
          800: "var(--side)",
          700: "var(--card2)",
          600: "var(--mu)",
        },
        electric: {
          DEFAULT: "var(--o1)",
          600: "var(--o2)",
          500: "var(--o1)",
          400: "#fb923c",
          300: "#fdba74",
          200: "#fed7aa",
          100: "rgba(251, 124, 60, 0.15)",
          50: "rgba(251, 124, 60, 0.08)",
        },
        sardine: {
          slate: "var(--mu)",
          muted: "var(--dim)",
        }
      },
      fontFamily: {
        sans: ['Outfit', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        card: '22px',
        btn: '14px',
        input: '12px',
        pill: '9999px',
        nav: '14px',
      },
      boxShadow: {
        'hero': '0 20px 40px -20px rgba(240, 70, 40, 0.6)',
        'btn': '0 8px 20px -8px rgba(240, 80, 40, 0.7)',
        'nav-active': '0 8px 24px -8px rgba(240, 80, 40, 0.6)',
        'bento': '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.06)',
        'bento-hover': '0 10px 25px -5px rgba(0, 0, 0, 0.25)',
      }
    },
  },
  plugins: [],
}
