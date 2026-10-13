# Style scrollbars with standard properties to match the palette

Rule: Style scrollbars using standard CSS properties (`scrollbar-color` and `scrollbar-width`), not non-standard `::-webkit-scrollbar` pseudo-elements as the primary implementation. Set `scrollbar-color` and `scrollbar-width` to match the design tokens and make the scrollbar unobtrusive. If arrow buttons must be suppressed in Chromium via `::-webkit-scrollbar`, isolate the rule inside an `@supports selector(::-webkit-scrollbar)` block, kept mutually exclusive from the standard `@supports not selector(::-webkit-scrollbar)` declaration, and document the compositing tradeoff in place.

Prevents: Default system scrollbar styling breaking the palette, or cross-browser styling failures from relying on proprietary WebKit pseudo-elements.

Enforce with: Inspect changed CSS for scrollbar styling. Verify `scrollbar-color` and `scrollbar-width` are declared on the root or scroll container. Verify bare, ungated `::-webkit-scrollbar` declarations do not override standard properties. Review cross-browser use of standard properties and gated WebKit fallbacks.
