From: Grace Okafor <g.okafor@northside-school.example>
Date: 2026-10-12
Subject: Changes to my grade book program

Hello,

I use the grade book program in the `gradebook` repo for my class every week. The school changed its grading
rules this term, and I need two changes.

1. Weighted categories. Every grade is now homework or exam. Homework counts 40% of the final grade and exams 60%.
   Inside a category, the scores are averaged as today. I want to type the category when I add a grade:

       python3 gradebook.py add Ana exam1 90 --category exam

   The message stays as it is today (`Added 90 for Ana on exam1`). Only `homework` and `exam` are allowed; for
   anything else print `Category must be homework or exam.` to the error output (stderr) and exit with code 1.

   `python3 gradebook.py report` shows each student's final grade, in the same format as today
   (`Ana: 86.2`).

2. Export to a spreadsheet. `python3 gradebook.py export grades.csv` writes a CSV file with the header
   `student,homework,exam,final` and one row per student, sorted by name, with the averages and the final grade
   (one decimal, like the report). It prints `Exported 2 students to grades.csv` (the number of students and
   the file name I gave).

A few things you should know: I have already entered this term's homework, before categories existed. And some
students joined late, so they have exams but no homework yet.

Everything else should work as it does now.

Kind regards,
Grace Okafor
