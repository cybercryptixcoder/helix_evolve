## Certificates the engine can check (for features)

- `inert`: it gives every candidate the same value in every decision, so it can't change a choice;
- `duplicate` (with `of`: a feature id): it ranks candidates exactly like that feature (up to sign or a monotone transform);
- `span`: within every decision it is a linear combination of the kept features, so it can only re-weight them.

The engine has already tested these against every evaluated feature on sampled decisions. You see each feature's code, the kept features' code, and the nearest match the engine found. Look for what it might have missed: algebraic identities, a feature equal to another up to a monotone transform on the problem's actual inputs, a condition that is never true for the problem's inputs.
