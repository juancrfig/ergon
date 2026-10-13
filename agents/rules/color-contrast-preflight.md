# Preflight color contrast against dynamic surfaces

Rule: Before placing a color on text, an icon, a border, or an indicator, verify its contrast and visibility against the surface it sits on. Recheck whenever the underlying surface can vary across light and dark themes, nested parent containers, overlays, or component states (hovered, active, selected, disabled). A color pairing that holds on the page background must not be assumed to work on a card, drawer, or inverted theme.

Prevents: Text, icons, and status indicators vanishing or falling below accessible contrast thresholds inside nested surfaces, overlays, or theme variants.

Enforce with: Review changed colors against every valid parent surface, supported theme, and state. Check contrast and confirm no element shares its background color in any combination.
