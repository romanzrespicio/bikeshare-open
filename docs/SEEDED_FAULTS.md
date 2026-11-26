# Seeded faults (Exercise 2)

Every block below is pasted output from this repository, not a description.
Agent: `kimi-k2.7-code` via Ollama cloud, driven through Claude Code 2.1.138
in headless mode (`claude -p`). "Turns" is the harness's `num_turns` for the
run that fixed the fault from the single prompt "make test is failing ...
find the cause, and fix it in src/".

Each fault was seeded by the agent with the Edit tool, so the PostToolUse
hook fired inside the harness. "Hook stderr" is the output of
`.claude/hooks/check_leakage.sh` run on the faulted tree with the same
payload the harness sends.

| # | Fault | Red test | Hook | Turns to fix |
|---|---|---|---|---|
| 1 | `casual` appended in `feature_columns` | `test_no_forbidden_features` | exit 2 | 6 |
| 2 | `.shift(1)` deleted from `cnt_roll_7` | `test_rolling_mean_excludes_today` | exit 2 | 6 (second attempt; first run derailed) |
| 3 | `raise` removed from `encode_weather` | none at first; `test_weather_encoder_rejects_unknown_labels` after we added it | silent at first; exit 2 after | 6 |
| 4 | tampered CSV copied into `data/raw/` from Bash | none at first; `test_every_raw_column_is_classified` after we added it | silent (cannot see it) | not an agent fix |
| 5 | `temporal_split` includes `TRAIN_END` in validation | `test_splits_are_ordered_in_time`, `test_no_overlapping_dates` | silent (leakage hook only) | fixed by the agent in the same skill run |

## Exercise 1: the failing test, before the feature existed

`test_rolling_std_excludes_today` was committed (615ae44) before
`cnt_roll_std_7` was implemented (aa8b99f). `python -m pytest tests/test_leakage.py -q --tb=line`:

```
The above exception was the direct cause of the following exception:
E   KeyError: 'cnt_roll_std_7'
/Users/romanrespicio/bikeshare-open/.venv/lib/python3.12/site-packages/pandas/core/indexes/base.py:3648: KeyError: 'cnt_roll_std_7'
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_rolling_std_excludes_today - KeyError: 'cn...
1 failed, 7 passed in 0.84s
```

## Fault 1: a forbidden column added to `feature_columns`

Commits: seeded 1d0d604, fixed 3a25835.

```diff
diff --git a/src/features.py b/src/features.py
index 24aa066..6edc25e 100644
--- a/src/features.py
+++ b/src/features.py
@@ -82,7 +82,7 @@ def build_features(df: pd.DataFrame) -> pd.DataFrame:
 def feature_columns(df: pd.DataFrame) -> list[str]:
     """Numeric columns that are safe to feed the model."""
     numeric = df.select_dtypes(include="number").columns
-    return [c for c in numeric if c not in FORBIDDEN]
+    return [c for c in numeric if c not in FORBIDDEN] + ["casual"]
 
 
 if __name__ == "__main__":
```

`make test`:

```
python -m pytest tests/ -q
.....F.........                                                          [100%]
=================================== FAILURES ===================================
__________________________ test_no_forbidden_features __________________________

feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7 cnt_roll_std_7
0   2011-01-10     10.0  WINTER  ...     1...857     820.919420
713 2012-12-31    731.0  WINTER  ...      920.0  1531.428571     821.327646

[714 rows x 29 columns]

    def test_no_forbidden_features(feats):
        """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
        construction, so this cannot discover a *new* leaky column. What it
        catches is someone editing feature_columns() or FORBIDDEN -- which is
        exactly the fault the Step 7 hook demonstrates."""
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'casual'}
E       assert not ({'atemp', 'casual', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7', 'cnt_roll_std_7', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})

tests/test_leakage.py:31: AssertionError
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
1 failed, 14 passed in 2.48s
make: *** [test] Error 1
make test exit: 2
```

Hook stderr:

```
Leakage tests failed after editing /Users/romanrespicio/bikeshare-open/src/features.py:
feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7 cnt_roll_std_7
0   2011-01-10     10.0  WINTER  ...     1...857     820.919420
713 2012-12-31    731.0  WINTER  ...      920.0  1531.428571     821.327646

[714 rows x 29 columns]

    def test_no_forbidden_features(feats):
        """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
        construction, so this cannot discover a *new* leaky column. What it
        catches is someone editing feature_columns() or FORBIDDEN -- which is
        exactly the fault the Step 7 hook demonstrates."""
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'casual'}
E       assert not ({'atemp', 'casual', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7', 'cnt_roll_std_7', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})

tests/test_leakage.py:31: AssertionError
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
1 failed, 7 passed in 0.59s
hook exit code: 2
```

Fix: 6 turns. The agent ran `make test`, read `src/features.py`, removed
`+ ["casual"]`, and reran the tests (15 passed).

## Fault 2: `.shift(1)` deleted from `cnt_roll_7`

Commits: seeded 247edd0, fixed e8d617c.

```diff
diff --git a/src/features.py b/src/features.py
index 24aa066..3e2574c 100644
--- a/src/features.py
+++ b/src/features.py
@@ -73,7 +73,7 @@ def build_features(df: pd.DataFrame) -> pd.DataFrame:
     # If you add a longer lag, raise LAG_WARMUP in src/config.py.
     out["cnt_lag_1"] = out[TARGET].shift(1)
     out["cnt_lag_7"] = out[TARGET].shift(LAG_WARMUP)
-    out["cnt_roll_7"] = out[TARGET].shift(1).rolling(LAG_WARMUP).mean()
+    out["cnt_roll_7"] = out[TARGET].rolling(LAG_WARMUP).mean()
     out["cnt_roll_std_7"] = out[TARGET].shift(1).rolling(LAG_WARMUP).std(ddof=0)
 
     return out.dropna().reset_index(drop=True)
```

`make test`:

```
python -m pytest tests/ -q
........F......                                                          [100%]
=================================== FAILURES ===================================
_______________________ test_rolling_mean_excludes_today _______________________

feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7 cnt_roll_std_7
0   2011-01-10     10.0  WINTER  ...     1...571     820.919420
713 2012-12-31    731.0  WINTER  ...      920.0  1789.857143     821.327646

[714 rows x 29 columns]

    def test_rolling_mean_excludes_today(feats):
        """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
        by_date = feats.set_index("dteday")[TARGET]
        date = feats.dteday.iloc[200]
        window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
        if all(d in by_date.index for d in window):
            expected = sum(by_date[d] for d in window) / 7
>           assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E           assert np.float64(4389.0) == 4414.857142857143 ± 0.00441486
E             
E             comparison failed
E             Obtained: 4389.0
E             Expected: 4414.857142857143 ± 0.00441486

tests/test_leakage.py:57: AssertionError
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 14 passed in 5.42s
make: *** [test] Error 1
make test exit: 2
```

Hook stderr:

```
Leakage tests failed after editing /Users/romanrespicio/bikeshare-open/src/features.py:
[714 rows x 29 columns]

    def test_rolling_mean_excludes_today(feats):
        """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
        by_date = feats.set_index("dteday")[TARGET]
        date = feats.dteday.iloc[200]
        window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
        if all(d in by_date.index for d in window):
            expected = sum(by_date[d] for d in window) / 7
>           assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E           assert np.float64(4389.0) == 4414.857142857143 ± 0.00441486
E             
E             comparison failed
E             Obtained: 4389.0
E             Expected: 4414.857142857143 ± 0.00441486

tests/test_leakage.py:57: AssertionError
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 7 passed in 3.47s
hook exit code: 2
```

Fix: 6 turns, on the second attempt. In the first attempt the agent ran
`make test`, saw the output above, then described a failing test that does
not exist in this repo (`tests/test_cookie_security.py`), tried to read a
file outside the project (denied by permissions), and the run crashed
after 2 turns with nothing changed. The same prompt rerun restored
`.shift(1)` and passed (15 passed).

## Fault 3: the weather encoder's `raise` removed

Commits: test added be5fa24, seeded 6d6fafa, fixed 77a830e.

```diff
diff --git a/src/features.py b/src/features.py
index 24aa066..792f717 100644
--- a/src/features.py
+++ b/src/features.py
@@ -26,8 +26,6 @@ def encode_weather(series: pd.Series) -> pd.Series:
     """
     known = series.dropna()
     unknown = set(known.unique()) - set(WEATHER_ORDER)
-    if unknown:
-        raise ValueError(f"unmapped weather labels: {sorted(unknown)}")
     return series.map(WEATHER_ORDER).astype(float)
```

**First seeding: nothing went red.** The raw data only contains GOOD, MISTY
and BAD, so removing the raise changes nothing the starter's tests look at.
`make test`:

```
python -m pytest tests/ -q
...............                                                          [100%]
15 passed in 2.43s
make test exit: 0
```

Hook stderr (empty):

```
hook exit code: 0
```

A suite that stays green under a seeded fault is not checking that fault,
so we reverted the fault and added `test_weather_encoder_rejects_unknown_labels`
to `tests/test_leakage.py` (it feeds the encoder the label `STORMY` and
expects `ValueError`). Seeded again, `make test`:

```
python -m pytest tests/ -q
..........F.....                                                         [100%]
=================================== FAILURES ===================================
_________________ test_weather_encoder_rejects_unknown_labels __________________

    def test_weather_encoder_rejects_unknown_labels():
>       with pytest.raises(ValueError):
             ^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE ValueError

tests/test_leakage.py:71: Failed
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_weather_encoder_rejects_unknown_labels - F...
1 failed, 15 passed in 2.87s
make: *** [test] Error 1
make test exit: 2
```

Hook stderr:

```
Leakage tests failed after editing /Users/romanrespicio/bikeshare-open/src/features.py:
......F..                                                                [100%]
=================================== FAILURES ===================================
_________________ test_weather_encoder_rejects_unknown_labels __________________

    def test_weather_encoder_rejects_unknown_labels():
>       with pytest.raises(ValueError):
             ^^^^^^^^^^^^^^^^^^^^^^^^^
E       Failed: DID NOT RAISE ValueError

tests/test_leakage.py:71: Failed
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_weather_encoder_rejects_unknown_labels - F...
1 failed, 8 passed in 0.59s
hook exit code: 2
```

Fix: 6 turns. The agent restored the raise with a slightly different
message (`Unknown weather labels: ...`); behaviour is the same (16 passed).

## Fault 4: a copy into `data/raw/` from Bash

The tampered file is the raw CSV plus one column, `demand_index`, equal to
`cnt`: a leaked target under an innocent name.

**What happened, in order.**

1. `cp data/processed/tampered.csv data/raw/bike_daily.csv` from the
   agent's Bash tool was **denied** by Claude Code 2.1.138, even with
   `Bash(cp:*)` allowed. Agent's reply, verbatim: "Permission to use Bash
   with command cp data/processed/tampered.csv data/raw/bike_daily.csv has
   been denied." The raw file's hash was unchanged. This version of the
   harness appears to apply the `data/raw/**` deny rules to a plain `cp`,
   which is stricter than the lesson describes.
2. The same copy as a Python one-liner went straight through:
   `python -c "import shutil; shutil.copy('data/processed/tampered.csv', 'data/raw/bike_daily.csv')"`.
   Agent's reply, verbatim: "The command completed silently with no output,
   no hooks, and no errors." The raw file's sha256 changed from
   `a6bed1577f6e4de5...` to `9e42ea93f64ec224...`.
3. Nothing noticed. `make test`:

```
python -m pytest tests/ -q
................                                                         [100%]
16 passed in 2.85s
make test exit: 0
```

Hook stderr (empty; PostToolUse matches `Edit|Write`, and this was Bash):

```
hook exit code: 0
```

4. `make all` then reported a near-perfect model, because `demand_index`
   is numeric and not in `FORBIDDEN`, so `feature_columns` let it in:

```
OK ingest: 728 rows, 2011-01-03 -> 2012-12-31
python -m src.features
OK features: 714 rows, 16 features -> features.parquet
  temp, atemp, hum, windspeed, demand_index, dayofweek, is_weekend, is_holiday, is_workday, month_sin, month_cos, weather_severity, cnt_lag_1, cnt_lag_7, cnt_roll_7, cnt_roll_std_7
n_features 16
{'ridge': {'valid': {'r2': 0.9999, 'mae': 10.5}, 'test': {'r2': 0.9999, 'mae': 12.6}}, 'hgb': {'valid': {'r2': 0.6891, 'mae': 593.8}, 'test': {'r2': 0.3933, 'mae': 1013.3}}}
```

**What would have caught it.** Not the PostToolUse hook: it only fires on
Edit and Write, and only runs the leakage tests. Any of these would:

- a hash check on `data/raw/bike_daily.csv` in `make data` (or in
  `load_raw`), which fails the moment the bytes change, whatever changed them;
- a filesystem permission (`chmod -w data/raw`), which stops the write itself;
- a PreToolUse hook on Bash that rejects commands mentioning `data/raw/`,
  which is only as good as its pattern (the one-liner above shows how
  easily a pattern is walked past);
- a Stop hook running `make test`, but only once a test exists that can see
  the change.

We implemented the last kind of check as a test rather than a hook:
`test_every_raw_column_is_classified` in `tests/test_contract.py`, with
`RAW_INPUT_COLS` in `src/config.py` (commit 5c0f8d4). With the tampered file in
place it goes red:

```
python -m pytest tests/ -q
....F............                                                        [100%]
=================================== FAILURES ===================================
_____________________ test_every_raw_column_is_classified ______________________

raw =      instant     dteday  season  ...  days_since_2011 cnt_2d_bfr demand_index
0          3 2011-01-03  WINTER  ...    ...095         1796
727      731 2012-12-31  WINTER  ...              730       1341         2729

[728 rows x 19 columns]

    def test_every_raw_column_is_classified(raw):
        """No raw column may be read until it has been classified as either
        forbidden or an allowed raw input."""
        unclassified = set(raw.columns) - FORBIDDEN - RAW_INPUT_COLS - {"dteday"}
>       assert unclassified == set(), f"unclassified raw columns: {unclassified}"
E       AssertionError: unclassified raw columns: {'demand_index'}
E       assert {'demand_index'} == set()
E         
E         Extra items in the left set:
E         'demand_index'
E         Use -v to get more diff

tests/test_contract.py:65: AssertionError
=========================== short test summary info ============================
FAILED tests/test_contract.py::test_every_raw_column_is_classified - Assertio...
1 failed, 16 passed in 2.19s
make: *** [test] Error 1
make test exit: 2
```

Its limit: it catches a new or renamed column, not edited values inside
existing columns. Only the hash check catches that, and we did not
implement one. The raw file was restored with `git checkout` and its
sha256 again begins `a6bed1577f6e4de5`.

## Fault 5: `temporal_split` places the train end date into validation

Commit: seeded b234b58.

```diff
diff --git a/src/train.py b/src/train.py
index 75ad607..b81444e 100644
--- a/src/train.py
+++ b/src/train.py
@@ -57,7 +57,7 @@ def temporal_split(df: pd.DataFrame):
     """Split by date, never at random. A random split on a time series
     puts tomorrow in train and today in test."""
     train = df[df.dteday <= TRAIN_END]
-    valid = df[(df.dteday > TRAIN_END) & (df.dteday <= VALID_END)]
+    valid = df[(df.dteday >= TRAIN_END) & (df.dteday <= VALID_END)]
     test = df[df.dteday > VALID_END]
     return train, valid, test
```

`make test`:

```
python -m pytest tests/ -q
...............FF                                                        [100%]
=================================== FAILURES ===================================
_______________________ test_splits_are_ordered_in_time ________________________

splits = (        dteday  instant  season  ...  cnt_lag_7   cnt_roll_7 cnt_roll_std_7
0   2011-01-10     10.0  WINTER  ...     ...57     820.919420
713 2012-12-31    731.0  WINTER  ...      920.0  1531.428571     821.327646

[184 rows x 29 columns])

    def test_splits_are_ordered_in_time(splits):
        train, valid, test = splits
>       assert train.dteday.max() < valid.dteday.min()
E       AssertionError: assert Timestamp('2011-12-31 00:00:00') < Timestamp('2011-12-31 00:00:00')
E        +  where Timestamp('2011-12-31 00:00:00') = max()
E        +    where max = 0     2011-01-10\n1     2011-01-11\n2     2011-01-12\n3     2011-01-13\n4     2011-01-14\n         ...    \n343   2011-12-27\n344   2011-12-28\n345   2011-12-29\n346   2011-12-30\n347   2011-12-31\nName: dteday, Length: 348, dtype: datetime64[us].max
E        +      where 0     2011-01-10\n1     2011-01-11\n2     2011-01-12\n3     2011-01-13\n4     2011-01-14\n         ...    \n343   2011-12-27\n344   2011-12-28\n345   2011-12-29\n346   2011-12-30\n347   2011-12-31\nName: dteday, Length: 348, dtype: datetime64[us] =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7 cnt_roll_std_7\n0   2011-01-10     10.0  WINTER  ...     1...143     640.927326\n347 2011-12-31    365.0  WINTER  ...     1011.0  1709.714286     790.808215\n\n[348 rows x 29 columns].dteday
E        +  and   Timestamp('2011-12-31 00:00:00') = min()
E        +    where min = 347   2011-12-31\n348   2012-01-01\n349   2012-01-02\n350   2012-01-03\n351   2012-01-04\n         ...    \n525   2012-06-26\n526   2012-06-27\n527   2012-06-28\n528   2012-06-29\n529   2012-06-30\nName: dteday, Length: 183, dtype: datetime64[us].min
E        +      where 347   2011-12-31\n348   2012-01-01\n349   2012-01-02\n350   2012-01-03\n351   2012-01-04\n         ...    \n525   2012-06-26\n526   2012-06-27\n527   2012-06-28\n528   2012-06-29\n529   2012-06-30\nName: dteday, Length: 183, dtype: datetime64[us] =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7 cnt_roll_std_7\n347 2011-12-31    365.0  WINTER  ...     1...143     528.607451\n529 2012-06-30    547.0  SUMMER  ...     7458.0  6892.428571     640.767811\n\n[183 rows x 29 columns].dteday

tests/test_split.py:23: AssertionError
__________________________ test_no_overlapping_dates ___________________________

splits = (        dteday  instant  season  ...  cnt_lag_7   cnt_roll_7 cnt_roll_std_7
0   2011-01-10     10.0  WINTER  ...     ...57     820.919420
713 2012-12-31    731.0  WINTER  ...      920.0  1531.428571     821.327646

[184 rows x 29 columns])

    def test_no_overlapping_dates(splits):
        train, valid, test = splits
        dates = pd.concat([train.dteday, valid.dteday, test.dteday])
>       assert dates.is_unique
E       assert False
E        +  where False = 0     2011-01-10\n1     2011-01-11\n2     2011-01-12\n3     2011-01-13\n4     2011-01-14\n         ...    \n709   2012-12-27\n710   2012-12-28\n711   2012-12-29\n712   2012-12-30\n713   2012-12-31\nName: dteday, Length: 715, dtype: datetime64[us].is_unique

tests/test_split.py:30: AssertionError
=========================== short test summary info ============================
FAILED tests/test_split.py::test_splits_are_ordered_in_time - AssertionError:...
FAILED tests/test_split.py::test_no_overlapping_dates - assert False
2 failed, 15 passed in 2.29s
make: *** [test] Error 1
make test exit: 2
```

Hook stderr:

The PostToolUse hook (`.claude/hooks/check_leakage.sh`) only runs
`tests/test_leakage.py`. Because this fault is in `src/train.py` and is a
split-boundary bug rather than a feature-leakage bug, the leakage suite stays
green and the hook is silent:

```
python -m pytest tests/test_leakage.py -q
.........                                                                [100%]
9 passed in 0.53s
hook exit code: 0
```

The split tests in `tests/test_split.py` catch the overlap, but only the
full `make test` target runs them.
