---
name: seed-fault
description: Break the pipeline on purpose to prove a test and the hook catch it, record the evidence, then restore. Use when asked to seed a fault, break something deliberately, or check that a test can fail.
allowed-tools: Read, Edit, Bash(make*), Bash(git status*), Bash(git diff*), Bash(git add*), Bash(git commit*), Bash(git checkout -- src/*)
---

# Working tree

!`git status --short`

# Seeding a fault: $ARGUMENTS

1. Stop if the working tree above is not clean; a fault must be the only change.
2. Make the single smallest edit under `src/` that produces the fault described; never edit `tests/` and never touch `data/raw/`.
3. Run `make test`. Save the red output and any hook feedback received after the edit, verbatim.
4. Commit only the fault with message `Seed fault: <description>`.
5. Append a section to `docs/SEEDED_FAULTS.md` with the git diff, the `make test` output, and the hook stderr, pasted not paraphrased.
6. Restore: fix the fault in `src/` (or `git checkout --` the file), run `make test` until green, and commit with message `Fix fault: <description>`.

If `make test` stays green after the fault, say so plainly and stop before step 4. A fault no test catches is the finding: restore the file, name the missing test, and recommend writing it first. Do not weaken or delete a test to make a fault show up.
