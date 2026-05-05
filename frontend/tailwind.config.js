/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        rho: {
          50: '#eef2f9',
          100: '#d4ddef',
          200: '#a9bbdf',
          300: '#7e99cf',
          400: '#5377bf',
          500: '#3b5fa7',
          600: '#1F3864',
          700: '#1a2f54',
          800: '#142544',
          900: '#0f1c34',
        },
        sla: {
          green: '#22c55e',
          amber: '#f59e0b',
          red: '#ef4444',
        },
      },
    },
  },
  plugins: [],
};
