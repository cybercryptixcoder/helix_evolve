## What a candidate is here: a feature

- Measure exactly what the experiment says. Don't add weights or mix in other measurements: an optimiser fits the weight, and other features already exist.
- Keep the measurement continuous across candidates where the idea allows: a value identical for most candidates ranks nothing. If the idea is a condition, multiply it by a smooth term so candidates still order.
- You may return several columns (shape (k, c), c at most 4) when the measurement naturally has parts; each column gets its own weight.
- Keep the code small and fast: a single function, no loops over the whole problem, no unbounded search. It is called once per candidate per decision, so it must return in well under a second.

## Reply format

Start with the complete code in a single ```python block (imports, then the function with a one-line docstring saying exactly what it computes). After the block, one sentence: what the code computes, and how you read anything ambiguous.
