# Helix v3 policy: forage, gap 54.579%, progress 45.4%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f006 value_density_per_cycle_time (wide): Expected value density: value that survives the trip divided by the round-trip travel-plus-charge time cost, w
def _f006(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Expected value density: value that survives the trip divided by the round-trip travel-plus-charge time cost, with charger row scored by idle-wait opportunity."""
    # distances from drone to each candidate
    d = np.linalg.norm(targets - pos[None, :], axis=1)
    # time to reach each candidate
    t_go = d
    # value remaining on arrival (clipped at 0)
    val_after = np.clip(values - rates * t_go, 0.0, None)
    # battery needed and whether we can make it
    need = d * drain
    can = (need <= battery).astype(float)
    # time to fly back from candidate to charger plus recharge to full (approx)
    d_back = np.linalg.norm(targets - charger[None, :], axis=1)
    t_back = d_back
    # battery after flight: battery - need; recharge time to full
    batt_after = np.clip(battery - need, 0.0, 1.0)
    t_charge = (1.0 - batt_after) / max(charge_rate, 1e-6)
    # total cycle cost in time
    cycle = t_go + t_back + t_charge
    # density of surviving value per unit of cycle time
    is_item = (values > 0)
    dens = np.where(is_item, val_after / np.maximum(cycle, 1e-6), 0.0)
    dens = dens * can
    # charger row: prefer charging when battery low and no good item nearby
    charger_row = ~is_item
    # urgency of charging: low battery, small distance to charger
    charger_score = (1.0 - battery) * (1.0 - np.clip(d / np.maximum(time_left, 1e-6), 0.0, 1.0))
    dens = np.where(charger_row, charger_score, dens)
    # normalise to roughly [-1, 1]
    scale = np.max(np.abs(dens)) + 1e-9
    return dens / scale

# f020 local_arrival_opportunity_cost (deep): (value surviving the flight minus recent arrival-rate times flight time) / max current value, clipped to [-1,1
def _f020(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """(value surviving the flight minus recent arrival-rate times flight time) / max current value, clipped to [-1,1]; 0 for charger."""
    win = max(time - 20.0, 0.0)
    if history is None or len(history) == 0:
        lam = 0.0
    else:
        hist = np.asarray(history, dtype=float)
        recent = hist[hist[:, 2] >= win]
        if recent.shape[0] == 0:
            recent = hist
        span = max(time - win, 1.0)
        lam = float(np.sum(recent[:, 3])) / span

    d = np.sqrt(np.sum((targets - pos[None, :]) ** 2, axis=1))
    val_after = np.clip(values - rates * d, 0.0, None)
    scale = max(float(np.max(values)), 1e-6)
    net = (val_after - lam * d) / scale
    net = np.clip(net, -1.0, 1.0)
    net = np.where(values == 0, 0.0, net)
    return net

# f019 soft_battery_shortfall (deep): Negative tanh of the recharge time forced by a round trip the battery cannot cover (0 for charger).
def _f019(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Negative tanh of the recharge time forced by a round trip the battery cannot cover (0 for charger)."""
    d = np.linalg.norm(targets - pos, axis=1)
    d_back = np.linalg.norm(targets - charger, axis=1)
    need = drain * (d + d_back)
    deficit_time = np.clip(need - battery, 0.0, None) / max(charge_rate, 1e-9)
    out = -np.tanh(deficit_time / 5.0)
    out = np.where(values > 0, out, 0.0)
    return out

# f024 horizon_pressure_per_expiry_window (wide): Value per unit of *remaining horizon* risk: surviving value divided by (trip time + time until item's own expi
def _f024(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Value per unit of *remaining horizon* risk: surviving value divided by (trip time + time until item's own expiry), 0 for charger, charger row = idle decay rate of visible world scaled by battery slack."""
    d = np.linalg.norm(targets - pos[None, :], axis=1)
    is_item = values > 0
    # time until each item's value hits zero (its natural death)
    tau = np.where(is_item, values / np.maximum(rates, 1e-9), np.inf)
    # time to arrive
    t_go = d
    # surviving value
    val_after = np.clip(values - rates * t_go, 0.0, None)
    # effective window: we must arrive before expiry, and the remaining horizon also matters
    window = np.minimum(tau, time_left)
    # pressure: value arriving per unit of the tightest window left
    press = np.where(is_item, val_after / np.maximum(window + t_go, 1e-6), 0.0)
    # penalise items we'd arrive after they vanish (val_after already 0), and horizon overrun
    press = np.where(t_go > tau, 0.0, press)
    # charger row: how fast the whole visible world is bleeding value while we sit and recharge
    # only attractive when battery is low (need to go), else idle waiting is costly
    world_decay = float(np.sum(rates[is_item]))
    d_ch = float(np.linalg.norm(charger - pos))
    t_charge = max(1.0 - battery, 0.0) / max(charge_rate, 1e-6)
    charger_val = -world_decay * (d_ch + t_charge) * (1.0 - battery)
    out = np.where(is_item, press, charger_val)
    s = np.max(np.abs(out)) + 1e-9
    return out / s

# f022 competition_adjusted_arrival_value (wide): Competition-adjusted arrival value: surviving value minus the value better rivals will take first, divided by 
def _f022(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Competition-adjusted arrival value: surviving value minus the value better rivals will take first, divided by the candidate's own value, clipped; 0 for charger."""
    d = np.sqrt(np.sum((targets - pos[None, :]) ** 2, axis=1))
    is_item = values > 0
    val_after = np.clip(values - rates * d, 0.0, None)

    # How far is every candidate from every other candidate: who can beat whom to the punch
    diff = targets[:, None, :] - targets[None, :, :]
    dd = np.sqrt(np.sum(diff ** 2, axis=2))  # (k, k)
    # rival i vs candidate j: rival's arrival time from drone is d_i; candidate j arrives at d_j
    # rival beats candidate j if d_i + dd[i, j] < d_j (rival gets there first) -- but only if rival survives
    rival_val_after = np.clip(values[None, :] - rates[None, :] * d[:, None], 0.0, None)  # (k rivals, k cands)
    arrive_rival_at_j = d[:, None] + dd  # (k rivals, k cands)
    beats = arrive_rival_at_j < d[None, :]  # rival reaches j before drone does
    # value that will be stolen from j by rivals (only items, and rivals that are items)
    stolen = np.where(beats & (values[:, None] > 0), rival_val_after, 0.0).sum(axis=0)

    scale = np.maximum(np.abs(values), 1e-6)
    net = (val_after - stolen) / scale
    net = np.clip(net, -1.0, 1.0)
    net = np.where(is_item, net, 0.0)
    return net

# f030 best_alternative_opportunity_cost (wide): Opportunity cost of flying to each candidate measured only against the *best alternative* it displaces: surviv
def _f030(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Opportunity cost of flying to each candidate measured only against the *best alternative* it displaces: surviving value minus the value of the strongest rival item the trip would cost, normalised, 0 for charger."""
    is_item = values > 0
    d = np.sqrt(np.sum((targets - pos[None, :]) ** 2, axis=1))
    # surviving value on arrival
    val_after = np.clip(values - rates * d, 0.0, None)
    # per-unit-time "worth" of each item: surviving value / arrival time (density proxy)
    worth = val_after / np.maximum(d, 1e-3)
    # best rival worth excluding self (only among items)
    worth_items = np.where(is_item, worth, -1.0)
    k = len(values)
    if k > 1:
        idx = np.argsort(-worth_items)
        best = worth_items[idx[0]]
        second = worth_items[idx[1]] if k > 1 else best
        # for each candidate, the best rival worth (if candidate is the top, use second best)
        is_top = worth_items >= best
        best_rival = np.where(is_top, second, best)
    else:
        best_rival = np.full(k, -1.0)
    # opportunity cost: what we forgo by choosing this candidate now, weighted by time spent
    forgone = np.clip(best_rival, 0.0, None) * d
    scale = max(float(np.max(values)), 1e-6)
    net = (val_after - forgone) / scale
    net = np.clip(net, -1.0, 1.0)
    net = np.where(is_item, net, 0.0)
    return net

# f025 two_step_density_gain (deep): Relative density gain from chaining a nearby second item after each candidate, clipped to [-1,1]; 0 for charge
def _f025(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Relative density gain from chaining a nearby second item after each candidate, clipped to [-1,1]; 0 for charger."""
    pos = np.asarray(pos, dtype=float)
    targets = np.asarray(targets, dtype=float)
    values = np.asarray(values, dtype=float)
    rates = np.asarray(rates, dtype=float)
    charger = np.asarray(charger, dtype=float)

    k = targets.shape[0]
    is_item = values > 0

    d = np.linalg.norm(targets - pos[None, :], axis=1)          # (k,)
    Dc = np.linalg.norm(targets - charger[None, :], axis=1)     # (k,)

    # single leg
    c1 = d + Dc + (d + Dc) * drain / max(charge_rate, 1e-6)
    V1 = np.maximum(values - rates * d, 0.0)
    D1 = V1 / np.maximum(c1, 1e-6)

    # pairwise distances between candidates
    diff = targets[:, None, :] - targets[None, :, :]            # (k,k,2)
    Dm = np.linalg.norm(diff, axis=2)                           # (k,k)

    # two legs: i then j
    d_i = d[:, None]                                            # (k,1)
    Dc_j = Dc[None, :]                                          # (1,k)
    V2 = np.maximum(values[None, :] - rates[None, :] * (d_i + Dm), 0.0)   # (k,k)
    c2 = d_i + Dm + Dc_j + (d_i + Dm + Dc_j) * drain / max(charge_rate, 1e-6)
    D2 = (V1[:, None] + V2) / np.maximum(c2, 1e-6)              # (k,k)

    valid = is_item[:, None] & is_item[None, :] & (~np.eye(k, dtype=bool))
    best2 = np.where(valid, D2, -1.0).max(axis=1)               # (k,)
    has = valid.any(axis=1)

    out = np.clip((best2 - D1) / (best2 + D1 + 1e-6), -1.0, 1.0)
    return np.where(is_item & has, out, 0.0)

# f028 static_history_density_ratio (deep): Log ratio of past-arrival density within 0.15 of each candidate to the uniform density, clipped to [-1,1].
def _f028(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Log ratio of past-arrival density within 0.15 of each candidate to the uniform density, clipped to [-1,1]."""
    k = targets.shape[0]
    if history.shape[0] == 0:
        return np.zeros(k)
    dd = np.linalg.norm(targets[:, None, :] - history[None, :, :2], axis=2)
    counts = (dd < 0.15).sum(axis=1)
    area = np.pi * 0.15 ** 2
    r = (counts + 0.5) / (history.shape[0] * area + 0.5)
    return np.clip(np.log(r) / 2.0, -1.0, 1.0)

# f086 charger_unlockable_value (deep): Charger row: value-weighted battery shortfall of visible items (0 elsewhere).
def _f086(pos, targets, values, rates, battery, drain, charge_rate, charger, time, time_left, history):
    """Charger row: value-weighted battery shortfall of visible items (0 elsewhere)."""
    d = np.linalg.norm(targets - pos, axis=1)
    v_arr = np.maximum(values - rates * d, 0.0)
    need = d * drain
    item = values > 0
    short = np.where(item, np.clip(need - battery, 0.0, 1.0), 0.0)
    score = float(np.sum(v_arr * short) / (np.sum(np.where(item, v_arr, 0.0)) + 1e-6))
    out = np.zeros(targets.shape[0])
    out[~item] = np.clip(score, 0.0, 1.0)
    return out

_TERMS = [(_f006, np.array([6.251426])), (_f020, np.array([10.549859])), (_f019, np.array([6688.720277])), (_f024, np.array([-0.953915])), (_f022, np.array([9.660173])), (_f030, np.array([9.707134])), (_f025, np.array([-4.157561])), (_f028, np.array([0.049072])), (_f086, np.array([4766.589362]))]

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
