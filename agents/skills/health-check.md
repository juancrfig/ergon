# Wiki health check: the judgment part

Code already checked links, orphans, format, tags, length, dates and the index. Your part is what needs judgment:
two kinds of problem, reported to the human. You change nothing.

Read the pages you need with `read_pages`, many slugs per call: each call costs a turn.

- `contradiction`: two pages, or two claims in one page, disagree. Set `page`, set `other_page` when the claims
  are on two pages, and quote both claims in `text`, so the human can judge without opening the pages.
- `weak-claim`: a claim with no citation, a vague citation, or a claim stated as settled that its own citation
  presents as tentative. Quote the claim in `text`. A good citation says who said it, in what, and when ("Ana Ruiz,
  kickoff call, 2026-10-02"); a vague one names no person or date ("the docs", "the team").

Report a finding only when you can quote the text that shows it: each one costs the human a review. An empty
`findings` list is a valid answer.
