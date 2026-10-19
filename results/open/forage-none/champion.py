# Helix v3 policy: forage, gap 54.657%, progress 45.3%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f008 battery_feasibility_margin (deep): Feasibility margin: 1 - need/battery if reachable, -1 if not; charger scores 1 - battery.
def _f008(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Feasibility margin: 1 - need/battery if reachable, -1 if not; charger scores 1 - battery."""
    dist = np.sqrt(np.sum((targets - pos) ** 2, axis=1))
    need = dist * drain
    feasible = need <= battery
    score = np.where(feasible, 1.0 - need / (battery + 1e-6), -1.0)
    is_charger = values == 0
    score = np.where(is_charger, 1.0 - battery, score)
    return np.clip(score, -1.0, 1.0)

# f013 opportunity_cost_rank_gap (wide): Opportunity cost of ignoring other items: candidate's own value rate minus the best value rate among other ite
def _f013(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Opportunity cost of ignoring other items: candidate's own value rate minus the best value rate among other items reachable, both decayed to arrival time."""
    d = np.sqrt(np.sum((targets - pos) ** 2, axis=1))
    is_item = values > 0
    # value density per time for each candidate, decayed to arrival
    life = np.where(rates > 0, values / np.maximum(rates, 1e-12), 1e9)
    arrived = np.maximum(values - rates * d, 0.0)
    dens = arrived / np.maximum(d, 1e-6)
    # how much of each candidate's life is consumed by the trip
    life_frac = np.clip(d / np.maximum(life, 1e-6), 0.0, 1.0)
    # per-decision opportunity: compare against second-best density (exclude self)
    dens_items = np.where(is_item, dens, -1.0)
    order = np.argsort(-dens_items)
    best = dens_items[order[0]] if len(order) > 0 else 0.0
    second = dens_items[order[1]] if len(order) > 1 else 0.0
    # a candidate is valuable if it is near the top of the density ranking
    rank_gap = np.where(is_item, dens - second, 0.0)
    # combine: high if dense and its life is nearly gone (urgent) relative to competitors
    score = np.tanh(rank_gap * (1.0 + life_frac))
    # charger: mild positive early when battery is low and nearby
    charger_d = np.linalg.norm(charger - pos)
    charger_score = np.clip(1.0 - battery, 0.0, 1.0) * np.clip(1.0 - charger_d, 0.0, 1.0)
    return np.where(is_item, score, 0.3 * charger_score)

# f040 endgame_horizon_gate (deep): Reachability before the end times surviving value fraction for items; late-game charger boost for the charger.
def _f040(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Reachability before the end times surviving value fraction for items; late-game charger boost for the charger."""
    d = np.linalg.norm(targets - pos, axis=1)
    arrival = d
    slack = (time_left - arrival) / max(time_left, 1e-6)
    survival = values / (values + rates * d + 1e-6)
    item_score = np.clip(slack, -1.0, 1.0) * survival
    charger_score = np.clip(1.0 - time_left / 20.0, -1.0, 1.0)
    is_charger = values == 0
    out = np.where(is_charger, charger_score, item_score)
    return out

# f086 round_trip_reserve_vs_doomed_item_density (wide): Round-trip reserve slack conditioned on the candidate dying before the return trip could finish: items whose r
def _f086(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Round-trip reserve slack conditioned on the candidate dying before the return trip could finish: items whose remaining life is shorter than the outbound leg are scored by pure survival urgency instead of reserve."""
    dist = np.sqrt(np.sum((targets - pos) ** 2, axis=1))
    back = np.sqrt(np.sum((targets - charger) ** 2, axis=1))
    need = dist * drain
    reserve = back * drain
    feasible = need <= battery
    slack = battery - need - reserve
    reserve_score = np.where(feasible, np.tanh(slack / (battery + reserve + 1e-6)), -1.0)

    # remaining life in time units for each item (charger has rates 0)
    life = np.where(rates > 0, values / np.maximum(rates, 1e-12), 1e9)
    # does the item die before we could even reach it? does it die before we'd get back?
    dies_before_arrival = life < dist
    dies_before_return = life < (dist + back)

    # pure survival fraction at arrival (how much value is left when we get there)
    survival = np.clip((life - dist) / np.maximum(life, 1e-6), 0.0, 1.0)
    # value density of the doomed-but-reachable items, normalised across decision
    dens = np.where(values > 0, survival * values / np.maximum(dist, 1e-6), -1.0)
    dmax = np.max(dens) if np.any(values > 0) else 1.0
    dens_norm = np.where(values > 0, dens / (abs(dmax) + 1e-6), 0.0)

    # condition: if the item survives the return trip, use reserve slack;
    # if it dies before we'd get back but survives arrival, use density (grab it now);
    # if it dies before arrival, penalise.
    urgent_score = 0.7 * dens_norm + 0.3 * survival
    score = np.where(dies_before_arrival,
                     -1.0,
                     np.where(dies_before_return, urgent_score, reserve_score))

    is_charger = values == 0
    to_charger = np.sqrt(np.sum((charger - pos) ** 2))
    charger_score = (1.0 - battery) * np.tanh(to_charger)
    score = np.where(is_charger, np.clip(charger_score, -1.0, 1.0), score)
    return np.clip(score, -1.0, 1.0)

_TERMS = [(_f008, np.array([7.708675])), (_f013, np.array([0.261756])), (_f040, np.array([-0.090849])), (_f086, np.array([0.184063]))]

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
