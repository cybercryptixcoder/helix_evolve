## What a candidate is here: a feature

The policy is a weighted sum of **features** (measurements of a candidate). An optimiser fits the weights and signs, so never choose numbers or signs.

- **Varying a parent feature:** a different functional form, a condition (only for some decisions or some candidates), a combination with another quantity, a different normalisation. Tweaking a constant is wasted: the optimiser already tunes the weight.
- A feature that ranks candidates the same way as one on the scoreboard (including a sign flip or a monotone transform) is a duplicate.

## Reply format

Start with the complete code in a single ```python block (imports, then the function with a one-line docstring saying exactly what it measures). After the block, one line: `name: <short_snake_case_name>`.

A feature may apply only under a condition (only in some decisions, or for some candidates, when a quantity crosses a threshold) and be zero otherwise. The policy is one weighted sum, so a condition is the only way it can treat different cases differently.
