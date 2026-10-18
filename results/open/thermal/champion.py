# Helix v3 policy: thermal, gap 47.191%, progress 52.8%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f018 coupled_steady_state_slowdown_minutes (wide): Steady-state slowdown-minutes penalty of the new job per candidate rack (linear coupled solve), normalised to 
def _f018(size, free, rack, duration, temps, cooling, neighbors, server_free, running, queue, time):
    """Steady-state slowdown-minutes penalty of the new job per candidate rack (linear coupled solve), normalised to [-1,1]."""
    R = len(temps)
    S = server_free.shape[1]
    cap = S * 16.0
    used = cap - server_free.sum(axis=1)

    def slow(T):
        hot = np.maximum(T - 30.0, 0.0)
        very_hot = np.maximum(T - 42.0, 0.0)
        return 1.0 + (hot / 10.0) ** 2 + very_hot / 4.0

    rowsum = neighbors.sum(axis=1)
    M = np.diag(cooling + rowsum) - neighbors + 1e-3 * np.eye(R)
    try:
        Minv = np.linalg.inv(M)
    except np.linalg.LinAlgError:
        Minv = np.linalg.pinv(M)

    base_vec = cooling * 20.0
    load_before = used / cap
    T_ss_base_all = Minv @ (load_before + base_vec)          # (R,)

    delta_load = size / cap
    # column of Minv for each candidate's rack -> (k, R)
    cols = Minv[:, rack].T                                    # (k, R)
    T_ss_cand = T_ss_base_all[None, :] + delta_load * cols    # (k, R)

    # increment on the candidate's own rack (diagonal of the (k,R) perturbation)
    idx = np.arange(len(rack))
    dT_self = delta_load * cols[idx, rack]                    # (k,)
    T_base_self = T_ss_base_all[rack]
    T_cand_self = T_base_self + dT_self

    penalty_cand = duration * (slow(T_cand_self) - 1.0)       # (k,)
    penalty_base = duration * (slow(T_base_self) - 1.0)       # (k,)

    best_base = np.min(penalty_base) if penalty_base.size > 0 else 0.0
    val = (best_base - penalty_cand) / (1.0 + penalty_cand + best_base)
    return np.clip(val, -1.0, 1.0)

# f045 queue_scaled_relative_coolness (deep): Negative of the candidate rack's temperature excess over the coolest rack, squashed, scaled by queue-length ga
def _f045(size, free, rack, duration, temps, cooling, neighbors, server_free, running, queue, time):
    """Negative of the candidate rack's temperature excess over the coolest rack, squashed, scaled by queue-length gate q/(q+2)."""
    r = rack.astype(int)
    ex = temps[r] - temps.min()
    exn = ex / (10.0 + ex)
    q = float(queue.shape[0])
    gate = q / (q + 2.0)
    return -(exn * gate)

_TERMS = [(_f018, np.array([3.143381])), (_f045, np.array([-0.292712]))]

def priority(size, free, rack, duration, temps, cooling, neighbors, server_free, running, queue, time):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(size, free, rack, duration, temps, cooling, neighbors, server_free, running, queue, time), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(free))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
