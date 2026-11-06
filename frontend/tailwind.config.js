/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        paypal: {
          blue: "#0070BA",
          darkblue: "#003087",
          light: "#00457C",
          yellow: "#FFC439",
          gray: "#F5F7FA"
        }
      }
    },
  },
  plugins: [],
}

