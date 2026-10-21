# Build: carry out one task

An architect designed this task so that the builder makes no design decision: the files, the pieces and the
behavior are settled. Your job is the edit. When you answer, code checks which files changed, commits them, and
the next task starts in a new run.

## Work
1. Start from the files given below as they are now: every file the task changes and every file it names to read.
   Open another file only when the task or that code points at it.
2. Change only the files the task lists, as its change describes. Code compares every changed file with the list
   and sends back any other one to undo, which costs a whole retry. Remove files your checks create, such as data
   files; tool caches (`__pycache__`, `.pytest_cache` and the like) are already ignored, so leave them.
3. Follow the project conventions and each repo's AGENTS.md, given below.
4. Stay inside the project folder: everything the task needs is there. Keep every command inside the task's repos
   and leave installs and servers alone: no one approves commands during this run.

## Stop
Stop when the task leaves a design decision open (a name, a shape, a place or a behavior that neither the task nor
the code settles) or contradicts the code. A guess puts a design no one reviewed into the product; a stop sends the
question to the architect, who owns design. Code saves your edits as evidence and resets the repos.
