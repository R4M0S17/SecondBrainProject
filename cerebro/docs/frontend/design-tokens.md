---
name: Cerebro Terminal
colors:
  surface: '#13121b'
  surface-dim: '#13121b'
  surface-bright: '#3a3841'
  surface-container-lowest: '#0e0d15'
  surface-container-low: '#1c1b23'
  surface-container: '#201f27'
  surface-container-high: '#2a2932'
  surface-container-highest: '#35343d'
  on-surface: '#e5e0ed'
  on-surface-variant: '#c9c4d7'
  inverse-surface: '#e5e0ed'
  inverse-on-surface: '#312f38'
  outline: '#928ea0'
  outline-variant: '#474554'
  surface-tint: '#c7bfff'
  primary: '#c7bfff'
  on-primary: '#2b009e'
  primary-container: '#8e7fff'
  on-primary-container: '#25008c'
  inverse-primary: '#5a46d3'
  secondary: '#c4c6d3'
  on-secondary: '#2d303b'
  secondary-container: '#444652'
  on-secondary-container: '#b2b4c2'
  tertiary: '#ffb86d'
  on-tertiary: '#492900'
  tertiary-container: '#cd7f1a'
  on-tertiary-container: '#402300'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e4deff'
  primary-fixed-dim: '#c7bfff'
  on-primary-fixed: '#180065'
  on-primary-fixed-variant: '#4228bb'
  secondary-fixed: '#e0e2f0'
  secondary-fixed-dim: '#c4c6d3'
  on-secondary-fixed: '#181b25'
  on-secondary-fixed-variant: '#444652'
  tertiary-fixed: '#ffdcbd'
  tertiary-fixed-dim: '#ffb86d'
  on-tertiary-fixed: '#2c1600'
  on-tertiary-fixed-variant: '#683c00'
  background: '#13121b'
  on-background: '#e5e0ed'
  surface-variant: '#35343d'
typography:
  h1:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  h2:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  body:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  code:
    fontFamily: Space Grotesk
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
  small-mono:
    fontFamily: Space Grotesk
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  gutter: 12px
  container-padding: 16px
---

## Brand & Style

This design system is engineered for high-performance cognitive work, prioritizing efficiency and information density over decorative flourishes. The aesthetic is rooted in **Structural Minimalism** with a **Premium IDE** influence. It evokes the feeling of a high-end development environment: stable, precise, and authoritative.

The interface relies on flat color blocks and rigid structural alignment to create hierarchy. There are no gradients, shadows, or glow effects. Instead, depth is communicated through subtle shifts in background values and crisp 1px borders. The goal is to minimize cognitive load by presenting AI-generated data within a disciplined, architecturally sound framework.

## Colors

The color palette is strictly functional. The primary background (#0f1117) provides a deep, non-distracting canvas. Hierarchy is established using Slate (#1a1d27) for headers and sidebars, creating a clear "frame" for the content.

The Accent Purple (#7c6af7) is used sparingly for primary actions and active states, ensuring it retains its significance. All borders use a consistent #242736 to define blocks without creating high-contrast visual noise. Success states use a vibrant green (#4ade80) that remains legible against the dark background. No transparency or blurs are permitted; all colors are solid.

## Typography

This design system utilizes a dual-font strategy to distinguish between UI controls and technical data. **Inter** is the workhorse for the interface, providing exceptional legibility at small sizes and a neutral, professional tone. **Space Grotesk** is used for all technical data, file paths, and code snippets, providing a technical, geometric edge that signals "developer-first" content.

Type scales are kept tight to maximize information density. Headings are intentionally small, relying on weight and color rather than massive size increases to denote hierarchy. Monospaced elements should always be rendered with a slightly tighter tracking to maintain the "packed" feel of a terminal.

## Layout & Spacing

The layout follows a **Fixed-Internal Grid** model, optimized for wide-screen monitors. It utilizes a 4px base unit to ensure tight, purposeful spacing. Elements are packed closely to allow for a large volume of simultaneous information—multiple chat streams, code editors, and file trees.

Margins between major functional blocks are kept to a minimum (12px to 16px), while internal padding within blocks is even tighter (8px to 12px). This creates a "dashboard" feel where every pixel is utilized. Layout containers should use `overflow: auto` with customized, thin scrollbars to maintain the clean, geometric appearance.

## Elevation & Depth

In this design system, depth is expressed through **Z-axis Tonal Layering** and **Bold Borders**. There are no shadows. 

1.  **Level 0 (Base):** #0f1117 (Main canvas/background).
2.  **Level 1 (Surface):** #1a1d27 (Sidebars, headers, and inactive cards).
3.  **Level 2 (Elevated):** #242736 (Popovers or active input states).

Transitions between these levels are defined by 1px solid borders in #242736. This creates a flat, architectural look where sections feel "slotted" into one another rather than floating.

## Shapes

The shape language is strictly **Sharp (0px)**. All containers, buttons, inputs, and tabs use 90-degree corners. This reinforces the "Terminal" and "IDE" aesthetic, emphasizing precision and structural integrity. 

The only exception to the sharp rule is found in icons, which should use consistent line weights, but all UI-level bounding boxes and containers must remain square. This allows elements to be tiled seamlessly without the visual gaps created by rounded corners.

## Components

### Buttons
Buttons are rectangular blocks. **Primary:** Background #7c6af7, Text #0f1117 (High contrast). **Secondary:** Background transparent, 1px Border #242736, Text #e8eaf0. **Ghost:** Text #8b8fa8, no background or border until hover.

### Input Fields
Inputs use #1a1d27 as the background with a #242736 border. On focus, the border changes to #7c6af7. Labels are placed above the field using the `label-caps` typography style in #8b8fa8.

### Chips & Tags
Technical tags (e.g., language identifiers like "Python" or "JS") use #1a1d27 background with `small-mono` text. They are square-edged and separated by 4px of spacing.

### Lists & Trees
File trees and navigation lists use a subtle hover state (#242736) and a 2px vertical accent bar of #7c6af7 on the left side to indicate the active selection.

### Cards & Containers
Cards do not have shadows. They are defined by their #1a1d27 background and a 1px #242736 border. Header sections within cards should be separated by a horizontal 1px line.

### Progress & Status
The Success Green (#4ade80) is used for terminal-style success messages ("BUILD SUCCESSFUL") and completion bars. Use #242736 for the empty track of a progress bar.