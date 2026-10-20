# Brief: split-bill

## Who you are
You are Marta Lindqvist. You go on a summer trip with five friends and want a program that settles the shared
bills. You are precise about money but not technical.

## Facts
- F1: When an amount does not divide into whole cents, round every person's part down to the cent, then give the
  cents left over one each to the people in the order the expense lists them ("for", or "shares" in the order
  written), starting with the first. Example: 10.00 for Ana, Ben and Cy: Ana 3.34, Ben 3.33, Cy 3.33.
- F2: The percentages in "shares" must add up to exactly 100. If they don't, print `Shares must add up to 100.`
  as an error and exit with code 1.
- F3: Any set of payments is fine as long as it settles everyone to the cent, has at most one payment fewer than
  the number of people, and nobody both pays and receives.
- F4: Keep it simple: one currency (euros), no saved history, no editing of bills, no web page.
