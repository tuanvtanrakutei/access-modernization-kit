# Question list contract

<!--
  This is not a document anybody writes. `$ak decisions` generates `{{APP_ID}}_QuestionList.md`
  and `{{APP_ID}}_DecisionQueue.json` from the identifier register, and this file records what
  they are FOR and the rules a change to `scripts/build_decisions.py` must not break.

  It replaces a skeleton an agent filled in by hand at the end of a run. That list numbered
  its questions independently of the register, and one run's reused Q3, Q4 and Q5 for different
  questions than the ones the register already held (backlog A12). A list generated from the
  register cannot do that, because it has no numbers of its own.
-->

## Who reads it

**A person does**: the developer relaying questions to the customer and settling decisions for
the new system, and the party each agenda is addressed to. `{{APP_ID}}_DecisionQueue.json` is
for agents and sits beside the other registers.

## What it holds

One agenda per party, in the order to work through it:

- **Blocks work now** - items with no default. What they name waits until they are answered.
- **Work continues on an assumption** - items with a default. The pipeline carries the
  assumption and the answer confirms or corrects it, so these never stop anything.
- **Waits behind another item** - an item whose answer depends on another being settled first.

Then what the machine already did for the person: items **already with the customer** (posted
to the Q&A register and still open), items the customer **answered and nobody has recorded**,
Q&A rows open with the customer that **no item names**, and everything **closed**, by who
closed it - a person, a decision, or the bundle answering on its own.

## Rules

1. **Everything comes from the register.** Edit the register (or answer an item), never the
   file. A QuestionList.md that this command did not write is never overwritten without
   `--replace-handwritten`.
2. **No date, no timestamp.** The same register gives the same bytes, so a change to either
   output is a change to the register and can be diffed in git.
3. **An item with a default never waits.** Only an item with none is blocking, and it blocks
   only the objects it names.
4. **Dependencies first.** An answer that settles another item is asked before it. Among
   items free to go: blocking before proceeding, then what unblocks others, then the
   severity of the risk an item is or the risks it names, then how many things it names.
5. **Do not ask what has been asked.** An item linked to a Q&A row (`--link Q5=5`) is read from
   the customer's register, fresh each time, not from the snapshot `$ak interviews` stored.
6. **Names, not numbers.** Every identifier in a block list carries its title, and an `F-`
   always carries its whole name (ID-06).
7. **The decider's list is the same list.** A DISPOSITION, SCOPE or POLICY belongs to the
   `decider` and is rendered in its own section, last. Every open risk is one of them: its
   Mitigation is the default, and `$ak decisions --decide` is where the decider answers them.
8. **Policy before instance, and nothing disappears.** A risk whose class a decided rule in
   `policy.yaml` covers is settled by it and is not asked - and it is still listed, under
   "Settled by standing policy", with the rule that settled it. A proposed rule settles
   nothing; the list says which items it would take off the agenda.
