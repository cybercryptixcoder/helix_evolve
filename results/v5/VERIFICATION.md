# Verification of the Helix v4.5 and v5 constructions

Every best construction re-scored three independent ways (`tools/verify_ac2.py`): Helix's evaluator, DeepMind's own verification code (ported line by line), and exact rational arithmetic (on the float heights themselves up to 12,000 steps; above that on a copy rounded to integers at 2^30, itself a valid construction). Digits are truncated, not rounded.

| Construction | Steps | Helix | DeepMind's code | Exact | All agree |
|---|---|---|---|---|---|
| AlphaEvolve, May 2025 (DeepMind's published 50-step construction) | 50 | 0.896279944155 | 0.896279944155 | 0.896279944155 | True |
| v45-s1 | 4096 | 0.875129234521 | 0.875129234521 | 0.875129234520 | True |
| v45-s2 | 3200 | 0.897061745460 | 0.897061745460 | 0.897061745459 | True |
| v45-s3 | 800 | 0.926351211476 | 0.926351211476 | 0.926351211476 | True |
| v5-s1 | 450 | 0.872336241812 | 0.872336241812 | 0.872336241812 | True |
| v5-s2 | 3200 | 0.871848312625 | 0.871848312625 | 0.871848312624 | True |
| v5-s3 | 1600 | 0.933665094669 | 0.933665094669 | 0.933665094668 | True |
