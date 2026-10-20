From: Marta Lindqvist
Date: 2026-10-10
Subject: Splitting bills on our trips

Hello! Every summer six of us rent a house together and we always fight about who owes whom. I'd like a small
program that reads what everyone paid and tells us who pays whom to settle up.

How I'd like to use it:

- The program is `splitbill.py`, at the top of the `splitbill` repo. We run it as
  `python3 splitbill.py <bill file>`.
- The bill file is JSON. It lists the people, then the expenses. Each expense says who paid, the amount in euros
  as a string with two decimals, and who it was for. Example:

      {"people": ["Ana", "Ben", "Cy"],
       "expenses": [{"paid_by": "Ana", "amount": "30.00", "for": ["Ana", "Ben", "Cy"]}]}

  An expense "for" several people is split evenly between them.
- Sometimes we don't split evenly (Ana had the big room). Then the expense has "shares" instead of "for": whole
  percentages per person.

      {"paid_by": "Ben", "amount": "12.00", "shares": {"Ana": 50, "Ben": 25, "Cy": 25}}

- The program prints one line per payment, like `Ben pays Ana 10.00`, sorted by the name of who pays, then of who
  receives. If nobody owes anything it prints `All settled.`
- I want as few payments as possible. With six of us, five payments at most; in general at most one fewer than
  the number of people. Nobody should both pay and receive.
- Money must add up to the cent: when it's all settled, nobody is a cent up or down. Sometimes an amount does not
  divide evenly, like 10.00 between three of us; every cent still has to go to someone.
- If an expense names someone who is not in "people", print `Unknown person: <name>` to the error output (stderr) and exit with
  code 1. Typos happen.

Two examples from last summer:

1. Ana paid 30.00 for Ana, Ben and Cy. The program prints:

       Ben pays Ana 10.00
       Cy pays Ana 10.00

2. Ben paid 12.00 with shares Ana 50, Ben 25, Cy 25. The program prints:

       Ana pays Ben 6.00
       Cy pays Ben 3.00

Thanks!
Marta
