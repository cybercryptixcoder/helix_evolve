# Helix v3 policy: fairshare, gap 40.809%, progress 59.2%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f005 pref_match_floor (deep): 0.5 + 0.5 * (this shift is preferred by the candidate) for real candidates, 0 for uncovered.
def _f005(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):
    """0.5 + 0.5 * (this shift is preferred by the candidate) for real candidates, 0 for uncovered."""
    v = np.maximum(cand, 0)
    real = cand >= 0
    p = pref[v, shift]
    values = np.where(real, 0.5 + 0.5 * p, 0.0)
    return values

# f006 target_deficit_norm (deep): Remaining deficit (target - assigned) / max(target, 1), clipped to [-1, 1]; uncovered gets the minimum real de
def _f006(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):
    """Remaining deficit (target - assigned) / max(target, 1), clipped to [-1, 1]; uncovered gets the minimum real deficit."""
    v = np.maximum(cand, 0)
    real = cand >= 0
    d = (target[v] - assigned[v]) / np.maximum(target[v], 1.0)
    d = np.clip(d, -1.0, 1.0)
    if real.any():
        uncovered_val = np.min(d[real])
    else:
        uncovered_val = 0.0
    values = np.where(real, d, uncovered_val)
    return values

# f007 coverage_tightness_gate (deep): Tightness gate (1 - eligible candidates / positions left on this shift, clipped to [0,1]) applied to real cand
def _f007(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):
    """Tightness gate (1 - eligible candidates / positions left on this shift, clipped to [0,1]) applied to real candidates, 0 for uncovered."""
    real = cand >= 0
    k = float(real.sum())
    rem = float(demand[shift] - position)
    tight = min(max(1.0 - k / max(rem, 1.0), 0.0), 1.0)
    values = np.where(real, tight, 0.0)
    return values

# f009 opportunity_scarcity_pressure (wide): Deficit relative to remaining real opportunities: how many preferred shifts the volunteer still needs versus h
def _f009(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):
    """Deficit relative to remaining real opportunities: how many preferred shifts the volunteer still needs versus how many preferred shifts they can still take this week, gated by remaining slack, boosted when the current shift is preferred."""
    v = np.maximum(cand, 0)
    valid = (cand >= 0).astype(float)
    is_pref = pref[v, shift]
    load = assigned[v]
    tgt = target[v]
    mx = np.maximum(max_load[v], 1.0)

    # deficit to target (how many more shifts they'd like), clipped to [0, mx]
    deficit = np.clip(tgt - load, 0.0, mx)
    # remaining slack before max
    slack = np.clip(mx - load, 0.0, None)

    # remaining preferred and available opportunities strictly after this shift
    future = np.arange(shift + 1, 35)
    if len(future) > 0:
        pref_fut = pref[v][:, future].sum(axis=1)
        avail_fut = avail[v][:, future].sum(axis=1)
    else:
        pref_fut = np.zeros(len(v))
        avail_fut = np.zeros(len(v))

    # competition: how many future preferred opportunities per needed shift
    opp = np.maximum(pref_fut, 1.0)
    urgency = deficit / opp  # high when they need many shifts but few preferred slots left

    # scarcity of this specific shift: preferred opportunity pressure
    pref_frac = pref_fut / np.maximum(avail_fut, 1.0)

    # remaining demand on this shift relative to demand
    rem = max(demand[shift] - position - 1, 0) / max(demand[shift], 1)

    # scarcity of opportunity: the fewer preferred slots left, the more this shift matters
    scarcity = 1.0 / (1.0 + pref_fut)

    score = (0.6 + is_pref) * np.tanh(urgency) * np.clip(slack / mx, 0.0, 1.0)
    score += 0.4 * is_pref * scarcity
    score += 0.3 * rem * np.tanh(urgency)
    # slight penalty for taking non-preferred when preferred options still exist
    score -= 0.2 * (1.0 - is_pref) * (1.0 - pref_frac) * np.tanh(deficit / mx)

    return np.where(valid > 0, np.clip(score, -1.0, 1.0), 0.0)

name: opportunity_scarcity_pressure

# f013 need_per_opportunity_pref_pressure (deep): Preference-weighted target deficit per remaining real opportunity (future available-untaken shifts capped by r
def _f013(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):
    """Preference-weighted target deficit per remaining real opportunity (future available-untaken shifts capped by remaining capacity, +1)."""
    v = np.maximum(cand, 0)
    real = cand >= 0
    fut = (np.arange(35) > shift).astype(float)
    rem_avail = np.sum(avail[v] * (1.0 - taken[v]) * fut[None, :], axis=1)
    cap = np.maximum(max_load[v] - assigned[v], 0.0)
    eff_opp = np.minimum(rem_avail, cap)
    need = np.clip((target[v] - assigned[v]) / np.maximum(eff_opp + 1.0, 1.0), -1.0, 1.0)
    is_pref = pref[v, shift]
    val = (0.5 + 0.5 * is_pref) * (0.5 + 0.5 * need)
    val = np.where(real, val, 0.0)
    return val

# f010 opponent_adjusted_need (wide): Opponent-adjusted need: how much this volunteer needs the shift relative to competing candidates' need, gated 
def _f010(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):
    """Opponent-adjusted need: how much this volunteer needs the shift relative to competing candidates' need, gated by whether their future availability is thinning."""
    v = np.maximum(cand, 0)
    real = cand >= 0

    load = assigned[v]
    tgt = target[v]
    mx = np.maximum(max_load[v], 1.0)

    # Need beyond target is penalised: over-target work hurts |assigned - target|
    deficit = tgt - load                      # can be negative (already over target)
    need = np.clip(deficit / np.maximum(tgt, 1.0), -1.0, 1.0)

    # Flexibility: how many future available slots remain per remaining shift of the week
    future = np.arange(shift + 1, 35)
    if len(future) > 0:
        avail_future = avail[v][:, future].sum(axis=1)
        pref_future = pref[v][:, future].sum(axis=1)
    else:
        avail_future = np.zeros(len(v))
        pref_future = np.zeros(len(v))

    # Thinning: fewer future options than remaining capacity needed -> must take now
    remaining_cap = np.maximum(mx - load, 0.0)
    thin = 1.0 / (1.0 + avail_future / np.maximum(remaining_cap, 1.0))

    is_pref = pref[v, shift] if shift < 35 else np.zeros(len(v))
    is_pref = np.asarray(is_pref, dtype=float)

    # Preference weight: preferred shifts count full, unpreferred half
    pref_w = 0.5 + 0.5 * is_pref

    # Raw urgency for each real candidate
    urgency = need * pref_w * (0.5 + thin)

    # Opponent adjustment: subtract the mean urgency of the other candidates
    # (so a candidate wins only if they need it more than the competition)
    raw = np.where(real, urgency, 0.0)
    n_real = max(real.sum(), 1)
    mean_other = (raw.sum() - raw) / np.maximum(n_real - 1, 1)

    score = (raw - mean_other) / (1.0 + np.abs(raw - mean_other))
    score = np.where(real, score, -1.0)
    return np.clip(score, -1.0, 1.0)

name: opponent_adjusted_need

# f014 specialist_reservation_tight_share (deep): Negative share of tight (high demand/eligibility) future shifts in each candidate's remaining availability, ga
def _f014(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):
    """Negative share of tight (high demand/eligibility) future shifts in each candidate's remaining availability, gated by remaining slack; uncovered gets the minimum real value."""
    v = np.maximum(cand, 0)
    real = (cand >= 0)
    elig = np.sum(avail, axis=0)  # (35,)
    dem = np.maximum(demand.astype(float), 1.0)
    tight = np.clip(dem / np.maximum(elig, 1.0), 0.0, 1.0)
    fut = (np.arange(35) > shift).astype(float)
    w = fut * tight
    A = avail[v] * (1.0 - taken[v])  # (k, 35)
    exposed = A @ w
    total = np.sum(A * fut, axis=1)
    share = exposed / np.maximum(total, 1e-6)
    gate = np.clip((max_load[v] - assigned[v]) / np.maximum(max_load[v], 1.0), 0.0, 1.0)
    val = -share * gate
    if np.any(~real):
        fill = np.min(val[real]) if np.any(real) else 0.0
        val = np.where(real, val, fill)
    return val

# f023 capacity_surplus_ratio (deep): Surplus-capacity ratio: clip((slack - eff_opp)/(slack + 1), 0, 1) per real candidate; uncovered gets the min r
def _f023(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):
    """Surplus-capacity ratio: clip((slack - eff_opp)/(slack + 1), 0, 1) per real candidate; uncovered gets the min real value."""
    v = np.maximum(cand, 0)
    real = cand >= 0
    slack = np.maximum(max_load[v] - assigned[v], 0.0)
    future = np.arange(35)[None, :] > shift
    opp = np.sum((avail[v] * future) * (1.0 - taken[v]), axis=1)
    eff_opp = np.minimum(opp, slack)
    value = np.clip((slack - eff_opp) / (slack + 1.0), 0.0, 1.0)
    value = np.where(real, value, 0.0)
    if np.any(real):
        value = np.where(real, value, np.min(value[real]))
    return value

# f018 contested_urgency_room_gate (wide): Ratio of the candidate's remaining need (target deficit) to their remaining eligible capacity, but only among 
def _f018(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):
    """Ratio of the candidate's remaining need (target deficit) to their remaining eligible capacity, but only among shifts that are actually contested; times preference for this shift — a conditional urgency that switches off when the volunteer has plenty of room left."""
    v = np.maximum(cand, 0)
    real = cand >= 0
    is_pref = pref[v, shift]
    load = assigned[v]
    tgt = target[v]
    mx = np.maximum(max_load[v], 1.0)

    # remaining real opportunity: future available & untaken shifts, capped by remaining capacity
    fut = (np.arange(35) > shift).astype(float)
    rem_avail = np.sum(avail[v] * (1.0 - taken[v]) * fut[None, :], axis=1)
    cap = np.maximum(mx - load, 0.0)
    eff_opp = np.minimum(rem_avail, cap)

    deficit = np.clip(tgt - load, 0.0, None)
    # urgency: need relative to how many slots they can still realistically take
    urgency = np.tanh(deficit / np.maximum(eff_opp, 1.0))

    # only matters where the volunteer still has meaningful room to work
    room = np.clip(cap / np.maximum(mx, 1.0), 0.0, 1.0)

    # prefer giving the binding shift to those who actually want it
    pref_w = 0.5 + 0.5 * is_pref

    score = pref_w * urgency * room

    # penalise loading up volunteers who are over their target but could still be pulled in
    over = np.clip((load - tgt) / np.maximum(tgt, 1.0), 0.0, 1.0)
    score -= 0.5 * over * (1.0 - is_pref)

    return np.where(real, np.clip(score, -1.0, 1.0), 0.0)

name: contested_urgency_room_gate

# f020 target_overshoot_marginal (wide): Marginal effect on the candidate's own |worked - target| if they take this shift now, normalised to [-1, 1]; u
def _f020(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):
    """Marginal effect on the candidate's own |worked - target| if they take this shift now, normalised to [-1, 1]; uncovered gets the max over real candidates (least attractive to leave a gap for someone who'd be hurt)."""
    v = np.maximum(cand, 0)
    real = cand >= 0
    load = assigned[v]
    tgt = target[v]
    # marginal change in |worked - target|
    delta = np.abs(load + 1.0 - tgt) - np.abs(load - tgt)  # in [-1, 1] since load, tgt are ints
    # gate: only matters when the candidate is over or near target (delta > 0 means overshoot hurts)
    # normalise by 1 (already in [-1,1] range for integer loads)
    val = np.clip(delta, -1.0, 1.0)
    if real.any():
        fill = np.max(val[real])
    else:
        fill = 0.0
    return np.where(real, val, fill)

name: target_overshoot_marginal

# f027 signed_surplus_demand_exposure (wide): Signed surplus/deficit of demand-adjusted capacity: (slack - contested future demand on the candidate's availa
def _f027(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):
    """Signed surplus/deficit of demand-adjusted capacity: (slack - contested future demand on the candidate's available shifts) normalised, so over-subscribed volunteers (who are needed to cover scarce shifts) score high and surplus volunteers score low."""
    v = np.maximum(cand, 0)
    real = cand >= 0
    slack = np.maximum(max_load[v] - assigned[v], 0.0)

    # Demand pressure on each future shift: how many positions still need filling
    dem = demand.astype(float)
    fut = (np.arange(35)[None, :] > shift).astype(float)

    # How contested each future shift is: remaining positions per eligible volunteer
    elig = np.maximum(np.sum(avail, axis=0), 1.0)
    # A shift is "needed" by a volunteer if they are eligible and it isn't taken yet
    # Weight by remaining demand pressure (positions still to fill), normalised per shift
    rem_pos = np.maximum(dem - 0.0, 0.0)  # total demand; approximation of remaining positions
    pressure = rem_pos / elig  # (35,) in [0, ~1]

    # The candidate's exposure to contested future shifts: sum of pressure over their free eligible future shifts
    free_fut = avail[v] * (1.0 - taken[v]) * fut
    exposure = free_fut @ pressure  # (k,)

    # Signed surplus: positive slack beyond exposure -> surplus; negative -> oversubscribed (needed)
    # Normalise by their own capacity scale
    scale = np.maximum(slack, 1.0)
    value = np.clip((slack - exposure) / (scale + exposure), -1.0, 1.0)

    if np.any(real):
        fill = np.max(value[real])
    else:
        fill = 0.0
    return np.where(real, value, fill)

name: signed_surplus_demand_exposure

# f031 pref_need_per_remaining_capacity (deep): Preference-weighted target deficit per remaining capacity (max_load - assigned + 1), clipped to [-1, 1]; uncov
def _f031(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):
    """Preference-weighted target deficit per remaining capacity (max_load - assigned + 1), clipped to [-1, 1]; uncovered gets the min over real candidates."""
    v = np.maximum(cand, 0)
    real = cand >= 0
    deficit = target[v] - assigned[v]
    cap = np.maximum(max_load[v] - assigned[v], 0.0)
    is_pref = pref[v, shift]
    val = np.clip(is_pref * deficit / (cap + 1.0), -1.0, 1.0)
    if np.any(real):
        val = np.where(real, val, np.min(val[real]))
    else:
        val = np.zeros_like(val)
    return val

# f032 marginal_post_dissatisfaction_vs_mean (deep): Negative |candidate's post-assignment dissatisfaction - new population mean dissatisfaction|, scaled; uncovere
def _f032(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):
    """Negative |candidate's post-assignment dissatisfaction - new population mean dissatisfaction|, scaled; uncovered gets min over real candidates."""
    v = np.maximum(cand, 0)
    real = cand >= 0
    d_all = unpreferred + np.abs(assigned - target)
    S = float(d_all.sum())
    V = float(len(assigned))
    d_new = (unpreferred[v] + (1.0 - pref[v, shift])) + np.abs(assigned[v] + 1.0 - target[v])
    mean_new = (S - d_all[v] + d_new) / V
    scale = 1.0 + float(np.mean(np.abs(d_all)))
    val = np.clip(-np.abs(d_new - mean_new) / scale, -1.0, 0.0)
    if np.any(real):
        val = np.where(real, val, float(np.min(val[real])))
    else:
        val = np.where(real, val, 0.0)
    return val

# f026 endgame_preferred_supply_urgency (wide): Under-target volunteers get a positive score only on their last remaining preferred opportunities (endgame urg
def _f026(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):
    """Under-target volunteers get a positive score only on their last remaining preferred opportunities (endgame urgency); over-target or well-supplied volunteers score near zero."""
    v = np.maximum(cand, 0)
    real = cand >= 0
    is_pref = pref[v, shift]
    load = assigned[v]
    tgt = target[v]
    mx = np.maximum(max_load[v], 1.0)

    deficit = np.clip(tgt - load, 0.0, None)          # how many more they want
    slack = np.clip(mx - load, 0.0, None)             # room under max

    # remaining preferred & available opportunities strictly after this shift
    future = np.arange(35)[None, :] > shift
    pref_fut = np.sum(pref[v] * future, axis=1)
    avail_fut = np.sum(avail[v] * future, axis=1)

    # endgame: how many preferred slots remain versus the deficit still to fill
    # ratio >> 1 means plenty of preferred options left -> this shift is not urgent
    supply = pref_fut / np.maximum(deficit, 1.0)
    # 1 when preferred supply is scarce relative to need, ->0 when abundant
    endgame = 1.0 / (1.0 + supply)

    # only relevant if the volunteer still needs shifts; over-target kills it
    need_gate = np.clip(deficit / np.maximum(tgt, 1.0), 0.0, 1.0)
    # and only if this shift is actually usable (preferred) — non-preferred gets a small
    # residual signal so they can still be picked as a last resort
    pref_w = 0.25 + 0.75 * is_pref

    # available-opportunity pressure: if few available slots remain, urgency rises
    avail_ratio = 1.0 / (1.0 + avail_fut / np.maximum(slack, 1.0))

    score = pref_w * need_gate * endgame * (0.5 + 0.5 * avail_ratio)

    # damp for candidates already comfortably over target
    over = np.clip((load - tgt) / np.maximum(tgt, 1.0), 0.0, 1.0)
    score -= 0.5 * over

    score = np.where(real, np.clip(score, -1.0, 1.0), 0.0)
    return score

name: endgame_preferred_supply_urgency

# f040 near_term_decisive_reservation (deep): Negative share of imminent (next 5 shifts) decisive short shifts in the candidate's remaining availability, sc
def _f040(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):
    """Negative share of imminent (next 5 shifts) decisive short shifts in the candidate's remaining availability, scaled by slack."""
    v = np.maximum(cand, 0)
    real = cand >= 0
    t = np.arange(35)
    win = ((t > shift) & (t <= shift + 5)).astype(float)
    can = (avail * (1.0 - taken) * (assigned[:, None] < max_load[:, None])).astype(float)
    E = can.sum(0)
    rem = np.maximum(demand.astype(float) - taken.sum(0), 0.0)
    decisive = ((E <= rem) & (rem > 0)).astype(float) * win
    use = avail[v] * (1.0 - taken[v]) * win[None, :]
    L = (use * decisive[None, :]).sum(1)
    slack = np.maximum(max_load[v] - assigned[v], 0.0)
    return np.where(real, -np.clip(L / (slack + 1.0), 0.0, 1.0), 0.0)

# f045 critical_specialist_reservation (wide): Relative scarcity of this shift's remaining coverage: how many still-unfilled positions on the current shift e
def _f045(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):
    """Relative scarcity of this shift's remaining coverage: how many still-unfilled positions on the current shift exceed the number of candidates who are the *only* eligible volunteers for some later shift (key specialists), gated to the candidate by whether they are themselves such a specialist."""
    v = np.maximum(cand, 0)
    real = cand >= 0

    # Remaining positions on this shift after the current one
    rem_here = float(max(demand[shift] - position, 1))

    # For each future shift, count eligible-and-under-max volunteers; a shift is "critical"
    # when it has at most as many eligible volunteers as its remaining positions.
    under_max = (assigned[:, None] < max_load[:, None]).astype(float)
    elig = (avail * under_max)  # (V, 35)
    E = elig.sum(axis=0)        # eligible count per shift
    rem_pos = np.maximum(demand.astype(float) - taken.sum(axis=0), 0.0)
    critical = ((rem_pos > 0) & (E <= rem_pos)).astype(float)  # (35,)

    # Restrict to the future (strictly after this shift); the current shift is being decided now
    fut = (np.arange(35) > shift).astype(float)
    crit_fut = critical * fut

    # Does this candidate uniquely cover any critical future shift?
    covers_crit = (elig[v] * crit_fut[None, :]).sum(axis=1)  # (k,)
    # Total critical future shifts (for normalisation)
    total_crit = crit_fut.sum()

    # How contested the current shift is: candidates per remaining position
    k_real = float(real.sum())
    pressure = k_real / rem_here  # >1 means more candidates than positions

    # Specialist flag: candidate covers critical future shifts, weighted by how rare that is
    spec = covers_crit / (total_crit + 1.0)

    # If the current shift is well-supplied (many candidates, few positions), we should
    # avoid spending a critical specialist here; if it's tight, specialists are needed now too.
    # Score: specialists are penalised when the current shift is easy to cover,
    # and neutral/positive when it is tight.
    ease = np.clip(1.0 - 1.0 / (1.0 + pressure), 0.0, 1.0)  # 0 when tight, ->1 when oversupplied
    val = -spec * ease

    # Over-target specialists are especially wasteful here
    over = np.clip((assigned[v] - target[v]) / np.maximum(target[v], 1.0), 0.0, 1.0)
    val = val - 0.5 * spec * over

    return np.where(real, np.clip(val, -1.0, 1.0), 0.0)

name: critical_specialist_reservation

_TERMS = [(_f005, np.array([-4.271546])), (_f006, np.array([4.569469])), (_f007, np.array([1.048449])), (_f009, np.array([25.120158])), (_f013, np.array([97.786492])), (_f010, np.array([9.147589])), (_f014, np.array([45.716343])), (_f023, np.array([17.257009])), (_f018, np.array([-35.531612])), (_f020, np.array([-7.039526])), (_f027, np.array([28.475723])), (_f031, np.array([-3.196181])), (_f032, np.array([8.984136])), (_f026, np.array([9.864718])), (_f040, np.array([25.233045])), (_f045, np.array([-7.834671]))]

def priority(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(shift, cand, position, assigned, target, max_load, unpreferred, avail, pref, taken, demand), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(cand))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
