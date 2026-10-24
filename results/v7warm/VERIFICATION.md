# Verification of the Helix v7 job's constructions

Every best construction re-scored three independent ways (`tools/verify_ac2.py`): Helix's evaluator, DeepMind's own verification code (ported line by line), and exact rational arithmetic. Digits are truncated, not rounded.

| Construction | Steps | Helix | DeepMind's code | Exact | All agree |
|---|---|---|---|---|---|
| AlphaEvolve, May 2025 (DeepMind's published 50-step construction) | 50 | 0.896279944155 | 0.896279944155 | 0.896279944155 | True |
| v7-s1 | 42496 | 0.941252078243 | 0.941252078243 | 0.941252076899 | True |
