# Helix v9: the map of hills and the design map

## v102-helix

- Generations 1-88: best 0.666666667 -> 0.946550142 (p0544, track T2); the main track now: T2.
- Exploration levels: level 0: 65 generations, level 1: 14 generations, level 2: 9 generations.
- Planned experiments by slot: track 167, main 88, build 8, flip 1.

### Records (48)

| Gen | Best | Program | Its role | Its slot | Track |
|---|---|---|---|---|---|
| 1 | 0.802665035 | p0003 | deep | build | T2 |
| 2 | 0.852896164 | p0013 | deep | main | T2 |
| 3 | 0.853568835 | p0017 | wide | mutation | T2 |
| 4 | 0.897662945 | p0021 | deep | main | T2 |
| 5 | 0.898159459 | p0027 | deep | main | T2 |
| 6 | 0.898257458 | p0036 | deep | main | T2 |
| 7 | 0.898265412 | p0039 | wide | mutation | T2 |
| 8 | 0.898266870 | p0051 | deep | main | T2 |
| 9 | 0.898268919 | p0057 | deep | main | T2 |
| 11 | 0.902680221 | p0066 | wide | mutation | T2 |
| 12 | 0.903340524 | p0076 | deep | main | T2 |
| 13 | 0.904041397 | p0081 | deep | main | T2 |
| 14 | 0.904072817 | p0085 | deep | main | T2 |
| 17 | 0.904078401 | p0107 | deep | main | T2 |
| 18 | 0.904080512 | p0110 | deep | main | T2 |
| 22 | 0.932126682 | p0135 | deep | main | T2 |
| 23 | 0.933073443 | p0142 | deep | main | T2 |
| 24 | 0.937953178 | p0146 | wide | mutation | T2 |
| 25 | 0.938047870 | p0156 | deep | main | T2 |
| 26 | 0.944645586 | p0161 | wide | mutation | T2 |
| 27 | 0.945662592 | p0164 | wide | mutation | T2 |
| 28 | 0.945870416 | p0175 | deep | main | T2 |
| 29 | 0.945912358 | p0180 | deep | main | T2 |
| 30 | 0.945939512 | p0187 | wide | mutation | T2 |
| 31 | 0.946064548 | p0190 | deep | main | T2 |
| 33 | 0.946171519 | p0205 | deep | main | T2 |
| 34 | 0.946299297 | p0210 | wide | mutation | T2 |
| 35 | 0.946388763 | p0214 | deep | main | T2 |
| 36 | 0.946437408 | p0222 | deep | main | T2 |
| 37 | 0.946451675 | p0229 | deep | main | T2 |
| 38 | 0.946464612 | p0232 | deep | main | T2 |
| 42 | 0.946475785 | p0257 | wide | mutation | T2 |
| 43 | 0.946485332 | p0265 | deep | main | T2 |
| 44 | 0.946494301 | p0268 | wide | mutation | T2 |
| 46 | 0.946506469 | p0284 | deep | main | T2 |
| 47 | 0.946513755 | p0292 | deep | main | T2 |
| 48 | 0.946521562 | p0297 | deep | main | T2 |
| 49 | 0.946532059 | p0303 | deep | main | T2 |
| 50 | 0.946537451 | p0310 | deep | main | T2 |
| 51 | 0.946539533 | p0313 | deep | main | T2 |
| 52 | 0.946540824 | p0323 | deep | main | T2 |
| 54 | 0.946542298 | p0335 | deep | main | T2 |
| 57 | 0.946543251 | p0353 | wide | mutation | T2 |
| 59 | 0.946544214 | p0366 | deep | main | T2 |
| 63 | 0.946545864 | p0386 | wide | mutation | T2 |
| 68 | 0.946547097 | p0422 | deep | main | T2 |
| 83 | 0.946548585 | p0511 | wide | mutation | T2 |
| 85 | 0.946549778 | p0527 | deep | main | T2 |

### Side tracks opened (0)


### Generation by generation

| Gen | Best | Record | Stall / typical | Level | Slots | Explorations' best | Track events |
|---|---|---|---|---|---|---|---|
| 1 | 0.802665035 | yes | 0 / 3 | 0 | main, build, flip | 0.802665 | the map begins with 1 known hills: H1 (0.666667, reached 0 more times); T2 took the record (0.802665): it is now the main track, and T1 a side track; T2 opened (a new design built from nothing around A13 -> Coarse to fine, upsampling by interpolation betwe…); T3 opened (a flip of A18 -> a new option on p0001); new hill H2, found by T2 (build): 0.802665, distance 0.324 from the nearest known hill (H1) |
| 2 | 0.852896164 | yes | 0 / 3 | 0 | main, track:T3, build | 0.784460 | T4 opened (a new design built from nothing around A9 -> Exact line search on R per block or run of f (no …); new hill H3, found by T3 (flip): 0.784460, distance 0.204 from the nearest known hill (H1) |
| 3 | 0.853568835 | yes | 0 / 1 | 0 | main, track:T3, build | 0.792974 | T3 gained (0.784460 -> 0.800507); T5 opened (a new design built from nothing around A10 -> A softmax- or p-norm-weighted set of the top lags); T3 goes on to the next rung (6 experiments): still rising (best 0.800507 at 3 experiments) |
| 4 | 0.897662945 | yes | 0 / 1 | 0 | main, track:T4, build | 0.794089 | T3 gained (0.800507 -> 0.804847); T4 gained (0.782305 -> 0.794089); T6 opened (a new design built from nothing around A14 -> A tall spike plus a comb of smaller peaks); new hill H4, found by T4 (build): 0.794089, distance 0.220 from the nearest known hill (H1) |
| 5 | 0.898159459 | yes | 0 / 1 | 0 | main, track:T3, build | 0.804847 | T4 gained (0.794089 -> 0.803704); T5 gained (0.752599 -> 0.801808); T7 opened (a new design built from nothing around A17 -> Small-mass runs of f first) |
| 6 | 0.898257458 | yes | 0 / 1 | 0 | main, track:T5, track:T4 | 0.803713 | T4 gained (0.803704 -> 0.803713); T4 goes on to the next rung (6 experiments): still rising (best 0.803713 at 3 experiments); new hill H5, found by T5 (build): 0.801808, distance 0.219 from the nearest known hill (H1) |
| 7 | 0.898265412 | yes | 0 / 1 | 0 | main, track:T6, track:T3 | 0.804847 | new hill H6, found by T6 (build): 0.746445, distance 0.298 from the nearest known hill (H3) |
| 8 | 0.898266870 | yes | 0 / 1 | 0 | main, track:T7, track:T4 | 0.803713 | new hill H7, found by T7 (build): 0.780639, distance 0.130 from the nearest known hill (H5) |
| 9 | 0.898268919 | yes | 0 / 1 | 0 | main, track:T6, track:T5 | 0.801808 | T6 gained (0.746445 -> 0.750591); T7 gained (0.780639 -> 0.810165); T5 goes on to the next rung (6 experiments): still rising (best 0.801808 at 3 experiments); T6 goes on to the next rung (6 experiments): still rising (best 0.750591 at 3 experiments) |
| 10 | 0.898269086 |  | 0 / 1 | 0 | main, track:T7, track:T3 | 0.810214 | T6 gained (0.750591 -> 0.750624); T7 gained (0.810165 -> 0.824044); T3 paused by the race at 6 experiments: stopped rising at 6 experiments (best 0.804847); T7 goes on to the next rung (6 experiments): still rising (best 0.824044 at 3 experiments) |
| 11 | 0.902680221 | yes | 1 / 1 | 0 | main, track:T6, track:T4 | 0.803713 | T6 gained (0.750624 -> 0.795417); T7 gained (0.824044 -> 0.825294) |
| 12 | 0.903340524 | yes | 0 / 1 | 0 | main, track:T7, track:T5 | 0.825650 | T7 gained (0.825294 -> 0.825650) |
| 13 | 0.904041397 | yes | 0 / 1 | 0 | main, track:T6, track:T4 | 0.812464 | T6 gained (0.795417 -> 0.812464); T4 paused by the race at 6 experiments: stopped rising at 6 experiments (best 0.803713) |
| 14 | 0.904072817 | yes | 0 / 1 | 0 | main, track:T7, build | 0.825655 | T7 gained (0.825650 -> 0.826414); T8 opened (a new design built from nothing around A11 -> Adam with gradient noise and elitist respawn of t…) |
| 15 | 0.904072817 |  | 0 / 1 | 0 | main, track:T6, track:T5 | 0.812464 | T1 gained (0.793300 -> 0.795273); T8 gained (0.745231 -> 0.745301); T6 goes on to the next rung (12 experiments): still rising (best 0.812464 at 6 experiments) |
| 16 | 0.904072817 |  | 1 / 1 | 0 | main, track:T7, track:T8 | 0.767747 | T8 gained (0.745301 -> 0.767747); T7 goes on to the next rung (12 experiments): still rising (best 0.826414 at 6 experiments); new hill H8, found by T8 (build): 0.767747, distance 0.138 from the nearest known hill (H4) |
| 17 | 0.904078401 | yes | 2 / 1 | 1 | main, track:T8, track:T5 | 0.801808 | T8 gained (0.767747 -> 0.767806); T5 paused by the race at 6 experiments: stopped rising at 6 experiments (best 0.801808, below the cohort's 50% quantile); T8 goes on to the next rung (6 experiments): still rising (best 0.767806 at 3 experiments) |
| 18 | 0.904080512 | yes | 0 / 1 | 0 | main, track:T8, build | 0.767806 | T7 gained (0.826414 -> 0.834774); T8 gained (0.767806 -> 0.770539); T9 opened (a new design built from nothing around A12 -> f = w^2 exactly (a cell at zero stays at zero: th…) |
| 19 | 0.904080512 |  | 0 / 1 | 0 | main, track:T7, track:T6 | 0.836400 | T6 gained (0.812464 -> 0.812517); T7 gained (0.834774 -> 0.836400); T8 gained (0.770539 -> 0.776184) |
| 20 | 0.904080512 |  | 1 / 1 | 0 | main, track:T8, track:T9 | 0.797606 | T6 gained (0.812517 -> 0.812549); T8 gained (0.776184 -> 0.797606); new hill H9, found by T9 (build): 0.723440, distance 0.164 from the nearest known hill (H4) |
| 21 | 0.904080630 |  | 2 / 1 | 1 | main, track:T6, track:T7 | 0.836406 | T6 gained (0.812549 -> 0.812570); T7 gained (0.836400 -> 0.836406) |
| 22 | 0.932126682 | yes | 3 / 1 | 1 | main, track:T8, track:T9 | 0.797606 | T9 gained (0.723440 -> 0.726037); T8 goes on to the next rung (12 experiments): still rising (best 0.797606 at 6 experiments); T9 goes on to the next rung (6 experiments): still rising (best 0.726037 at 3 experiments) |
| 23 | 0.933073443 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.812591 | T1 gained (0.795273 -> 0.795300); T6 gained (0.812570 -> 0.812591); T9 gained (0.726037 -> 0.762543) |
| 24 | 0.937953178 | yes | 0 / 1 | 0 | main, track:T9, track:T8 | 0.797606 | T6 gained (0.812591 -> 0.812621); T9 gained (0.762543 -> 0.762553) |
| 25 | 0.938047870 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.836412 | T6 gained (0.812621 -> 0.812646); T7 gained (0.836406 -> 0.836412); T9 gained (0.762553 -> 0.762754) |
| 26 | 0.944645586 | yes | 0 / 1 | 0 | main, track:T9, track:T8 | 0.913606 | T1 gained (0.795300 -> 0.795302); T8 gained (0.797606 -> 0.913606); T9 gained (0.762754 -> 0.774357) |
| 27 | 0.945662592 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.836412 | T7 gained (0.836412 -> 0.836443); T9 gained (0.774357 -> 0.774363) |
| 28 | 0.945870416 | yes | 0 / 1 | 0 | main, track:T8, track:T9 | 0.913606 | T9 goes on to the next rung (12 experiments): still rising (best 0.774363 at 6 experiments) |
| 29 | 0.945912358 | yes | 0 / 1 | 0 | main, track:T7, track:T6 | 0.836464 | T6 gained (0.812646 -> 0.836524); T7 gained (0.836443 -> 0.836464); T9 gained (0.774363 -> 0.774367); T6 goes on to the next rung (24 experiments): still rising (best 0.836524 at 12 experiments); T7 goes on to the next rung (24 experiments): still rising (best 0.836464 at 12 experiments) |
| 30 | 0.945939512 | yes | 0 / 1 | 0 | main, track:T9, track:T8 | 0.913615 | T7 gained (0.836464 -> 0.837090); T8 gained (0.913606 -> 0.913615) |
| 31 | 0.946064548 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.838719 | T6 gained (0.836524 -> 0.836558); T7 gained (0.837090 -> 0.838719) |
| 32 | 0.946064548 |  | 0 / 1 | 0 | main, track:T8, track:T9 | 0.913619 | T8 gained (0.913615 -> 0.913710); T9 gained (0.774367 -> 0.774369) |
| 33 | 0.946171519 | yes | 1 / 1 | 0 | main, track:T6, track:T7 | 0.848026 | T6 gained (0.836558 -> 0.848026); T7 gained (0.838719 -> 0.838727) |
| 34 | 0.946299297 | yes | 0 / 1 | 0 | main, track:T8, track:T9 | 0.913710 | T6 gained (0.848026 -> 0.848140); T8 goes on to the next rung (24 experiments): still rising (best 0.913710 at 12 experiments) |
| 35 | 0.946388763 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.848146 | T6 gained (0.848140 -> 0.848146); T7 gained (0.838727 -> 0.839035) |
| 36 | 0.946437408 | yes | 0 / 1 | 0 | main, track:T6, track:T8 | 0.913710 | T1 gained (0.795302 -> 0.795340) |
| 37 | 0.946451675 | yes | 0 / 1 | 0 | main, track:T7, track:T9 | 0.839592 | T7 gained (0.839035 -> 0.839592) |
| 38 | 0.946464612 | yes | 0 / 1 | 0 | main, track:T7, track:T6 | 0.848146 | T7 gained (0.839592 -> 0.839599) |
| 39 | 0.946464748 |  | 0 / 1 | 0 | main, track:T7, track:T8 | 0.913710 | T1 gained (0.795340 -> 0.795581); T6 gained (0.848146 -> 0.852509) |
| 40 | 0.946464794 |  | 1 / 1 | 0 | main, track:T6, track:T9 | 0.865334 | T6 gained (0.852509 -> 0.865334) |
| 41 | 0.946464830 |  | 2 / 1 | 1 | main, track:T6, track:T7 | 0.865917 | T1 gained (0.795581 -> 0.796077); T6 gained (0.865334 -> 0.865917); T7 gained (0.839599 -> 0.840004) |
| 42 | 0.946475785 | yes | 3 / 1 | 1 | main, track:T6, track:T8 | 0.913710 | T6 gained (0.865917 -> 0.866043); T7 gained (0.840004 -> 0.840055) |
| 43 | 0.946485332 | yes | 0 / 1 | 0 | main, track:T7, track:T9 | 0.840066 | T7 gained (0.840055 -> 0.840075); T9 paused by the race at 12 experiments: stopped rising at 12 experiments (best 0.774369, below the cohort's 50% quantile) |
| 44 | 0.946494301 | yes | 0 / 1 | 0 | main, track:T6, build | 0.866044 | T6 gained (0.866043 -> 0.866067); T10 opened (a new design built from nothing around A15 -> A fine, coherent periodic lattice of teeth (perio…) |
| 45 | 0.946494303 |  | 0 / 1 | 0 | main, track:T7, track:T8 | 0.840080 | T6 gained (0.866067 -> 0.866199); T7 gained (0.840075 -> 0.840080); T10 gained (0.516534 -> 0.518929) |
| 46 | 0.946506469 | yes | 1 / 1 | 0 | main, track:T6, track:T10 | 0.866199 | T10 gained (0.518929 -> 0.521813); new hill H10, found by T10 (build): 0.521813, distance 0.188 from the nearest known hill (H5) |
| 47 | 0.946513755 | yes | 0 / 1 | 0 | main, track:T7, track:T8 | 0.913710 | T7 gained (0.840080 -> 0.840083); T10 gained (0.521813 -> 0.532838) |
| 48 | 0.946521562 | yes | 0 / 1 | 0 | main, track:T10, track:T6 | 0.866199 | T7 gained (0.840083 -> 0.840084); T10 gained (0.532838 -> 0.535343); T10 goes on to the next rung (6 experiments): still rising (best 0.535343 at 3 experiments) |
| 49 | 0.946532059 | yes | 0 / 1 | 0 | main, track:T7, track:T8 | 0.913710 | T6 gained (0.866199 -> 0.866485); T10 gained (0.535343 -> 0.544537) |
| 50 | 0.946537451 | yes | 0 / 1 | 0 | main, track:T6, track:T10 | 0.866664 | T6 gained (0.866485 -> 0.866664); T10 gained (0.544537 -> 0.555585); T6 goes on to the next rung (48 experiments): still rising (best 0.866664 at 24 experiments) |
| 51 | 0.946539533 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.866723 | T6 gained (0.866664 -> 0.866723); T10 gained (0.555585 -> 0.556608); T7 goes on to the next rung (48 experiments): still rising (best 0.840084 at 24 experiments) |
| 52 | 0.946540824 | yes | 0 / 1 | 0 | main, track:T10, track:T8 | 0.913710 | T10 gained (0.556608 -> 0.803363) |
| 53 | 0.946541683 |  | 0 / 1 | 0 | main, track:T6, track:T7 | 0.866744 | T6 gained (0.866723 -> 0.866744) |
| 54 | 0.946542298 |  | 1 / 1 | 0 | main, track:T10, track:T8 | 0.803363 | T10 gained (0.803363 -> 0.809568); T10 goes on to the next rung (12 experiments): still rising (best 0.809568 at 6 experiments) |
| 55 | 0.946542588 |  | 0 / 1 | 0 | main, track:T6, track:T7 | 0.866803 | T6 gained (0.866744 -> 0.866803) |
| 56 | 0.946542720 |  | 1 / 1 | 0 | main, track:T10, track:T8 | 0.809568 | T1 gained (0.796077 -> 0.796087) |
| 57 | 0.946543251 |  | 2 / 1 | 1 | main, track:T6, track:T7 | 0.866940 | T6 gained (0.866803 -> 0.866940) |
| 58 | 0.946543886 |  | 0 / 1 | 0 | main, track:T6, track:T8 | 0.913710 | T6 gained (0.866940 -> 0.866959) |
| 59 | 0.946544214 |  | 1 / 1 | 0 | main, track:T6, track:T10 | 0.866966 | T6 gained (0.866959 -> 0.866966) |
| 60 | 0.946544967 |  | 0 / 1 | 0 | main, track:T6, track:T7 | 0.866966 |  |
| 61 | 0.946544967 |  | 1 / 1 | 0 | main, track:T8, track:T10 | 0.913711 |  |
| 62 | 0.946544967 |  | 2 / 1 | 1 | main, track:T6, track:T7 | 0.866966 | T10 gained (0.809568 -> 0.810411) |
| 63 | 0.946545864 |  | 3 / 1 | 1 | main, track:T10, track:T8 | 0.913710 | T8 goes on to the next rung (48 experiments): no longer rising, but best 0.913710 at 24 experiments is at or above the cohort's 50% quantile (0.866664) |
| 64 | 0.946546050 |  | 0 / 1.5 | 0 | main, track:T6, track:T7 | 0.866966 |  |
| 65 | 0.946546206 |  | 1 / 1.5 | 0 | main, track:T8, track:T10 | 0.913710 | T10 gained (0.810411 -> 0.865144) |
| 66 | 0.946546714 |  | 2 / 1.5 | 1 | main, track:T10, track:T6 | 0.866989 | T7 gained (0.840084 -> 0.840724); T10 goes on to the next rung (24 experiments): still rising (best 0.865144 at 12 experiments) |
| 67 | 0.946546714 |  | 3 / 1.5 | 1 | main, track:T7, track:T8 | 0.913710 | T7 gained (0.840724 -> 0.842801) |
| 68 | 0.946547097 |  | 4 / 1.5 | 1 | main, track:T7, track:T6 | 0.866966 | T1 gained (0.796087 -> 0.796089) |
| 69 | 0.946547097 |  | 0 / 2 | 0 | main, track:T10, track:T8 | 0.913712 | T8 gained (0.913710 -> 0.913712); T10 gained (0.865144 -> 0.875050) |
| 70 | 0.946547357 |  | 1 / 2 | 0 | main, track:T8, track:T6 | 0.913712 |  |
| 71 | 0.946547589 |  | 2 / 2 | 0 | main, track:T10, track:T7 | 0.842801 |  |
| 72 | 0.946547654 |  | 3 / 2 | 1 | main, track:T6, track:T8 | 0.913712 | T1 gained (0.796089 -> 0.796091) |
| 73 | 0.946547667 |  | 4 / 2 | 1 | main, track:T7, track:T10 | 0.875847 | T7 gained (0.842801 -> 0.842986); T10 gained (0.875050 -> 0.875847) |
| 74 | 0.946547667 |  | 5 / 2 | 1 | main, track:T7, track:T6 | 0.866966 |  |
| 75 | 0.946547667 |  | 6 / 2 | 2 | main, track:T10, track:T8 | 0.913712 | T7 gained (0.842986 -> 0.843062) |
| 76 | 0.946547667 |  | 7 / 2 | 2 | main, track:T7, track:T6 | 0.866966 | T1 gained (0.796091 -> 0.796136) |
| 77 | 0.946547668 |  | 8 / 2 | 2 | main, track:T8, track:T10 | 0.913712 | T7 gained (0.843062 -> 0.843084); T10 gained (0.875847 -> 0.876022) |
| 78 | 0.946547668 |  | 9 / 2 | 2 | main, track:T7, track:T6 | 0.866966 | T1 gained (0.796136 -> 0.796138); T7 gained (0.843084 -> 0.843114); T10 gained (0.876022 -> 0.876051) |
| 79 | 0.946547669 |  | 10 / 2 | 2 | main, track:T10, track:T8 | 0.913712 |  |
| 80 | 0.946547672 |  | 11 / 2 | 2 | main, track:T7, track:T6 | 0.866966 | T1 gained (0.796138 -> 0.796140); T7 gained (0.843114 -> 0.843413) |
| 81 | 0.946547672 |  | 12 / 2 | 2 | main, track:T7, track:T8 | 0.913712 | T7 gained (0.843413 -> 0.843467) |
| 82 | 0.946547672 |  | 13 / 2 | 2 | main, track:T7, track:T10 | 0.843858 | T7 gained (0.843467 -> 0.843858) |
| 83 | 0.946548585 |  | 14 / 2 | 2 | main, track:T7, track:T6 | 0.866966 | T1 gained (0.796140 -> 0.796142) |
| 84 | 0.946549264 |  | 0 / 2.5 | 0 | main, track:T8, track:T10 | 0.913712 |  |
| 85 | 0.946549778 |  | 1 / 2.5 | 0 | main, track:T6, track:T7 | 0.866966 | T10 gained (0.876051 -> 0.876111) |
| 86 | 0.946549888 |  | 0 / 2.5 | 0 | main, track:T10, track:T8 | 0.876113 | T1 gained (0.796142 -> 0.796143); T10 gained (0.876111 -> 0.876113) |
| 87 | 0.946550024 |  | 1 / 2.5 | 0 | main, track:T10, track:T6 | 0.876113 | T1 gained (0.796143 -> 0.796146) |
| 88 | 0.946550142 |  | 2 / 2.5 | 0 | main, track:T7, track:T8 | 0.913712 | T7 gained (0.843858 -> 0.843968); T10 gained (0.876113 -> 0.876118) |

### Hills (10: 2 on the map after its first generation, 8 found since)

| Hill | Top | Found | By | Other tracks landed on it | Description |
|---|---|---|---|---|---|
| H2 | 0.946550 (p0527) | 1 | T2 (build) | 0 | This program optimizes a smooth log-sum-exp surrogate of the sup-norm with an annealed sharpness parameter inside a Dinkelbach loop, rather than directly maximizing the exact ratio. It uses L-BFGS-B with analytic gradien |
| H8 | 0.913712 (p0426) | 16 | T8 (build) | 0 | This program abandons the record's high-resolution climb entirely, instead starting from the given start and running a prune-refine-upsample loop that repeatedly zeroes the smallest fraction of cells and re-optimises ins |
| H10 | 0.876118 (p0543) | 46 | T10 (build) | 0 | This program seeds from a periodic cosine-tooth envelope rather than from the record's start, and it optimises with a Dinkelbach loop over an LSE-smoothed max (beta up to 1e12) instead of exact-move golden-section/pair p |
| H6 | 0.866966 (p0365) | 7 | T6 (build) | 0 | This program builds a hand-crafted spike-plus-decaying-comb seed at n=512 and then doubles resolution in four stages (512→1024→2048→4096), spending only 20% of budget on the first stage and re-annealing beta from 1e4 upw |
| H7 | 0.843968 (p0546) | 8 | T7 (build) | 0 | This program builds a hand-crafted seed of a 10-tooth raised-cosine comb plus a graded ramp of 30 bumps, then grows it by coordinate-wise golden-section tuning of per-run multiplicative factors and additive bumps (doubli |
| H3 | 0.804847 (p0022) | 2 | T3 (flip) | 0 | This program optimizes a Dinkelbach-style surrogate (smooth-max minus λ·num) with L-BFGS-B gradients on a fixed grid, rather than the record's approach of building a tuned small-n construction and carefully upsampling it |
| H4 | 0.803713 (p0035) | 4 | T4 (build) | 0 | This program starts from the given `start` and refines it with local, parameterised moves (run scaling, additive cosine packets, constant-run shifts, bump replacement, and pairwise mass transfer), each tuned by a 1-D gri |
| H5 | 0.801808 (p0031) | 6 | T5 (build) | 0 | This program uses linear interpolation to upsample between fixed ladder sizes (256→4096) rather than repeat-based upsampling, and it anneals the smooth-max exponent p from 4 to 400 within each stage instead of re-anneali |
| H9 | 0.774369 (p0196) | 20 | T9 (build) | 0 | This program abandons the record's multi-resolution pipeline (refine at 4096/8192/32768 then pool down) and instead works directly at a single fixed resolution (N=1024), starting from the constant-ones seed rather than a |
| H1 | 0.666667 (p0001) | 1 | - | 0 | the starting program (Code Zero) |

Decisions every hill shared (mapped at generation 82):

- D1: Objective/constraint formulation for the sup-norm in the denominator (all: Smooth the max with a log-sum-exp (or p-norm) surrogate and drive the sharpness parameter to a huge value (beta up to 1e13, p up to 400) inside a Dinkelbach/pe…)
- D2: How the function is represented on the grid (all: A nonnegative vector of cell heights on a uniform 1-D grid, normalized so sum(f)=1, with f*f evaluated by FFT and the L2 norm computed by the trapezoid-style k…)
- D3: Resolution strategy (all: Fix a resolution ladder (or a single high resolution) and upsample between stages by interpolation or pixel-repeat, then polish at the finest level; resolution…)
- D4: Local optimizer used for the smooth surrogate (all: L-BFGS-B (or gradient ascent / Adam) with analytic gradients on the full or active set of coordinates, with box bounds [0, inf))
- D5: How the peak/plateau of f*f is treated (all: Treat the near-max knots as a set to be flattened or penalized (LSE pulls them together, capped penalty pushes down overshoot), implicitly assuming a flat plat…)
- D6: Search for global structure vs local polish (all: Start from a hand-crafted or random seed (spike+comb, arcsine, cosine-tooth, Gaussian packets) and then run local ascent; seeds are chosen by intuition and nev…)
- D7: Handling of the L1 normalization (all: Enforce sum(f)=1 by renormalizing after every step (or via the chain-rule gradient correction), treating it as a hard constraint imposed externally)
- D8: Time/budget allocation across stages (all: Hand-tuned fixed time shares per ladder stage (e.g. 20% first stage, rest at max n) with process_time deadlines checked between optimizer calls)

### The design map (19 decisions, 525 programs placed)

| Decision | Options | Read twice: agreement | Importance (last fit) |
|---|---|---|---|
| A23: How is the resolution of the returned final answer chosen (native, truncated, pooled, or b | Evaluate a handful of candidate resoluti; Return the native high-resolution field ; Choose the output resolution by a valida; A separate polish pass at the largest gr; No separate polish; keep one beta schedu ... | 93% of 44 (kappa 0.87) | 4% |
| A2: How is the first solution built? | Constant or supplied start; Random smooth field; Hand-designed bump or comb; Random Gaussian packet mixture; Deterministic analytic construction ... | 77% of 44 (kappa 0.69) | 2% |
| A12: How is f >= 0 enforced | f = w^2 exactly (a cell at zero stays at; Clip or project to f >= 0 after each ste; An explicit support mask pruned on purpo; none imposed; f is unconstrained and sca; fix //f//_1 or //f//_2 to a constant to  ... | 93% of 44 (kappa 0.86) | 2% |
| A14: What is the macro shape (the envelope) of f across its domain | One heavy comb block holding about 30% o; A tall spike plus a comb of smaller peak; A smooth arcsine-like density, 1/sqrt(1 ; A parametric series sum_j a_j (1 - 4x^2); Regular sparse packets under a smooth ra | 68% of 25 (kappa 0.58) | 2% |
| A1: How is a candidate solution represented? | Dense grid direct values; Parametric analytic form; Sparse low-degree basis; Spline/Fourier basis coefficients; Softmax/log parameterization ... | 98% of 44 (kappa 0.66) | - |
| A3: What quantity does the search optimise while it runs? | Minimax dual active-set weights; Exact line search on R; Alternating projection to target; Direct ratio maximisation; Bisection on ratio feasibility ... | 84% of 44 (kappa 0.72) | - |
| A4: Which moves or update steps change a solution? | No search, fixed output; Derivative-free local search; Coordinate and line-search moves; Block/segment multi-cell moves; Gradient-based full-vector steps ... | 89% of 44 (kappa 0.83) | - |
| A5: How does the search accept worse solutions or escape a local optimum? | Restart or basin-hopping; Noise kick then re-polish; Gradient-guided perturbation re-polish; Fourier perturbation; Structural block surgery ... | 80% of 44 (kappa 0.72) | - |
| A7: Which parts, if any, are solved exactly? |  | - | - |
| A8: How is the time budget split between phases? | Run to completion, no budget; Run until time budget elapses; Adaptive budget by improvement rate; Reserved budget kick-and-repolish; Parallel multi-seed, keep best ... | 95% of 44 (kappa 0.94) | - |
| A15: What is the fine structure of f (the comb of teeth or blocks) | A fine, coherent periodic lattice of tee; Contiguous blocks with irregular spacing; A coarser parent with each cell split in; Number-theoretic support (Sidon/B2 sets,; Regular [small, big, small] triplets | 61% of 28 (kappa 0.17) | - |
| A18: How is the objective (the convolution and its norms) computed numerically? | compute f*f by direct convolution on the; evaluate the ratio analytically for a pa; use FFT-based convolution with careful n; finite interval with zero-padding implie; periodic (circular) convolution on a tor ... | 91% of 44 (kappa 0.80) | - |
| A20: What symmetry or shape assumptions are imposed on f? | general unconstrained shape, no symmetry; enforce even symmetry (f(x)=f(-x)); enforce a unimodal or compactly supporte; Optionally symmetrize the construction (; Impose an explicit periodic or comb stru ... | 91% of 44 (kappa 0.80) | - |
| A24: How is the scale/normalization of f fixed (e.g. //f//_1=1 renormalization, //f*f//_inf=1,  | Fix //f//_1 = 1 by renormalizing after e; Fix //f*f//_inf = 1 and let mass float, ; Fix //f//_2 = 1 and optimize the full th; Enforce //f//_1 = 1 (or L2=1) by renorma; Use an explicit constrained optimizer (S ... | 93% of 29 (kappa 0.80) | - |
| A25: How is the final answer selected from the candidates produced during the search? | Keep the best-R candidate found across s; Return the last polished candidate uncon; return start as best, keep new as altern; the single best-scoring construction fou; return an ensemble/average of several ne ... | 82% of 22 (kappa 0.58) | - |
| A26: How is the sup-norm (L-infinity) of f*f handled in the objective: smoothed surrogate, exac | Smooth surrogate with annealing; Exact subgradient/active-set; Epigraph constrained formulation; Penalize near-max knot variance; Constrain top-k knots equal ... | 100% of 11 (kappa 1.00) | - |
| A28: How is the grid resolution chosen and changed across stages (fixed single resolution vs. a | Fixed single resolution, no resampling; Meshfree particle representation; Power-of-two resolution ladder with upsa; Fixed high resolution from start; Continuous adaptive mesh / moving knots ... | 100% of 8 (kappa 1.00) | - |
| A29: How is the search's time budget allocated across the resolution ladder (how many rungs, an | Screens periods at n=2048, then a short ; Four-rung ladder 2048→4096→8192→16384 wi | - | - |
| A30: How is the initial solution (or restart seed) chosen before the main search? | arcsine-shaped seed / envelope-based res; same code but different seed/restart pat | - | - |

Interacting decisions in the last fit: ('A15', 'A25'), ('A4', 'A15')

### Explorations chosen from the map (9: 8 builds, 1 flips)

| Track | Kind | Opened | Target | Built (read back) | Experiments | Best | Race | Hill |
|---|---|---|---|---|---|---|---|---|
| T2 | build | 1 | A13 -> Coarse to fine, upsampling by  | 1/1 | 88 | 0.946550 | running | founder H2 |
| T3 | flip | 1 | A18 -> a new option, unlike the liste | 1/1 | 6 | 0.804847 | paused at 6 | founder H3 |
| T4 | build | 2 | A9 -> Exact line search on R per blo | 1/1 | 6 | 0.803713 | paused at 6 | founder H4 |
| T5 | build | 3 | A10 -> A softmax- or p-norm-weighted  | 1/1 | 6 | 0.801808 | paused at 6 | founder H5 |
| T6 | build | 4 | A14 -> A tall spike plus a comb of sm | 1/1 | 44 | 0.866966 | running at 24 | founder H6 |
| T7 | build | 5 | A17 -> Small-mass runs of f first | 1/1 | 43 | 0.843968 | running at 24 | founder H7 |
| T8 | build | 14 | A11 -> Adam stochastic ascent with re | 1/1 | 36 | 0.913712 | running at 24 | founder H8 |
| T9 | build | 18 | A12 -> f = w^2 exactly (a cell at zer | 1/1 | 12 | 0.774369 | paused at 12 | founder H9 |
| T10 | build | 44 | A15 -> A fine, coherent periodic latt | 1/1 | 22 | 0.876118 | running at 12 | founder H10 |

### Discoveries (programs at the same design that scored too differently: what differs?)

- generation 44, p0270 vs p0269: How is the final answer selected from the candidates produced during the search? (A25, new)
- generation 84, p0286 vs p0269: How is the search's time budget allocated across the resolution ladder (how many rungs, and what share each gets)? (A29, new)
- generation 88, p0492 vs p0491: How is the initial solution (or restart seed) chosen before the main search? (A30, new)

## v102-helix-s2

- Generations 1-89: best 0.666666667 -> 0.904524431 (p0457, track T6); the main track now: T6.
- Exploration levels: level 0: 46 generations, level 1: 8 generations, level 2: 35 generations.
- Planned experiments by slot: track 170, main 89, build 7, flip 1.

### Records (37)

| Gen | Best | Program | Its role | Its slot | Track |
|---|---|---|---|---|---|
| 1 | 0.842087388 | p0002 | wide | mutation | T1 |
| 4 | 0.842209958 | p0022 | wide | mutation | T1 |
| 5 | 0.842954069 | p0030 | deep | main | T1 |
| 6 | 0.849786988 | p0037 | deep | track | T5 |
| 7 | 0.857120371 | p0044 | deep | main | T5 |
| 8 | 0.857510119 | p0052 | deep | main | T5 |
| 10 | 0.860071723 | p0061 | deep | main | T5 |
| 11 | 0.860074252 | p0068 | deep | main | T5 |
| 12 | 0.862073247 | p0074 | deep | main | T5 |
| 13 | 0.862558110 | p0083 | deep | main | T5 |
| 14 | 0.862564420 | p0087 | deep | main | T5 |
| 19 | 0.862783505 | p0119 | wide | mutation | T5 |
| 20 | 0.862784436 | p0125 | deep | main | T5 |
| 21 | 0.862804903 | p0134 | deep | main | T5 |
| 22 | 0.862806074 | p0140 | deep | main | T5 |
| 23 | 0.862994360 | p0145 | deep | main | T5 |
| 24 | 0.863198432 | p0150 | deep | main | T5 |
| 25 | 0.863465596 | p0157 | deep | main | T5 |
| 26 | 0.863548361 | p0161 | deep | main | T5 |
| 27 | 0.863552810 | p0167 | deep | main | T5 |
| 28 | 0.863772390 | p0171 | wide | mutation | T5 |
| 29 | 0.864140809 | p0182 | deep | main | T5 |
| 30 | 0.864678463 | p0184 | deep | main | T5 |
| 31 | 0.864726552 | p0194 | deep | main | T5 |
| 32 | 0.864831942 | p0199 | deep | main | T5 |
| 33 | 0.864865098 | p0205 | deep | main | T5 |
| 34 | 0.864868956 | p0214 | deep | main | T5 |
| 35 | 0.865146902 | p0220 | deep | track | T6 |
| 36 | 0.866109860 | p0225 | wide | mutation | T6 |
| 37 | 0.866112124 | p0230 | wide | mutation | T6 |
| 46 | 0.871953081 | p0283 | wide | mutation | T1 |
| 47 | 0.872040109 | p0294 | deep | main | T1 |
| 48 | 0.874848296 | p0295 | deep | main | T1 |
| 49 | 0.874993630 | p0303 | deep | main | T1 |
| 50 | 0.876804810 | p0311 | deep | main | T1 |
| 52 | 0.904522743 | p0320 | deep | track | T6 |
| 57 | 0.904524431 | p0355 | deep | main | T6 |

### Side tracks opened (0)


### Generation by generation

| Gen | Best | Record | Stall / typical | Level | Slots | Explorations' best | Track events |
|---|---|---|---|---|---|---|---|
| 1 | 0.842087388 | yes | 0 / 3 | 0 | main, build, flip | 0.707550 | the map begins with 1 known hills: H1 (0.666667, reached 0 more times); T2 opened (a new design built from nothing around A11 -> L-BFGS with Anderson acceleration of the Dinkelba…); T3 opened (a flip of A9 -> Alternating projection: push f*f towards a two-le… on p0001); new hill H2, found by T1 (seed): 0.842087, distance 0.211 from the nearest known hill (H1) |
| 2 | 0.842087492 |  | 0 / 3 | 0 | main, track:T2, build | 0.725267 | T3 gained (0.707550 -> 0.723766); T4 opened (a new design built from nothing around A13 -> Average-pool a finer construction down to n, then…); new hill H3, found by T2 (build): 0.723731, distance 0.211 from the nearest known hill (H1) |
| 3 | 0.842087492 |  | 1 / 3 | 0 | main, track:T3, build | 0.723734 | T4 gained (0.725267 -> 0.727261); T5 opened (a new design built from nothing around A16 -> Perturb along the gradient of the transition loss…); T4 landed on H3 (distance 0.030); T4 is now the top of H3 (0.727261); T3 landed on H3 (distance 0.039); T5 landed on H3 (distance 0.030) |
| 4 | 0.842209958 | yes | 2 / 3 | 0 | main, track:T2, build | 0.723734 | T2 gained (0.723731 -> 0.723734); T3 gained (0.723766 -> 0.723862); T6 opened (a new design built from nothing around A14 -> A tall spike plus a comb of smaller peaks); T2 goes on to the next rung (6 experiments): still rising (best 0.723734 at 3 experiments) |
| 5 | 0.842954069 | yes | 0 / 2 | 0 | main, track:T4, track:T3 | 0.727317 | T2 gained (0.723734 -> 0.723887); T3 gained (0.723862 -> 0.723900); T4 gained (0.727261 -> 0.731157); T3 goes on to the next rung (6 experiments): still rising (best 0.723900 at 3 experiments); T3 stops racing: after 3 experiments it sits on H3 below that hill's top (a copy of a known design) |
| 6 | 0.849786988 | yes | 0 / 1 | 0 | main, track:T5, track:T2 | 0.849787 | T4 gained (0.731157 -> 0.738594); T5 gained (0.723734 -> 0.849787); T5 took the record (0.849787): it is now the main track, and T1 a side track; new hill H4, found by T5 (build): 0.849787, distance 0.243 from the nearest known hill (H3) |
| 7 | 0.857120371 | yes | 0 / 1 | 0 | main, track:T6, build | 0.723263 | T4 gained (0.738594 -> 0.749784); T7 opened (a new design built from nothing around A10 -> A fixed mild smooth max (beta about 100-500 relat…) |
| 8 | 0.857510119 | yes | 0 / 1 | 0 | main, track:T4, track:T2 | 0.767465 | T2 gained (0.723887 -> 0.788655); T4 gained (0.749784 -> 0.767465); T4 goes on to the next rung (6 experiments): still rising (best 0.767465 at 3 experiments) |
| 9 | 0.857510119 |  | 0 / 1 | 0 | main, track:T7, track:T6 | 0.799558 | T7 gained (0.723263 -> 0.784764); T6 goes on to the next rung (6 experiments): still rising (best 0.799558 at 3 experiments); new hill H5, found by T6 (build): 0.799558, distance 0.127 from the nearest known hill (H2); new hill H6, found by T7 (build): 0.784764, distance 0.090 from the nearest known hill (H5) |
| 10 | 0.860071723 | yes | 1 / 1 | 0 | main, track:T2, track:T4 | 0.795939 | T2 gained (0.788655 -> 0.795939); T4 gained (0.767465 -> 0.776348); T2 goes on to the next rung (12 experiments): still rising (best 0.795939 at 6 experiments) |
| 11 | 0.860074252 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.845793 | T6 gained (0.799558 -> 0.803224); T7 gained (0.784764 -> 0.845793); T7 goes on to the next rung (6 experiments): still rising (best 0.845793 at 3 experiments) |
| 12 | 0.862073247 | yes | 0 / 1 | 0 | main, track:T2, track:T4 | 0.795939 | T4 gained (0.776348 -> 0.777272); T6 gained (0.803224 -> 0.806957) |
| 13 | 0.862558110 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.836686 | T6 gained (0.806957 -> 0.836686); T7 gained (0.845793 -> 0.847552) |
| 14 | 0.862564420 | yes | 0 / 1 | 0 | main, track:T4, track:T2 | 0.806552 | T2 gained (0.795939 -> 0.796177); T4 gained (0.777272 -> 0.806552); T4 goes on to the next rung (12 experiments): still rising (best 0.806552 at 6 experiments) |
| 15 | 0.862564420 |  | 0 / 1 | 0 | main, track:T6, track:T7 | 0.847552 | T2 gained (0.796177 -> 0.796180); T7 gained (0.847552 -> 0.849000); T6 goes on to the next rung (12 experiments): still rising (best 0.836686 at 6 experiments) |
| 16 | 0.862564666 |  | 1 / 1 | 0 | main, track:T2, track:T4 | 0.811150 | T2 gained (0.796180 -> 0.811150); T4 gained (0.806552 -> 0.808850); T6 gained (0.836686 -> 0.843123) |
| 17 | 0.862564666 |  | 2 / 1 | 1 | main, track:T6, track:T7 | 0.849000 | T4 gained (0.808850 -> 0.809019); T6 gained (0.843123 -> 0.844825); T7 gained (0.849000 -> 0.851370); T7 goes on to the next rung (12 experiments): still rising (best 0.851370 at 6 experiments) |
| 18 | 0.862564666 |  | 3 / 1 | 1 | main, track:T2, track:T4 | 0.846634 | T2 gained (0.811150 -> 0.846634); T4 gained (0.809019 -> 0.809786); T6 gained (0.844825 -> 0.844938) |
| 19 | 0.862783505 | yes | 4 / 1 | 2 | main, track:T6, track:T7 | 0.851437 | T2 gained (0.846634 -> 0.847345); T7 gained (0.851370 -> 0.851523) |
| 20 | 0.862784436 | yes | 0 / 1 | 0 | main, track:T2, track:T4 | 0.847346 | T4 gained (0.809786 -> 0.809863); T6 gained (0.844938 -> 0.846812); T7 gained (0.851523 -> 0.851724); T2 goes on to the next rung (24 experiments): still rising (best 0.847345 at 12 experiments) |
| 21 | 0.862804903 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.851724 | T2 gained (0.847345 -> 0.847919); T4 gained (0.809863 -> 0.810004) |
| 22 | 0.862806074 | yes | 0 / 1 | 0 | main, track:T2, track:T4 | 0.847920 | T2 gained (0.847919 -> 0.847920); T4 gained (0.810004 -> 0.810259); T6 gained (0.846812 -> 0.848463); T7 gained (0.851724 -> 0.852624) |
| 23 | 0.862994360 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.852914 | T2 gained (0.847920 -> 0.847921); T4 gained (0.810259 -> 0.810276); T6 gained (0.848463 -> 0.848806); T7 gained (0.852624 -> 0.852914) |
| 24 | 0.863198432 | yes | 0 / 1 | 0 | main, track:T2, track:T4 | 0.847922 | T1 gained (0.842964 -> 0.842966); T6 gained (0.848806 -> 0.848827) |
| 25 | 0.863465596 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.848857 | T2 gained (0.847921 -> 0.847922); T6 gained (0.848827 -> 0.848857) |
| 26 | 0.863548361 | yes | 0 / 1 | 0 | main, track:T2, track:T4 | 0.857688 | T1 gained (0.842966 -> 0.842967); T2 gained (0.847922 -> 0.857688); T4 gained (0.810276 -> 0.810383); T6 gained (0.848857 -> 0.848858); T4 goes on to the next rung (24 experiments): still rising (best 0.810383 at 12 experiments) |
| 27 | 0.863552810 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.853069 | T4 gained (0.810383 -> 0.810430); T6 gained (0.848858 -> 0.849670); T7 gained (0.852914 -> 0.853315); T6 goes on to the next rung (24 experiments): still rising (best 0.849670 at 12 experiments) |
| 28 | 0.863772390 | yes | 0 / 1 | 0 | main, track:T2, track:T4 | 0.858370 | T1 gained (0.842967 -> 0.843012); T2 gained (0.857688 -> 0.858370); T4 gained (0.810430 -> 0.810709) |
| 29 | 0.864140809 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.853378 | T2 gained (0.858370 -> 0.858632); T6 gained (0.849670 -> 0.849928); T7 gained (0.853315 -> 0.853378); T7 goes on to the next rung (24 experiments): still rising (best 0.853378 at 12 experiments); T6 landed on H6 (distance 0.057); T6 climbed from H5 into H6 |
| 30 | 0.864678463 | yes | 0 / 1 | 0 | main, track:T2, track:T4 | 0.858963 | T2 gained (0.858632 -> 0.858963); T6 gained (0.849928 -> 0.850611); new hill H7, found by T6 (build): 0.850611, distance 0.076 from the nearest known hill (H6) |
| 31 | 0.864726552 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.859720 | T6 gained (0.850611 -> 0.859720); T7 gained (0.853378 -> 0.853542) |
| 32 | 0.864831942 | yes | 0 / 1 | 0 | main, track:T2, track:T4 | 0.859158 | T2 gained (0.858963 -> 0.859158); T4 gained (0.810709 -> 0.813788); T6 gained (0.859720 -> 0.859887) |
| 33 | 0.864865098 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.859889 | T1 gained (0.843012 -> 0.844047); T2 gained (0.859158 -> 0.859177); T6 gained (0.859887 -> 0.859889); T7 gained (0.853542 -> 0.853588) |
| 34 | 0.864868956 | yes | 0 / 1 | 0 | main, track:T2, track:T4 | 0.859266 | T2 gained (0.859177 -> 0.859266); T4 gained (0.813788 -> 0.814021) |
| 35 | 0.865146902 | yes | 0 / 1 | 0 | main, track:T6, track:T7 | 0.865147 | T4 gained (0.814021 -> 0.814032); T6 gained (0.859889 -> 0.865147); T7 gained (0.853588 -> 0.853595); T6 took the record (0.865147): it is now the main track, and T5 a side track; T5 goes on to the next rung (31 experiments): still rising (best 0.857120 at 3 experiments) |
| 36 | 0.866109860 | yes | 0 / 1 | 0 | main, track:T5, track:T2 | 0.864890 | T1 gained (0.844047 -> 0.844810); T2 gained (0.859266 -> 0.859349); T5 gained (0.864886 -> 0.864890); T5 goes on to the next rung (32 experiments): still rising (best 0.864890 at 31 experiments) |
| 37 | 0.866112124 | yes | 0 / 1 | 0 | main, track:T4, track:T7 | 0.853595 | T1 gained (0.844810 -> 0.844954); T4 gained (0.814032 -> 0.814235) |
| 38 | 0.866112124 |  | 0 / 1 | 0 | main, track:T2, track:T5 | 0.864890 | T2 gained (0.859349 -> 0.859726); T7 gained (0.853595 -> 0.853606); T5 paused by the race at 32 experiments: stopped rising at 32 experiments (best 0.864890) |
| 39 | 0.866112124 |  | 1 / 1 | 0 | main, track:T4, build | 0.723887 | T2 gained (0.859726 -> 0.860125); T7 gained (0.853606 -> 0.853607); T8 opened (a new design built from nothing around A19 -> Force even symmetry h[i]=h[N-1-i]) |
| 40 | 0.866112124 |  | 2 / 1 | 1 | main, track:T7, track:T2 | 0.860170 | T2 gained (0.860125 -> 0.860170) |
| 41 | 0.866112124 |  | 3 / 1 | 1 | main, track:T8, track:T4 | 0.814270 | T1 gained (0.844954 -> 0.858230); T4 gained (0.814235 -> 0.814270); new hill H8, found by T8 (build): 0.723887, distance 0.222 from the nearest known hill (H1) |
| 42 | 0.866112124 |  | 4 / 1 | 2 | main, track:T2, track:T7 | 0.860477 | T2 gained (0.860170 -> 0.860477); T4 gained (0.814270 -> 0.814303) |
| 43 | 0.866112124 |  | 5 / 1 | 2 | main, track:T4, track:T8 | 0.814331 | T4 gained (0.814303 -> 0.814331); T8 goes on to the next rung (6 experiments): still rising (best 0.723887 at 3 experiments) |
| 44 | 0.866112124 |  | 6 / 1 | 2 | main, track:T2, track:T7 | 0.860522 | T2 gained (0.860477 -> 0.860525); T2 goes on to the next rung (48 experiments): still rising (best 0.860525 at 24 experiments) |
| 45 | 0.866112124 |  | 7 / 1 | 2 | main, track:T4, track:T8 | 0.723888 |  |
| 46 | 0.871953081 | yes | 8 / 1 | 2 | main, track:T2, track:T7 | 0.860610 | T1 gained (0.858230 -> 0.871953); T2 gained (0.860525 -> 0.860610); T1 took the record (0.871953): it is now the main track, and T6 a side track; T6 goes on to the next rung (48 experiments): still rising (best 0.866112 at 24 experiments) |
| 47 | 0.872040109 | yes | 0 / 1 | 0 | main, track:T6, track:T4 | 0.867731 | T6 gained (0.866928 -> 0.867731) |
| 48 | 0.874848296 | yes | 0 / 1 | 0 | main, track:T2, track:T8 | 0.860611 | T2 gained (0.860610 -> 0.860611); T7 gained (0.853607 -> 0.853614) |
| 49 | 0.874993630 | yes | 0 / 1 | 0 | main, track:T7, track:T4 | 0.853621 | T7 gained (0.853614 -> 0.853621) |
| 50 | 0.876804810 | yes | 0 / 1 | 0 | main, track:T6, track:T2 | 0.869549 | T6 gained (0.867731 -> 0.869549); T6 landed on H2 (distance 0.051); T6 climbed from H7 into H2 |
| 51 | 0.876804810 |  | 0 / 1 | 0 | main, track:T7, track:T8 | 0.853632 | T7 gained (0.853621 -> 0.853632); T8 paused by the race at 6 experiments: stopped rising at 6 experiments (best 0.723887, below the cohort's 50% quantile) |
| 52 | 0.904522743 | yes | 1 / 1 | 0 | main, track:T6, track:T4 | 0.904523 | T2 gained (0.860611 -> 0.860614); T4 gained (0.814331 -> 0.814498); T6 gained (0.869549 -> 0.904523); T6 took the record (0.904523): it is now the main track, and T1 a side track; T4 goes on to the next rung (48 experiments): still rising (best 0.814498 at 24 experiments); new hill H9, found by T6 (build): 0.904523, distance 0.315 from the nearest known hill (H8) |
| 53 | 0.904522743 |  | 0 / 1 | 0 | main, track:T2, build | 0.860616 | T2 gained (0.860614 -> 0.860616); T7 gained (0.853632 -> 0.853683); T9 opened (a new design built from nothing around A20 -> Use no regularization) |
| 54 | 0.904522743 |  | 1 / 1 | 0 | main, track:T7, track:T4 | 0.853683 |  |
| 55 | 0.904522743 |  | 2 / 1 | 1 | main, track:T2, track:T9 | 0.860616 | T4 gained (0.814498 -> 0.814569); T7 gained (0.853683 -> 0.853734) |
| 56 | 0.904522743 |  | 3 / 1 | 1 | main, track:T4, track:T7 | 0.853750 | T7 gained (0.853734 -> 0.853756); T7 goes on to the next rung (48 experiments): still rising (best 0.853756 at 24 experiments) |
| 57 | 0.904524431 | yes | 4 / 1 | 2 | main, track:T7, track:T2 | 0.860616 | T4 gained (0.814569 -> 0.814713) |
| 58 | 0.904524431 |  | 0 / 1 | 0 | main, track:T4, track:T9 | 0.863917 | T4 gained (0.814713 -> 0.814873); T9 goes on to the next rung (6 experiments): still rising (best 0.863917 at 3 experiments); T9 landed on H2 (distance 0.072) |
| 59 | 0.904524431 |  | 1 / 1 | 0 | main, track:T4, track:T2 | 0.873041 | T2 gained (0.860616 -> 0.873041); T4 gained (0.814873 -> 0.814912); T7 gained (0.853756 -> 0.853762); T2 landed on H2 (distance 0.050); T2 climbed from H3 into H2 |
| 60 | 0.904524431 |  | 2 / 1 | 1 | main, track:T7, track:T9 | 0.862123 | T2 gained (0.873041 -> 0.873718); T7 gained (0.853762 -> 0.853827); new hill H10, found by T2 (build): 0.873718, distance 0.263 from the nearest known hill (H5) |
| 61 | 0.904524431 |  | 3 / 1 | 1 | main, track:T2, track:T4 | 0.873745 | T2 gained (0.873718 -> 0.873745); T7 gained (0.853827 -> 0.853847) |
| 62 | 0.904524431 |  | 4 / 1 | 2 | main, track:T7, track:T9 | 0.863917 | T2 gained (0.873745 -> 0.873784); T7 gained (0.853847 -> 0.853852) |
| 63 | 0.904524431 |  | 5 / 1 | 2 | main, track:T2, track:T4 | 0.873788 | T2 gained (0.873784 -> 0.873788) |
| 64 | 0.904524431 |  | 6 / 1 | 2 | main, track:T7, track:T9 | 0.864569 | T7 gained (0.853852 -> 0.853864); T9 gained (0.863917 -> 0.864569); T9 goes on to the next rung (12 experiments): still rising (best 0.864569 at 6 experiments) |
| 65 | 0.904524431 |  | 7 / 1 | 2 | main, track:T2, track:T4 | 0.874132 | T2 gained (0.873788 -> 0.874132); T2 landed on H2 (distance 0.051); T2 climbed from H10 into H2 |
| 66 | 0.904524431 |  | 8 / 1 | 2 | main, track:T7, track:T9 | 0.878404 | T2 gained (0.874132 -> 0.874144); T7 gained (0.853864 -> 0.878404); T9 gained (0.864569 -> 0.864730); T2 landed on H6 (distance 0.044) |
| 67 | 0.904524431 |  | 9 / 1 | 2 | main, track:T2, track:T4 | 0.874144 | T4 gained (0.814912 -> 0.814919) |
| 68 | 0.904524431 |  | 10 / 1 | 2 | main, track:T7, track:T9 | 0.879016 | T7 gained (0.878404 -> 0.879016) |
| 69 | 0.904524431 |  | 11 / 1 | 2 | main, track:T4, track:T2 | 0.874144 | T9 gained (0.864730 -> 0.866838) |
| 70 | 0.904524431 |  | 12 / 1 | 2 | main, track:T7, track:T9 | 0.879135 | T7 gained (0.879016 -> 0.879135) |
| 71 | 0.904524431 |  | 13 / 1 | 2 | main, track:T7, track:T2 | 0.879248 | T4 gained (0.814919 -> 0.814922); T7 gained (0.879135 -> 0.879248); T9 gained (0.866838 -> 0.875911) |
| 72 | 0.904524431 |  | 14 / 1 | 2 | main, track:T4, track:T9 | 0.875911 | T7 gained (0.879248 -> 0.879304) |
| 73 | 0.904524431 |  | 15 / 1 | 2 | main, track:T7, track:T2 | 0.879394 | T7 gained (0.879304 -> 0.879394) |
| 74 | 0.904524431 |  | 16 / 1 | 2 | main, track:T7, track:T4 | 0.879394 | T4 gained (0.814922 -> 0.814923) |
| 75 | 0.904524431 |  | 17 / 1 | 2 | main, track:T4, track:T9 | 0.876906 | T4 gained (0.814923 -> 0.814956); T7 gained (0.879394 -> 0.879484); T9 gained (0.875911 -> 0.876906); T9 is now the top of H2 (0.876906) |
| 76 | 0.904524431 |  | 18 / 1 | 2 | main, track:T7, track:T2 | 0.874144 |  |
| 77 | 0.904524431 |  | 19 / 1 | 2 | main, track:T4, track:T9 | 0.876906 | T4 gained (0.814956 -> 0.845830); T7 gained (0.879484 -> 0.879565); T9 goes on to the next rung (24 experiments): still rising (best 0.876906 at 12 experiments) |
| 78 | 0.904524431 |  | 20 / 1 | 2 | main, track:T7, track:T2 | 0.879634 | T7 gained (0.879565 -> 0.879634) |
| 79 | 0.904524431 |  | 21 / 1 | 2 | main, track:T4, track:T9 | 0.876906 |  |
| 80 | 0.904524431 |  | 22 / 1 | 2 | main, track:T7, track:T2 | 0.879634 |  |
| 81 | 0.904524431 |  | 23 / 1 | 2 | main, track:T4, track:T9 | 0.876906 | T4 gained (0.845830 -> 0.852874); T7 gained (0.879634 -> 0.879688) |
| 82 | 0.904524431 |  | 24 / 1 | 2 | main, track:T7, track:T2 | 0.879688 | T2 gained (0.874144 -> 0.874642); T4 gained (0.852874 -> 0.857183); T2 landed on H2 (distance 0.064) |
| 83 | 0.904524431 |  | 25 / 1 | 2 | main, track:T4, track:T9 | 0.876906 |  |
| 84 | 0.904524431 |  | 26 / 1 | 2 | main, track:T2, track:T7 | 0.879689 | T2 gained (0.874642 -> 0.874707); T7 gained (0.879688 -> 0.879705) |
| 85 | 0.904524431 |  | 27 / 1 | 2 | main, track:T2, track:T4 | 0.874986 | T2 gained (0.874707 -> 0.874986); T4 gained (0.857183 -> 0.857756) |
| 86 | 0.904524431 |  | 28 / 1 | 2 | main, track:T7, track:T9 | 0.879705 |  |
| 87 | 0.904524431 |  | 29 / 1 | 2 | main, track:T2, track:T4 | 0.875705 | T2 gained (0.874986 -> 0.875705) |
| 88 | 0.904524431 |  | 30 / 1 | 2 | main, track:T2, track:T7 | 0.879720 | T2 gained (0.875705 -> 0.876175); T7 gained (0.879705 -> 0.879720) |
| 89 | 0.904524431 |  | 31 / 1 | 2 | main, track:T2, track:T9 | 0.876906 | T2 finished the race (48 experiments): still rising (best 0.876175 at 48 experiments); it is now an ordinary side track |

### Hills (10: 2 on the map after its first generation, 8 found since)

| Hill | Top | Found | By | Other tracks landed on it | Description |
|---|---|---|---|---|---|
| H9 | 0.904524 (p0355) | 52 | T6 (build) | 0 | This program abandons the spike/comb atom-position search entirely and instead seeds from a dense clipped-arcsine profile, then climbs it with Adam on a coarse (500→1000→2000→4000) multiresolution ladder with multiplicat |
| H6 | 0.879720 (p0551) | 9 | T7 (build) | 2 | This program optimises a smooth soft-max surrogate of the sup-norm (exponential penalty with β annealed 500→2000→8000) via Dinkelbach iterations on a squared-weight parametrisation, rather than perturbing along a transit |
| H2 | 0.876906 (p0464) | 1 | T1 (seed) | 5 | The new program uses a multi-resolution approach: it starts from a resampled grid and applies block-multiplicative perturbations, edge-preserving smoothing, and global noise, rather than the record's single-resolution co |
| H10 | 0.873788 (p0391) | 60 | T2 (build) | 0 | This program runs a fixed, time-boxed pipeline (two L-BFGS passes, three Fourier-perturbation rounds, a fixed 4000-step Adam phase, then a final L-BFGS polish) rather than the record's adaptive multi-resolution surgery w |
| H7 | 0.867731 (p0290) | 30 | T6 (build) | 0 | This program runs its structural surgery at multiple low resolutions (1500 and 3000) rather than a single n_low=2500 round, and it polishes the surgery result with L-BFGS-B every 4 accepts instead of validating only at l |
| H4 | 0.864890 (p0221) | 6 | T5 (build) | 0 | This program optimises the full autocorrelation ratio directly via Dinkelbach iterations on a square-root variable with a soft-max surrogate for the infinity norm, rather than isolating the level-transition loss and pert |
| H3 | 0.860616 (p0331) | 2 | T2 (build) | 3 | This program optimises a smooth soft-max surrogate of the sup-norm (log-sum-exp with increasing sharpness β) via L-BFGS on a squared-parameterisation w↦w², rather than hill-climbing heights directly. It adds Anderson ext |
| H5 | 0.849670 (p0170) | 9 | T6 (build) | 0 | This program seeds a hand-built spike-plus-decaying-comb shape and refines it with a Dinkelbach-style ascent that maximizes num − λ·l1·linf via random contiguous-block scaling, rather than starting from the record's symm |
| H8 | 0.723887 (p0244) | 41 | T8 (build) | 0 | This program fixes N=4000 and optimises a symmetric step function h = [u, u[::-1]] parametrised as u = w², using exact analytic gradients of R (including a tie-averaged max subgradient) rather than the record's multi-res |
| H1 | 0.666667 (p0001) | 1 | - | 0 | the starting program (Code Zero) |

Decisions every hill shared (mapped at generation 85):

- D1: objective for the sup-norm (Linf) term (all: smooth surrogate of max: soft-max/LSE with annealed beta, or exact argmax-lag gradient, or Dinkelbach on the max)
- D2: parametrisation of the nonnegative height vector (all: h directly (with clipping to >=0), or w=sqrt(h) squared, or softplus(w); all monotone maps of a single nonnegative vector)
- D3: search backbone (all: gradient-based local ascent (Adam and/or L-BFGS-B) on a smooth objective, with multiplicative noise kicks and multiresolution rungs)
- D4: representation of f (all: a dense per-cell height vector on a uniform grid, resampled between rungs)
- D5: handling of the plateau width (all: implicitly via the ratio R; plateau widening only emerges from the Linf surrogate or from ad-hoc flat-top penalties added on top)
- D6: acceptance / elitism policy (all: strictly elitist: keep best-R iterate, revert kicks that lower R beyond a threshold)
- D7: symmetry / support assumptions (all: symmetric or near-symmetric f with support concentrated in a contiguous central region (spike+comb or clipped arcsine), zeros elsewhere)
- D8: time allocation across resolutions (all: coarse-to-fine ladder (e.g. 500->1000->2000->4000->8k/16k/50k) with most budget at the finest rung)

### The design map (20 decisions, 498 programs placed)

| Decision | Options | Read twice: agreement | Importance (last fit) |
|---|---|---|---|
| A22: Every program so far: Optimising programs keep and return the best-R array seen, not the f | as every program so far: Optimising prog; Return the final iterate; Return the best of the last k iterates; Return an average of top candidates; the best-R array seen ... | 81% of 48 (kappa 0.70) | 25% |
| A4: Which moves or update steps change a solution? | Projected gradient ascent; Structural run edits; Scattered single-cell mutations; Global parametric transforms; L-BFGS smooth surrogate ... | 87% of 60 (kappa 0.77) | 19% |
| A20: How is the autocorrelation f*f computed and updated during search (full recompute, increme | recompute or incrementally update the fu; use FFT-based convolution with analytic ; exploit sparsity/structure (e.g. only up; as every program so far: No smoothness, ; Add a small total-variation penalty ... | 95% of 59 (kappa 0.88) | 14% |
| A10: How is the maximum of f*f (the L-infinity norm) handled in the optimised objective | Exact max subgradient; Annealed LogSumExp smooth max; Fixed mild smooth max; Top-lag softmax or p-norm; Dinkelbach minimax reformulation ... | 82% of 60 (kappa 0.69) | 12% |
| A14: What is the macro shape (the envelope) of f across its domain | Heavy comb block plus ramp; Spike plus smaller comb peaks; Smooth arcsine density; Parametric series sum of bumps; Sparse packets under smooth envelope ... | 84% of 58 (kappa 0.79) | 6% |
| A1: How is a candidate solution represented? | Adaptive or variable-length grid; Low-dimensional parametric family; Signed or complex irregular function; Nonnegative heights on fixed grid; Compact support with zero padding ... | 87% of 60 (kappa 0.40) | - |
| A2: How is the first solution built? | Return start or constant; Perturb or optimize provided start; Construct from scratch; Smooth analytic bump seed; Random multi-start vectors ... | 65% of 60 (kappa 0.44) | - |
| A5: How does the search accept worse solutions or escape a local optimum? | Simulated annealing / Metropolis; Random kicks on stall; Strict monotone hill climbing; Population diversity / archive; Noise plus re-polish ... | 78% of 60 (kappa 0.68) | - |
| A6: How is the problem's scale handled (all at once, coarse to fine, in parts)? | Continuous multigrid refinement; Coarse-to-fine ladder; Multiscale budget allocation; Stochastic restarts; Fixed hand-tuned resolution ... | 83% of 60 (kappa 0.73) | - |
| A7: Which parts, if any, are solved exactly? |  | - | - |
| A12: How is f >= 0 enforced | Square parametrisation w²; Clip or project to nonnegative; Explicit pruned support mask; Unconstrained support topology; Structured support shape constraints ... | 98% of 60 (kappa 0.96) | - |
| A13: How is the number of steps n chosen and changed | Exact k-fold repeat np.repeat(f, k) (R u; Zero-pad to the step limit and polish th; Average-pool a finer construction down t; Coarse to fine, upsampling by interpolat; as every program so far: Whether the bre ... | 85% of 60 (kappa 0.79) | - |
| A19: How is the scale/normalization of f handled (implicit fixed scale, normalize to unit L2/L1 | implicitly fixed scale (constant 1), no ; normalize f to unit L2 or unit L1 before; search over scale as an explicit free pa; keep f nonnegative and let the ratio be ; fix //f//_1 = 1 or //f//_2 = 1 each step ... | 93% of 60 (kappa 0.83) | - |
| A28: Is the plateau/shoulder width targeted explicitly as an objective term, or left to emerge  | Explicit plateau width objective; Two-phase width then max; Diagnostics only, no width term; Top-K mean sup surrogate; Dinkelbach ratio surrogate ... | 92% of 60 (kappa 0.88) | - |
| A29: How is the time budget allocated and when does the search stop (deadline with fixed margin | Adaptive marginal-gain stopping; Fixed deadline, best-so-far; Fixed iteration count; Anytime adaptive budget reallocation; Restart-heavy diverse short runs ... | 97% of 34 (kappa 0.93) | - |
| A30: Is any symmetry (even, periodic, or reflection-symmetric support) enforced on f, or is the | no enforced symmetry except the optional; enforce full even symmetry h[i]=h[N-1-i]; enforce a periodic/circulant or reflecti; No symmetry enforced in the main program; Force even symmetry h[i]=h[N-1-i] to hal ... | 87% of 31 (kappa 0.77) | - |
| A32: Which local optimizer performs the final polish (gradient quasi-Newton vs derivative-free  | L-BFGS-B (gradient-based quasi-Newton) w; A derivative-free/coordinate or pattern-; A second-order method exploiting the con | 100% of 15 (kappa 1.00) | - |
| A33: What objective functional is ascended (exact ratio vs equivalent reformulation vs surrogat | Directly ascend the exact ratio (or its ; Optimize a different but equivalent func; Use a learned/surrogate model (e.g. fit ; maximise the exact ratio R (or a Dinkelb; optimise a surrogate that targets the pl ... | 60% of 15 (kappa 0.35) | - |
| A34: Is a subpixel shift/phase of the whole shape searched and re-polished? | Subpixel shift sweep | - | - |
| A35: Is f parametrised as a small set of continuous atoms splatted to the grid rather than free | Atom parametrisation with CMA-ES | - | - |

### Explorations chosen from the map (8: 7 builds, 1 flips)

| Track | Kind | Opened | Target | Built (read back) | Experiments | Best | Race | Hill |
|---|---|---|---|---|---|---|---|---|
| T2 | build | 1 | A11 -> L-BFGS with Anderson accelerat | 1/1 | 48 | 0.876175 | finished at 48 | on H2 |
| T3 | flip | 1 | A9 -> Alternating projection: push f | 1/1 | 3 | 0.723900 | paused at 6 | on H3 |
| T4 | build | 2 | A13 -> Average-pool a finer construct | 1/1 | 42 | 0.857756 | running at 24 | top H3 |
| T5 | build | 3 | A16 -> Perturb along the gradient of  | 1/1 | 32 | 0.864890 | paused at 32 | founder H4 |
| T6 | build | 4 | A14 -> Spike plus smaller comb peaks | 1/1 | 66 | 0.904524 | running at 24 | founder H9 |
| T7 | build | 7 | A10 -> Fixed mild smooth max | 1/1 | 41 | 0.879720 | running at 24 | founder H6 |
| T8 | build | 39 | A19 -> Force even symmetry h[i]=h[N-1 | 1/1 | 6 | 0.723887 | paused at 6 | founder H8 |
| T9 | build | 53 | A20 -> Use no regularization | - | 17 | 0.876906 | running at 12 | top H2 |

### Discoveries (programs at the same design that scored too differently: what differs?)

- generation 36, p0196 vs p0195: How is the final returned array selected from the search trajectory (best-R seen vs final iterate, and at which resolution)? (A27, new)
