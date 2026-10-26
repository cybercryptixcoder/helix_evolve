# Verification of the Helix v8 job's constructions

Every best construction re-scored three independent ways (`tools/verify_ac2.py`): Helix's evaluator, DeepMind's own verification code (ported line by line), and exact rational arithmetic. Digits are truncated, not rounded.

| Construction | Steps | Helix | DeepMind's code | Exact | All agree |
|---|---|---|---|---|---|
| AlphaEvolve, May 2025 (DeepMind's published 50-step construction) | 50 | 0.896279944155 | 0.896279944155 | 0.896279944155 | True |
| v8-s1 | 104992 | 0.941441743993 | 0.941441743993 | 0.941441740905 | True |
