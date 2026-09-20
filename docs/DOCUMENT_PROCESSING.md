# OCR and large documents

The shared document engine prepares sources for every CLI/API reader. DOCX, XLSX,
CSV/TSV and text extraction follow [the format guide](SOURCE_FORMATS.md). PDF OCR
and bounded reading use the same implementation from Codex and Claude Code.

## Local OCR

Run `ocr_setup.cmd` once on Windows to install Tesseract and Norwegian
language data. This downloads software/language data, never source documents.
English is included in the installer. The script checks the downloaded Norwegian
language file against a pinned SHA-256. Restart the host; `show_setup` reports the
OCR version and available languages. Alternatively install Tesseract yourself and
set `SDA_TESSERACT_BIN` if it is outside the standard locations/PATH.

Both MCP import tools accept `ocr_mode` and `ocr_languages`:

- `auto` (MCP default): OCR pages with fewer than 25 non-whitespace extracted characters.
- `force`: OCR every page; useful when scans coexist with digital headers or a poor text layer.
- `off`: use the existing PDF text layer. Legacy Python callers default to off.
- `ocr_languages`: `eng+nor` by default; use `eng` for English-only sources, or other installed Tesseract language codes.

OCR renders physical PDF pages locally at 300 DPI, with a 120-second recognition
timeout per page and a 40-million-pixel rendering limit. No LLM is involved. PDF
originals are never rewritten. A different OCR mode/language creates a new document
record; old runs keep their old extraction. When reimporting, select the returned
document IDs for new runs rather than automatically adding every project document.

Extraction profiles record OCR pages, engine version, requested languages and DPI.
Quotes are checked against the OCR transcription. Verify important quotations,
numbers and table layouts against the original page image. Auto detection is a
sparse-text heuristic, not a guarantee that every embedded image is covered. OCR
does not interpret charts or photographs. Blank/unreadable pages remain visible;
an absent-text answer cannot claim full coverage while such pages remain.

## Bounded reading

New plans record these `engine_settings` for every engine:

```json
{
  "document_processing": "auto",
  "input_budget_bytes": 60000,
  "max_chunks": 100
}
```

The budget measures serialized UTF-8 request bytes (including instructions and
schema). It is a conservative, provider-independent size control, **not an exact
token count or a guarantee for every model**. Choose it with room for the selected
model's output/reasoning budget and provider overhead. Single requests within the
budget follow the existing one-call workflow. `single` refuses oversized input.
Previously approved plans retain single-call behaviour; create a new plan version
to enable bounded reading.

For a larger source:

1. Group source units within the input budget. Split an oversized unit by character
   range, retaining its original ID and up to 200 characters of overlap. No text is
   silently dropped. Instructions/metadata too large for the budget cause an error.
2. Each fresh reader call extracts relevant quotations, qualifications and findings
   for every criterion. It makes no final whole-document classification. All units
   in every chunk must be acknowledged; quotations must occur in that chunk.
3. One synthesis call applies the criteria to all checked findings. It must preserve
   contradictions and avoid double counting overlaps. Final evidence must be among
   the checked quotations for that criterion and pass the usual source validation.

One source file still produces one run and one final assessment per criterion.
`show_plan` shows expected call counts; `show_input_package` shows exact extraction
requests, fragment ranges and the synthesis instruction before approval. The exact
synthesis request necessarily depends on intermediate answers; it is saved before
that call. `timeout_seconds` applies to the document across its reading stages.

Partial coverage, invalid evidence, interruption or failure prevents a completed
result. An absence answer is rejected if chunk evidence or unresolved chunk notes
contradict it. If the collected findings exceed the synthesis budget, execution stops
with the intermediate work preserved; increase the budget or narrow the criteria
in a new plan. There is no silent truncation, recursive summarization, retry or
engine change. Retrying starts a new complete attempt and can incur new usage.

Chunking can lose context relevant to cross-section interpretation, detailed counts
or calculations. Acknowledged coverage proves which input was supplied and reported
read, not that every relevant fact was understood. Human review remains necessary.
The local checks establish orchestration and validation, not model accuracy.

## Inspect the audit trail

Start with the exported `plan-summary.md`, `results.csv` and `evidence.csv`.
`forsok/<attempt>/input.json` describes the source inventory and planned calls;
it explicitly marks a chunked source as not sent in one request. Under
`forsok/<attempt>/calls/`, each stage retains its exact `input.json`, raw answer and
manifest with parameters, request hash, reported model and usage. The final stored
coverage is aggregated from extraction calls; the raw synthesis answer retains an
empty `sider_lest` because synthesis reads findings rather than the original source.

OCR implementation follows [Tesseract's CLI](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html)
and [PDFium rendering](https://pypdfium2.readthedocs.io/en/stable/python_api.html).

## User priorities and reader judgment

Ask which file challenges are expected and which sections, terms or worksheets matter most. `priority_terms` matches source text; `priority_locations` matches source locators (for example worksheet names or PDF page labels). Both accept lists of strings and are stored in the plan. Matches reorder chunk calls, with original order retained for ties. Full coverage still includes every fragment. Priorities do not remove appendices or shorten the total read.

Use `additional_instructions` for substantive interpretation and reporting preferences. An agreed scope reduction is a separate decision: prepare an explicitly scoped, traceable derivative and preserve the original. Do not quietly skip chunks, change models or infer an exact count from incomplete findings. The host can propose conversion, external extraction or a revised budget; changed analysis instructions require a new plan and approval. Worker calls remain bounded and use only their supplied source or checked findings.

`inspect_source` provides source-unit previews and an optional complete Markdown inspection copy. Markdown aids inspection; the original file and extracted unit IDs remain the evidence reference. OCR and extraction can lose content, and automatic validation cannot prove semantic completeness.
