# pantry

Ruiz Bakery's stock program, as a command-line program. Map of the repo for agents.

- `pantry.py`: the entry point. Run `python3 pantry.py <command> [arguments]`; `python3 pantry.py help` lists
  the commands.
- `inventory/`: the modules behind the commands, one per part of the bakery. Its own AGENTS.md maps them.
- `tests/`: unit tests of the modules. Run `python3 -m unittest discover -s tests` from the repo root.
- `pantry.json`: the bakery's book, created where the program runs; ignored by git.
