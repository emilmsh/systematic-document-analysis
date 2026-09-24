# One task across selected files

Systematic Document Analysis applies one versioned task and reader configuration independently to each selected file. The task can be any repeatable work the chosen reader can perform; file format determines what the plugin can extract automatically.

Before approval, inspect `show_plan` source profiles. Agree what one file represents, the result variables and how unreadable or missing content should be reported. The execution unit is one whole file; selecting individual workbook rows or sheets as separate runs is future work.

| Format | Included | Source reference |
|---|---|---|
| PDF | Extracted text and optional local Tesseract OCR; missing-text and OCR provenance checks | Physical page |
| DOCX | Main-body paragraphs and tables, including nested tables | Body block and table row/cell path |
| XLSX | Non-empty cells on all worksheets, including hidden sheets and rows; formulas and available cached results | Worksheet and cell range; individual cell addresses preserved |
| CSV / TSV | Non-empty records including the first record; values stay text | Record number and column positions |
| TXT / Markdown | Non-empty text lines; Markdown is source text | Original line number |
| Other files | Original bytes are preserved without automatic extraction; a file-capable CLI worker may inspect the assigned copy | Original file; no extracted text locator |

Text/CSV uses UTF-8 (optional BOM) or BOM-marked UTF-16. CSV delimiter detection supports comma, semicolon, tab and pipe, and refuses ambiguous input. A quoted multiline CSV record counts as one record. No source file is edited. Imported copies retain the original extension and hash; format is part of import deduplication.

Word pagination is not inferred. Headers, footers, footnotes, comments, tracked-change wrappers, text boxes and images are outside the current DOCX extractor. Workbook charts, images, comments and embedded objects are outside the XLSX extractor. Formula caches may be missing or stale; formulas are never executed or recalculated, and external links are not followed. Excel numeric values are not the same as their formatted display (for example percentages); number formats accompany ordinary cell values in the input metadata. Old binary DOC/XLS, XLSM, presentations, images and other formats are preserved but not automatically parsed. An API reader cannot process such an opaque file here; it fails before dispatch. A file-capable CLI worker can attempt the task on its assigned original, and any lack of extraction stays visible.

Extraction scope and structural summaries are stored with the imported file, shown in the plan and preserved in input/exports. Read coverage refers to extracted units within this stated scope. A missing formula cache, omitted object or structural mismatch must not be interpreted as a substantive negative finding. Agree how to handle uncertain answers in the task.

## Traceability

Each extracted unit has a stable ID and a locator within the preserved source. Optional `quote_checks` resolve declared unit fields to locations and test substrings against extracted text. When only whitespace differs, a quote can be restored from the sole source span with the same non-whitespace tokens. Ambiguous matches and changed wording fail. The raw reply, original and restored quote, unit, span, source-text hash and rule remain in the attempt audit; the derived result is identified as `source_whitespace_repair`, never as human review. Matching a quote does not establish that it supports a conclusion or exactly matches a rendered page. Detail sheets retain the declared source locations.

Internal fields such as `sider` and `antall_sider` represent source units for non-PDF files. Extraction metadata records scope and limitations. Use `inspect_source` for previews or a complete Markdown inspection copy with original locators.

One worker handles each whole file. Large CLI input uses the original file and source-unit map; oversized API input fails explicitly. Describe substantive reading priorities in the task instruction. See [document processing](DOCUMENT_PROCESSING.md).

Parser behaviour follows [python-docx document iteration](https://python-docx.readthedocs.io/en/latest/api/document.html) and [openpyxl workbook loading](https://openpyxl.readthedocs.io/en/3.1/tutorial.html#loading-from-a-file).
