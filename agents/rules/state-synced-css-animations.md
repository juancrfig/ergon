# Synchronize imperative animation classes with component render state

Rule: Any CSS class added to trigger transitions, shakes, or keyframe animations (`classList.add(...)`) must also be tracked in component state and reflected in JSX `className`. In declarative virtual-DOM libraries, a state update alongside an imperative DOM mutation can trigger reconciliation that overwrites the element's class attribute, stripping the animation class before it can paint. Bind animation states in JSX, use `requestAnimationFrame` for reflow sequencing when needed, and clear active states with lifecycle-safe timers.

Prevents: CSS animations silently failing when virtual-DOM reconciliation overwrites an imperatively added class.

Enforce with: Inspect components that trigger CSS animations via imperative handles, refs, or event handlers. Verify the animation class is included in the JSX `className` binding and is not solely applied via native `classList.add()`.
