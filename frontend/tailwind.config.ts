import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      // Design System: Executive Talent Engine
      // Based on Stitch design output
      colors: {
        // Primary - Deep Indigo
        primary: {
          DEFAULT: '#15157d',
          container: '#2e3192',
          fixed: '#e1e0ff',
          'fixed-dim': '#c0c1ff',
        },
        // Secondary - Soft Slate
        secondary: {
          DEFAULT: '#505f76',
          container: '#d0e1fb',
          fixed: '#d3e4fe',
          'fixed-dim': '#b7c8e1',
        },
        // Tertiary - Emerald Green (Success)
        tertiary: {
          DEFAULT: '#002f1e',
          container: '#004830',
          fixed: '#85f8c4',
          'fixed-dim': '#68dba9',
        },
        // Error states
        error: {
          DEFAULT: '#ba1a1a',
          container: '#ffdad6',
        },
        // Surface colors
        surface: {
          DEFAULT: '#faf8ff',
          dim: '#d2d9f4',
          bright: '#faf8ff',
          container: {
            lowest: '#ffffff',
            low: '#f2f3ff',
            DEFAULT: '#eaedff',
            high: '#e2e7ff',
            highest: '#dae2fd',
          },
          variant: '#dae2fd',
          tint: '#4f54b4',
        },
        // Text colors
        'on-primary': '#ffffff',
        'on-primary-container': '#9da1ff',
        'on-primary-fixed': '#04006d',
        'on-primary-fixed-variant': '#373a9b',
        'on-secondary': '#ffffff',
        'on-secondary-container': '#54647a',
        'on-secondary-fixed': '#0b1c30',
        'on-secondary-fixed-variant': '#38485d',
        'on-tertiary': '#ffffff',
        'on-tertiary-container': '#47bd8d',
        'on-tertiary-fixed': '#002114',
        'on-tertiary-fixed-variant': '#005137',
        'on-error': '#ffffff',
        'on-error-container': '#93000a',
        'on-surface': '#131b2e',
        'on-surface-variant': '#464652',
        'on-background': '#131b2e',
        // Inverse colors
        'inverse-surface': '#283044',
        'inverse-on-surface': '#eef0ff',
        'inverse-primary': '#c0c1ff',
        // Borders
        outline: '#777683',
        'outline-variant': '#c7c5d4',
        // Background
        background: '#faf8ff',
      },
      fontFamily: {
        // Headings - Manrope (geometric, refined)
        display: ['Manrope', 'sans-serif'],
        headline: ['Manrope', 'sans-serif'],
        title: ['Manrope', 'sans-serif'],
        // Body - Inter (neutral, systematic)
        body: ['Inter', 'sans-serif'],
        label: ['Inter', 'sans-serif'],
      },
      fontSize: {
        // Display
        'display-lg': ['48px', { lineHeight: '1.2', letterSpacing: '-0.02em', fontWeight: '700' }],
        // Headlines
        'headline-md': ['30px', { lineHeight: '1.3', letterSpacing: '-0.01em', fontWeight: '600' }],
        // Titles
        'title-sm': ['20px', { lineHeight: '1.4', fontWeight: '600' }],
        // Body
        'body-lg': ['18px', { lineHeight: '1.6', fontWeight: '400' }],
        'body-md': ['16px', { lineHeight: '1.5', fontWeight: '400' }],
        'body-sm': ['14px', { lineHeight: '1.5', fontWeight: '400' }],
        // Labels
        'label-caps': ['12px', { lineHeight: '1.2', letterSpacing: '0.05em', fontWeight: '600' }],
        'label-sm': ['12px', { lineHeight: '1.2', fontWeight: '500' }],
      },
      spacing: {
        'base': '4px',
        'xs': '8px',
        'sm': '16px',
        'md': '24px',
        'lg': '40px',
        'xl': '64px',
        'gutter': '24px',
        'margin': '32px',
        'max-width': '1440px',
      },
      borderRadius: {
        'sm': '0.125rem',  // 2px - subtle
        DEFAULT: '0.25rem', // 4px - base
        'md': '0.375rem',   // 6px
        'lg': '0.5rem',     // 8px - cards
        'xl': '0.75rem',    // 12px - large containers
        'full': '9999px',   // pills
      },
      boxShadow: {
        // Ambient shadows - tinted with primary color
        'ambient-sm': '0 1px 2px 0 rgba(21, 21, 125, 0.05)',
        'ambient': '0 4px 6px -1px rgba(21, 21, 125, 0.1), 0 2px 4px -2px rgba(21, 21, 125, 0.1)',
        'ambient-md': '0 10px 15px -3px rgba(21, 21, 125, 0.1), 0 4px 6px -4px rgba(21, 21, 125, 0.1)',
        'ambient-lg': '0 20px 25px -5px rgba(21, 21, 125, 0.1), 0 8px 10px -6px rgba(21, 21, 125, 0.1)',
      },
      backdropBlur: {
        'xs': '2px',
        'sm': '4px',
        'md': '12px',
      },
    },
  },
  plugins: [],
};

export default config;
