import numpy as np


def priority(item, bins, capacity):
    """Best-Fit with a "dot-product" distortion of the leftover.

    Core of the old program: prefer the bin leaving the least total free space.
    Bold changes:
      1. Normalise each resource by capacity so the rule generalises.
      2. Instead of the plain L1 leftover, score by the *product* of the two
         normalised residuals.  Minimising c*m (maximising -c*m) strongly
         penalises any bin that would leave one resource nearly exhausted,
         because then the product collapses to ~0 only if the other residual is
         also tiny -- it keeps bins square and reusable for mixed jobs.
      3. Add a small L1 term so that among equally balanced bins the tightest
         one (least total slack) still wins, matching classic best-fit.
    """
    res = bins - item                     # >= 0 for every fitting bin
    res = res / capacity                  # normalise, capacity-agnostic
    c = res[:, 0]
    m = res[:, 1]
    # main term: -c*m (tightest AND balanced); tie-break with -0.5*(c+m).
    return -(c * m) - 0.5 * (c + m)
