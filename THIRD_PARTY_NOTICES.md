# Third-Party Notices and Acknowledgements

No third-party source code or binaries are vendored in this repository.

## Architectural inspiration

The V2.1 component-index, hierarchical decomposition, leaf-first ordering, session-isolation, and affected-module-refresh design was informed by publicly visible architectural ideas from `FSoft-AI4Code/CodeWiki`.

CodeWiki is not installed, imported, executed, or included as a runtime dependency. This acknowledgement does not imply endorsement or sponsorship.

The prose rules in `plugins/ak/references/technical-writing.md` and the `readability` group of `validate_phase_conformance.py` are adapted from `AminBlg/SimpleEnglish` (MIT License, Copyright (c) 2026 AminBlg), which applies ASD-STE100 Simplified Technical English to software documents. The rules were reworded for this kit's phase documents. No SimpleEnglish file is vendored, installed, or executed.

The Stage 4 verification tools in `plugins/ak/modernize/scripts` (`screen_parity.py`, `screen_canary.py`, `screen_rule_tests.py`, `screen_rule_ids.py`, `screen_verify.py`) were informed by publicly visible ideas of the `code-modernization` plugin in `anthropics/claude-plugins-official`: a proof built from files a script can check, a deliberate break that the tests must notice, and a rule counted as tested only when a test that ran names it. They were written from scratch for this kit. No file of that plugin is vendored, installed, executed or copied, and this acknowledgement does not imply endorsement or sponsorship.

## Managed and optional external capabilities

Graphify and its declared PDF/Office normalization dependencies are installed on demand into an isolated managed environment when a five-phase investigation is requested. They are not vendored in this repository and remain subject to their own licenses and terms.

Microsoft Access/ACE, Microsoft SQL Server ODBC drivers, browser automation, Tesseract OCR/language data, and presentation runtimes remain conditional external capabilities. They are not bundled and remain subject to their own licenses and terms when installed by a user.
