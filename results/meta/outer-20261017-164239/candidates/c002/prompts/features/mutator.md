## What a candidate is here: a feature

The policy is a weighted sum of **features** (measurements of a candidate). An optimiser fits the weights and signs, so never choose numbers or signs.

- **Varying a parent feature:** a different functional form, a condition (only for some decisions or some candidates), a combination with another quantity, a different normalisation. Tweaking a constant is wasted: the optimiser already tunes the weight.
- A feature that ranks candidates the same way as one on the scoreboard (including a sign flip or a monotone transform) is a duplicate.
- Keep the code small and fast: a single function, no loops over the whole problem, no unbounded search. It is called once per candidate per decision, so it must return in well under a second.

## Reply format

Start with the complete code in a single ```python block (imports, then the function with a one-line docstring saying exactly what it measures). After the block, one line: `name: <short_snake_case_name>`.
