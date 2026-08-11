/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui"] },
      boxShadow: { card: "0 14px 38px rgba(30, 41, 59, .08)" },
      typography: {},
    }
  },
  plugins: []
};
