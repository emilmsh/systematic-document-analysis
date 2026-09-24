# OCR and large documents

The shared document engine prepares sources for every CLI/API reader. DOCX, XLSX,
CSV/TSV and text extraction follow [the format guide](SOURCE_FORMATS.md). PDF OCR
and file preparation use the same implementation from Codex and Claude Code.

## Local OCR

Normal Windows installation (`installer.cmd`) installs missing Tesseract OCR and
verifies both English and Norwegian language data. Existing working OCR is reused.
Missing language files are downloaded from a pinned upstream release, checked with
SHA-256 and stored in the user's local application data, without writing into
Program Files. No source documents are uploaded. `--skip-ocr` is an explicit opt-out.
`installer.cmd ocr` remains available for repair after a cancelled or failed install;
an OCR failure leaves the plugin installed but reports incomplete setup.
`show_setup` reports the OCR version and available languages. An explicit
`SDA_TESSERACT_BIN` overrides automatic executable discovery.

## File tools in local reader sessions

New Claude/Codex plans enable `file_tools` by default. Existing approved plans keep
their recorded settings; enabling tools for one requires a new plan version.
Each reading call starts a fresh CLI session in a new `workfiles` directory with
one original source copy, assigned source units and `SOURCE_GUIDE.md`. The plugin also
writes the extracted units into small, numbered plain-text files under `source-chunks/`
and lists them in `source-index.txt`. Either CLI can use its available tools to inspect
the original, search the copies, and create derived work. No extra MCP tool is installed in
the reader session. These reading copies work regardless of whether the original
is PDF, Word, Excel, CSV or text. `source-units.json` remains the exact evidence map. A source unit larger
than the target chunk size stays whole, so readers may need line-range reads for it.
User and project instructions, memory, plugins, other MCP servers and previous conversations are
disabled. No previous file results are included.

Readers have their respective built-in tools, including shell and web where their CLI offers them.
A bundled Python interpreter and optional helper remain available for PDF, Word, Excel,
CSV/TSV, text/Markdown, PDF page rendering and per-page Tesseract OCR. The worker may
choose another method. Claude runs in safe mode with its default built-in tools and
permission checks bypassed. Codex runs with `danger-full-access` and no approval prompts.
Both still start without inherited user/project instructions, plugins, MCP servers or
previous conversations. Their native tool sets are not identical, and managed policies
may still deny an action. This is context separation, not OS-level file or network isolation.

The source checksum, initial file hashes, workspace guide, helper identity, raw
tool transcript and generated workfiles are retained with the attempt/export.
If the host execution policy blocks Codex CLI shell commands, the plugin marks the
file-reading attempt failed even if Codex returns a schema-valid answer. A successful
`show_setup` checks availability and login, not permission to use the reader's shell.
The original source remains unchanged; changing the working source copy rejects
the result. Export never follows worker-created symlinks or junctions. Omitting
sources from export also omits `workfiles/source.*`; transcripts, OCR and rendered
pages still contain source-derived content, just like recorded text input.

Tool reading can inspect the complete original document and its source-unit map.
The reader chooses a method for the agreed task. For text work it can search the plain-text chunks,
read relevant neighboring chunks, and inspect all chunks when full text coverage is required. A reported list of units read is still a
self-report, not proof of complete reading or semantic accuracy.
The inline byte budget does not cap tool output or total model context. CLI calls
can include multiple tool turns. Visual/OCR findings do not silently change the
approved extraction: quotations absent from it require reimport/review. This
keeps a clear distinction between seeing content and validating exact evidence.

The MCP import tool accept `ocr_mode` and `ocr_languages`:

- `auto` (MCP default): OCR pages with fewer than 25 non-whitespace extracted characters.
- `force`: OCR every page; useful when scans coexist with digital headers or a poor text layer.
- `off`: use the existing PDF text layer. Direct Python imports default to off.
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

## Input limits

Each attempt invokes one worker for the whole file. `input_budget_bytes` defaults to 60000 and measures serialized UTF-8 request bytes including instructions/schema. It is not a token count or a model-context guarantee.

For large CLI input with file tools, the prompt references the complete original and searchable source chunks in the working directory. The worker decides how to read them. For APIs or text-only CLI calls, oversized input fails before dispatch. Increase the agreed budget or choose a file-capable reader; the plugin never silently truncates or changes the task into extraction and synthesis. Instructions/schema must fit the limit in either mode. A CLI session may use multiple internal tool turns; tool output is not capped by the input byte budget.

`show_input_package` previews the actual input mode and request. Exact inputs, raw replies, telemetry and workfiles remain in the attempt and documentation ZIP. Start with Results.xlsx; inspect the archive when provenance is needed. Optional quote checks match preserved extracted text, not images or substantive meaning.

Use task instructions for file-specific priorities. An agreed narrower source scope should be explicit in a new plan, not inferred from an input-size failure. `inspect_source` provides source-unit previews and an optional complete Markdown reading copy.
