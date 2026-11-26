# Bikeshare demand: methodology report

Forecasting daily Capital Bikeshare rides (`cnt`) for 2012 from 2011, with
calendar, weather and lagged-demand features. Train is 2011 (348 days),
validation is H1 2012 (182 days), test is H2 2012 (184 days). Every number
below is from `make all` on the final commit and matches
`reports/metrics.json` to the printed digit.

## Results

"Before" is the unmodified starter (14 features). "After" adds one feature,
`cnt_roll_std_7`: the standard deviation of `cnt` over the 7 calendar days
before the day being predicted (15 features). The baselines do not use the
feature, so their rows do not move.

| Model | Feature set | Valid R² | Valid MAE | Test R² | Test MAE |
|---|---|---|---|---|---|
| baseline_mean | before | -0.9318 | 2002.2 | -2.1441 | 2847.7 |
| baseline_mean | after | -0.9318 | 2002.2 | -2.1441 | 2847.7 |
| baseline_persistence | before | 0.4507 | 900.6 | 0.5099 | 840.1 |
| baseline_persistence | after | 0.4507 | 900.6 | 0.5099 | 840.1 |
| ridge | before | 0.6475 | 832.9 | 0.5833 | 947.1 |
| ridge | after | 0.7224 | 700.4 | 0.6356 | 840.3 |
| hgb | before | 0.2185 | 1296.6 | -0.4975 | 1972.6 |
| hgb | after | 0.0977 | 1381.6 | -0.6959 | 2108.4 |

MAE is in rides per day. The committed `reports/metrics.json` is the
"after" pipeline, untransformed.

Verification behind the table: `make test` runs 17 tests (14 from the
starter, 3 added). Four faults were seeded on purpose; two of them passed
the starter's suite untouched and now fail it. The evidence is in
`docs/SEEDED_FAULTS.md`. `agent/audit.py` on this repo reports no leakage,
a valid temporal split, both baselines reported, and no findings
(`reports/audit.jsonl`); I agree with it and changed nothing in response.

## Headline finding

A ridge regression on lagged demand, weather and calendar features reaches
test R² 0.6356 (MAE 840.3 rides), against 0.5099 (MAE 840.1) for predicting
yesterday's count and -2.1441 for predicting the 2011 mean. So the honest
size of the result is 0.13 R² better than doing nothing clever, with no
improvement in typical error. Gradient boosting on the same features scores
-0.6959 on test: it still beats the mean baseline comfortably (-2.1441) but
loses badly to persistence, because ridership grew about 60% from 2011 to
2012 and a tree cannot predict above the largest value it was trained on.
The 2011 maximum is 6,043 rides, 56.5% of test days are above it, and the
booster's largest test prediction is 5,564. A negative R² and losing to the
baseline are different facts here: hgb is negative and beats the mean
baseline; ridge is positive and only narrowly beats persistence.

What my feature changed: `cnt_roll_std_7` raised ridge validation R² from
0.6475 to 0.7224 and lowered hgb's from 0.2185 to 0.0977. I kept it, because
the ridge gain is well above the 0.01 floor in the `new-feature` skill and
its input is known before the day being predicted; the hgb drop is reported
rather than hidden.

## Exercise 4: target transformation

**Transformation.** Fit each model on `cnt / cnt_roll_7`, the day's rides
relative to the mean of the previous seven days, then multiply the
prediction back by `cnt_roll_7` and score in rides. It lives behind a flag
(`python -m src.train --target-transform ratio`), prints validation only by
default, and never writes `reports/metrics.json`.

**Chosen on validation.** These numbers were committed before the test set
was read:

| Model | Valid R² untransformed | Valid R² ratio | Valid MAE untransformed | Valid MAE ratio |
|---|---|---|---|---|
| ridge | 0.7224 | 0.6128 | 700.4 | 857.3 |
| hgb | 0.0977 | 0.7483 | 1381.6 | 685.5 |

The tree goes from far behind ridge to slightly ahead of it. The mechanism
is the one in the headline: the ratio stays near 1 in both years, so the
tree is no longer asked to predict a level it has never seen.

**Test, touched once.** After that commit I ran the flag once with
`--with-test`: hgb-ratio scores test R² 0.6280 (MAE 832.8), against
untransformed ridge at 0.6356 (MAE 840.3) and persistence at 0.5099
(MAE 840.1). Ridge under the same transform falls to 0.1977 on test. I
changed nothing after seeing these numbers.

**Is it defensible?** Partly. The divisor is known before the day being
predicted, the transform is a standard way to remove a level, and it was
selected on validation with test read once. That part is defensible. What
is not is the comparison it invites: I went looking for a transformation
because one model was losing, I tried one, and it helps the tree while
hurting ridge. Reporting "hgb 0.628" beside "ridge 0.636" as if both had
been given the same treatment would be a way to win the comparison. The
fair statement is that the tree competes once the trend is removed and
still does not beat untransformed ridge, and that a simple "last week's
average times a constant" baseline already gets validation R² 0.5947 under
this transform, so most of the rescue comes from the divisor, not the tree.
The pipeline of record stays untransformed.

## Exercise 5: ridge vs persistence

On the final pipeline ridge beats "yesterday again" on test R² (0.6356
against 0.5099) and ties it on MAE (840.3 against 840.1 rides). I would not
deploy ridge over persistence as it stands. R² and RMSE (1,051 against
1,219) reward ridge for avoiding large misses, which is real: it does not
repeat yesterday's collapse the day after a storm. But on a typical day it
is worse. Its median absolute error is 743 rides against 507 for
persistence, it is the closer of the two on only 43.5% of test days, and it
under-predicts by 372 rides a day on average because it was fit on 2011
levels, while persistence is unbiased (+16). Dropping the two Hurricane
Sandy days does not change the picture (ridge MAE 809, persistence 819).
An operator rebalancing bikes cares about the typical day and about a
forecast that is not systematically low, and persistence costs nothing to
run. Ridge is worth deploying only after its bias is fixed, for example by
refitting on a rolling window, and that is a change I have not tested.
These test-set comparisons were computed after all modelling choices were
final and were not used to change anything.

## Attribution

**Model:** all agent-written code in this repository came from
`kimi-k2.7-code` (open weights, 1.04T parameters, 256K context, hosted on
Ollama cloud), driven by Claude Code 2.1.138. I switched
models once: I started on `qwen3.5:9b` via local Ollama with a 64k context,
which took about ten minutes per turn on a 16 GB laptop and produced no
committed change. A second assistant was also involved and is not
open-weight: I used Claude Fable 5.2 in the Claude desktop app to operate
the session. It wrote the prompts given to the agent, ran the agent in
headless mode (`claude -p`), re-ran every reported number, captured the
test and hook output, made the commits, and drafted the documentation
listed below. It did not write the pipeline or test code.

**Generated by the agent (`kimi-k2.7-code`):**

- `tests/test_leakage.py`: `test_rolling_std_excludes_today`,
  `test_weather_encoder_rejects_unknown_labels`
- `src/features.py`: the `cnt_roll_std_7` line, and the fixes for seeded
  faults 1 to 3
- `tests/test_contract.py`: `test_every_raw_column_is_classified`;
  `src/config.py`: `RAW_INPUT_COLS`
- `src/train.py`: `fit_and_score_ratio` and the argparse flags; the fault 5
  seed and fix
- `.claude/skills/seed-fault/SKILL.md` (text from my spec; saved by hand
  because the harness blocks agent writes under `.claude/`)
- the `cnt_roll_std_7` line in `docs/DECISIONS.md` and the Fault 5 section
  of `docs/SEEDED_FAULTS.md` (its test-output block was later replaced
  with directly captured output)
- `reports/audit.jsonl` (the auditor's answer, run through `agent/audit.py`)

**Drafted by Claude Fable 5.2 as operator, reviewed by me:** this report,
`docs/SEEDED_FAULTS.md` (assembled from captured output), the remaining
lines of `docs/DECISIONS.md`, the `CLAUDE.md` and `.gitignore` edits, and
the commit messages.

**How far the agent could be trusted.** In four of roughly twenty runs the
agent's reply described work on a different project (a smart-home guide, a
cookie-security test, paths under other home directories); permissions
blocked every out-of-repo access and one run crashed. It once skipped
`make test` after writing a test, and its `seed-fault` run altered two
lines of previously pasted evidence. Nothing it reported was accepted
without re-running it.

**Decisions that were mine** (each is a line in `docs/DECISIONS.md`):

- What to predict, what counts as leakage, how to split, which baselines:
  kept from the starter (its five lines), unchanged.
- Keep `cnt_roll_std_7`.
- Switch the agent from the local model to a hosted one.
- A seeded fault that leaves the suite green gets a test before a fix.
- Classify raw columns with an allowlist so a new column fails loudly.
- Do not implement the raw-file hash check; name it instead.
- Add the `seed-fault` skill, and capture evidence from commands rather
  than agent replies.
- The ratio transform is defensible as a method but not adopted as the
  pipeline; the test set was read once for it.
- Whether the answer is believable: ridge's edge over persistence is real
  in R² and absent in MAE, and I would not deploy it as is.
