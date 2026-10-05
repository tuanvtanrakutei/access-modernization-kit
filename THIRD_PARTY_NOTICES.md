# Third-Party Notices and Acknowledgements

No third-party source code or binaries are vendored in this repository.

## Architectural inspiration

The V2.1 component-index, hierarchical decomposition, leaf-first ordering, session-isolation, and affected-module-refresh design was informed by publicly visible architectural ideas from `FSoft-AI4Code/CodeWiki`.

CodeWiki is not installed, imported, executed, or included as a runtime dependency. This acknowledgement does not imply endorsement or sponsorship.

The prose rules in `plugins/ak/references/technical-writing.md` and the `readability` group of `validate_phase_conformance.py` are adapted from `AminBlg/SimpleEnglish` (MIT License, Copyright (c) 2026 AminBlg), which applies ASD-STE100 Simplified Technical English to software documents. The rules were reworded for this kit's phase documents. No SimpleEnglish file is vendored, installed, or executed.

## Managed and optional external capabilities

Graphify and its declared PDF/Office normalization dependencies are installed on demand into an isolated managed environment when a six-phase investigation is requested. They are not vendored in this repository and remain subject to their own licenses and terms.

Microsoft Access/ACE, Microsoft SQL Server ODBC drivers, browser automation, Tesseract OCR/language data, and presentation runtimes remain conditional external capabilities. They are not bundled and remain subject to their own licenses and terms when installed by a user.
