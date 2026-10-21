# pantry feature map

What pantry does and how a user reaches it. Every feature is a command: `python3 pantry.py <command>`. Drive each
with `sh pantry/.agents/skills/verify/app <state> <command> ...` (SKILL.md). Quantities are typed with a unit
(`25kg`, `500g`, `2l`, `30un`) and shown in each item's base unit.

## Stock
- **What it does:** every catalog item and how much is in stock, one line each (`flour: 25 kg`).
- **How to reach it:** `stock`.
- **Driving it:** `app s1 stock`; after a `receive`, the item's line shows the new amount.
- **Gotchas:** lists every catalog item, including those with nothing in stock.

## Receive a delivery
- **What it does:** adds a lot (an amount with a use-by date) of an item. Prints `Received <qty> of <item>`.
- **How to reach it:** `receive <item> <qty> <use-by>`, the date as YYYY-MM-DD.
- **Driving it:** `app s1 receive flour 25kg 2099-12-31`.
- **Gotchas:** an item not in the catalog or a quantity in the wrong unit is an error, exit 1.

## Use stock
- **What it does:** takes stock out, from the lot that expires first. Prints `Used <qty> of <item>`.
- **How to reach it:** `use <item> <qty>`.
- **Driving it:** receive two lots with different dates, `app s1 use flour 30kg`, then `app s1 label flour` to see
  which lots remain.
- **Gotchas:** more than what is in stock prints `Not enough <item>: <qty> in stock.`, exit 1, and takes nothing.

## Recipes
- **What it does:** what one batch of a product takes, one line per ingredient.
- **How to reach it:** `recipe <name>`.
- **Driving it:** `app s1 recipe croissant`.
- **Gotchas:** an unknown recipe is an error, exit 1.

## Sales
- **What it does:** records a sale of a product, and shows today's totals per product.
- **How to reach it:** `sell <product> <count>` prints `Sold <count> <product>`; `sales` prints `<product>: <count>`
  lines.
- **Driving it:** `app s1 sell croissant 12`, then `app s1 sales`.
- **Gotchas:** a count must be a whole number above 0 (`Count must be a whole number above 0.`, exit 1). `sales`
  with none today prints `No sales today.`

## Shelf labels
- **What it does:** label lines for each lot of an item in stock.
- **How to reach it:** `label <item>`.
- **Driving it:** after a `receive`, `app s1 label flour`.
- **Gotchas:** an item with no stock prints `No <item> in stock.`

## Help
- **What it does:** lists the commands. `help` exits 0; an unknown command prints the same list and exits 1.
