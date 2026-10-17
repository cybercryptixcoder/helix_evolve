# Helix v3 policy: jobshop, gap 7.186%, progress 86.4%
# priority = sum over features of value x weight; the highest-scoring candidate wins (ties: the first).
import numpy as np
import math

# f004 machine_idle_vs_job_tail_mix (wide): Slack of the candidate relative to the decision machine: how much later than the machine's free time the job c
def _f004(proc_time, job_ready, job_work_left, job_ops_left, next_machine_work, machine_free, machine_work_left):
    """Slack of the candidate relative to the decision machine: how much later than the machine's free time the job can start, normalised by its processing time scale."""
    scale = np.maximum(proc_time, 1.0)
    start = np.maximum(job_ready, machine_free)
    # idle gap the machine would suffer waiting for this job vs starting now
    wait = np.maximum(job_ready - machine_free, 0.0)
    # remaining work pressure on the job after this op
    tail = job_work_left - proc_time
    # fraction of job's remaining work already elapsed-ish pressure
    urgency = tail / np.maximum(job_work_left, 1.0)
    cols = np.stack([
        wait / scale,
        -proc_time / scale,
        urgency,
        (job_ops_left - 1.0) / np.maximum(job_ops_left, 1.0),
        next_machine_work / np.maximum(next_machine_work + job_work_left, 1.0),
    ], axis=1)
    return np.tanh(cols)

# f003 candidate_idle_slack (wide): Slack of the candidate: how much idle time the decision machine would waste waiting for this job vs. the machi
def _f003(proc_time, job_ready, job_work_left, job_ops_left, next_machine_work, machine_free, machine_work_left):
    """Slack of the candidate: how much idle time the decision machine would waste waiting for this job vs. the machine's own backlog."""
    # earliest possible start of candidate
    start = np.maximum(job_ready, machine_free)
    # waiting imposed on the machine by this candidate (idle before it can run)
    idle = np.maximum(0.0, job_ready - machine_free)
    # scale: total remaining work on decision machine plus job's own remaining work
    scale = machine_work_left + job_work_left + proc_time + 1.0
    # how much the job is "behind": remaining work relative to its ops
    job_avg = job_work_left / np.maximum(job_ops_left, 1.0)
    # combining: prefer candidates that don't stall the machine and whose job is nearly free
    val = (idle / scale) - (job_avg / scale) + (proc_time / scale) * 0.5
    return np.clip(val, -1.0, 1.0)

# f061 hinge_idle_beyond_op (deep): Hinge on forced idle beyond the op's own duration: max(0, idle - proc_time) / (idle + proc_time + 1).
def _f061(proc_time, job_ready, job_work_left, job_ops_left, next_machine_work, machine_free, machine_work_left):
    """Hinge on forced idle beyond the op's own duration: max(0, idle - proc_time) / (idle + proc_time + 1)."""
    idle = np.maximum(0.0, job_ready - machine_free)
    excess = np.maximum(0.0, idle - proc_time)
    denom = idle + proc_time + 1.0
    return excess / denom

_TERMS = [(_f004, np.array([-7.215422, 1.362259, 17.571985, 43.218494])), (_f003, np.array([-38.559361])), (_f061, np.array([-12.762096]))]

def priority(proc_time, job_ready, job_work_left, job_ops_left, next_machine_work, machine_free, machine_work_left):
    k = None
    total = None
    for f, w in _TERMS:
        v = np.asarray(f(proc_time, job_ready, job_work_left, job_ops_left, next_machine_work, machine_free, machine_work_left), dtype=float)
        v = v[:, None] if v.ndim == 1 else v
        total = (np.zeros(len(v)) if total is None else total) + v[:, :len(w)] @ w[:v.shape[1]]
    if total is None:
        return np.zeros(len(proc_time))
    return np.round(np.nan_to_num(total, nan=0.0, posinf=1e3, neginf=-1e3), 9)
