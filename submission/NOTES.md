# Approach and operating notes

This submission is a deterministic offline Python baseline using only the standard library. It needs no API keys, paid APIs, internet access, embeddings service, or database server. Runtime knowledge comes exclusively from the Snapshot objects provided to ingest(); solution.py never reads eval/public_eval.jsonl or any expected answers.

## What is current?

Each full snapshot is indexed separately under its taken_on date. A current query selects the greatest date; as_of selects the greatest date not after the requested date. A missing page in a subsequent full snapshot is not carried forward. A request before the first observation is refused. Historical retrieval therefore cannot leak facts from a future crawl. An explicit ISO 'as of YYYY-MM-DD' in the question is also recognized when the argument is absent. Crawl time is observation time, not proof of a fact's real-world effective time.

## Evidence and selection

Markdown rate tables are parsed into qualified facts. Product/row labels, balance brackets, term, customer scope, metric, source URL, and source excerpt are retained. APY, APR and dividend rate have separate metric identities. Purchase/refinance and jumbo/regular are separate labels. Points and payment-example columns are excluded from interest-rate extraction. Currency formatting and footnotes are normalized for comparison. Product-specific query handlers choose official product tables; generic narrative questions use deterministic inverse-document-frequency lexical ranking over cleaned paragraphs with heading context. The branch locator distinguishes actual Dupaco branches from third-party ATMs. Newsroom publication dates help rank branch counts and Forbes announcements. Rate answers report the matching rows rather than surrounding calculator numbers.

Answers include Source URLs, snapshot IDs and excerpts. Confidence means that this implementation found direct usable evidence; it is not a calibrated probability. Missing requested rate-table facts cause a refusal. Generic unknown questions use lexical coverage as an additional guard. Repeated calls return deep copies of a deterministic cached result; ingest invalidates that cache.

## Contradictions and history

conflicts() groups equal qualified table facts and compares their values across pages and crawls. Latest observation wins, with official product/rate sources preferred over calculators/blogs. Reasons distinguish within-snapshot disagreement from an ordinary historical rate change. Historical changes are exposed because the assignment requests cross-snapshot differences, but are explicitly labeled as history, not proof of a simultaneous contradiction. A fact that disappears is not claimed to be current. The last observation for that exact historical key may therefore be in an older snapshot.

## Validation and practical limits

Run the unmodified organizer harness from the kit root:

    python harness/run_eval.py --submission submission --eval eval/public_eval.jsonl --out results/solution

On the supplied 40-question practice set: weighted QA score 0.9388, zero stale-trap hits, zero errors, repeat consistency 1.0. Latest measured p95 answer time was 0.22 seconds and ingest was 6.6 seconds. The score excludes the conflict pillar because participant conflict gold is not supplied. Hidden-set performance is unknown. Public paraphrase groups contain single examples, so the harness's 1.0 paraphrase metric is weak evidence; synthetic repetition/history tests provide additional checks.

The non-LLM scorer awards zero to ordinary questions without must_include tokens, including the valid complete certificate list. The employee VTO reference expects 294 (2023); this system returns the observed 256 count explicitly for 2024. The reference's general mortgage text mentions a 15-year 6.25% rate, while the latest supplied table shows 6.75%; the implementation follows the table. Do not change retrieved facts merely to match stale prose in evaluation references.

This is a strong interpretable baseline, not exhaustive natural-language understanding. Domain routing and generic retrieval may miss novel paraphrases. Narrative contradiction extraction, comprehensive promotion expiry logic, arbitrary relative-date interpretation and within-crawl effective-date reconciliation remain limited. Historical schema changes can split a logical fact into multiple keys. Model-year ranges are matched for answers but overlapping ranges are not fully unified for conflicts. Some conflict candidates need review, and conflict recall/precision cannot be claimed without gold data. No live facts after September 28, 2026 are available.
