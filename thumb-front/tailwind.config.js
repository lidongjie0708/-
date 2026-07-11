/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#0f766e',
        'primary-dark': '#115e59',
        danger: '#dc2626',
      },
    },
  },
  plugins: [],
};
