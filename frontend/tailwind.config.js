/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#081026",
          950: "#040814",
          900: "#081026",
          800: "#0d1a3a",
          700: "#15254f",
          600: "#1e346b",
        },
        electric: {
          DEFAULT: "#4b5bfc",
          600: "#3847f5",
          500: "#4b5bfc",
          400: "#6c79fd",
          300: "#7ea1f3",
          200: "#a8bffd",
          100: "#edf1fe",
          50: "#f5f7ff",
        },
        sardine: {
          slate: "#6b7c99",
          muted: "#a4acc4",
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'bento': '0 1px 3px 0 rgba(8, 16, 38, 0.05), 0 1px 2px -1px rgba(8, 16, 38, 0.05)',
        'bento-hover': '0 10px 25px -5px rgba(8, 16, 38, 0.08), 0 8px 10px -6px rgba(8, 16, 38, 0.05)',
        'glow-electric': '0 0 25px -5px rgba(75, 91, 252, 0.35)',
      }
    },
  },
  plugins: [],
}
