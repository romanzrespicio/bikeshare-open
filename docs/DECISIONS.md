# Decisions

One line per methodological decision: what you chose, why, and what it changed.
Agents append here via the `/new-feature` skill; you append here by hand.

- Exclude `casual`, `registered`: they sum to `cnt` exactly. Leaky model R^2 1.000 -> honest ridge 0.583.
- Exclude `cnt_2d_bfr`: a shipped 2-day lag we cannot test the alignment of. Build our own lags instead.
- Exclude `instant`, `yr`, `days_since_2011`: time indexes let a tree predict a flat constant past 2011 and a linear model extrapolate a trend we have no grounds for.
- Split 2011 / H1 2012 / H2 2012 by date. Test set touched once, after all feature work.
- Report mean and persistence baselines with every score. Persistence (test R^2 0.510, MAE 840) is within 0.07 R^2 of ridge and beats it on MAE; that caveat goes in the report.
- 2026-11-25 add `cnt_roll_std_7`: population std of `cnt` over the 7 calendar days strictly before the forecast date; valid R² delta ridge +0.0749 (0.6475 -> 0.7224), hgb -0.1208 (0.2185 -> 0.0977). Ridge gain exceeds the 0.01 threshold -- keep the feature despite hgb's drop.
- 2026-11-25 Keep `cnt_roll_std_7`: ridge validation R^2 +0.0749 clears the 0.01 floor and the input is known before day d. It makes hgb worse on validation (0.2185 -> 0.0977); that is reported, not a reason to drop it, because hgb's failure is the growth trend, not this feature.
- 2026-11-25 Switch the agent model: `qwen3.5:9b` local (16 GB laptop) took about 10 minutes per turn and produced no committed change, so all agent code comes from `kimi-k2.7-code` on Ollama cloud. Changed nothing in the pipeline; changes what the report must attribute.
- 2026-11-25 A seeded fault that leaves `make test` green gets a test before it gets a fix. Removing the `raise` in `encode_weather` passed 15/15, so we added `test_weather_encoder_rejects_unknown_labels`; the same fault now fails 1 of 16 and trips the hook.
- 2026-11-25 Classify raw columns explicitly (`RAW_INPUT_COLS` in `src/config.py`, `test_every_raw_column_is_classified`). A column `demand_index` = `cnt` copied into `data/raw/` gave ridge validation R^2 0.9999 with every test green; it now fails the suite. We chose an allowlist for raw inputs so a new column fails loudly instead of entering silently.
- 2026-11-25 Do not implement a hash check on the raw file. The unclassified-column test cannot see edited values in existing columns; a sha256 check in `make data` would. Named in `docs/SEEDED_FAULTS.md` as the missing guard; left out to keep to the required deliverables.
- 2026-11-25 Add the `seed-fault` skill for the break/record/restore loop we ran three times by hand. Its first run retyped pasted output with errors, so evidence blocks in `docs/SEEDED_FAULTS.md` are captured from the command, not from the agent's reply.
- 2026-11-25 Exercise 4: fit on `cnt / cnt_roll_7` and multiply back (`--target-transform ratio`). Chosen on validation only: hgb validation R^2 0.0977 -> 0.7483, ridge 0.7224 -> 0.6128. Defensible: the divisor is known before day d and removes the level a tree cannot extrapolate. Not adopted as the pipeline: it was picked to rescue one model, and the committed `reports/metrics.json` stays untransformed.
- 2026-11-25 Test set read once for the transformed models, after the choice above was committed: hgb-ratio test R^2 0.6280 (MAE 832.8) against untransformed ridge 0.6356 (MAE 840.3). The tree competes; it does not win. Nothing was changed after seeing these numbers.
- 2026-11-25 `CLAUDE.md`: added the headline command, both skills, the raw-column classification rule and the ratio-flag rule. Removed nothing; every starter line still changes what an agent would do.
