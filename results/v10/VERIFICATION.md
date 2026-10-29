# Verification of the Helix v10 jobs' constructions

Every best construction re-scored independently (`tools/verify_ac2.py`): Helix's evaluator, DeepMind's own verification code (ported line by line), EinsteinArena's verifier (as its API publishes it) and, up to 400,000 steps, exact rational arithmetic. Digits are truncated, not rounded. The arena's record is 0.963588110582; a new arena #1 needs 0.963598110582.

| Construction | Steps | Helix | DeepMind's code | Arena's code | Exact | All agree | Against the record |
|---|---|---|---|---|---|---|---|
| AlphaEvolve, May 2025 (DeepMind's published 50-step construction) | 50 | 0.896279944155 | 0.896279944155 | 0.896279944155 | 0.896279944155 | True | -6.731e-02 |
| v10-axes | 104992 | 0.941441744965 | 0.941441744965 | 0.941441744965 | 0.941441741627 | True | -2.215e-02 |
| v10-warm | 1999999 | 0.963588148491 | 0.963588148491 | 0.963588148491 | - | True | +3.791e-08 |
