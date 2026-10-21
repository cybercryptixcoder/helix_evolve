# Verification of the Helix v4 constructions

Every best construction re-scored three independent ways (`tools/verify_ac2.py`): Helix's evaluator, DeepMind's own verification code (ported line by line), and exact rational arithmetic (on the float heights themselves up to 12,000 steps; above that on a copy rounded to integers at 2^30, itself a valid construction). Digits are truncated, not rounded.

| Construction | Steps | Helix | DeepMind's code | Exact | All agree |
|---|---|---|---|---|---|
| AlphaEvolve, May 2025 (DeepMind's published 50-step construction) | 50 | 0.896279944155 | 0.896279944155 | 0.896279944155 | True |
| atlas-s1 | 42496 | 0.939016147130 | 0.939016147130 | 0.939016147232 | True |
| atlas-s2 | 544 | 0.892272819244 | 0.892272819244 | 0.892272819244 | True |
| atlas-s3 | 20000 | 0.882442130207 | 0.882442130207 | 0.882442129794 | True |
| control-s1 | 160000 | 0.882531730987 | 0.882531730987 | 0.882531730049 | True |
| control-s2 | 25600 | 0.913581646332 | 0.913581646332 | 0.913581645371 | True |
| control-s3 | 4096 | 0.882489095934 | 0.882489095934 | 0.882489095933 | True |
| journal-s1 | 6000 | 0.934184689792 | 0.934184689792 | 0.934184689791 | True |
| journal-s2 | 4000 | 0.924182240140 | 0.924182240140 | 0.924182240140 | True |
| journal-s3 | 200000 | 0.882541746107 | 0.882541746107 | 0.882541740472 | True |
