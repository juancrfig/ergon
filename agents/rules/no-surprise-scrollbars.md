# Prevent surprise scrollbars during transitions and layout rendering

Rule: Visual transitions, modal mounts, and layout updates must never cause scrollbars to flash, appear, or disappear unexpectedly. Place entering and exiting overlay layers inside an `overflow-hidden` shell using absolute or fixed `inset-0` positioning; do not stack multiple full-height panels in normal document flow while both are mounted. Do not animate layout dimensions (`height`, `min-height`, `width`) to reveal or dismiss viewport chrome. Viewport-bound screens set `overflow: hidden` on the outer page shell and confine scrolling (`overflow-y: auto`) to designated internal content regions, not the root document.

Prevents: Abrupt layout shifts, page bouncing, and scrollbar flicker when dialogs open, transitions play, or panels mount side by side.

Enforce with: Review changed layout styles for overflow boundaries, out-of-flow overlay layers, and transitions that avoid viewport scrollbar flashes or document scrolling in viewport-bound layouts.
