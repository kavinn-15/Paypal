# Agentic Financial Crime Platform for Fraud Prevention & AML design system

> Extracted by [Inspo](https://github.com/Nutlope/inspo) (open source, MIT, powered by Together AI). Reference material for *intentional* design decisions: adapt, don't copy.

> Save this as `DESIGN.md` in your project and re-reference it as you build; re-fetch anytime at https://inspomcp.dev/d/sardine-ai/DESIGN.md

- **Source:** https://sardine.ai
- **Captured:** 2026-06-01
- **Mode:** light
- **Macrostructure:** Bento Grid
- **Stack:** Next.js, Tailwind

## Tone

The top agentic risk platform used by leading banks and merchants worldwide to stop fraud in real-time, prevent AI-driven attacks, automate fraud & AML operations  ·  minimalism, swiss, dark-mode, saas, fintech, ai, hero-with-cta, logo-cloud, testimonial-wall, newsletter-signup

## Colors

| Hex | Role (heuristic) |
|---|---|
| `#4b5bfc` | support |
| `#7ea1f3` | support |
| `#081026` | ink |
| `#6b7c99` | support |
| `#a4acc4` | muted |

## Typography

Detected typefaces: **fkGroteskNeue**, **Inter**

| Role | Family | Size | Weight | Line-height | Letter-spacing |
|---|---|---|---|---|---|
| h1 | fkGroteskNeue | 56px | 500 | 1.05 | -2.8px |
| h2 | fkGroteskNeue | 16px | 400 | 1.5 | 0 |
| h3 | fkGroteskNeue | 28px | 500 | 1.15 | -0.56px |
| body | Inter | 16px | 400 | 1.5 | 0 |
| caption | Inter | 14px | 400 | 1.5 | 0 |
| button | fkGroteskNeue | 15px | 500 | 1.2 | 0.225px |

## Spacing scale

`24px` · `32px` · `48px` · `80px`

Base step looks like **4px**.

## Border radius

`0px` · `1px` · `2px` · `4px` · `6px` · `8px` · `10px` · `12px`

## Container

Max content width: **1440px**

## CSS variables exposed by the source

```css
:root {
  --color-purple-200: lab(57.6229% 31.3373 -46.6458);
  --text-2xl: 1.5rem;
  --color-pink-300: lab(75.4855% 36.6052 -23.7918);
  --color-grey-200: lab(11.5921% .00797957 -9.04694);
  --text-lg: 1.125rem;
  --color-beige-100: lab(82.6573% .872046 4.14431);
  --font-body: "Inter","Inter Fallback","sans-serif";
  --color-grey-100: lab(3.53337% 1.64062 -9.35474);
  --color-pink-400: lab(90.9145% 12.7872 -8.65192);
  --color-grey-600: lab(85.9028% -.0850856 -3.82075);
  --text-5xl--line-height: 1;
  --color-green-100: lab(22.5706% -17.6404 .227809);
  --text-base--line-height: calc(1.5/1);
  --font-fkGroteskNeue: "fkGroteskNeue","fkGroteskNeue Fallback";
  --color-blue-300: lab(63.0687% 6.21092 -51.0712);
  --font-mono: "fkGroteskMono","fkGroteskMono Fallback","monospace";
  --color-gray-500: lab(47.7841% -.393182 -10.0268);
  --color-gray-50: lab(98.2596% -.247031 -.706708);
  --color-beige-200: lab(93.1446% .304997 1.72133);
  --font-geistSans: "Geist","Geist Fallback";
  --color-purple-100: lab(11.2899% 21.2444 -25.7653);
  --text-lg--line-height: calc(1.75/1.125);
  --color-white: #fff;
  --color-gray-400: lab(65.9269% -.832707 -8.17473);
  --color-grey-500: lab(76.7552% -.551254 -6.32621);
  --color-blue-400: lab(89.93% -.446081 -12.5512);
  --radius-sm: .25rem;
  --font-sans: ui-sans-serif,system-ui,sans-serif,"Apple Color Emoji","Segoe UI Emoji","Segoe UI Symbol","Noto Color Emoji";
  --font-weight-bold: 700;
  --color-gray-100: lab(96.1596% -.0823438 -1.13575);
  --color-coral-300: lab(70.7558% 36.7673 39.0482);
  --text-xs--line-height: calc(1/.75);
  --font-inter: "Inter","Inter Fallback";
  --color-blue: lab(41.5574% 42.8512 -92.0387);
  --radius-2xl: 1rem;
  --color-blue-light: lab(92.8889% -.0188053 -9.10208);
  --radius-md: .375rem;
  --color-pink-100: lab(24.7008% 36.4703 -22.8091);
  --radius-lg: .5rem;
  --font-heading: "fkGroteskNeue","fkGroteskNeue Fallback","sans-serif";
  --font-fkGroteskMono: "fkGroteskMono","fkGroteskMono Fallback";
  --color-blue-100: lab(11.3541% -2.18716 -19.5803);
  --font-geistMono: "Geist Mono","Geist Mono Fallback";
  --color-purple-1000: lab(1.66659% 6.18027 -9.64296);
  --color-beige-300: lab(95.6276% .552237 .721121);
  --text-2xl--line-height: calc(2/1.5);
  --color-grey-800: lab(95.4409% -.210166 -.600767);
  --spacing: .25rem;
  --color-coral-200: lab(63.7121% 53.1421 46.7539);
  --color-pink-200: lab(43.8334% 56.7513 -35.374);
  --font-weight: 400;
  --color-grey-300: lab(18.845% .770062 -13.2709);
  --color-grey-700: lab(90.9052% -.079602 -1.09786);
  --font-weight-semibold: 600;
  --text-sm: .875rem;
  --color-green-400: lab(86.653% -30.3315 47.5465);
  --color-gray-900: lab(8.11897% .811279 -12.254);
  --color-gray-700: lab(27.1134% -.956401 -12.3224);
  --color-gray-600: lab(35.6337% -1.58697 -10.8425);
  --color-purple-400: lab(87.545% 7.88289 -12.8217);
}
```

## Components present

- hero with cta
- logo cloud
- testimonial wall
- newsletter signup

## Notes for the agent

- **Adapt, don't copy.** The type ramp is a *starting point*. Scale it to your project's base size; preserve the *ratio*, not the literal pixels.
- **Color roles are heuristic** (luminance + dominance). Verify against the source URL before committing tokens.
- **Spacing** assumes a constant base step; round detected values to your project's scale (4 / 8 / 16) when implementing.
- **CSS variables** dumped above (when present) are the source's *actual* tokens - those are higher signal than guesses.
- This page's macrostructure is **Bento Grid**.

---

*Generated by Inspo. Open source under MIT, owned and operated by [Together AI](https://www.together.ai). Original site copyright remains with its authors.*

