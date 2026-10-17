Rule:
The merge dry run re-runs the project gate only when the merged result differs from the worker-tested commit in paths the gate covers. Compare the two commits against the gate's declared path scope. If only files outside that scope changed (another project, a Dockerfile the gate does not build, docs), record "gate not re-run: no covered path changed" with the paths, and merge on the worker's passing gate. The same applies to reviews already approved: a screenshot or code review is not repeated on unchanged input.

Prevents:
A merge-time gate re-run cost about 5 minutes with no new information, because only another project's files and the Dockerfile had changed since the worker's passing gate. The orchestrator also re-ran gates and re-reviewed screenshots that agents had already approved.

Enforce with:
The merge report names the gate-covered paths that changed between the worker-tested commit and the merged result, or states that none changed. A gate re-run with no covered path changed fails this rule. A skipped re-run with a covered path changed fails it too.
