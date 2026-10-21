# inventory

The modules behind `pantry.py`. `cli.py` reads the command line; every other module owns one part of the bakery
and is the only place that part's rules live.

- `cli.py`: the commands (`HELP` lists them, `run` dispatches). Each loads the book, does one thing, saves if it
  changed something and prints one line per result.
- `store.py`: the book in `pantry.json`: stock as lots (one per delivery, with a use-by date), sales, today's
  date, what is available and taking stock out.
- `catalog.py`: every item the bakery stocks, with its base unit, minimum, target and supplier.
- `units.py`: quantities: parsing typed amounts and showing stored ones.
- `recipes.py`: what one batch of each product takes.
- `suppliers.py`: suppliers, their minimum orders and pack sizes.
- `sales.py`: recorded sales and day totals.
- `labels.py`: shelf labels per lot.
- `errors.py`: `PantryError`, a user mistake: `cli` prints it to stderr and exits with code 1.
