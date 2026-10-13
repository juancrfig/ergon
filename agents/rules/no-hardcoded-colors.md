# Reference design tokens instead of hardcoded colors

Rule: Do not hardcode literal color values (hex, rgb, hsl, or named colors) in component styles, templates, or markup. Reference a design-system token with a semantic role (such as foreground or accent), or a CSS custom property if no token exists. Where CSS custom properties are defined locally, declare and re-declare them per theme so every rendered color remains a function of the selected theme rather than a static constant.

Outputs that cannot read CSS variables (documents, email, images) use one palette module with semantic names whose values copy the matching CSS tokens. Literal colors live only in that module; every other file references its names.

Prevents: Hardcoded colors becoming invisible or drifting from the interface palette when themes or output formats change.

Enforce with: Review changed CSS, style attributes, and templates for literal hex, rgb/rgba, hsl/hsla, or named colors. Check color properties use design-system tokens or theme-bound CSS variables. For document or email output, check literal colors appear only in the palette module and match CSS tokens.
