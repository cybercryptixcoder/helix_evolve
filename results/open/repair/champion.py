# Helix v3 policy: repair, gap 79.093%, progress 20.9%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f006 fail_line_contrast (deep): fail_cov/F - pass_cov/P, but with the failing side weighted by how much error each failing test carries.
def _f006(kind, line, depth, fail_cov, pass_cov, covered, edited, line_tries, status, error, outcomes, tries, budget):
    """fail_cov/F - pass_cov/P, but with the failing side weighted by how much error each failing test carries."""
    F = max(int(outcomes[1:].sum()), 1)
    P = max(int(outcomes[0]), 1)
    # weight each test by its error contribution (exceptions/halts count as 1, wrong values by rel/(1+rel))
    w = np.where(status >= 2, 1.0, error / (1.0 + error))
    w = np.where(status == 1, w, np.where(status >= 2, 1.0, 0.0))
    W = max(float(w.sum()), 1e-12)
    # error-weighted fraction of failing tests executing the line
    fail_w = (covered * w[None, :]).sum(axis=1) / W
    return fail_w - pass_cov / P

# f043 rare_explanation_failure_specificity (deep): Failing-test coverage weighted by test specificity (1 / number of distinct candidate lines executing the test)
def _f043(kind, line, depth, fail_cov, pass_cov, covered, edited, line_tries, status, error, outcomes, tries, budget):
    """Failing-test coverage weighted by test specificity (1 / number of distinct candidate lines executing the test), minus pass coverage rate."""
    k = covered.shape[0]
    cov = covered.astype(float)
    P = max(outcomes[0], 1)
    U = np.unique(cov, axis=0)
    n_t = np.maximum(U.sum(axis=0), 1.0)
    s_t = 1.0 / n_t
    m_t = (status != 0).astype(float)
    w_t = s_t * m_t
    denom = w_t.sum()
    if denom == 0:
        return np.zeros(k)
    return (cov * w_t).sum(axis=1) / denom - pass_cov / P

# f046 fail_line_contrast_sharp_error_mode_gated (wide): Error-weighted fail coverage where each failing test's weight is its *uncertainty* (rel/(1+rel)) times a sharp
def _f046(kind, line, depth, fail_cov, pass_cov, covered, edited, line_tries, status, error, outcomes, tries, budget):
    """Error-weighted fail coverage where each failing test's weight is its *uncertainty* (rel/(1+rel)) times a sharpened specificity, minus pass rate, gated by whether the line actually explains the dominant failure mode."""
    F = max(int(outcomes[1:].sum()), 1)
    P = max(int(outcomes[0]), 1)
    Pn = max(float(outcomes[0]), 1e-12)
    cov = covered.astype(float)

    # per-test weight: wrong values by rel/(1+rel); exceptions/halts full
    w = np.where(status >= 2, 1.0, error / (1.0 + error))
    w = np.where(status == 1, w, np.where(status >= 2, 1.0, 0.0))

    # sharpen: emphasise tests with near-total failure (rel close to 1) over marginal ones
    w_sharp = w * w
    W = max(float(w_sharp.sum()), 1e-12)

    fail_w = (cov * w_sharp[None, :]).sum(axis=1) / W

    # pass side: use *count* fraction but discounted when pass tests are few (unreliable signal)
    pass_rate = pass_cov / Pn

    # dominant failure mode: exception-ish vs wrong-value-ish
    exc_mass = float((status >= 2).sum())
    wrong_mass = float((status == 1).sum())
    total_fail = max(exc_mass + wrong_mass, 1.0)
    exc_share = exc_mass / total_fail

    # candidate explains exceptions if it covers exception tests; explains wrong if covers wrong tests
    covers_exc = (cov * (status >= 2).astype(float)[None, :]).sum(axis=1) / total_fail
    covers_wrong = (cov * (status == 1).astype(float)[None, :]).sum(axis=1) / total_fail
    explains = exc_share * covers_exc + (1.0 - exc_share) * covers_wrong

    # gate: only trust the fail-weighted term when it beats pass rate; otherwise damp
    raw = fail_w - pass_rate
    gate = np.where(fail_w > pass_rate, 1.0, 0.5)
    return gate * raw + 0.25 * explains

_TERMS = [(_f006, np.array([3.392566])), (_f043, np.array([1.844325])), (_f046, np.array([0.117987]))]

def priority(kind, line, depth, fail_cov, pass_cov, covered, edited, line_tries, status, error, outcomes, tries, budget):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(kind, line, depth, fail_cov, pass_cov, covered, edited, line_tries, status, error, outcomes, tries, budget), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(kind))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
