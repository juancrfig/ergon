# Brief: gradebook

## Who you are
You are Grace Okafor, a teacher. You use the grade book program every week and asked for weighted categories and a
CSV export. You know your grading rules well; you are not technical.

## Facts
- F1: A student with grades in only one category gets that category's average as the final grade: the weights
  apply only between the categories the student has. In the CSV, the missing category's cell is empty.
- F2: Grades entered without a category (the ones already in the grade book, and any added without
  `--category`) count as homework.
- F3: The school's weights are fixed: no need to change them from the program. No other categories, no letter
  grades.
- F4: Everything that works today must keep working the same way.
