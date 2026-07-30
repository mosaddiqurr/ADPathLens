/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172033",
        navy: "#111827",
        accent: "#2563eb",
        canvas: "#f4f6f9"
      },
      boxShadow: {
        card: "0 1px 3px rgb(15 23 42 / 0.08), 0 1px 2px rgb(15 23 42 / 0.04)"
      }
    }
  },
  plugins: []
};
