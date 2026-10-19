# Helix v3 policy: forage, gap 53.126%, progress 46.9%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f002 feasible_arrival_value (wide): Battery-feasibility-adjusted arrival: net value after decay, gated by whether the flight can be made without r
def _f002(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Battery-feasibility-adjusted arrival: net value after decay, gated by whether the flight can be made without running out."""
    d = np.linalg.norm(targets - pos[None, :], axis=1)
    is_charger = values <= 0
    # time to reach, plus charging time if we end at charger
    travel = d
    # effective arrival value after decay during flight (never below 0)
    life = np.where(rates > 0, values / np.maximum(rates, 1e-9), np.inf)
    arrival_val = np.maximum(values - rates * travel, 0.0)
    # feasibility: does the flight fit in the battery?
    need = d * drain
    feasible = (need <= battery).astype(float)
    # for charger candidate, treat as always feasible with value scaled by urgency (low battery good)
    charger_score = is_charger.astype(float) * (1.0 - battery)
    # normalise arrival value
    scale = np.maximum(values.max(), 1e-9)
    item_score = np.where(is_charger, 0.0, arrival_val / scale) * feasible
    return item_score + charger_score

# f015 reachable_value_after_pickup (deep): Sum of decayed values of items reachable from each candidate (battery after arriving there, plus return to cha
def _f015(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Sum of decayed values of items reachable from each candidate (battery after arriving there, plus return to charger), normalised by the best arrival value and clipped."""
    d = np.linalg.norm(targets - pos, axis=1)
    is_item = values > 0
    arrival = np.maximum(values - rates * d, 0.0)
    norm = max(arrival.max(), 1e-9)
    b_after = battery - d * drain
    D = np.linalg.norm(targets[:, None, :] - targets[None, :, :], axis=2)
    dch = np.linalg.norm(targets - charger, axis=1)
    reach = (b_after[:, None] - (D + dch[None, :]) * drain) > 0
    reach &= is_item[None, :]
    np.fill_diagonal(reach, False)
    vj = np.maximum(values[None, :] - rates[None, :] * (d[:, None] + D), 0.0)
    look = (vj * reach).sum(axis=1) / norm
    out = np.clip(look / 3.0, -1.0, 1.0)
    out = np.where(is_item, out, 0.0)
    return out

# f016 stranded_shortfall_penalty (deep): Negative normalised battery shortfall of the out-and-back trip (pos->target->charger), zero for the charger.
def _f016(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Negative normalised battery shortfall of the out-and-back trip (pos->target->charger), zero for the charger."""
    d = np.linalg.norm(targets - pos, axis=1)
    dch = np.linalg.norm(targets - charger, axis=1)
    need = (d + dch) * drain
    shortfall = np.maximum(need - battery, 0.0)
    feat = -np.minimum(shortfall / max(battery, 0.05), 1.0)
    is_item = values > 0
    return np.where(is_item, feat, 0.0)

# f012 perishable_affordable_value_per_time (wide): Value-per-flight-time, but only counting value that survives the trip, and conditioned on the trip being affor
def _f012(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Value-per-flight-time, but only counting value that survives the trip, and conditioned on the trip being affordable so cheap far-away items don't win on a dying battery."""
    d = np.linalg.norm(targets - pos[None, :], axis=1)
    is_charger = values <= 0
    # value that will still be there on arrival (never negative)
    arrival = np.maximum(values - rates * d, 0.0)
    # affordability: fraction of battery the trip consumes, saturating
    need = d * drain
    afford = np.clip(1.0 - need / np.maximum(battery, 1e-9), 0.0, 1.0)
    # urgency of decay: how much of the horizon the item has left vs the trip
    life = np.where(rates > 0, values / np.maximum(rates, 1e-9), 1e9)
    # perishable items get a boost when the trip eats a large share of their remaining life
    perish = np.clip(d / np.maximum(life, 1e-9), 0.0, 1.0)
    scale = np.maximum(values.max(), 1e-9)
    s = (arrival / scale) * afford * (1.0 + perish) / (d + 0.2)
    return np.where(is_charger, 0.0, s)

# f014 feasible_arrival_value_roundtrip_amortised (wide): Arrival value amortised over the full battery cycle: flight out plus the trip back to the charger (and recharg
def _f014(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Arrival value amortised over the full battery cycle: flight out plus the trip back to the charger (and recharge time) needed to keep flying, so candidates far from the charger or draining a lot of battery are discounted; charger scores 1 - battery."""
    d = np.linalg.norm(targets - pos[None, :], axis=1)
    is_charger = values <= 0
    d_charger = np.linalg.norm(targets - charger[None, :], axis=1)
    # total flight path if we go to the item and then must return to the charger
    tour = d + d_charger
    # battery spent on that tour
    spent = np.clip(tour * drain, 0.0, None)
    # recharge time needed to recover what was spent (after arriving at the charger)
    recharge = np.clip(spent / max(charge_rate, 1e-9), 0.0, None)
    # full cycle time: out, back, recharge
    cycle = tour + recharge
    # arrival value after decay during the outbound flight only
    arrival_val = np.maximum(values - rates * d, 0.0)
    # amortise over the cycle, guarding division
    eff = arrival_val / np.maximum(cycle, 1e-3)
    # normalise by the best achievable efficiency among items
    item_eff = np.where(is_charger, 0.0, eff)
    scale = np.maximum(item_eff.max(), 1e-9)
    # feasibility gate for the outbound leg
    feasible = (d * drain <= battery + 1e-9).astype(float)
    item_score = (item_eff / scale) * feasible
    charger_score = is_charger.astype(float) * (1.0 - battery)
    return item_score + charger_score

# f028 best_followup_item_after_pickup (wide): Max-decayed-value of any single other item reachable after picking this candidate (battery after arrival, then
def _f028(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Max-decayed-value of any single other item reachable after picking this candidate (battery after arrival, then detour to that item and back to charger), minus the value-at-risk of the chosen candidate; charger row uses 1 - battery."""
    d = np.linalg.norm(targets - pos[None, :], axis=1)          # pos -> each candidate
    is_item = values > 0
    D = np.linalg.norm(targets[:, None, :] - targets[None, :, :], axis=2)  # candidate -> other
    dch = np.linalg.norm(targets - charger[None, :], axis=1)    # candidate -> charger
    b_after = battery - d * drain                               # battery at each candidate
    # reachability from candidate i to other item j and back to charger
    trip = D + dch[None, :]                                     # (i,j)
    reach = (b_after[:, None] - trip * drain) > 0
    reach &= is_item[None, :]
    np.fill_diagonal(reach, False)
    # decayed value of j at time we'd get there (via i)
    vj = np.maximum(values[None, :] - rates[None, :] * (d[:, None] + D), 0.0)
    # best single follow-up item (not sum) -> focuses on the next good move
    masked = np.where(reach, vj, 0.0)
    best_follow = masked.max(axis=1) if masked.size else np.zeros(len(targets))
    norm = max(values.max(), 1e-9)
    follow = best_follow / norm

    # value-at-risk of the chosen candidate itself (how much it decays before arrival)
    arrival = np.maximum(values - rates * d, 0.0)
    risk = np.where(is_item, 1.0 - arrival / np.maximum(values, 1e-9), 0.0)

    item_score = np.clip(follow * 0.7 - risk * 0.5, -1.0, 1.0)
    charger_score = (~is_item).astype(float) * (1.0 - battery)
    return np.where(is_item, item_score, charger_score)

name: best_followup_item_after_pickup

# f027 stranded_recharge_time_penalty (wide): Negative shortfall of the out-and-back trip measured in recharge-time units (how long you'd be stuck rechargin
def _f027(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Negative shortfall of the out-and-back trip measured in recharge-time units (how long you'd be stuck recharging), gated to items only; zero for the charger and zero when the trip is affordable."""
    d = np.linalg.norm(targets - pos[None, :], axis=1)
    dch = np.linalg.norm(targets - charger[None, :], axis=1)
    need = (d + dch) * drain
    shortfall_batt = np.maximum(need - battery, 0.0)
    # convert the battery shortfall into the wall-clock time it costs to recover it
    stuck_time = shortfall_batt / max(charge_rate, 1e-9)
    # also add the raw flight time that the shortfall implies (must detour via charger)
    extra_fly = shortfall_batt / max(drain, 1e-9)
    cost = stuck_time + extra_fly
    # normalise by a soft time scale: the whole horizon + a floor
    scale = max(time_left, 1.0) + 1.0
    feat = -np.clip(cost / scale, 0.0, 1.0)
    is_item = values > 0
    return np.where(is_item, feat, 0.0)

name: stranded_recharge_time_penalty

# f042 pair_slack_chain (deep): Min over the two legs of the best pair (c then j) of the slack life - travel time, clipped and zero for the ch
def _f042(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Min over the two legs of the best pair (c then j) of the slack life - travel time, clipped and zero for the charger."""
    k = targets.shape[0]
    is_item = values > 0
    d = np.linalg.norm(targets - pos[None, :], axis=1)  # (k,)
    diff = targets[:, None, :] - targets[None, :, :]     # (k, k, 2)
    D = np.linalg.norm(diff, axis=2)                     # (k, k)
    life = values / np.maximum(rates, 1e-9)              # (k,)
    slack1 = life - d                                    # (k,)
    second = life[None, :] - (d[:, None] + D)            # (k, k)
    masked = np.where(np.eye(k, dtype=bool), -1e9, np.minimum(slack1[:, None], second))
    pair = masked.max(axis=1)                            # (k,)
    return np.where(is_item, np.clip(pair / 3.0, -1.0, 1.0), 0.0)

# f054 endgame_surviving_density (wide): Endgame density of value that still survives to arrival, minus the unreachable overshoot: arrival value per un
def _f054(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Endgame density of value that still survives to arrival, minus the unreachable overshoot: arrival value per unit time-to-reach, weighted by how much of the item's remaining life the trip consumes, zero outside the last stretch before the end."""
    k = targets.shape[0]
    is_item = values > 0
    d1 = np.sqrt(((targets - pos) ** 2).sum(axis=1))
    travel = np.maximum(d1, 1e-3)
    arrival = np.maximum(values - rates * travel, 0.0)
    # does the trip even finish before the episode ends? if not, it collects nothing
    finishes = (travel <= time_left).astype(float)
    # how much of the item's remaining life the trip eats (urgency)
    life = np.where(rates > 0, values / np.maximum(rates, 1e-9), 1e9)
    life_share = np.clip(travel / np.maximum(life, 1e-9), 0.0, 1.0)
    # density: surviving value per unit of time spent flying there, boosted when the trip eats the item's life
    dens = (arrival / travel) * (1.0 + life_share) * finishes
    dens = np.where(is_item, dens, 0.0)
    dens = np.where(np.isfinite(dens), dens, 0.0)
    dmax = dens.max() if k > 0 else 0.0
    # gate: only in the endgame window, and only meaningful if something is still capturable
    window = np.clip((8.0 - time_left) / 8.0, 0.0, 1.0)
    if dmax > 0.0 and window > 0.0:
        out = (dens / dmax) * window
    else:
        out = np.zeros(k)
    out = np.where(is_item, out, 0.0)
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)

# f074 roundtrip_battery_margin_gate (deep): Negative clipped excess of the out-and-back battery need over 70% of the current battery (0 for the charger).
def _f074(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Negative clipped excess of the out-and-back battery need over 70% of the current battery (0 for the charger)."""
    pos = np.asarray(pos, dtype=float)
    targets = np.asarray(targets, dtype=float)
    values = np.asarray(values, dtype=float)
    charger = np.asarray(charger, dtype=float)

    d1 = np.linalg.norm(targets - pos[None, :], axis=1)
    d_back = np.linalg.norm(targets - charger[None, :], axis=1)
    need = drain * (d1 + d_back)
    ratio = need / max(float(battery), 1e-6)
    score = -np.clip(ratio - 0.7, 0.0, 1.0)
    score = np.where(values == 0, 0.0, score)
    return np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)

_TERMS = [(_f002, np.array([-1.606034])), (_f015, np.array([2.452487])), (_f016, np.array([74.74505])), (_f012, np.array([2.346131])), (_f014, np.array([0.37485])), (_f028, np.array([3.520027])), (_f027, np.array([6041.787487])), (_f042, np.array([-0.616778])), (_f054, np.array([1.700013])), (_f074, np.array([0.478509]))]

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
