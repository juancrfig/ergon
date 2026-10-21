# gradebook

A grade book for one class, as a command-line program. Map of the repo for agents.

- `gradebook.py`: the whole program. Run `python3 gradebook.py <command> [arguments]`.
  - Storage: `load` and `save` keep every grade in `grades.json`, in the folder the program runs from.
  - Output: `say` prints one line; `one_decimal` and `average` format and compute every number shown.
  - Input: `parse_score` reads a score; a wrong one raises `GradebookError`, which `main` prints as an error
    with exit code 1.
  - Commands: one `cmd_<name>` function each, listed in `COMMANDS`; `main` dispatches to them.
- `tests/test_gradebook.py`: runs the program as a subprocess in a temporary folder. Run
  `python3 -m unittest discover -s tests`.
