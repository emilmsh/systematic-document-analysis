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

Extraction scope and structural summaries are stored with the imported file, shown in the plan and preserved in input/exports. Read coverage refers to extracted units within this stated scope. A missing formula cache, omitted object or structural mismatch must not be interpreted as a substantive negative finding. Agree how to handle uncertain answers in the criteria.

## Traceability and compatibility

Each extracted unit has a stable ID and a locator within the preserved source. The model cites the unit ID; the application resolves its location. Evidence CSV includes `source_format`, `source_unit`, `source_location` and quotations. `physical_page` is populated only for PDFs. Short spreadsheet evidence must match a full cell value rather than a digit in a cell address. A located quote still needs human review to establish that it supports the conclusion.

Existing database fields `sider`, `antall_sider`, `side` and `sider_lest` retain their technical names but represent source units for non-PDF files. Older PDF records and attempt files remain readable. A small additive database migration stores extraction metadata; it does not rewrite existing attempts.

Use `inspect_source` to preview units and optionally save a complete Markdown inspection copy with original locators. New plans split oversized extracted input into bounded reading calls and a synthesis of checked findings. This processing is shared by CLI and API readers. Discuss source challenges and important sections before approval; priority terms and locations alter chunk order while retaining full coverage. See [document processing](DOCUMENT_PROCESSING.md).

Parser behaviour follows [python-docx document iteration](https://python-docx.readthedocs.io/en/latest/api/document.html) and [openpyxl workbook loading](https://openpyxl.readthedocs.io/en/3.1/tutorial.html#loading-from-a-file).
