# Checks every change must pass

General behavior any product should have, whatever the project. A rule here applies when the change touches what it
names. Each rule is written so it can be driven and seen through the project's verification skill. Add a rule when a
bug shows a class of mistake that could come back in another project; write it without any name from that project.

1. **A form resets after it succeeds.** After a submit that succeeds, every field returns to its initial state, so
   the form can be used again at once. After a submit that fails, the fields keep what the user typed, so the user can
   correct it. This holds for every form in the product, including ones added later.
