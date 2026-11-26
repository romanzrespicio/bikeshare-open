# Audit (Exercise 3)

## What was audited

I have no teammate for this assignment, so there is no teammate repository
to audit. Instead I audited a separate copy of the starter in which I
planted three faults, so the auditor's answer could be checked against a
known one.

- Repository: `bikeshare-audit-target` (https://github.com/romanzrespicio/bikeshare-audit-target, private; local
  path `/Users/romanrespicio/bikeshare-audit-target`)
- Commits: `ebb53d8` unmodified starter, `252498f` the planted faults. The
  commit message ("Add demand_index feature and tidy features.py") does not
  name them.
- Planted in `src/features.py`:
  1. `demand_index = 0.5 * casual + 0.5 * registered`, which is `0.5 * cnt`
     under an innocent name;
  2. `.shift(1)` removed from `cnt_roll_7`;
  3. the `raise` removed from `encode_weather`.
- Run: Claude Code 2.1.138, model `kimi-k2.7-code` (Ollama cloud), prompt
  "Use the leakage-auditor subagent to audit this repository: review the
  diff between the first commit and HEAD (git diff HEAD~1 HEAD) against its
  five checks." The subagent made 17 tool calls in 345 seconds: it read the
  diff, `src/` and `tests/`, ran the tests, and ran `python -m src.train`.

## `/leakage-auditor` output, verbatim

````
Audit of `/Users/romanrespicio/bikeshare-audit-target/src/features.py` between `ebb53d8` (HEAD~1) and `252498f` (HEAD).

Check 1 — Target leakage: **FAILED**
- `/Users/romanrespicio/bikeshare-audit-target/src/features.py:76` adds:
  ```python
  out["demand_index"] = 0.5 * out["casual"] + 0.5 * out["registered"]
  ```
- Verified: `casual + registered == cnt` exactly on every row, so `demand_index == 0.5 * cnt`.
- `feature_columns()` excludes only the names in `FORBIDDEN`; `demand_index` is a new numeric column, so it is returned in the model feature list. A model given this column learns the target, not demand dynamics. Remove this line; do not encode the target by combining its components.

Check 2 — Temporal ordering: **FAILED**
- `/Users/romanrespicio/bikeshare-audit-target/src/features.py:74` changed from:
  ```python
  out["cnt_roll_7"] = out[TARGET].shift(1).rolling(LAG_WARMUP).mean()
  ```
  to:
  ```python
  out["cnt_roll_7"] = out[TARGET].rolling(LAG_WARMUP).mean()
  ```
- The rolling window now includes the current day's `cnt`. This is not available at forecast time and is a direct target leak. The comment on lines 69-70 correctly warns that `.shift(1)` is required, but the code no longer follows it.
- `test_rolling_mean_excludes_today` fails because of this.
- Fix: restore `.shift(1)` before `.rolling(7).mean()`.

Check 3 — Calendar gaps: **PASSED**
- `build_features()` calls `reindex_to_calendar()` at line 52 before building lags, and `test_calendar_is_complete_before_lagging` confirms the reindexed calendar has no gaps. Lags mean calendar days.

Check 4 — Silent row loss: **FAILED (latent)**
- `/Users/romanrespicio/bikeshare-audit-target/src/features.py:26-29` removed the guard:
  ```python
  if unknown:
      raise ValueError(f"unmapped weather labels: {sorted(unknown)}")
  ```
- `encode_weather()` now silently maps unknown labels to NaN; `build_features()` then drops those rows via `.dropna()` at line 78 with no warning. The current data has only `GOOD`, `MISTY`, and `BAD`, so tests pass today, but the defensive behavior the docstring advertises is gone. Any future unseen weather label will vanish from the dataset silently. Restore the `ValueError` guard.

Check 5 — Unreported baseline: **PASSED**
- `/Users/romanrespicio/bikeshare-audit-target/src/train.py:49-50` reports both `baseline_mean` and `baseline_persistence`, and `test_persistence_baseline_is_reported` confirms it.

Summary: Checks 1, 2, and 4 fail. The two leaks (`demand_index` restating `cnt` and `cnt_roll_7` including today's `cnt`) would make the ridge and HGB scores look far better than they are and invalidate any model comparison. The weather guard removal creates a latent silent-row-loss hazard.
````

## My verdict

The auditor found all three planted faults and invented none; checks 3 and
5 pass in its report and I agree they should. Two of its findings change a
number and I agree with both. The `demand_index` leak is the large one:
with it, ridge reports validation R^2 0.9999 and test 0.9999 (MAE 12.2)
against the starter's 0.6475 and 0.5833, and the suite does not catch it,
because `test_no_forbidden_features` only checks names in `FORBIDDEN`. The
missing `.shift(1)` also changes a number: on its own it lifts ridge to
validation 0.7758 and test 0.7075, a believable-looking gain that is
entirely today's count leaking into the rolling mean; this one the
starter's `test_rolling_mean_excludes_today` does catch. The third finding
changes no number on this data, since the raw file only contains GOOD,
MISTY and BAD, and the auditor said so itself by labelling it latent. I
agree with the label and would still fix it, but under "report only
findings that change a number" it is a hazard, not a result. Where I part
from the auditor is its summary sentence that the leaks make "the ridge
and HGB scores look far better": it did not quote the scores it saw when
it ran training, so the size of the damage above is my measurement, not
its. One caution on reading this as evidence of auditor quality: I wrote
the faults and the auditor is the same model that wrote the code in my
main repo, so this shows it can find leaks of kinds its checklist names,
not that it would find one nobody thought of.
