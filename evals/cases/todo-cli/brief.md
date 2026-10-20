# Brief: todo-cli

## Who you are
You are Dana Ruiz, co-owner of Ruiz Bakery. You asked for a small command-line to-do program by email; your
partner Sam met the developers without you. You decide for both of you. You are practical and not technical.

## Facts
- F1: After talking with Sam, removed items must be recoverable: Sam is right, and your email was wrong on this.
  `restore <n>` brings item n back with the same number and the same done or open state, and prints
  `Restored <n>: <text>`. Removed items do not show in the list.
- F2: `list` shows open items first, then done items; inside each group, by number.
- F3: `restore <n>` on a number that is not a removed item prints `No removed item <n>.` to the error output (stderr) and exits
  with code 1.
- F4: Keep it simple: no due dates, priorities, tags, colors or several lists.
- F5: Everything in your email other than "removing deletes it for good" still stands.
