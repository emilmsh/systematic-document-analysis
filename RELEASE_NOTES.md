# 0.6.0 — Systematic Document Analysis

The plugin is now named **Systematic Document Analysis**, with English primary documentation and workflows for English and Norwegian users. One Windows ZIP supports Codex and Claude Code.

- Select English (`en`) or Norwegian (`nb`) commentary in each plan. Language, model and effort are preserved through inputs, plan history, attempt manifests and exports. Quotes and answer labels remain verbatim.
- English MCP tools and criteria/settings fields accompany the existing Norwegian interface.
- English CSV headers, README and plan summary accompany the preserved audit files. Some technical status codes and diagnostics remain Norwegian; the host explains them in the user's language.
- Existing databases are reused without moving them. Legacy environment variables and tools remain compatible. New installations use the new product name and data directory.

Install with `installer.cmd`, then start a new conversation. When upgrading from OE Kildeanalyse, disable or uninstall the old plugin registration after installing the new one to avoid duplicate MCP servers. This does not delete the separate analysis database. See START_HERE.md or START_HER.md.

Verification: 87 local tests passed; clean MCP bootstrap with 34 English/Norwegian tools, plan language changes, export and restart passed. Fresh installation and repeated update in both CLIs passed using temporary app configurations. No model calls were made. Real provider behaviour and substantive analysis quality were not measured.
