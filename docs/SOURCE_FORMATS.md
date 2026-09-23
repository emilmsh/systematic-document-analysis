# Comparable sources, one shared analysis routine

Systematic Document Analysis applies the same versioned criteria, interpretation rules, reader settings and review procedure to a list of comparable files. File format determines how content is extracted and referenced; it does not define the research question.

Before approval, inspect `show_plan` source profiles. Agree what one file represents, which common sections or fields matter, what counts as missing information and how structural exceptions should be treated. Matching extensions or column names alone do not establish substantive comparability. The current execution unit is one whole file; selecting individual workbook rows or sheets as separate runs is future work.

| Format | Included | Source reference |
|---|---|---|
| PDF | Extracted text and optional local Tesseract OCR; missing-text and OCR provenance checks | Physical page |
| DOCX | Main-body paragraphs and tables, including nested tables | Body block and table row/cell path |
| XLSX | Non-empty cells on all worksheets, including hidden sheets and rows; formulas and available cached results | Worksheet and cell range; individual cell addresses preserved |
| CSV / TSV | Non-empty records including the first record; values stay text | Record number and column positions |
| TXT / Markdown | Non-empty text lines; Markdown is source text | Original line number |

Text/CSV uses UTF-8 (optional BOM) or BOM-marked UTF-16. CSV delimiter detection supports comma, semicolon, tab and pipe, and refuses ambiguous input. A quoted multiline CSV record counts as one record. No source file is edited. Imported copies retain the original extension and hash; format is part of import deduplication.

Word pagination is not inferred. Headers, footers, footnotes, comments, tracked-change wrappers, text boxes and images are outside the current DOCX extractor. Workbook charts, images, comments and embedded objects are outside the XLSX extractor. Formula caches may be missing or stale; formulas are never executed or recalculated, and external links are not followed. Excel numeric values are not the same as their formatted display (for example percentages); number formats accompany ordinary cell values in the input metadata. Old binary DOC/XLS, XLSM, presentations, images and other formats are unsupported and produce an explicit error when selected.

Extraction scope and structural summaries are stored with the imported file, shown in the plan and preserved in input/exports. Read coverage refers to extracted units within this stated scope. A missing formula cache, omitted object or structural mismatch must not be interpreted as a substantive negative finding. Agree how to handle uncertain answers in the task.

## Traceability

Each extracted unit has a stable ID and a locator within the preserved source. Optional `quote_checks` resolve declared unit fields to locations and test exact substrings against extracted text. Matching a quote does not establish that it supports a conclusion or exactly matches a rendered page. Detail sheets retain the declared source locations.

Internal fields such as `sider` and `antall_sider` represent source units for non-PDF files. Extraction metadata records scope and limitations. Use `inspect_source` for previews or a complete Markdown inspection copy with original locators.

One worker handles each whole file. Large CLI input uses the original file and source-unit map; oversized API input fails explicitly. Describe substantive reading priorities in the task instruction. See [document processing](DOCUMENT_PROCESSING.md).

Parser behaviour follows [python-docx document iteration](https://python-docx.readthedocs.io/en/latest/api/document.html) and [openpyxl workbook loading](https://openpyxl.readthedocs.io/en/3.1/tutorial.html#loading-from-a-file).
