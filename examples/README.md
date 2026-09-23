# Example gallery

Use the same analysis workflow for different kinds of comparable material. Each folder contains editable, **fictional** source files, draft criteria and English/Norwegian start prompts. These are optional demonstrations; ordinary work starts with your own documents.

| Use case | Files | What to discuss before reading |
|---|---|---|
| [Policy reports](01-policy-reports/README.md) | Text PDF, scanned PDF, long appendix | OCR quality, qualifications far from the headline, whole-file reading |
| [Supplier offers](02-supplier-offers/README.md) | DOCX with tables | Contractual guarantees versus targets; exceptions |
| [Project portfolio](03-project-workbooks/README.md) | XLSX with formulas and hidden sheets | Formula caches, decision logs, scope |
| [Consultation analysis](04-consultation-notes/README.md) | English Markdown and Norwegian text | Conditional support, source language and reporting language |
| [Incident registers](05-incident-registers/README.md) | CSV and TSV | Multiline records, missing data, policy versus individual action |

Import only a case's `documents/` folder, then discuss its criteria with the assistant. Choose a real CLI or API reader when ready; there is no required simulation step. Document difficulty and likely failure modes are part of the planning conversation. Priorities change reading order; narrowing the source scope requires a visible, agreed decision.

The generator `bin/build_examples.py` reproduces the bundled files using development dependencies. It is not needed to use them. Real public annual reports are separately listed in [the source manifest](../eksempler/arsrapporter-2024/kilder.json); they are not bundled in the release.
