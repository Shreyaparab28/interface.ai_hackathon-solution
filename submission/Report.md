# Snapshot Knowledge System

## Approach

The system answers questions about a credit union from five dated website snapshots. It runs offline with the Python standard library and implements the organizer's `build()`, `ingest()`, `answer()`, and `conflicts()` interface.

Each snapshot is indexed independently. A current question uses the newest snapshot. A question with an explicit `as_of` date uses the newest snapshot on or before that date. Pages that disappear from a later full snapshot are treated as unavailable in that view.

The system extracts rates from Markdown tables and retains their product, term, tier, metric, and source. Rate queries use product pages where possible. For other questions, the system ranks passages using query terms, headings, and source type. Answers include source URLs, snapshot IDs, and excerpts when evidence is available. Unsupported requests can return a low-confidence response that directs the member to Dupaco.

Conflict detection groups table facts by their qualifiers and compares values within and across snapshots. It favors official product pages over secondary sources and labels ordinary changes over time separately from disagreements found in the same crawl.

## Evaluation

| Check                                             |     Result |
| ------------------------------------------------- | ---------: |
| Weighted QA score on 40 public practice questions | **93.88%** |
| Public stale-answer hits                          |      **0** |
| Public runtime errors                             |      **0** |
| Public repeat consistency                         |   **100%** |
| Answers correct on the small organizer self-test  | **1 of 5** |
| Labeled conflicts matched on that self-test       | **0 of 1** |

The public run did not include conflict gold. Hidden-set performance is unknown. In the public auto-loan example, the answer selected the official **5.39% APR** and cited the product page. The conflict output missed the competing **5.34%** calculator figure because the sources describe overlapping model-year tiers differently.

To reproduce the public result, run the organizer's harness from the participant kit root with the path to the folder containing `solution.py`.

```sh
python -X utf8 harness/run_eval.py --submission PATH_TO_SUBMISSION --eval eval/public_eval.jsonl
```

## Known limitations

- Historical queries work with an explicit `as_of` argument or an ISO date in the question. Month-and-year phrases such as “as of May 2026” can fall back to the latest snapshot. The implementation also lacks filtering by individual rates' effective dates.
- Differences in table headers or tier labels can prevent equivalent facts from matching. Conflict extraction covers structured tables. It misses prose-only contradictions, including the organizer's self-test example.
- Some queries need stricter qualifier checks. Mortgage amounts between published tier limits may be declined, checking queries can return unrelated tiers, and named-branch hours can fall back to schedules for other branches.
