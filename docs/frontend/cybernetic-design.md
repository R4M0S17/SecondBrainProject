---
name: Cybernetic Minimalism
colors:
  surface: '#131317'
  surface-dim: '#131317'
  surface-bright: '#39393d'
  surface-container-lowest: '#0e0e12'
  surface-container-low: '#1b1b1f'
  surface-container: '#1f1f23'
  surface-container-high: '#2a292e'
  surface-container-highest: '#353439'
  on-surface: '#e4e1e7'
  on-surface-variant: '#b9cacb'
  inverse-surface: '#e4e1e7'
  inverse-on-surface: '#303034'
  outline: '#849495'
  outline-variant: '#3a494b'
  surface-tint: '#00dce6'
  primary: '#e0fdff'
  on-primary: '#00373a'
  primary-container: '#00f2fe'
  on-primary-container: '#006a70'
  inverse-primary: '#00696f'
  secondary: '#c0c1ff'
  on-secondary: '#1000a9'
  secondary-container: '#3131c0'
  on-secondary-container: '#b0b2ff'
  tertiary: '#fff6e4'
  on-tertiary: '#3b2f00'
  tertiary-container: '#fed83a'
  on-tertiary-container: '#725e00'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#6ff6ff'
  primary-fixed-dim: '#00dce6'
  on-primary-fixed: '#002022'
  on-primary-fixed-variant: '#004f53'
  secondary-fixed: '#e1e0ff'
  secondary-fixed-dim: '#c0c1ff'
  on-secondary-fixed: '#07006c'
  on-secondary-fixed-variant: '#2f2ebe'
  tertiary-fixed: '#ffe173'
  tertiary-fixed-dim: '#e8c423'
  on-tertiary-fixed: '#221b00'
  on-tertiary-fixed-variant: '#554500'
  background: '#131317'
  on-background: '#e4e1e7'
  surface-variant: '#353439'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.04em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  body-base:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: '1.5'
    letterSpacing: -0.01em
  label-mono:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1.0'
    letterSpacing: 0.05em
  headline-md-mobile:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: '1.2'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 16px
  margin-desktop: 32px
  margin-mobile: 16px
  panel-width: 320px
---

## Brand & Style

This design system embodies the intersection of high-end consumer electronics and advanced artificial intelligence. It leverages a **Modern Minimalist Cybernetic** aesthetic, drawing heavy influence from sophisticated dark-mode environments. The personality is precise, powerful, and hushed—evoking the feeling of a professional workstation from the near future.

The visual narrative is built on three pillars:
- **Depth through Glassmorphism:** Semi-transparent frosted layers create a sense of physical space within the software.
- **Controlled Luminescence:** Neon accents are used sparingly to guide the eye toward active processes and system status.
- **Apple-inspired Precision:** High-fidelity typography and ample whitespace ensure the complex data of an AI Operating System remains legible and premium.

## Colors

The palette is anchored in absolute blacks to maximize contrast and visual comfort in dark environments.

- **Primary Background:** Deep Matte Black (#0B0B0F). This provides the "infinite depth" feel required for a cybernetic aesthetic.
- **Surface & Containers:** Charcoal Gray (#1A1A1F) with variable opacity. Glassmorphism is achieved using a 60-80% opacity fill combined with a background blur of 20px-40px.
- **Electric Cyan:** The primary action color, used for "Engine On" states, progress indicators, and active selection glow.
- **Muted Indigo:** A functional secondary color used for non-destructive active states, secondary buttons, and hover interactions.
- **Monotone Hierarchy:** Grayscale values range from pure white (Headlines) to mid-gray (Secondary text) to deep charcoal (Borders).

## Typography

The typography system relies on high-fidelity sans-serif faces to maintain a clean, technical edge.

- **Inter** is the primary typeface, utilized for all UI controls, headings, and body content due to its exceptional legibility and neutral tone.
- **JetBrains Mono** (or similar monospaced font) is used exclusively for metadata, system status, and model parameters to reinforce the "Operating System" feel.
- **Weighting:** Use `Medium (500)` for labels and `SemiBold (600)` for section headers to ensure hierarchy without adding visual bulk.
- **Tracking:** Headlines should use slight negative tracking (-2% to -4%) for a tighter, more "designed" appearance.

## Layout & Spacing

The layout follows a **Fixed-Fluid hybrid model**. Sidebars (Settings, Fleet Orchestrator) are fixed-width at 320px to maintain consistent density for complex controls, while the central workspace remains fluid.

- **The 8px Grid:** All spacing is derived from a 4px base unit, with 8px and 16px being the standard increments for component spacing.
- **Density:** High whitespace in the main workspace contrasts with high-density control panels on the periphery.
- **Safe Zones:** Use 32px global margins for desktop applications to provide the "Dribbble-style" breathing room. Panels should have internal padding of 24px.

## Elevation & Depth

Depth is communicated through **Optical Stacking** rather than traditional drop shadows.

- **Base Layer:** The matte black background.
- **Mid Layer:** Frosted glass panels (Glassmorphism). These utilize a subtle 1px inner border (Light/White at 8% opacity) to catch the light on the "edge" of the glass.
- **Top Layer:** Popovers and active modals. These use a slightly higher opacity fill and a very soft, large-radius ambient shadow (32px blur, 40% black) to separate them from the mid-layer.
- **Accent Glows:** Active elements (like the circular progress rings) emit a soft cyan outer glow (`box-shadow: 0 0 15px rgba(0, 242, 254, 0.3)`) to simulate a light source.

## Shapes

The shape language balances the organic nature of AI with the precision of hardware.

- **Containers:** Standard panels use `rounded-lg` (16px) to match modern OS standards.
- **Interactive Elements:** Buttons and input bars use a more pronounced rounding (8px) or full pill-shapes for primary actions.
- **Status Indicators:** Perfectly circular (50% radius) for progress rings and status pips to contrast against the rectangular layout grid.

## Components

- **Input Bars:** Minimalist ghost-style inputs. Transparent fill with a 1px border. On focus, the border transitions to the Cyan accent with a subtle inner glow.
- **Progress Rings:** Glowing circular strokes. Use a dual-stroke method: a low-opacity background track and a high-luminance Cyan foreground track that represents the active value.
- **Buttons:** 
  - *Primary:* Solid Cyan with black text for maximum visibility.
  - *Secondary:* Ghost style with a thin gray border.
  - *Toggle:* Apple-inspired pill switches; when active, the background glows with the Indigo accent.
- **Cards:** Semi-transparent containers with a subtle 1px border. Hovering over a card should increase the background blur and border brightness.
- **Micro-Icons:** 1.5pt stroke weight icons, using the Indigo accent for secondary functionality and White for primary.
- **Chips/Badges:** Monospaced text inside small, high-contrast pills (e.g., GGUF tags) with a solid dark-gray background.