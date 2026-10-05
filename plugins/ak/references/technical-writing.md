# Technical Writing for Phase Documents

Reader: the agent that writes or revises a phase document. The document itself is read
by a person: a developer who must rebuild the system, reads it once, and is under time
pressure. Catalogues and registers are read by agents and are out of scope here.

Every rule below exists so that this person reads a claim correctly on the first read.
The prose rules are adapted from [SimpleEnglish](https://github.com/AminBlg/SimpleEnglish)
(MIT), which applies ASD-STE100 Simplified Technical English to software documents. The
diagram rules are this kit's own, measured on the A01 reference set and on A06.

`validate_phase_conformance.py` reports the measurable part as the `readability` group,
on the EN document of each phase. That group warns and never fails a run, because the
reference set is the calibration and it does not pass every rule. Treat a warning as a
question to answer, not a defect to hide.

## 1. Choose the form before you write

Use the first form that can hold the claim:

1. A diagram, when the thing has a shape.
2. A table, when the thing is a set of parallel items.
3. Prose, only for what neither can hold: a cause, an argument, an exception, a
   consequence.

A section that describes a picture in prose is a diagram that was not drawn. A06's
Phase 2 carries five diagrams and is shorter than the four-diagram draft it replaced,
because each diagram removed a paragraph.

### Which diagram

| The thing you describe | Mermaid type | What to make visible |
|---|---|---|
| An actor does steps in an order (operator, screen, query, table) | `sequenceDiagram` | The handoffs and the waits between them |
| A decision tree, or a pipeline with a failure branch | `flowchart TD` | The failure node, filled red |
| One object reaches many (a screen writes six tables, a query feeds four reports) | `flowchart LR` | The fan-out, one edge per target |
| Entities and their keys | `erDiagram` | Only the relationships the section argues about |
| A record that moves through states (draft, confirmed, shipped, cancelled) | `stateDiagram-v2` | The transition that the code permits and the business does not |
| A daily or monthly cycle (import, edit, print, close) | `sequenceDiagram` or `gantt` | What must finish before the next step starts |
| Two sources that disagree (a document and the code) | `flowchart LR` with two nodes | Both claims side by side, with the evidence ID on each |
| Hosts, databases, and shares | `flowchart LR` with subgraphs | What reaches what, and over which path |

A required diagram per phase is a floor, not a budget. Draw one whenever the subject
has an order, a cycle, a lifecycle, a fan-out, or a disagreement.

### Rules for each diagram

1. Write one sentence before the diagram that states its claim. "Re-running the morning
   import deletes the quantities that staff typed the night before." The diagram proves
   the sentence. A diagram with no claim is decoration.
2. Keep a diagram to about 15 nodes. If it needs more, split it by phase of the flow and
   link the parts.
3. Use the production name in a node, as the naming convention section requires. If a
   node cannot carry the alias, the naming section must list that name.
4. Put the evidence ID or the BR-, WF-, or DISC- identifier on the node or the edge that
   the claim depends on.
5. Fill the node where it goes wrong: `style X fill:#f8d7da,stroke:#c00`.
6. Make sure that the diagram renders. Run
   `validate_phase_conformance.py --outputs <dir> --render`. A diagram that does not
   render is not evidence that a reader can see.

## 2. Write the prose

These rules apply to EN, VI, and JA. The word limits are for English. The gate measures
EN documents only, because Japanese has no spaces to count words by, and a Vietnamese
word is one syllable. The VI and JA documents translate the EN one, so they inherit its
structure.

1. One sentence, one claim. Descriptive sentences have 25 words at most. Instructions
   have 20 words at most and one action each.
2. Put the condition before the command, with a comma: "If the import file is empty,
   the screen deletes nothing."
3. Use active voice and name the actor: "`受注データ取込` deletes the rows", not "the
   rows are deleted".
4. Use simple tenses. Use the present tense for what the code does. Use the simple past
   for what happened in a run or an interview.
5. Use `can`, `will`, and `must`. Do not use `should`, `may`, `might`, or `would` about
   the system. If the behaviour is not known, say so and give it a `UK-` identifier. A
   hedge hides an unknown that the register must hold.
6. Use one word for one meaning in the whole document. The terms in
   `specifications/ja-en-terms.yaml` are fixed. Do not alternate "order", "slip", and
   "voucher" for one object.
7. Define a concept term at its first use, in fewer than ten words. Do not define product
   names or standard names such as SQL Server or VBA.
8. State the fact, not its importance. Delete "crucial", "robust", "seamless",
   "comprehensive", "it is worth noting", and "in order to".
9. Give each fact before the step that needs it. Name the screen, the table, or the prior
   step that a statement depends on.
10. Write a warning with the condition or command first and the risk second: "Do not run
    `受注データ取込` twice on one day. The second run deletes the manual edits."
11. Use bold only for a label that a reader scans for. Do not use bold as emphasis, and
    do not start a paragraph with a bold phrase.
12. Do not use an em-dash to join two ideas. Write two sentences, or name the relation:
    "because", "but", "for example".

Do not change code, identifiers, quoted error text, production names, or numbers when you
revise prose.

## 3. Check before you publish

1. Run `validate_phase_conformance.py --outputs <dir> --render`. Fix each `content`
   failure. Answer each `readability` warning: fix it, or know why the section needs it.
2. Read the three longest sentences in each section. If one has more than 25 words,
   split it.
3. Search for `should`, `may`, `might`, `would`, and `—`. Replace each hedge with a fact
   or a `UK-` identifier.
4. For each section that has more than 300 words of prose for each diagram, find the
   paragraph that describes a shape, and draw it.
