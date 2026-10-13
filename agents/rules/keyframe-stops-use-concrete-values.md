# Keyframe percentage stops use concrete values

Rule: Percentage stops inside `@keyframes` rules declare concrete dimensions, values, transforms, and timing functions directly, rather than referencing CSS custom properties (`var(...)`) or dynamic `calc()` expressions with time or unit arithmetic. Variables inside keyframe stops may fail to resolve consistently across rendering engines and can invalidate declarations. Keep keyframe definitions concrete (for example, `transform: translateX(6px)` and `animation-timing-function: cubic-bezier(...)`); restrict CSS variable usage to the animation application rule (for example, `animation: my-anim var(--duration) linear`).

Prevents: CSS animations failing silently or keyframe declarations being dropped by browser CSS parsers.

Enforce with: Review changed stylesheets and CSS-in-JS declarations for `var(` inside `@keyframes`; check transforms, positions, opacity, and timing functions in percentage stops use concrete values.
