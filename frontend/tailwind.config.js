/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bgDark: '#070709',
        cardDark: '#0f1014',
        cardBorder: '#1f2128',
      },
    },
  },
  plugins: [],
};
