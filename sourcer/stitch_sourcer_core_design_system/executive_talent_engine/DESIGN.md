---
name: Executive Talent Engine
colors:
  surface: '#faf8ff'
  surface-dim: '#d2d9f4'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#eaedff'
  surface-container-high: '#e2e7ff'
  surface-container-highest: '#dae2fd'
  on-surface: '#131b2e'
  on-surface-variant: '#464652'
  inverse-surface: '#283044'
  inverse-on-surface: '#eef0ff'
  outline: '#777683'
  outline-variant: '#c7c5d4'
  surface-tint: '#4f54b4'
  primary: '#15157d'
  on-primary: '#ffffff'
  primary-container: '#2e3192'
  on-primary-container: '#9da1ff'
  inverse-primary: '#c0c1ff'
  secondary: '#505f76'
  on-secondary: '#ffffff'
  secondary-container: '#d0e1fb'
  on-secondary-container: '#54647a'
  tertiary: '#002f1e'
  on-tertiary: '#ffffff'
  tertiary-container: '#004830'
  on-tertiary-container: '#47bd8d'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e1e0ff'
  primary-fixed-dim: '#c0c1ff'
  on-primary-fixed: '#04006d'
  on-primary-fixed-variant: '#373a9b'
  secondary-fixed: '#d3e4fe'
  secondary-fixed-dim: '#b7c8e1'
  on-secondary-fixed: '#0b1c30'
  on-secondary-fixed-variant: '#38485d'
  tertiary-fixed: '#85f8c4'
  tertiary-fixed-dim: '#68dba9'
  on-tertiary-fixed: '#002114'
  on-tertiary-fixed-variant: '#005137'
  background: '#faf8ff'
  on-background: '#131b2e'
  surface-variant: '#dae2fd'
typography:
  display-lg:
    fontFamily: Manrope
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Manrope
    fontSize: 30px
    fontWeight: '600'
    lineHeight: '1.3'
    letterSpacing: -0.01em
  title-sm:
    fontFamily: Manrope
    fontSize: 20px
    fontWeight: '600'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: 0.05em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1.2'
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 8px
  sm: 16px
  md: 24px
  lg: 40px
  xl: 64px
  gutter: 24px
  margin: 32px
  max_width: 1440px
---

## Brand & Style

The design system is engineered for high-stakes recruitment, where clarity and authority are paramount. It adopts a **Corporate / Modern** aesthetic with a lean toward **Minimalism**, emphasizing precise information density and an "Agentic" intelligence. The visual narrative moves away from generic tech aesthetics toward a bespoke, artisanal professional tool. 

The personality is composed, proactive, and discerning. It seeks to evoke a sense of "quiet power"—where the software acts as a sophisticated partner rather than a simple database. High-contrast interfaces and generous whitespace ensure that candidate profiles and data visualizations remain the focal point, providing a premium experience for talent acquisition leaders.

## Colors

The palette is anchored by **Deep Indigo**, a color that conveys tradition and institutional trust while feeling more modern than standard navy. This is the primary driver for navigation, primary actions, and brand presence.

**Soft Slate** serves as the secondary structural color, used for supporting icons, secondary buttons, and subtle borders to prevent the UI from feeling overly heavy. **Emerald Green** is utilized strictly for "Success" states, positive growth metrics, and "Hire" actions, providing a vibrant, high-contrast counterpoint to the deep indigo. 

The neutral scale is weighted heavily toward the darker end (#0F172A) for typography to ensure maximum legibility against a very clean, slightly cool-tinted off-white background.

## Typography

This design system utilizes a dual-font strategy to balance character with utility. **Manrope** is used for headings and titles; its geometric yet refined curves provide a modern, high-end feel that distinguishes the platform from standard corporate tools.

**Inter** is employed for all functional UI elements, body text, and data points. Its neutral, systematic nature and excellent x-height ensure that complex recruitment data—such as resumes and analytics—remain readable at small sizes. We utilize a strict "Label-caps" style for section headers and table headers to create clear visual hierarchy without needing large font sizes.

## Layout & Spacing

The layout follows a **Fixed Grid** model on desktop, centering content within a 1440px container to maintain readability on ultra-wide monitors. A 12-column system is used with 24px gutters to allow for complex dashboard layouts.

Spacing follows a strict 4px base-unit scale. Generous "LG" and "XL" spacing tiers are used to separate major functional blocks, reinforcing the premium, uncluttered aesthetic. For candidate pipelines and lists, "SM" and "MD" spacing provides the necessary density for agentic workflows where users need to scan large amounts of information quickly.

## Elevation & Depth

Depth in this design system is achieved through **Tonal Layers** and **Low-contrast Outlines** rather than heavy shadows. The background is a soft #F8FAFC, while primary content cards use a pure white (#FFFFFF) surface with a subtle 1px border in a lightened Slate.

When shadows are necessary (such as for floating modals or dropdown menus), they are implemented as "Ambient Shadows"—highly diffused, using a 10% opacity of the Deep Indigo primary color. This creates a tinted depth that feels integrated with the brand rather than a generic grey drop-shadow. Background blurs (12px) are used sparingly on sticky navigation bars to maintain context while scrolling.

## Shapes

The design system uses a **Soft** shape language (0.25rem / 4px base radius). This subtle rounding maintains a professional and "architectural" feel while removing the harshness of sharp corners. 

Buttons and input fields use the base 4px radius. Larger containers like profile cards or dashboard widgets may use the `rounded-lg` (8px) setting to create a softer nesting effect. This restrained approach to roundedness signals precision and technical sophistication, appropriate for a B2B SaaS environment.

## Components

### Buttons
- **Primary:** Solid Deep Indigo with white text. High-contrast, minimal elevation.
- **Secondary:** Ghost style with Slate borders and Slate text.
- **Success:** Emerald Green, reserved for final-stage actions like "Extend Offer."

### Form Inputs
Inputs use a white background with a 1px Slate-200 border. On focus, the border shifts to Deep Indigo with a subtle 2px outer glow in the same hue. Labels are always positioned above the field in "Label-sm" Inter.

### Chips & Badges
Used for candidate tags (e.g., "Top Talent," "JavaScript"). These use a desaturated version of the primary or success colors with dark text to ensure readability without being distracting.

### Cards
Cards are the primary container for candidate profiles. They feature a 1px border and no shadow in their default state. On hover, a subtle ambient Indigo shadow is applied to indicate interactivity.

### Additional Components
- **Pipeline Tracker:** A horizontal stepper using Deep Indigo for completed stages and Emerald Green for the current active stage if successful.
- **Data Tables:** High-density rows with "Body-sm" text and 1px horizontal dividers only, emphasizing a clean, "agentic" look.