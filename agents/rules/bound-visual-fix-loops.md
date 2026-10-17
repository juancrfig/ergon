Rule:
A worker caps the capture, finding and fix cycle of a visual change at 3 recapture rounds. During iteration it captures only the screens the change touches; it captures the full required set once, at the end. After round 3 it hands the open findings back in its summary and stops. A task that changes two independent UI parts is split into one task per part.

Prevents:
A worker received a two-part UI change. It used 250 iterations in 54 minutes in capture, finding, fix and recapture loops, stopped before the final recapture and gate, and a second agent had to finish it.

Enforce with:
Read the worker summary. It states how many recapture rounds ran and which screens each round captured. More than 3 rounds without a handoff of open findings, or a full-set capture on every round, is a failure of this rule. A task that bundles two independent UI parts is returned to the main agent for splitting.
