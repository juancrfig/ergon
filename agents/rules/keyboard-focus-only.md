# Focus chrome indicates keyboard navigation only

Rule: Focus indicators, focus rings, border flashes, and outline chrome appear during keyboard navigation, not in response to pointer clicks or taps. Navigation via Tab and arrow keys must always provide clear, high-contrast indicators for the focused control. Because browser `:focus-visible` can trigger focus styling on text-input clicks, gate visible focus chrome on explicit keyboard modality (for example, `html[data-focus="keyboard"]`, activated by Tab or arrow keydown and cleared on pointerdown). Apply this across components; for composite or grouped controls, render the focus indicator on the enclosing shell rather than an inner input.

Prevents: Focus outlines appearing after pointer interaction while keyboard users lack clear focus visibility.

Enforce with: Review changed focus styles for pointer-modality suppression and clear indicators during keyboard navigation through interactive controls and composite shells.
