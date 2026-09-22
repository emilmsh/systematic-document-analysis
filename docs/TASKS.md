# One task, repeated over files

The plugin is a controlled for-loop: one versioned task, one independent CLI/API worker per file, preserved inputs and results. Use the host conversation to prepare the task and to interpret or present results afterward. Cross-file synthesis is a derived step, not hidden context passed between workers.

## A small starting point

Call `create_analysis` with `project_id`, `name`, `request`, and an explicit `engine`. Add `model` for APIs. Without `criteria_file`, this creates an instruction-first task. `task_instructions` optionally expands the original request. Choose `language="nb"` or `"en"`.

For example: “For each consultation, extract the exact passages about mandatory annual audits and voluntary self-assessment. Keep their source locations and explain uncertainty.” No yes/no labels or classification criteria are necessary.

The default result is Markdown. The worker chooses a useful structure for the task. The plugin carries it in a wire envelope:

```json
{
  "result": "The actual deliverable in Markdown...",
  "source_units_read": [1, 2],
  "limitations": []
}
```

Only this execution envelope is fixed. It does not prescribe headings, findings or final presentation. Coverage is reported by the worker, not proof of understanding. The default checks the envelope and nonempty result, and reports coverage/limitations. It does not validate quotations embedded in arbitrary Markdown or guarantee semantic correctness.

## Optional task-defined structure and checks

`output_schema` describes **result**, not the envelope. It can describe a string, array, object or other JSON value. For portable structured output, use inline schemas, closed objects (`additionalProperties: false`) and list all object properties in `required`; nullable fields represent missing values. Incompatible contracts are rejected rather than silently tightened. Actual provider schema support can still vary; a provider rejection is recorded without fallback.

This example is one possible extraction contract, not a built-in task profile:

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

Use `new_plan_version` to change instructions, schemas or quote checks. `quote_checks=[]` clears checks; `reset_output_schema=true` restores the default Markdown contract. Existing versions and their runs are unchanged. Supplying `criteria_file` creates a legacy coding plan instead; the two specifications cannot be combined.

## Controlled execution, including large files

Preview the plan and selected runs before approval. Every attempt records source identity/hash, exact instruction and source input, result schema, requested settings, raw response, reported telemetry, errors and validation. CLI/API execution uses the existing independent worker path. A failed file does not stop unrelated files, and retries require an explicit reason.

`document_processing=auto` is the default. A file within `input_budget_bytes` uses one call. A larger file is split into bounded source fragments. Each map call receives the same task plus its fragment, extracts task-relevant findings and exact quotes, and reports coverage/limitations. Checked findings from all fragments go to a reduce call with the user's result contract. The plugin deduplicates neither substantive claims nor counts mechanically: the reduce instruction requires source-based deduplication and explicit uncertainty. All intermediate calls and character ranges remain in the audit trail.

The raw reduce response reports no direct source reading; the stored response separately records aggregate map coverage. The validator labels that basis. The same source-unit IDs survive splitting and overlap. Declared final quotes must come from checked map evidence. A failed map call prevents synthesis for that file, while other files continue.

Budgets, `max_chunks` and the document-wide timeout bound the work. Explicit `document_processing=single` disables splitting. Instructions that alone exceed the budget, excessive chunk count or findings that cannot fit the reduce budget produce visible failures with preserved intermediate work; the system never silently discards findings. Revise the plan/budget or task detail and request a new attempt as appropriate. Model context/token limits are not exactly measured by a byte budget.

## Results, review and further work

`show_run` exposes `result` directly. `export_results` writes `results/<run>.md` and `.json`, linked from the start file. JSON preserves the task's structure; Markdown is a generic reading copy. Each result links to the attempt, source hash, plan and audit data. All attempts, raw outputs, validations and reviews are preserved under `audit/`. Source copies are optional; extracted source content remains in exact input/audit records even when copies are omitted.

Use the host to produce a task-appropriate table, report or synthesis from that snapshot. Retain originating run/attempt/plan IDs and distinguish derived work from original worker results. CSV/workbook columns are not imposed on general tasks. Criteria-based analyses retain their existing Excel exporter.

`record_review` can approve or reject a whole task result. To correct it, supply `replacement_response` with the complete wire envelope above. The replacement must pass the same declared checks. Original responses and each review remain unchanged; a retry starts without prior review. Export edits do not write back to the store.
