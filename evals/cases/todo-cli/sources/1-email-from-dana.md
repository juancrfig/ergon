From: Dana Ruiz <dana@ruizbakery.example>
To: the developers
Date: 2026-10-05
Subject: A simple to-do list for the bakery

Hi,

I run Ruiz Bakery with my partner Sam. We keep our daily jobs on paper and lose them. I want a small to-do
program we can run on the shop computer from the command line. Nothing fancy.

How I picture it:

- The program is `todo.py`, at the top of the `todo` repo. We run it as `python3 todo.py <command>`.
- It keeps our list in a file called `todo.json`, in the folder we run it from.
- `python3 todo.py add buy more flour` adds an item and prints `Added 1: buy more flour`. The text is
  everything after `add`.
- Items get numbers 1, 2, 3 and so on. A number is never given out twice, not even after an item is gone, so
  nobody confuses an old job with a new one.
- `python3 todo.py list` prints one line per item, like `1. [ ] buy more flour`. A finished item is shown with an
  x: `1. [x] buy more flour`. Done items stay in the list; I like seeing what we finished. When there is nothing
  at all, it prints `Nothing to do.`
- I care most about what is still open, so I would like the open jobs where I see them first. Let's talk about
  the order.
- `python3 todo.py done 1` marks item 1 as finished and prints `Done 1: buy more flour`.
- `python3 todo.py remove 1` removes item 1 and prints `Removed 1: buy more flour`. Removing deletes it for good:
  I don't want clutter.
- If we type a number that doesn't exist, it should print `No item 7.` (with the number we typed) to the error output (stderr)
  and exit with code 1, so we notice.

Thanks,
Dana
