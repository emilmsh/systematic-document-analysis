# A controlled for-loop over files

The core applies one agreed task independently to each file through a CLI or API worker. It preserves the task version, source, exact input, settings, response, errors and review history for each attempt. It does not prescribe a research method or a final presentation.

## Implementation plan

1. Add an instruction-first plan without required classification criteria. Allow an optional JSON Schema for the task result; default to readable Markdown. Keep execution metadata separate from the result.
2. Reuse the existing queue, source hashes, isolated CLI sessions/API requests, immutable attempts and approval/version boundaries. Give large files task-aware map–reduce, preserving intermediate findings and their source locations.
3. Validate the declared contract and reported source coverage. Offer optional exact-quotation checks against extracted source units. State explicitly which checks ran and what they cannot establish.
4. Expose the actual task result in run inspection and portable per-file exports. Keep original responses and all attempts alongside derived presentation; preserve legacy classification exports.
5. Rewrite the skill and onboarding around scope, task, execution and flexible follow-up. Test arbitrary result structures, defaults, failures, versioning, isolation, review and backwards compatibility.

## Principles

- **Repeatability:** the same instruction and settings apply to a selected list of files. Material changes create a new plan version.
- **Separation:** one file per run, a fresh worker context per attempt, no other file's answers as hidden context.
- **Traceability:** a result links to source identity, plan version, exact input, requested/reported settings, raw response and errors. Unknown telemetry stays unknown.
- **Readability:** expose the actual deliverable, not merely status, counts or a path into technical logs.
- **Validation:** choose checks appropriate to the task. Passing a schema is not proof of factual accuracy, completeness or human review.
- **Flexibility:** the host can prepare the task and derive tables, reports or further analyses afterward. Retain links to originating run/attempt IDs and distinguish transformations from original worker output.

## Deliberate boundaries

The default Markdown result is a fallback, not a prescribed report layout. A small wire envelope carries result, reported source coverage and limitations; users choose the result's content and optional schema. No task-type enum or fixed workbook is required. Existing criteria-based plans remain supported.

General tasks use a single call when the file fits and task-aware map–reduce when it does not. All fragments retain the same task, source IDs and overlap ranges. Checked intermediate findings go to synthesis with the task-defined final contract. Explicit budgets/timeouts remain binding, and no findings are silently truncated. Legacy criteria plans retain their classification-specific checks.

This change does not claim OS-level isolation, automated semantic verification, or provider access validated by offline tests.
