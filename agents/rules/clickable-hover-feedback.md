# Clickable controls provide color hover feedback

Rule: Any clickable or interactive control must show a visible hover under the pointer. Hover is a color shift, not motion: use `cursor: pointer` and a surface mixed with the primary color (for example, a `--hover` token). On frequently used work screens, the hover color changes instantly, with no transition. Only on rarely seen screens may the color fade, at most 150ms with `ease`. Put hover styles behind `@media (hover: hover) and (pointer: fine)`, because touch devices may fire hover on tap. Do not translate, scale or change layout on hover. Static elements never show a pointer cursor.

Prevents: Controls that look inactive under the pointer, and frequent controls feeling slow because every hover fades.

Enforce with: In changed styles, check each interactive element for a pointer cursor and hover color; check frequent work screens have no transition on that hover color and any fade elsewhere is 150ms or less; check hover sits behind the hover/pointer media query; check no hover moves or scales anything and no static element has a pointer cursor.
