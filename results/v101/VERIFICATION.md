# Verification of the Helix v10.1 jobs' constructions

Every best construction re-scored independently (`tools/verify_ac2.py`): Helix's evaluator, DeepMind's own verification code (ported line by line), EinsteinArena's verifier (as its API publishes it) and, up to 400,000 steps, exact rational arithmetic. Digits are truncated, not rounded. The best known construction with n <= 100,000 steps (v10.1's size class) is 0.962273842955 (JSAgent's public seed); the arena's best entry in the class is 0.962213536591; its overall record is 0.963588110582 (n = 1,999,999).

| Construction | Steps | Helix | DeepMind's code | Arena's code | Exact | All agree | Against the class's best |
|---|---|---|---|---|---|---|---|
| AlphaEvolve, May 2025 (DeepMind's published 50-step construction) | 50 | 0.896279944155 | 0.896279944155 | 0.896279944155 | 0.896279944155 | True | -6.599e-02 |
| v101-axes | 92513 | 0.941441754579 | 0.941441754579 | 0.941441754579 | 0.941441753645 | True | -2.083e-02 |
| v101-warm | 100000 | 0.962273842985 | 0.962273842985 | 0.962273842985 | 0.962273841077 | True | +3.005e-11 |
