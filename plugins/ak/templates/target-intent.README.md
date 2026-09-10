# `target-intent/` — what the new system must be

Everything in this folder is a statement about **the system being built**, not about the
one being replaced. Two kinds of record live here, and they are the same kind of thing:

- **Scope decisions** — which screens, reports, tables and rules the replacement will
  and will not include.
- **Change requests** — a rule that changes, a screen that goes away, a feature that did
  not exist before.

Any format: `.md`, `.txt`, `.xlsx`, `.drawio`, `.pdf`, `.png`. A marked-up drawing is a
perfectly good scope record; if it has no text layer, transcribe the marks into a `.md`
beside it and say that is what you did.

## Each file must name who decided, and when

```markdown
| Decided by | 山田 太郎 (customer) |
| Decided on | 2026-09-08 |
| Source | A06_Scope.drawio.pdf, screens marked X |
```

Same requirement as `interviews/`, for the same reason: a scope decision that cannot be
taken back to whoever made it cannot be revisited when it turns out to cost something.
A record with no attribution is read as a draft and carries no weight.

## What this evidence can and cannot do

It settles **SCOPE** claims — what the replacement includes — and **nothing else**.

It cannot tell the kit what a legacy table means, what a screen does, what an operator
uses it for, or why it was built that way. That is rule **EC-07**, and it is total on
purpose: a customer deciding a screen is out of scope has said nothing about what that
screen does.

Most real records say both things at once. *"Drop the six 累積 screens, they are only
used at month end"* is a scope decision **and** a usage claim about the legacy system.
The scope half belongs here. The usage half is an **INTERVIEW** — ask them, write it
down in `interviews/`, name them and date it. Splitting the two is the point: the
decision stands even if the reason turns out to be wrong, and the reason has to be
checkable separately.

## What it changes about the run

Phase 6 degrades without it: the roadmap covers everything the legacy application does,
so a project that has already dropped screens reads as though it had not. Phases 1 to 5
describe the legacy system and are unaffected — scope does not change what the old thing
is.

## Why this is not in `decisions/`

`decisions/` holds `glossary.yaml` and `meanings.yaml`: two files the kit writes for you
to edit, and reads back by name. Dropping a free-form scope record beside them would
make one directory mean two things, which is exactly the confusion that left A06's first
two scope records sitting in the workspace, read by nothing.
