/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        espol: {
          navy: "#0B2545",
          blue: "#134074",
          accent: "#E63946",
          teal: "#2A9D8F",
        },
      },
    },
  },
  plugins: [],
}

