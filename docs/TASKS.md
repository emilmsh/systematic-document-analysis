# One task, repeated over files

The plugin is a controlled for-loop: one versioned task, one independent CLI/API worker per file, preserved inputs and results. Use the host conversation to prepare the task and to interpret or present results afterward. Cross-file synthesis is a derived step, not hidden context passed between workers.

## A small starting point

Call `create_analysis` with `project_id`, `name`, `request`, and an explicit `engine`. Add `model` for APIs. `task_instructions` optionally expands the original request. Choose `language="nb"` or `"en"`.

For example: “For each consultation, extract the exact passages about mandatory annual audits and voluntary self-assessment. Keep their source locations and explain uncertainty.” No yes/no labels or classification criteria are necessary.

The default deliverable is an Excel dataset: **one row per iteration/run, columns for the generated variables**. Propose useful variables while preparing the task, not after execution. Normally use an object `output_schema`: each scalar field is a variable. Give fields readable `title` and `description`, including measurement units, scoring scales, and how uncertainty/missing values are represented. The user should approve the meaning of the task and variables, not have to write JSON.

For example, entity extraction might produce `organisation`, `country` and `mentions`; scoring might produce `score`, `rationale` and `evidence`; calculations might produce typed numeric amounts and explicit units. These are task-specific examples, not built-in profiles. Nested objects become separate columns. Lists keep the main row intact and get related detail sheets when needed.

The plugin carries each result in a small wire envelope:

```json
{
  "result": {"organisation": "Example", "score": 3, "rationale": "Supported by source unit 2."},
  "source_units_read": [1, 2],
  "limitations": []
}
```

Only this execution envelope is fixed. Coverage is reported by the worker, not proof of understanding. Prose-only tasks without `output_schema` retain their Markdown string contract, presented in one result column. Export does not perform new model calls or infer analytical variables from old prose. Schema and exact-text checks do not guarantee semantic correctness.

## Optional task-defined structure and checks

`output_schema` describes **result**, not the envelope. It can describe a string, array, object or other JSON value. For portable structured output, use inline schemas, closed objects (`additionalProperties: false`) and list all object properties in `required`; nullable fields represent missing values. Incompatible contracts are rejected rather than silently tightened. Actual provider schema support can still vary; a provider rejection is recorded without fallback.

This example is a supported repeated extraction contract. It produces one primary row per run, with an item count in the main sheet and one detail row per extracted passage:

```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "theme": {"type": "string"},
      "passage": {"type": "string"},
      "unit": {"type": "integer"}
    },
    "required": ["theme", "passage", "unit"],
    "additionalProperties": false
  }
}
```

Optional `quote_checks` validate exact substrings against the preserved extracted text:

```json
[{"path": "", "quote_field": "passage", "unit_field": "unit"}]
```

`path` is a JSON Pointer relative to result; an empty path means the result itself. It must resolve to an array. For an object containing `passages`, use `/passages`. Fields name the quote and source unit on each entry. No case, whitespace or punctuation normalization is applied. For OCR/PDF sources, this proves correspondence to extracted text, not the rendered original. Matching words also do not prove thematic relevance or completeness. An empty array can be a valid result; whether that means no relevant material requires substantive review.

Use `new_plan_version` to change instructions, schemas or quote checks. `quote_checks=[]` clears checks; `reset_output_schema=true` restores the prose contract, exported as one text variable. Existing versions and their runs are unchanged.

## Controlled execution, including large files

Preview the plan and selected runs before approval. Every attempt records source identity/hash, exact instruction and source input, result schema, requested settings, raw response, reported telemetry, errors and validation. CLI/API execution uses the existing independent worker path. A failed file does not stop unrelated files, and retries require an explicit reason.

Each iteration creates a new adapter and a fresh CLI session or API request, with no previous result in its input. A CLI worker may take multiple internal tool turns and use its built-in tools to solve the task; the plugin dispatches it once per attempt. The worker chooses whether to read sections, use code or any helper agents its CLI offers, keep intermediate notes and combine them within that session. Any helpers belong to that file's run. The API reader sends one request.

`input_budget_bytes` defaults to 60000 and measures serialized request bytes, not tokens. CLI readers with `file_tools=true` use the complete original file, the source-unit map and small searchable text copies of those units when inline input exceeds the budget. The same worker chooses how to read them with its standard file tools. APIs and text-only readers fail if their request exceeds the budget; increase it in an agreed plan or use a file-capable CLI reader. Instructions/schema must fit too. There is no automatic model chunk extraction, summarization or synthesis. The byte budget does not bound CLI tool output or guarantee a model's context capacity. `timeout_seconds` bounds the worker call.

`max_concurrent_runs` (1–16, default 1) is the agreed ceiling for workers running at once within one analysis. Each run still has its own thread, adapter, session or request and attempt workspace; it is not part of the input package or its hash. `start_runs` and `resume_runs` accept a lower `concurrent_runs`. Stop prevents new dispatch and cancels every attempt in flight. One worker lock per analysis prevents a second start of the same analysis while different analyses may run side by side.

## Results, review and further work

`show_run` exposes `result` directly. Agree the delivery format, row unit, columns and location before execution. For an agreed workbook, call `export_results` after runs finish and link its returned `workbook`. The snapshot has three top-level files: **Results.xlsx**, a short **START_HERE.md**, and **Documentation.zip** (Norwegian names when selected). Users need not open JSON or navigate separate files for each run.

The first workbook sheet, Results, has one row per run by default, including failed, rejected, empty and unstarted runs. Variables from valid current responses retain their types; invalid or rejected responses have blank variables and their reasons in auxiliary sheets. Missing values are not zeros. Document names and status lead the view; Errors and notes and retry Attempts sheets appear only when relevant. Variables are explained in the workbook; detailed telemetry remains in the documentation ZIP. Identical schemas share columns; different definitions remain separate. Use row_scope="documents" only for the newest planned run per document, with no fallback to older successes.

Nested objects become columns. Repeated collections default to related detail sheets with typed values and run, record and parent IDs. The main row includes collection counts. `list_layout="inline"` additionally shows numbered values in main-row cells. Schema titles/descriptions control readable labels; further custom presentation can be derived from the exported tables. Sibling lists never create a Cartesian product. Empty lists have no detail rows and are not interpreted as negative findings. Only unit fields declared by `quote_checks` are resolved as source locations. Unknown integer fields are not guessed to be page numbers. Long text is continued in a linked sheet in the same workbook; original values remain intact in the archive. Text beginning with `=` is literal text, never an Excel formula.

The documentation ZIP preserves the plan, original-shape `results/<run>.json`, readable copies, optional source files, all attempts, corrections and raw audit files. Extract it to inspect the full chain. `include_csv=true` adds exact-value CSV tables under `datasets/` inside the ZIP for further analysis. Formula-like strings remain exact in CSV: use the XLSX for safe Excel viewing. Source copies are optional; extracted source content remains in exact input/audit records even when copies are omitted. Export publication is staged and does not overwrite older snapshots or user edits.

Further host analysis or synthesis should retain originating run/attempt/plan IDs and stay distinguishable from original worker results.

`record_review` can approve or reject a whole task result. To correct it, supply `replacement_response` with the complete wire envelope above. The replacement must pass the same declared checks. Original responses and each review remain unchanged; a retry starts without prior review. Export edits do not write back to the store.
