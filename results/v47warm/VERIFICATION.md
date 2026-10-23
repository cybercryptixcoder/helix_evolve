# Verification of the Helix v4.7 job's constructions

Every best construction re-scored three independent ways (`tools/verify_ac2.py`): Helix's evaluator, DeepMind's own verification code (ported line by line), and exact rational arithmetic (on the float heights themselves up to 12,000 steps; above that on a copy rounded to integers at 2^30, itself a valid construction). Digits are truncated, not rounded.

| Construction | Steps | Helix | DeepMind's code | Exact | All agree |
|---|---|---|---|---|---|
| AlphaEvolve, May 2025 (DeepMind's published 50-step construction) | 50 | 0.896279944155 | 0.896279944155 | 0.896279944155 | True |
| v47-s1 | 42496 | 0.940794544359 | 0.940794544359 | 0.940794543121 | True |
| v47-s2 | 42496 | 0.941229688472 | 0.941229688472 | 0.941229684181 | True |
