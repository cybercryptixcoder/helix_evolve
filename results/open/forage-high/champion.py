# Helix v3 policy: forage, gap 53.294%, progress 46.7%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f037 opportunity_cost_trip_feasibility (wide): Signed urgency score: positive for items ranked by survival-weighted value per unit of energy-and-time budget 
def _f037(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Signed urgency score: positive for items ranked by survival-weighted value per unit of energy-and-time budget consumed (with forced-recharge overhead), scaled by a competition factor that compares each item's marginal value against the best competing option, negative-but-small for the charger when it's still worth deferring."""
    d = np.linalg.norm(targets - pos[None, :], axis=1)          # travel time (speed 1)
    is_item = values > 0

    d_target_charger = np.linalg.norm(charger[None, :] - targets, axis=1)
    # energy budget for round-trip (fly there + get back to charger from there)
    need = (d + d_target_charger) * drain
    feasible = (need <= battery) | (~is_item)

    # time budget: travel + forced recharge for the energy spent outbound
    energy_out = d * drain
    recharge_time = energy_out / np.maximum(charge_rate, 1e-3)
    trip_time = np.maximum(d + recharge_time, 1e-3)

    # survival fraction through the trip
    projected = np.maximum(values - rates * d, 0.0)
    survival = np.where(values > 0, projected / np.maximum(values, 1e-6), 0.0)

    # does it survive at all AND before end?
    arrives_before_end = d <= time_left
    time_ok = np.where(is_item, arrives_before_end.astype(float), 1.0)

    # competition: best competing item's survival-weighted value rate
    rate_surv = np.where(is_item, projected / trip_time, -np.inf)
    best_compet = np.max(rate_surv) if np.any(is_item) else 0.0
    # each item's marginal edge over the best competitor (0..1): dominant items ~1, dominated ~0
    edge = np.where(is_item,
                    np.clip(rate_surv / np.maximum(best_compet, 1e-6), 0.0, 1.0),
                    0.0)

    # energy efficiency: projected value per unit battery spent
    energy_use = np.maximum(d * drain, 1e-3)
    eff = np.where(is_item, projected / energy_use, 0.0)

    # combine: log-squash efficiency, weight by survival and edge, gate by feasibility & time
    item_score = np.log1p(eff) * survival * (0.25 + 0.75 * edge) * feasible.astype(float) * time_ok
    item_score = np.where(feasible & arrives_before_end, item_score, -0.5 * (1.0 - survival))

    # charger: negative pull (defer) when battery healthy, strong positive when battery low
    # battery left after reaching charger
    batt_at_charger = battery - d * drain
    low_batt = np.clip(1.0 - batt_at_charger / 0.35, 0.0, 1.0)  # normalise around a soft reserve
    any_feasible_item = np.any(is_item & feasible & arrives_before_end)
    stranded = 0.0 if any_feasible_item else 1.0
    # defer bonus: if battery is comfortable and items exist, keep the charger negative
    defer = -0.6 * (1.0 - low_batt) * (1.0 if any_feasible_item else 0.0)
    charger_score = 2.0 * low_batt + 1.2 * stranded + defer

    score = np.where(is_item, item_score, charger_score)
    return np.tanh(score)

# f053 rate_normalised_survival_trip_density (wide): Per item: arrival-surviving value divided by round-trip time, but the survival horizon is judged against each 
def _f053(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Per item: arrival-surviving value divided by round-trip time, but the survival horizon is judged against each item's own remaining lifetime (rate-normalised) so fast-decaying items that will vanish mid-trip are penalised hard; charger gets a signed deferral/stranding score."""
    d = np.linalg.norm(targets - pos[None, :], axis=1)
    is_item = values > 0

    d_back = np.linalg.norm(charger[None, :] - targets, axis=1)
    need = (d + d_back) * drain
    feasible = (need <= battery) | (~is_item)

    # recharge overhead only for the outbound leg, plus return leg time
    recharge_time = (d * drain) / np.maximum(charge_rate, 1e-3)
    round_trip = np.maximum(d + d_back + recharge_time, 1e-3)

    # projected value at arrival
    projected = np.maximum(values - rates * d, 0.0)

    # rate-normalised survival horizon: how many 'lifetimes' the trip costs
    lifetime = values / np.maximum(rates, 1e-6)
    trip_frac = np.where(is_item, d / np.maximum(lifetime, 1e-6), 0.0)
    decay_penalty = np.exp(-np.clip(trip_frac, 0.0, 50.0))   # 1 if trip is instant vs lifetime, ->0 if trip >> lifetime

    arrives_before_end = d <= time_left

    # value-per-round-trip-time, squashed, weighted by how little of its life the trip eats
    eff = np.where(is_item, projected / round_trip, 0.0)
    item_score = np.log1p(eff) * decay_penalty * feasible.astype(float) * arrives_before_end.astype(float)

    # infeasible or too-late items pushed negative in proportion to their lost value
    bad = is_item & ((~feasible) | (~arrives_before_end))
    lost_frac = 1.0 - np.where(values > 0, projected / np.maximum(values, 1e-6), 0.0)
    item_score = np.where(bad, -0.5 * lost_frac - 0.1, item_score)

    # charger: low battery -> strong pull; otherwise deferral; stranded if nothing reachable
    batt_at_charger = battery - d * drain
    low_batt = np.clip(1.0 - batt_at_charger / 0.35, 0.0, 1.0)
    any_reachable = np.any(is_item & feasible & arrives_before_end)
    stranded = 0.0 if any_reachable else 1.0
    defer = -0.6 * (1.0 - low_batt)
    charger_score = 2.0 * low_batt + 1.2 * stranded + defer

    score = np.where(is_item, item_score, charger_score)
    return np.tanh(score)

# f065 two_stop_pair_tour_rate (deep): Best feasible two-stop tour value (this item + best surviving follow-up) per two-leg time, scaled to [-1, 1].
def _f065(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Best feasible two-stop tour value (this item + best surviving follow-up) per two-leg time, scaled to [-1, 1]."""
    k = len(values)
    is_item = values > 0
    d = np.linalg.norm(targets - pos[None, :], axis=1)
    life = values / np.maximum(rates, 1e-9)
    Vs = np.where(is_item, np.maximum(values - rates * d, 0.0), 0.0)

    # pairwise distances between candidates
    diff = targets[:, None, :] - targets[None, :, :]
    T = np.linalg.norm(diff, axis=2)
    back = np.linalg.norm(targets - charger[None, :], axis=1)

    Ts = d[:, None] + T  # time from now to item j via item i
    Vs2 = values[None, :] * np.clip(1.0 - Ts / np.maximum(life[None, :], 1e-9), 0.0, 1.0)
    feasible2 = (is_item[:, None] & is_item[None, :]
                 & ~np.eye(k, dtype=bool)
                 & ((d[:, None] + T + back[None, :]) * drain <= battery))
    Vs2 = np.where(feasible2, Vs2, 0.0)

    second = Vs2.max(axis=1)
    Tsecond = np.where(Vs2 > 0, Ts, np.inf).min(axis=1)
    Tsecond = np.where(np.isfinite(Tsecond), Tsecond, 0.0)

    rate = np.where(is_item, (Vs + second) / (0.1 + d + Tsecond), 0.0)
    mx = rate.max()
    return np.where(is_item, 2.0 * rate / (mx + 1e-9) - 1.0, 0.0)

# f076 soft_range_gate_pair_tour (deep): Best-pair tour value per time (V/(L+0.05)) times tanh(3*(range-E)/range) smooth battery-range margin, normalis
def _f076(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Best-pair tour value per time (V/(L+0.05)) times tanh(3*(range-E)/range) smooth battery-range margin, normalised to ~[-1,1]; charger 0."""
    k = targets.shape[0]
    is_item = values > 0
    out = np.zeros(k, dtype=float)
    if not np.any(is_item):
        return out

    d = np.sqrt(np.maximum(((targets - pos) ** 2).sum(axis=1), 0.0))  # (k,)
    D = np.sqrt(np.maximum(((targets[:, None, :] - targets[None, :, :]) ** 2).sum(axis=2), 0.0))  # (k,k)
    DB = np.sqrt(np.maximum(((targets - charger) ** 2).sum(axis=1), 0.0))  # (k,)

    v = values
    r = rates
    L = d[:, None] + D  # (k,k) time to reach i then j
    Vi = np.maximum(0.0, v - r * d)  # (k,) value of i at arrival
    Vj = np.maximum(0.0, v[None, :] - r[None, :] * L)  # (k,k) value of j at arrival
    V = Vi[:, None] + Vj  # (k,k)
    base = V / (L + 0.05)  # (k,k)

    E = (d[:, None] + D + DB[None, :]) * drain  # (k,k)
    rng = battery / max(drain, 1e-9)
    margin = (rng - E) / max(rng, 1e-6)
    gate = np.tanh(3.0 * margin)

    score = base * gate  # (k,k)
    # only item rows as i and item columns as j
    score = np.where(is_item[:, None] & is_item[None, :], score, -np.inf)
    best = np.max(score, axis=1)  # (k,)
    best = np.where(is_item, best, 0.0)

    scale = np.max(np.abs(best[is_item])) if np.any(is_item) else 0.0
    scale = max(scale, 1e-9)
    out = best / scale
    out = np.where(is_item, out, 0.0)
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)

# f102 burst_gated_short_hop (deep): Burst-gated short-hop closeness: tanh-scaled recent arrival-rate burst times exp(-distance/0.3) for items, 0 f
def _f102(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Burst-gated short-hop closeness: tanh-scaled recent arrival-rate burst times exp(-distance/0.3) for items, 0 for charger."""
    k = targets.shape[0]
    out = np.zeros(k, dtype=float)
    n_h = history.shape[0]
    if n_h < 3 or time < 5:
        return out
    n_rec = np.count_nonzero(history[:, 2] >= time - 10.0)
    expected = n_h * min(10.0, time) / time
    s = (n_rec - expected) / (n_rec + expected + 1.0)
    burst = max(float(np.tanh(2.5 * s)), 0.0)
    if burst == 0.0:
        return out
    d = np.sqrt(np.sum((targets - pos) ** 2, axis=1))
    closeness = np.exp(-d / 0.3)
    item_mask = values > 0
    out[item_mask] = burst * closeness[item_mask]
    return out

_TERMS = [(_f037, np.array([0.461556])), (_f053, np.array([-0.080115])), (_f065, np.array([0.083569])), (_f076, np.array([0.067338])), (_f102, np.array([0.418216]))]

def priority(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(targets))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
