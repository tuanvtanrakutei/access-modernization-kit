# Capability Matrix

No extra package is universally required beyond Python 3.10 or newer. Install or enable capabilities only when the manifest and source inventory require them.

| Capability | Required when | Preferred integration | Fallback |
|---|---|---|---|
| Multi-agent runtime | More than one worker is requested | Runtime-native subagent tools | Execute task envelopes sequentially |
| Graphify | App graph, E2E relationship query, or cross-document graph is requested | Graphify skill and CLI | Phase documents and evidence remain valid without graph output |
| XLSX processing | Japanese XLSX sources exist | Spreadsheet skill/runtime | Export worksheets to CSV with cell references preserved |
| PDF text extraction | Japanese PDF sources exist | Runtime PDF/document reader | Local PDF text extractor |
| OCR | PDF/image lacks a text layer | Tesseract or runtime OCR | Mark source unreadable and create an open question |
| HTML visual QA | E2E or Boundary HTML is rendered | Playwright/browser automation | Static HTML validation only |
| PPTX generation | Presentation is requested | Presentation skill/runtime | Produce storyboard only and mark PPTX blocked |
| Live SQL Server | User authorizes live metadata/data access | pyodbc plus Microsoft ODBC Driver | Use exported SQL scripts and table definitions |
| MDB/ACCDB extraction | Access binary is declared and exports are incomplete | Microsoft Access/ACE automation on a copied snapshot | Use existing VBA/SQL/screenshots and mark binary-only areas blocked |
| ADP extraction | ADP project is declared | Compatible legacy Microsoft Access runtime on a copied snapshot | Preserve the ADP and use separately exported VBA/SQL metadata |
| Compilation database | `compile_commands.json` is declared | Built-in read-only normalizer | Inventory the file and mark build-context enrichment unavailable |
| Clang AST | Deep semantic analysis of a supported compiled language is explicitly requested | Clang/libclang | Structural source analysis; not applicable to Access/VBA |
| DOCX | Word artifacts exist | Document skill/runtime | Export to PDF or text while preserving source reference |

Do not install CodeWiki, Neo4j, an OCR stack, pyodbc, Access/ACE, Clang, or a presentation runtime by default. Preflight must report the exact missing capability and the artifact it blocks. CodeWiki patterns are reimplemented as provider-neutral contracts without importing or vendoring that project.
