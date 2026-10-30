# Helix v9: the map of hills and the design map

## v102-helix

- Generations 1-155: best 0.666666667 -> 0.946630994 (p0963, track T2); the main track now: T2.
- Exploration levels: level 0: 84 generations, level 1: 26 generations, level 2: 45 generations.
- Planned experiments by slot: track 295, main 155, build 14, flip 1.

### Records (57)

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
| 126 | 0.946567566 | p0781 | deep | main | T2 |
| 127 | 0.946582022 | p0788 | wide | mutation | T2 |
| 129 | 0.946598543 | p0803 | deep | main | T2 |
| 130 | 0.946600815 | p0808 | deep | main | T2 |
| 131 | 0.946612673 | p0817 | deep | main | T2 |
| 134 | 0.946624332 | p0833 | deep | main | T2 |
| 140 | 0.946625762 | p0869 | deep | main | T2 |
| 148 | 0.946627471 | p0920 | wide | mutation | T2 |
| 150 | 0.946630536 | p0933 | wide | mutation | T2 |

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
| 89 | 0.946550142 |  | 3 / 2.5 | 1 | main, track:T10, track:T6 | 0.876122 | T7 gained (0.843968 -> 0.844105); T10 gained (0.876118 -> 0.876122) |
| 90 | 0.946550142 |  | 4 / 2.5 | 1 | main, track:T7, track:T8 | 0.913713 | T1 gained (0.796146 -> 0.796147); T10 gained (0.876122 -> 0.876124) |
| 91 | 0.946550142 |  | 5 / 2.5 | 1 | main, track:T10, track:T6 | 0.876126 | T10 gained (0.876124 -> 0.876126); T10 goes on to the next rung (48 experiments): still rising (best 0.876126 at 24 experiments) |
| 92 | 0.946550143 |  | 6 / 2.5 | 1 | main, track:T10, track:T7 | 0.876127 | T1 gained (0.796147 -> 0.796149); T7 gained (0.844105 -> 0.844120); T10 gained (0.876126 -> 0.876127) |
| 93 | 0.946550167 |  | 7 / 2.5 | 2 | main, track:T7, track:T8 | 0.844122 | T7 gained (0.844120 -> 0.844122) |
| 94 | 0.946550167 |  | 8 / 2.5 | 2 | main, track:T10, track:T6 | 0.876129 | T10 gained (0.876127 -> 0.876129) |
| 95 | 0.946550177 |  | 9 / 2.5 | 2 | main, track:T7, track:T8 | 0.913712 | T7 gained (0.844122 -> 0.844125) |
| 96 | 0.946550177 |  | 10 / 2.5 | 2 | main, track:T10, track:T6 | 0.876129 | T6 paused by the race at 48 experiments: stopped rising at 48 experiments (best 0.866966) |
| 97 | 0.946550184 |  | 11 / 2.5 | 2 | main, track:T7, build | 0.844126 | T7 gained (0.844125 -> 0.844129); T8 gained (0.913712 -> 0.914066); T11 opened (a new design built from nothing around A4 -> Beam search over grids); T7 finished the race (48 experiments): still rising (best 0.844129 at 48 experiments); it is now an ordinary side track |
| 98 | 0.946550195 |  | 12 / 2.5 | 2 | main, track:T8, build | 0.914066 | T1 gained (0.796149 -> 0.796162); T11 gained (0.818322 -> 0.824136); T12 opened (a new design built from nothing around A14 -> One heavy comb block holding about 30% of the mas…) |
| 99 | 0.946550233 |  | 13 / 2.5 | 2 | main, track:T7, track:T10 | 0.876133 | T7 gained (0.844129 -> 0.844130); T10 gained (0.876129 -> 0.876133); T11 gained (0.824136 -> 0.824138) |
| 100 | 0.946550292 |  | 14 / 2.5 | 2 | main, track:T11, track:T8 | 0.914066 | T11 gained (0.824138 -> 0.825146); new hill H11, found by T11 (build): 0.825146, distance 0.123 from the nearest known hill (H7) |
| 101 | 0.946550292 |  | 15 / 2.5 | 2 | main, track:T12, track:T7 | 0.844130 | T11 gained (0.825146 -> 0.825628) |
| 102 | 0.946550292 |  | 16 / 2.5 | 2 | main, track:T10, track:T8 | 0.914066 | T11 gained (0.825628 -> 0.825645) |
| 103 | 0.946550331 |  | 17 / 2.5 | 2 | main, track:T11, track:T7 | 0.844130 | T1 gained (0.796162 -> 0.796168); T11 goes on to the next rung (6 experiments): still rising (best 0.825645 at 3 experiments) |
| 104 | 0.946550333 |  | 18 / 2.5 | 2 | main, track:T12, track:T8 | 0.914066 | T12 paused by the race at 3 experiments: no valid program that changed its start |
| 105 | 0.946550333 |  | 19 / 2.5 | 2 | main, track:T10, build | 0.876134 | T10 gained (0.876133 -> 0.876134); T13 opened (a new design built from nothing around A5 -> Fourier perturbation) |
| 106 | 0.946550333 |  | 20 / 2.5 | 2 | main, track:T10, track:T11 | 0.876134 | T11 gained (0.825645 -> 0.826286) |
| 107 | 0.946550333 |  | 21 / 2.5 | 2 | main, track:T13, track:T8 | 0.914066 | T1 gained (0.796168 -> 0.801001); T11 gained (0.826286 -> 0.826349); new hill H12, found by T13 (build): 0.806843, distance 0.083 from the nearest known hill (H5) |
| 108 | 0.946550333 |  | 22 / 2.5 | 2 | main, track:T11, track:T10 | 0.876134 | T11 gained (0.826349 -> 0.826444); T13 gained (0.806843 -> 0.825864) |
| 109 | 0.946550333 |  | 23 / 2.5 | 2 | main, track:T13, track:T8 | 0.914144 | T8 gained (0.914066 -> 0.914144); T11 gained (0.826444 -> 0.826484); T13 gained (0.825864 -> 0.827386); T13 goes on to the next rung (6 experiments): still rising (best 0.827386 at 3 experiments) |
| 110 | 0.946550333 |  | 24 / 2.5 | 2 | main, track:T11, track:T10 | 0.876134 | T11 gained (0.826484 -> 0.826528); T13 gained (0.827386 -> 0.828873); T11 goes on to the next rung (12 experiments): still rising (best 0.826528 at 6 experiments) |
| 111 | 0.946550333 |  | 25 / 2.5 | 2 | main, track:T8, track:T13 | 0.914144 | T13 gained (0.828873 -> 0.829283) |
| 112 | 0.946550333 |  | 26 / 2.5 | 2 | main, track:T11, track:T10 | 0.876135 | T11 gained (0.826528 -> 0.826531) |
| 113 | 0.946550333 |  | 27 / 2.5 | 2 | main, track:T13, track:T8 | 0.914144 | T13 gained (0.829283 -> 0.859686); T13 landed on H6 (distance 0.056); T13 climbed from H12 into H6 |
| 114 | 0.946550333 |  | 28 / 2.5 | 2 | main, track:T11, track:T10 | 0.876134 | T13 gained (0.859686 -> 0.862294) |
| 115 | 0.946550333 |  | 29 / 2.5 | 2 | main, track:T13, track:T8 | 0.914144 | T13 gained (0.862294 -> 0.862298); T8 finished the race (48 experiments): still rising (best 0.914144 at 48 experiments); it is now an ordinary side track; T13 goes on to the next rung (12 experiments): still rising (best 0.862298 at 6 experiments) |
| 116 | 0.946550333 |  | 30 / 2.5 | 2 | main, track:T13, build | 0.862298 | T11 gained (0.826531 -> 0.826535); T13 gained (0.862298 -> 0.862492); T14 opened (a new design built from nothing around A15 -> Number-theoretic support (Sidon/B2 sets, differen…) |
| 117 | 0.946550333 |  | 31 / 2.5 | 2 | main, track:T11, track:T10 | 0.876134 | T13 gained (0.862492 -> 0.862749) |
| 118 | 0.946550333 |  | 32 / 2.5 | 2 | main, track:T13, track:T14 | 0.862951 | T13 gained (0.862749 -> 0.863177) |
| 119 | 0.946550333 |  | 33 / 2.5 | 2 | main, track:T13, track:T10 | 0.876134 | T13 gained (0.863177 -> 0.863440) |
| 120 | 0.946550333 |  | 34 / 2.5 | 2 | main, track:T13, track:T11 | 0.863442 | T11 gained (0.826535 -> 0.826538); T13 gained (0.863440 -> 0.863442) |
| 121 | 0.946550333 |  | 35 / 2.5 | 2 | main, track:T11, track:T14 | 0.826546 | T11 gained (0.826538 -> 0.826547); T13 gained (0.863442 -> 0.863495); T14 paused by the race at 3 experiments: no valid program that changed its start |
| 122 | 0.946550333 |  | 36 / 2.5 | 2 | main, track:T13, build | 0.666667 | T13 gained (0.863495 -> 0.863653); T15 opened (a new design built from nothing around A12 -> Explicit support mask pruning) |
| 123 | 0.946550333 |  | 37 / 2.5 | 2 | main, track:T11, track:T10 | 0.876134 | T11 gained (0.826547 -> 0.826579); T13 gained (0.863653 -> 0.863681); T11 goes on to the next rung (24 experiments): still rising (best 0.826579 at 12 experiments) |
| 124 | 0.946550333 |  | 38 / 2.5 | 2 | main, track:T13, track:T15 | 0.863681 | T15 gained (0.555669 -> 0.766122); T13 goes on to the next rung (24 experiments): still rising (best 0.863681 at 12 experiments); new hill H13, found by T15 (build): 0.766122, distance 0.152 from the nearest known hill (H9) |
| 125 | 0.946550333 |  | 39 / 2.5 | 2 | main, track:T11, track:T10 | 0.876134 | T11 gained (0.826579 -> 0.828993); T13 gained (0.863681 -> 0.863687) |
| 126 | 0.946567566 | yes | 40 / 2.5 | 2 | main, track:T13, track:T15 | 0.863691 | T13 gained (0.863687 -> 0.863697); T15 gained (0.766122 -> 0.788503); T15 goes on to the next rung (6 experiments): still rising (best 0.788503 at 3 experiments) |
| 127 | 0.946582022 | yes | 0 / 3.5 | 0 | main, track:T11, track:T10 | 0.876134 | T11 gained (0.828993 -> 0.829148); T13 gained (0.863697 -> 0.863852); T15 gained (0.788503 -> 0.789059) |
| 128 | 0.946582022 |  | 0 / 3.5 | 0 | main, track:T13, track:T15 | 0.863893 | T13 gained (0.863852 -> 0.863905); T15 gained (0.789059 -> 0.789178) |
| 129 | 0.946598543 | yes | 1 / 3.5 | 0 | main, track:T11, track:T10 | 0.829152 | T11 gained (0.829148 -> 0.829152); T13 gained (0.863905 -> 0.863907); T15 gained (0.789178 -> 0.789454) |
| 130 | 0.946600815 | yes | 0 / 3 | 0 | main, track:T13, track:T15 | 0.863908 | T13 gained (0.863907 -> 0.863921); T15 gained (0.789454 -> 0.789664) |
| 131 | 0.946612673 | yes | 0 / 3 | 0 | main, track:T11, track:T10 | 0.876145 | T10 gained (0.876134 -> 0.876145); T11 gained (0.829152 -> 0.830062); T15 gained (0.789664 -> 0.790069) |
| 132 | 0.946612673 |  | 0 / 2 | 0 | main, track:T13, track:T15 | 0.863928 | T13 gained (0.863921 -> 0.863928); T15 gained (0.790069 -> 0.790317); T15 goes on to the next rung (12 experiments): still rising (best 0.790317 at 6 experiments) |
| 133 | 0.946612886 |  | 1 / 2 | 0 | main, track:T10, track:T11 | 0.876145 | T11 gained (0.830062 -> 0.830291); T15 gained (0.790317 -> 0.790418) |
| 134 | 0.946624332 | yes | 2 / 2 | 0 | main, track:T13, track:T15 | 0.790418 |  |
| 135 | 0.946624614 |  | 0 / 2 | 0 | main, track:T11, track:T10 | 0.830305 | T11 gained (0.830291 -> 0.830398) |
| 136 | 0.946624842 |  | 1 / 2 | 0 | main, track:T11, track:T13 | 0.863928 | T11 gained (0.830398 -> 0.830415); T13 gained (0.863928 -> 0.863930) |
| 137 | 0.946624842 |  | 2 / 2 | 0 | main, track:T11, track:T15 | 0.830427 | T11 gained (0.830415 -> 0.830427); T13 gained (0.863930 -> 0.864050) |
| 138 | 0.946625060 |  | 3 / 2 | 1 | main, track:T13, track:T10 | 0.876145 | T11 gained (0.830427 -> 0.830429) |
| 139 | 0.946625186 |  | 4 / 2 | 1 | main, track:T11, track:T15 | 0.830465 | T11 gained (0.830429 -> 0.830465); T15 gained (0.790418 -> 0.792053) |
| 140 | 0.946625762 |  | 5 / 2 | 1 | main, track:T11, track:T10 | 0.876145 | T11 gained (0.830465 -> 0.834704) |
| 141 | 0.946625762 |  | 0 / 2 | 0 | main, track:T15, track:T13 | 0.864127 | T13 gained (0.864050 -> 0.864127) |
| 142 | 0.946625762 |  | 1 / 2 | 0 | main, track:T11, track:T10 | 0.876147 | T10 gained (0.876145 -> 0.876147); T11 gained (0.834704 -> 0.834965) |
| 143 | 0.946625762 |  | 2 / 2 | 0 | main, track:T13, track:T15 | 0.864127 | T13 gained (0.864127 -> 0.864137); T15 gained (0.792053 -> 0.804730) |
| 144 | 0.946625762 |  | 3 / 2 | 1 | main, track:T10, track:T11 | 0.876147 | T15 gained (0.804730 -> 0.815560); T10 finished the race (48 experiments): still rising (best 0.876147 at 48 experiments); it is now an ordinary side track; T11 goes on to the next rung (48 experiments): still rising (best 0.834965 at 24 experiments) |
| 145 | 0.946625762 |  | 4 / 2 | 1 | main, track:T13, build | 0.864137 | T15 gained (0.815560 -> 0.829105); T16 opened (a new design built from nothing around A4 -> Population evolutionary search) |
| 146 | 0.946625762 |  | 5 / 2 | 1 | main, track:T15, track:T10 | 0.876149 | T10 gained (0.876147 -> 0.876149); T15 gained (0.829105 -> 0.830553); T16 gained (0.785765 -> 0.786318); T15 goes on to the next rung (24 experiments): still rising (best 0.830553 at 12 experiments) |
| 147 | 0.946626135 |  | 6 / 2 | 2 | main, track:T16, track:T11 | 0.834965 | T16 gained (0.786318 -> 0.801141); new hill H14, found by T16 (build): 0.801141, distance 0.104 from the nearest known hill (H12) |
| 148 | 0.946627471 | yes | 7 / 2 | 2 | main, track:T10, track:T13 | 0.876149 | T13 gained (0.864137 -> 0.865513); T15 gained (0.830553 -> 0.831283); T16 gained (0.801141 -> 0.806599) |
| 149 | 0.946627699 |  | 0 / 2.5 | 0 | main, track:T15, track:T11 | 0.834965 | T15 gained (0.831283 -> 0.831293); T16 gained (0.806599 -> 0.806600) |
| 150 | 0.946630536 | yes | 1 / 2.5 | 0 | main, track:T16, track:T10 | 0.876149 | T16 gained (0.806600 -> 0.811059); T16 goes on to the next rung (6 experiments): still rising (best 0.811059 at 3 experiments) |
| 151 | 0.946630642 |  | 0 / 2 | 0 | main, track:T13, track:T11 | 0.868658 | T11 gained (0.834965 -> 0.835016); T13 gained (0.865513 -> 0.868658); T16 gained (0.811059 -> 0.812272); T13 goes on to the next rung (48 experiments): still rising (best 0.868658 at 24 experiments); T13 is now the top of H6 (0.868658) |
| 152 | 0.946630668 |  | 1 / 2 | 0 | main, track:T15, track:T16 | 0.831298 | T15 gained (0.831293 -> 0.831298); T16 gained (0.812272 -> 0.813182) |
| 153 | 0.946630896 |  | 2 / 2 | 0 | main, track:T11, track:T13 | 0.868660 | T11 gained (0.835016 -> 0.835018); T13 gained (0.868658 -> 0.868660); T15 gained (0.831298 -> 0.838035); T16 gained (0.813182 -> 0.813615) |
| 154 | 0.946630896 |  | 3 / 2 | 1 | main, track:T15, track:T16 | 0.842923 | T15 gained (0.838035 -> 0.842923); T16 gained (0.813615 -> 0.813946) |
| 155 | 0.946630994 |  | 4 / 2 | 1 | main, track:T11, track:T13 | 0.868662 | T11 gained (0.835018 -> 0.835077); T13 gained (0.868660 -> 0.868662); T15 gained (0.842923 -> 0.843515); T16 gained (0.813946 -> 0.820094) |

### Hills (14: 2 on the map after its first generation, 12 found since)

| Hill | Top | Found | By | Other tracks landed on it | Description |
|---|---|---|---|---|---|
| H2 | 0.946631 (p0933) | 1 | T2 (build) | 0 | This program optimizes a smooth log-sum-exp surrogate of the sup-norm with an annealed sharpness parameter inside a Dinkelbach loop, rather than directly maximizing the exact ratio. It uses L-BFGS-B with analytic gradien |
| H8 | 0.914144 (p0677) | 16 | T8 (build) | 0 | This program abandons the record's high-resolution climb entirely, instead starting from the given start and running a prune-refine-upsample loop that repeatedly zeroes the smallest fraction of cells and re-optimises ins |
| H10 | 0.876149 (p0908) | 46 | T10 (build) | 0 | This program seeds from a periodic cosine-tooth envelope rather than from the record's start, and it optimises with a Dinkelbach loop over an LSE-smoothed max (beta up to 1e12) instead of exact-move golden-section/pair p |
| H6 | 0.868662 (p0965) | 7 | T6 (build) | 1 | This program builds a hand-crafted spike-plus-decaying-comb seed at n=512 and then doubles resolution in four stages (512→1024→2048→4096), spending only 20% of budget on the first stage and re-annealing beta from 1e4 upw |
| H7 | 0.844130 (p0613) | 8 | T7 (build) | 0 | This program builds a hand-crafted seed of a 10-tooth raised-cosine comb plus a graded ramp of 30 bumps, then grows it by coordinate-wise golden-section tuning of per-run multiplicative factors and additive bumps (doubli |
| H13 | 0.843515 (p0960) | 124 | T15 (build) | 0 | This program searches over support masks rather than continuous heights: it proposes discrete mask moves (delete/add/swap/shift/split cells) and re-polishes only the active cells with L-BFGS-B under a smoothed log-sum-ex |
| H11 | 0.835077 (p0961) | 100 | T11 (build) | 0 | This program runs a coarse-to-fine multiresolution ladder (256→16384) with a beam of candidates, using Adam gradient descent on an analytic gradient of R plus golden-section coordinate polish, rather than the record's ex |
| H12 | 0.829283 (p0688) | 107 | T13 (build) | 0 | This program abandons the record's exact-move polisher and instead optimizes a Dinkelbach-transformed LSE-smoothed max with L-BFGS-B gradients, using exact golden-section coordinate sweeps only as a secondary polish. It  |
| H14 | 0.820094 (p0959) | 147 | T16 (build) | 0 | This program runs a genetic algorithm (population of 10, mutation/crossover, staged upsampling from 1024 to 16384) rather than the record's exact-coordinate/pair-sweep plus Dinkelbach polish pipeline. It relies on L-BFGS |
| H3 | 0.804847 (p0022) | 2 | T3 (flip) | 0 | This program optimizes a Dinkelbach-style surrogate (smooth-max minus λ·num) with L-BFGS-B gradients on a fixed grid, rather than the record's approach of building a tuned small-n construction and carefully upsampling it |
| H4 | 0.803713 (p0035) | 4 | T4 (build) | 0 | This program starts from the given `start` and refines it with local, parameterised moves (run scaling, additive cosine packets, constant-run shifts, bump replacement, and pairwise mass transfer), each tuned by a 1-D gri |
| H5 | 0.801808 (p0031) | 6 | T5 (build) | 0 | This program uses linear interpolation to upsample between fixed ladder sizes (256→4096) rather than repeat-based upsampling, and it anneals the smooth-max exponent p from 4 to 400 within each stage instead of re-anneali |
| H9 | 0.774369 (p0196) | 20 | T9 (build) | 0 | This program abandons the record's multi-resolution pipeline (refine at 4096/8192/32768 then pool down) and instead works directly at a single fixed resolution (N=1024), starting from the constant-ones seed rather than a |
| H1 | 0.666667 (p0001) | 1 | - | 0 | the starting program (Code Zero) |

Decisions every hill shared (mapped at generation 154):

- D1: objective used for the inner continuous optimizer (all: a smooth surrogate of the sup-norm (log-sum-exp with annealed beta, or a Dinkelbach-transformed LSE) optimized by L-BFGS-B with analytic gradients)
- D2: representation of f (all: a single nonnegative real vector on a uniform 1-D grid, normalized to sum 1, with zero-padding for convolution)
- D3: search trajectory across resolution (all: coarse-to-fine upsampling (doubling or ladder 64→...→49152) with re-polishing at each scale, or fixed high-resolution polish of an upsampled seed)
- D4: how nonlocal/support structure is changed (all: local moves: single-cell or block scaling, ramps, births into zero runs, or FFT low-mode multiplicative perturbations — all small perturbations around the incu…)
- D5: handling of the argmax / plateau of f*f (all: treat the max as a single (or tied) knot and either smooth it via LSE or pin/penalize it, with the plateau width emerging as a byproduct)
- D6: initialization (all: either the provided start, a random Gaussian packet, or a hand-crafted comb/spike seed — all dense or near-dense nonnegative profiles)
- D7: time allocation between exploration and polishing (all: a fixed fraction (roughly 20-60%) to a coarse/exploratory phase and the remainder to gradient polishing at the finest resolution, with a hard wall-clock deadli…)
- D8: symmetry / normalization constraints imposed (all: only nonnegativity and sum-normalization; no enforced symmetry, periodicity, or moment constraints on f)

### The design map (16 decisions, 922 programs placed)

| Decision | Options | Read twice: agreement | Importance (last fit) |
|---|---|---|---|
| A5: How does the search accept worse solutions or escape a local optimum? | Restart or basin-hopping; Noise kick then re-polish; Fourier/convolution-space perturbation; Structural block surgery; Exact plateau moves ... | 96% of 84 (kappa 0.95) | 11% |
| A3: What quantity does the search optimise while it runs? | Minimax dual active-set weights; Exact line search on R; Alternating projection to target; Direct ratio maximisation; Bisection on ratio feasibility ... | 87% of 84 (kappa 0.83) | 6% |
| A14: What is the macro shape (the envelope) of f across its domain | One heavy comb block holding about 30% o; A tall spike plus a comb of smaller peak; A smooth arcsine-like density, 1/sqrt(1 ; A parametric series sum_j a_j (1 - 4x^2); Regular sparse packets under a smooth ra | 62% of 47 (kappa 0.51) | 6% |
| A2: How is the first solution built? | Constant or supplied start; Random smooth field; Hand-designed bump or comb; Random Gaussian packet mixture; Deterministic analytic construction ... | 80% of 84 (kappa 0.70) | 6% |
| A28: How is the grid resolution chosen and changed across stages (fixed single resolution vs. a | Fixed single resolution; Meshfree particle representation; Fixed resolution ladder with upsampling; Continuous adaptive mesh / moving knots; Adaptive mesh refinement near structure ... | 98% of 48 (kappa 0.96) | 6% |
| A1: How is a candidate solution represented? | Dense grid direct values; Parametric analytic form; Sparse low-degree basis; Spline/Fourier basis coefficients; Softmax/log parameterization ... | 99% of 84 (kappa 0.66) | - |
| A4: Which moves or update steps change a solution? | No search, fixed output; Derivative-free local search; Coordinate/line-search moves; Block/segment multi-cell moves; Gradient-based full-vector steps ... | 90% of 84 (kappa 0.87) | - |
| A7: Which parts, if any, are solved exactly? |  | - | - |
| A8: How is the time budget split between phases? | Run to completion, no budget; Run until wall-clock budget elapses; Adaptive budget by improvement rate; Reserved budget kick-and-repolish; Parallel multi-seed, keep best ... | 88% of 84 (kappa 0.85) | - |
| A12: How is f >= 0 enforced | Square to enforce nonnegativity; Clip or project to f>=0; Explicit support mask pruning; Unconstrained, rely on ratio; Fix norm to remove scale ... | 95% of 84 (kappa 0.33) | - |
| A15: What is the fine structure of f (the comb of teeth or blocks) | A fine, coherent periodic lattice of tee; Contiguous blocks with irregular spacing; A coarser parent with each cell split in; Number-theoretic support (Sidon/B2 sets,; Regular [small, big, small] triplets | 62% of 53 (kappa 0.17) | - |
| A18: How is the objective (the convolution and its norms) computed numerically? | compute f*f by direct convolution on the; evaluate the ratio analytically for a pa; use FFT-based convolution with careful n; finite interval with zero-padding implie; periodic (circular) convolution on a tor ... | 86% of 84 (kappa 0.77) | - |
| A20: What symmetry or shape assumptions are imposed on f? | general unconstrained shape, no symmetry; enforce even symmetry (f(x)=f(-x)); enforce a unimodal or compactly supporte; Optionally symmetrize the construction (; Impose an explicit periodic or comb stru ... | 79% of 84 (kappa 0.69) | - |
| A24: How is the scale/normalization of f fixed (e.g. //f//_1=1 renormalization, //f*f//_inf=1,  | Renormalize L1 after each step; Fix sup-norm of f*f; Fix L2 norm of f; Hard sum(f)=1 constraint; Simplex projected/exponentiated gradient ... | 93% of 69 (kappa 0.26) | - |
| A33: How is the sup-norm (max) kink handled in the objective: smoothed with an annealed paramet | smooth it (LSE with annealed beta) or re; explicitly track and equalize the set of; use a soft-max with a different smoothin; treat the sup-norm as a single (or avera; explicitly design a flat-top target shap ... | 87% of 23 (kappa 0.79) | - |
| A36: How are new cells inserted into the grid to refine resolution? | greedy split at highest gradient cells | 0% of 1 (kappa 0.00) | - |

Interacting decisions in the last fit: ('A5', 'A15')

### Explorations chosen from the map (15: 14 builds, 1 flips)

| Track | Kind | Opened | Target | Built (read back) | Experiments | Best | Race | Hill |
|---|---|---|---|---|---|---|---|---|
| T2 | build | 1 | A13 -> Coarse to fine, upsampling by  | 1/1 | 155 | 0.946631 | running | founder H2 |
| T3 | flip | 1 | A18 -> a new option, unlike the liste | 1/1 | 6 | 0.804847 | paused at 6 | founder H3 |
| T4 | build | 2 | A9 -> Exact line search on R per blo | 1/1 | 6 | 0.803713 | paused at 6 | founder H4 |
| T5 | build | 3 | A10 -> A softmax- or p-norm-weighted  | 1/1 | 6 | 0.801808 | paused at 6 | founder H5 |
| T6 | build | 4 | A14 -> A tall spike plus a comb of sm | 1/1 | 48 | 0.866966 | paused at 48 | founder H6 |
| T7 | build | 5 | A17 -> Small-mass runs of f first | 1/1 | 51 | 0.844130 | finished at 48 | founder H7 |
| T8 | build | 14 | A11 -> Adam stochastic ascent with re | 1/1 | 48 | 0.914144 | finished at 48 | founder H8 |
| T9 | build | 18 | A12 -> Square to enforce nonnegativit | 1/1 | 12 | 0.774369 | paused at 12 | founder H9 |
| T10 | build | 44 | A15 -> A fine, coherent periodic latt | 1/1 | 51 | 0.876149 | finished at 48 | founder H10 |
| T11 | build | 97 | A4 -> Beam search over grids | 0/1 | 29 | 0.835077 | running at 24 | founder H11 |
| T12 | build | 98 | A14 -> One heavy comb block holding a | - | 3 | - | paused at 3 | -  |
| T13 | build | 105 | A5 -> Fourier/convolution-space pert | 1/1 | 26 | 0.868662 | running at 24 | top H6 |
| T14 | build | 116 | A15 -> Number-theoretic support (Sido | 1/1 | 3 | - | paused at 3 | -  |
| T15 | build | 122 | A12 -> Explicit support mask pruning | 1/1 | 15 | 0.843515 | running at 12 | founder H13 |
| T16 | build | 145 | A4 -> Population evolutionary search | 1/1 | 5 | 0.820094 | running at 3 | founder H14 |

### Discoveries (programs at the same design that scored too differently: what differs?)

- generation 44, p0270 vs p0269: How is the final answer selected from the candidates produced during the search? (A25, new)
- generation 84, p0286 vs p0269: How is the search's time budget allocated across the resolution ladder (how many rungs, and what share each gets)? (A29, new)
- generation 88, p0492 vs p0491: How is the initial solution (or restart seed) chosen before the main search? (A30, new)
- generation 112, p0679 vs p0678: How is the starting point (the provided start) used relative to the multi-start seeds? (A32, new)
- generation 136, p0828 vs p0846: How is the time budget allocated across the different search phases (coordinate sweeps, pair sweeps, Dinkelbach/L-BFGS rounds, restarts)? (A34, new)
- generation 144, p0143 vs p0226: How does the search handle the resolution/representation of f during optimization (fixed grid vs. multi-resolution)? (A37, new)

## v102-helix-s2

- Generations 1-161: best 0.666666667 -> 0.941033359 (p1018, track T9); the main track now: T9.
- Exploration levels: level 0: 102 generations, level 1: 19 generations, level 2: 40 generations.
- Planned experiments by slot: track 310, main 161, build 11, flip 1.

### Records (79)

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
| 90 | 0.904527016 | p0562 | deep | main | T6 |
| 92 | 0.904622210 | p0572 | wide | mutation | T6 |
| 97 | 0.904628851 | p0605 | deep | main | T6 |
| 100 | 0.927286941 | p0625 | wide | mutation | T9 |
| 101 | 0.937140029 | p0630 | deep | main | T9 |
| 103 | 0.937658443 | p0641 | deep | main | T9 |
| 105 | 0.938965079 | p0655 | deep | main | T9 |
| 106 | 0.939864238 | p0658 | wide | mutation | T9 |
| 107 | 0.939924742 | p0667 | deep | main | T9 |
| 112 | 0.939933277 | p0698 | deep | main | T9 |
| 113 | 0.939948377 | p0700 | wide | mutation | T9 |
| 114 | 0.939959279 | p0709 | wide | mutation | T9 |
| 120 | 0.940038865 | p0752 | deep | main | T9 |
| 122 | 0.940051677 | p0763 | deep | main | T9 |
| 123 | 0.940108480 | p0768 | deep | main | T9 |
| 124 | 0.940119810 | p0775 | deep | main | T9 |
| 125 | 0.940128505 | p0782 | deep | main | T9 |
| 126 | 0.940136171 | p0787 | deep | main | T9 |
| 127 | 0.940144148 | p0791 | deep | main | T9 |
| 128 | 0.940153080 | p0802 | deep | main | T9 |
| 129 | 0.940160541 | p0810 | deep | main | T9 |
| 130 | 0.940167805 | p0811 | wide | mutation | T9 |
| 131 | 0.940174375 | p0818 | deep | main | T9 |
| 137 | 0.940178169 | p0861 | deep | main | T9 |
| 138 | 0.940320053 | p0867 | wide | mutation | T9 |
| 140 | 0.940334814 | p0882 | deep | main | T9 |
| 144 | 0.940366545 | p0908 | deep | main | T9 |
| 145 | 0.940417499 | p0913 | wide | mutation | T9 |
| 146 | 0.940457443 | p0919 | deep | main | T9 |
| 147 | 0.940557534 | p0925 | wide | mutation | T9 |
| 148 | 0.940610282 | p0936 | deep | main | T9 |
| 149 | 0.940648920 | p0943 | deep | main | T9 |
| 150 | 0.940687589 | p0948 | deep | main | T9 |
| 152 | 0.940725209 | p0957 | wide | mutation | T9 |
| 153 | 0.940769115 | p0966 | wide | mutation | T9 |
| 154 | 0.940885904 | p0970 | wide | mutation | T9 |
| 155 | 0.940989483 | p0977 | deep | main | T9 |
| 156 | 0.940993783 | p0983 | deep | main | T9 |
| 157 | 0.940997060 | p0991 | deep | main | T9 |
| 158 | 0.940999868 | p0997 | deep | main | T9 |
| 160 | 0.941012352 | p1009 | deep | main | T9 |
| 161 | 0.941033359 | p1018 | deep | main | T9 |

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
| 90 | 0.904527016 | yes | 32 / 1 | 2 | main, track:T7, build | 0.879737 | T4 gained (0.857756 -> 0.858616); T7 gained (0.879720 -> 0.879737); T10 opened (a new design built from nothing around A10 -> Level-transition lags) |
| 91 | 0.904527016 |  | 0 / 1.5 | 0 | main, track:T4, track:T2 | 0.876175 | T4 gained (0.858616 -> 0.859577); T10 gained (0.737925 -> 0.801049) |
| 92 | 0.904622210 | yes | 1 / 1.5 | 0 | main, track:T7, track:T9 | 0.879752 | T7 gained (0.879737 -> 0.879752); T10 gained (0.801049 -> 0.836984) |
| 93 | 0.904622210 |  | 0 / 1.5 | 0 | main, track:T10, track:T4 | 0.836984 | new hill H11, found by T10 (build): 0.836984, distance 0.944 from the nearest known hill (H4) |
| 94 | 0.904622210 |  | 1 / 1.5 | 0 | main, track:T7, track:T9 | 0.879767 | T7 gained (0.879752 -> 0.879767) |
| 95 | 0.904622210 |  | 2 / 1.5 | 1 | main, track:T7, track:T4 | 0.879767 | T4 gained (0.859577 -> 0.859581); T10 gained (0.836984 -> 0.848557) |
| 96 | 0.904622210 |  | 3 / 1.5 | 1 | main, track:T10, track:T9 | 0.876906 | T4 gained (0.859581 -> 0.859584); T10 gained (0.848557 -> 0.848639); T10 goes on to the next rung (6 experiments): still rising (best 0.848639 at 3 experiments) |
| 97 | 0.904628851 | yes | 4 / 1.5 | 1 | main, track:T4, track:T7 | 0.879782 | T4 gained (0.859584 -> 0.859588); T7 gained (0.879767 -> 0.879782) |
| 98 | 0.904628851 |  | 0 / 2 | 0 | main, track:T10, track:T9 | 0.880778 | T9 gained (0.876906 -> 0.880778); T10 gained (0.848639 -> 0.852826); T10 landed on H2 (distance 0.086); T10 climbed from H11 into H2 |
| 99 | 0.904628851 |  | 1 / 2 | 0 | main, track:T4, track:T7 | 0.879796 | T7 gained (0.879782 -> 0.879796) |
| 100 | 0.927286941 | yes | 2 / 2 | 0 | main, track:T9, track:T10 | 0.880778 | T9 gained (0.880778 -> 0.927287); T10 gained (0.852826 -> 0.858225); T9 took the record (0.927287): it is now the main track, and T6 a side track; T6 paused by the race at 48 experiments: stopped rising at 48 experiments (best 0.904524); new hill H12, found by T10 (build): 0.858225, distance 0.097 from the nearest known hill (H6) |
| 101 | 0.937140029 | yes | 0 / 2.5 | 0 | main, track:T7, build | 0.879809 | T7 gained (0.879796 -> 0.879809); T11 opened (a new design built from nothing around A33 -> Min-max plateau-gap surrogate); T7 finished the race (48 experiments): still rising (best 0.879809 at 48 experiments); it is now an ordinary side track |
| 102 | 0.937140029 |  | 0 / 2.5 | 0 | main, track:T10, build | 0.861976 | T10 gained (0.858225 -> 0.864674); T12 opened (a new design built from nothing around A14 -> Regular small-big-small triplets); T10 goes on to the next rung (12 experiments): still rising (best 0.864674 at 6 experiments) |
| 103 | 0.937658443 | yes | 1 / 2.5 | 0 | main, track:T7, track:T4 | 0.879823 | T7 gained (0.879809 -> 0.879823); T10 gained (0.864674 -> 0.869836); T4 finished the race (48 experiments): still rising (best 0.859588 at 48 experiments); it is now an ordinary side track |
| 104 | 0.937658443 |  | 0 / 2.5 | 0 | main, track:T11, build | 0.849308 | T10 gained (0.869836 -> 0.872339); T13 opened (a new design built from nothing around A20 -> Add an L2 penalty on heights); T10 landed on H6 (distance 0.049); T10 climbed from H12 into H6; new hill H13, found by T11 (build): 0.723461, distance 0.332 from the nearest known hill (H2) |
| 105 | 0.938965079 | yes | 1 / 2.5 | 0 | main, track:T10, track:T12 | 0.872339 | new hill H14, found by T12 (build): 0.818877, distance 0.253 from the nearest known hill (H13) |
| 106 | 0.939864238 | yes | 0 / 2.5 | 0 | main, track:T7, track:T11 | 0.879823 | T11 gained (0.723461 -> 0.832502); T13 gained (0.849308 -> 0.856209); T11 goes on to the next rung (6 experiments): still rising (best 0.832502 at 3 experiments) |
| 107 | 0.939924742 | yes | 0 / 2 | 0 | main, track:T13, track:T10 | 0.872482 | T10 gained (0.872339 -> 0.872482); T11 gained (0.832502 -> 0.834892); T13 gained (0.856209 -> 0.856664); new hill H15, found by T13 (build): 0.856664, distance 0.297 from the nearest known hill (H5) |
| 108 | 0.939924742 |  | 0 / 2 | 0 | main, track:T12, track:T7 | 0.879823 | T11 gained (0.834892 -> 0.835514); T13 gained (0.856664 -> 0.857070); T12 goes on to the next rung (6 experiments): still rising (best 0.818877 at 3 experiments) |
| 109 | 0.939924764 |  | 1 / 2 | 0 | main, track:T11, track:T10 | 0.872513 | T10 gained (0.872482 -> 0.872513); T12 gained (0.818877 -> 0.834019); T13 gained (0.857070 -> 0.857700) |
| 110 | 0.939924764 |  | 2 / 2 | 0 | main, track:T13, track:T12 | 0.857700 | T11 gained (0.835514 -> 0.839721); T12 gained (0.834019 -> 0.849907); T13 goes on to the next rung (6 experiments): still rising (best 0.857700 at 3 experiments); T11 landed on H6 (distance 0.059); T11 climbed from H13 into H6 |
| 111 | 0.939925143 |  | 3 / 2 | 1 | main, track:T10, track:T11 | 0.872517 | T10 gained (0.872513 -> 0.872517); T11 gained (0.839721 -> 0.839901); T12 gained (0.849907 -> 0.857737); T13 gained (0.857700 -> 0.915212) |
| 112 | 0.939933277 | yes | 4 / 2 | 1 | main, track:T12, track:T13 | 0.858585 | T11 gained (0.839901 -> 0.839939); T12 gained (0.857737 -> 0.858585); T13 gained (0.915212 -> 0.916825) |
| 113 | 0.939948377 | yes | 0 / 2 | 0 | main, track:T10, track:T11 | 0.872517 | T11 gained (0.839939 -> 0.839945); T12 gained (0.858585 -> 0.860448); T11 goes on to the next rung (12 experiments): still rising (best 0.839945 at 6 experiments) |
| 114 | 0.939959279 | yes | 0 / 1.5 | 0 | main, track:T12, track:T13 | 0.916825 | T12 gained (0.860448 -> 0.862493); T12 goes on to the next rung (12 experiments): still rising (best 0.862493 at 6 experiments) |
| 115 | 0.939959280 |  | 0 / 1 | 0 | main, track:T11, track:T10 | 0.872580 | T10 gained (0.872517 -> 0.872580); T10 goes on to the next rung (24 experiments): still rising (best 0.872580 at 12 experiments) |
| 116 | 0.939959280 |  | 1 / 1 | 0 | main, track:T12, track:T13 | 0.916871 | T12 gained (0.862493 -> 0.862501); T13 gained (0.916825 -> 0.916871); T13 goes on to the next rung (12 experiments): still rising (best 0.916871 at 6 experiments) |
| 117 | 0.939959280 |  | 2 / 1 | 1 | main, track:T10, track:T11 | 0.872581 | T10 gained (0.872580 -> 0.872581) |
| 118 | 0.939959280 |  | 3 / 1 | 1 | main, track:T12, track:T13 | 0.862501 | T11 gained (0.839945 -> 0.839953) |
| 119 | 0.939959280 |  | 4 / 1 | 2 | main, track:T10, track:T11 | 0.872581 | T11 gained (0.839953 -> 0.853454) |
| 120 | 0.940038865 | yes | 5 / 1 | 2 | main, track:T11, track:T12 | 0.862502 | T11 gained (0.853454 -> 0.855064) |
| 121 | 0.940038865 |  | 0 / 1.5 | 0 | main, track:T11, track:T13 | 0.916871 | T13 gained (0.916871 -> 0.916872) |
| 122 | 0.940051677 | yes | 1 / 1.5 | 0 | main, track:T13, track:T10 | 0.916872 |  |
| 123 | 0.940108480 | yes | 0 / 1.5 | 0 | main, track:T12, track:T11 | 0.862501 | T11 goes on to the next rung (24 experiments): still rising (best 0.855064 at 12 experiments) |
| 124 | 0.940119810 | yes | 0 / 1 | 0 | main, track:T10, track:T13 | 0.916872 | T11 gained (0.855064 -> 0.858032) |
| 125 | 0.940128505 | yes | 0 / 1 | 0 | main, track:T11, track:T12 | 0.862502 | T11 gained (0.858032 -> 0.859351) |
| 126 | 0.940136171 | yes | 0 / 1 | 0 | main, track:T11, track:T10 | 0.872670 | T10 gained (0.872581 -> 0.872670) |
| 127 | 0.940144148 | yes | 0 / 1 | 0 | main, track:T10, track:T13 | 0.916881 | T11 gained (0.859351 -> 0.859372); T13 gained (0.916872 -> 0.916881) |
| 128 | 0.940153080 | yes | 0 / 1 | 0 | main, track:T11, track:T12 | 0.859421 | T11 gained (0.859372 -> 0.859421); T12 goes on to the next rung (24 experiments): no longer rising, but best 0.862501 at 12 experiments is at or above the cohort's 50% quantile (0.855705) |
| 129 | 0.940160541 | yes | 0 / 1 | 0 | main, track:T13, track:T10 | 0.916881 | T11 gained (0.859421 -> 0.859432); T13 goes on to the next rung (24 experiments): still rising (best 0.916881 at 12 experiments) |
| 130 | 0.940167805 | yes | 0 / 1 | 0 | main, track:T11, track:T12 | 0.859444 | T11 gained (0.859432 -> 0.859444) |
| 131 | 0.940174375 | yes | 0 / 1 | 0 | main, track:T11, track:T10 | 0.872670 | T11 gained (0.859444 -> 0.859452) |
| 132 | 0.940174375 |  | 0 / 1 | 0 | main, track:T11, track:T13 | 0.916881 |  |
| 133 | 0.940174375 |  | 1 / 1 | 0 | main, track:T12, track:T10 | 0.872670 | T11 gained (0.859452 -> 0.859480) |
| 134 | 0.940174375 |  | 2 / 1 | 1 | main, track:T11, track:T13 | 0.916881 |  |
| 135 | 0.940174375 |  | 3 / 1 | 1 | main, track:T10, track:T12 | 0.872670 | T11 gained (0.859480 -> 0.859486) |
| 136 | 0.940174375 |  | 4 / 1 | 2 | main, track:T11, track:T13 | 0.916881 |  |
| 137 | 0.940178169 | yes | 5 / 1 | 2 | main, track:T10, track:T12 | 0.872670 |  |
| 138 | 0.940320053 | yes | 0 / 1 | 0 | main, track:T11, track:T13 | 0.916926 | T11 gained (0.859486 -> 0.859487); T13 gained (0.916881 -> 0.916926) |
| 139 | 0.940320053 |  | 0 / 1 | 0 | main, track:T11, track:T10 | 0.872670 | T11 gained (0.859487 -> 0.859489); T13 gained (0.916926 -> 0.917124); T10 goes on to the next rung (48 experiments): no longer rising, but best 0.872670 at 24 experiments is at or above the cohort's 50% quantile (0.862333) |
| 140 | 0.940334814 | yes | 1 / 1 | 0 | main, track:T13, track:T12 | 0.917151 | T13 gained (0.917124 -> 0.917151) |
| 141 | 0.940334814 |  | 0 / 1 | 0 | main, track:T11, track:T10 | 0.872670 | T11 gained (0.859489 -> 0.859490); T13 gained (0.917151 -> 0.917164) |
| 142 | 0.940334814 |  | 1 / 1 | 0 | main, track:T13, track:T12 | 0.917167 | T13 gained (0.917164 -> 0.917167) |
| 143 | 0.940334814 |  | 2 / 1 | 1 | main, track:T11, track:T10 | 0.872670 | T11 gained (0.859490 -> 0.859491); T11 goes on to the next rung (48 experiments): still rising (best 0.859491 at 24 experiments) |
| 144 | 0.940366545 | yes | 3 / 1 | 1 | main, track:T13, track:T12 | 0.917167 | T13 gained (0.917167 -> 0.917204) |
| 145 | 0.940417499 | yes | 0 / 1 | 0 | main, track:T11, track:T10 | 0.872670 | T11 gained (0.859491 -> 0.859909) |
| 146 | 0.940457443 | yes | 0 / 1 | 0 | main, track:T13, track:T12 | 0.917204 | T13 gained (0.917204 -> 0.917210) |
| 147 | 0.940557534 | yes | 0 / 1 | 0 | main, track:T11, track:T10 | 0.872670 |  |
| 148 | 0.940610282 | yes | 0 / 1 | 0 | main, track:T13, track:T12 | 0.917210 | T11 gained (0.859909 -> 0.860288) |
| 149 | 0.940648920 | yes | 0 / 1 | 0 | main, track:T11, track:T10 | 0.872670 | T11 gained (0.860288 -> 0.860314) |
| 150 | 0.940687589 | yes | 0 / 1 | 0 | main, track:T11, track:T12 | 0.862501 | T11 gained (0.860314 -> 0.860322) |
| 151 | 0.940687589 |  | 0 / 1 | 0 | main, track:T11, track:T13 | 0.917211 | T11 gained (0.860322 -> 0.861141) |
| 152 | 0.940725209 | yes | 1 / 1 | 0 | main, track:T11, track:T10 | 0.872670 |  |
| 153 | 0.940769115 | yes | 0 / 1 | 0 | main, track:T12, track:T13 | 0.917210 | T11 gained (0.861141 -> 0.863355) |
| 154 | 0.940885904 | yes | 0 / 1 | 0 | main, track:T11, track:T10 | 0.872670 | T11 gained (0.863355 -> 0.863410) |
| 155 | 0.940989483 | yes | 0 / 1 | 0 | main, track:T11, track:T12 | 0.863410 | T12 goes on to the next rung (48 experiments): no longer rising, but best 0.862501 at 24 experiments is at or above the cohort's 50% quantile (0.862333) |
| 156 | 0.940993783 | yes | 0 / 1 | 0 | main, track:T13, track:T10 | 0.917217 | T13 gained (0.917210 -> 0.917217); T13 goes on to the next rung (48 experiments): still rising (best 0.917217 at 24 experiments) |
| 157 | 0.940997060 | yes | 0 / 1 | 0 | main, track:T13, track:T11 | 0.917218 | T13 gained (0.917217 -> 0.917218) |
| 158 | 0.940999868 | yes | 0 / 1 | 0 | main, track:T13, track:T12 | 0.917218 |  |
| 159 | 0.940999933 |  | 0 / 1 | 0 | main, track:T10, track:T11 | 0.872670 |  |
| 160 | 0.941012352 | yes | 1 / 1 | 0 | main, track:T12, track:T13 | 0.917218 | T11 gained (0.863410 -> 0.863481) |
| 161 | 0.941033359 | yes | 0 / 1 | 0 | main, track:T11, track:T10 | 0.872670 |  |

### Hills (15: 2 on the map after its first generation, 13 found since)

| Hill | Top | Found | By | Other tracks landed on it | Description |
|---|---|---|---|---|---|
| H2 | 0.941033 (p1018) | 1 | T1 (seed) | 6 | The new program uses a multi-resolution approach: it starts from a resampled grid and applies block-multiplicative perturbations, edge-preserving smoothing, and global noise, rather than the record's single-resolution co |
| H15 | 0.917218 (p0994) | 107 | T13 (build) | 0 | This program keeps the grid fixed at N=8000 (or 16000) and optimises the full vector with L-BFGS-B on a squared-parameterisation, whereas the record refines only a compact nonzero support and grows resolution via exact R |
| H9 | 0.904629 (p0605) | 52 | T6 (build) | 0 | This program abandons the spike/comb atom-position search entirely and instead seeds from a dense clipped-arcsine profile, then climbs it with Adam on a coarse (500→1000→2000→4000) multiresolution ladder with multiplicat |
| H6 | 0.879823 (p0642) | 9 | T7 (build) | 4 | This program optimises a smooth soft-max surrogate of the sup-norm (exponential penalty with β annealed 500→2000→8000) via Dinkelbach iterations on a squared-weight parametrisation, rather than perturbing along a transit |
| H10 | 0.873788 (p0391) | 60 | T2 (build) | 0 | This program runs a fixed, time-boxed pipeline (two L-BFGS passes, three Fourier-perturbation rounds, a fixed 4000-step Adam phase, then a final L-BFGS polish) rather than the record's adaptive multi-resolution surgery w |
| H12 | 0.869836 (p0644) | 100 | T10 (build) | 0 | This program abandons the record's smooth log-sum-exp surrogate and flat-top plateau objective, instead optimizing the exact inf-norm via an analytic FFT gradient with a single argmax lag. It searches by a multi-resoluti |
| H7 | 0.867731 (p0290) | 30 | T6 (build) | 0 | This program runs its structural surgery at multiple low resolutions (1500 and 3000) rather than a single n_low=2500 round, and it polishes the surgery result with L-BFGS-B every 4 accepts instead of validating only at l |
| H4 | 0.864890 (p0221) | 6 | T5 (build) | 0 | This program optimises the full autocorrelation ratio directly via Dinkelbach iterations on a square-root variable with a soft-max surrogate for the infinity norm, rather than isolating the level-transition loss and pert |
| H14 | 0.862501 (p0719) | 105 | T12 (build) | 0 | This program optimises a fixed-length N=4000 vector directly with L-BFGS on an exact analytic gradient of R, whereas the record's line builds up through multi-scale upsampling (N=8000→16000→50000) and long Adam runs. It  |
| H3 | 0.860616 (p0331) | 2 | T2 (build) | 3 | This program optimises a smooth soft-max surrogate of the sup-norm (log-sum-exp with increasing sharpness β) via L-BFGS on a squared-parameterisation w↦w², rather than hill-climbing heights directly. It adds Anderson ext |
| H5 | 0.849670 (p0170) | 9 | T6 (build) | 0 | This program seeds a hand-built spike-plus-decaying-comb shape and refines it with a Dinkelbach-style ascent that maximizes num − λ·l1·linf via random contiguous-block scaling, rather than starting from the record's symm |
| H11 | 0.848639 (p0599) | 93 | T10 (build) | 0 | This program optimises the exact-max ratio directly with analytic gradients (FFT-based convolution adjoint and argmax derivative) through a softplus reparametrisation, rather than using Dinkelbach, top-K/LSE surrogates,  |
| H13 | 0.835514 (p0670) | 104 | T11 (build) | 0 | This program optimises the exact ratio R directly via a log-sum-exp surrogate of the inf-norm with annealed beta (30 to 1e4), rather than the record's flat-top hinge penalty and beta continuation to 1e9+. It seeds from a |
| H8 | 0.723887 (p0244) | 41 | T8 (build) | 0 | This program fixes N=4000 and optimises a symmetric step function h = [u, u[::-1]] parametrised as u = w², using exact analytic gradients of R (including a tie-averaged max subgradient) rather than the record's multi-res |
| H1 | 0.666667 (p0001) | 1 | - | 0 | the starting program (Code Zero) |

Decisions every hill shared (mapped at generation 143):

- D1: Variable parametrised for the ascent (all: Optimise the nonnegative height vector h (or its sqrt w=sqrt(h)) directly, with h>=0 enforced by squaring or by bounds)
- D2: Objective for the sup-norm denominator (all: Use either the exact max lag (argmax / tie-averaged subgradient) or a log-sum-exp / p-norm surrogate with a beta ladder)
- D3: Search algorithm core (all: Gradient-based local ascent: L-BFGS-B and/or Adam on a smooth or exact-R objective, with perturb-and-repolish to escape)
- D4: Grid resolution strategy (all: Coarse-to-fine ladder (e.g. 4000 -> 8000 -> 20000 -> 50000) via interpolation/repeat upsampling, polishing at each rung)
- D5: Handling of the L1 denominator (all: Normalise h to sum 1 (or fix the L1 of f*f) and treat the ratio as scale-invariant, so the L1 term is a constant)
- D6: Initialisation / seeding (all: Seed from structured comb/teeth profiles (periodic blocks with decaying envelope) or from the provided start, then polish)
- D7: Support structure (all: Keep a mostly sparse/blocky support (exact zeros or near-zeros) with contiguous runs, i.e. a comb-like or block-constant shape)
- D8: Time allocation (all: A fixed deadline (CPU-time budget, ~90-95% of allotted) split into sequential phases (seed, ladder, polish, perturb))

### The design map (20 decisions, 909 programs placed)

| Decision | Options | Read twice: agreement | Importance (last fit) |
|---|---|---|---|
| A37: Every program so far: The gradient of the exact ratio is derived analytically and passed t | as every program so far: The gradient of; Finite-difference gradients; Automatic differentiation; Derivative-free local search; recompute or incrementally update the fu ... | 96% of 101 (kappa 0.94) | 4% |
| A42: Is the support (set of nonzero cells/intervals) treated as fixed/dense or explicitly optim | Dense or post-hoc compacted support; Free interval boundaries optimised; Continuous parametric bump shape; Forced even symmetry; No symmetry enforced ... | 100% of 73 (kappa 1.00) | 3% |
| A40: How is the final solution selected/returned from the search (best-R iterate vs. a distinct | Best-R plus alternative construction; Return final iterate; Best of last k iterates; Average of top candidates; Best of archive plus polished buffer ... | 89% of 90 (kappa 0.74) | 2% |
| A5: How does the search accept worse solutions or escape a local optimum? | Simulated annealing acceptance; Random kicks on stall; Population diversity / recombination; Noise plus re-polish; Targeted structured perturbations ... | 84% of 102 (kappa 0.81) | 1% |
| A4: Which moves or update steps change a solution? | Projected gradient ascent; Structural run edits; Scattered single-cell mutations; Global parametric transforms; Quasi-Newton smooth surrogate ... | 84% of 102 (kappa 0.80) | 1% |
| A2: How is the first solution built? | Return start or constant; Perturb or optimize start; Construct from scratch; Smooth analytic bump seed; Random multi-start vectors ... | 69% of 102 (kappa 0.56) | - |
| A6: How is the problem's scale handled (all at once, coarse to fine, in parts)? | Multiscale budget allocation; Stochastic restarts; Line search / trust region; Parallel island population; Coarse-to-fine grid ladder ... | 92% of 102 (kappa 0.88) | - |
| A10: How is the maximum of f*f (the L-infinity norm) handled in the optimised objective | Exact max subgradient; Annealed smooth max; Fixed mild smooth max; Top-lag softmax or p-norm; Dinkelbach minimax reformulation ... | 80% of 102 (kappa 0.70) | - |
| A32: Which local optimizer performs the final polish (gradient quasi-Newton vs derivative-free  | L-BFGS-B quasi-Newton polish; Derivative-free coordinate/pattern searc; Structure-exploiting second-order (Gauss; Projected gradient / Frank-Wolfe simplex; Subpixel shift sweep ... | 98% of 57 (kappa 0.66) | - |
| A36: Every program so far: Nonnegativity is enforced by a smooth reparametrisation h = w^2 (or  | Smooth reparametrisation w^2/softplus; Direct optimise with clip/project; Log-barrier / interior-point penalty; Projected gradient / mirror descent; Explicit nonnegativity penalty ... | 100% of 102 (kappa 1.00) | - |
| A45: Every program so far: Every program fixes the support centered in the array and never opti | as every program so far: Every program f; Optimize a continuous shift; Align the max of f*f to a knot; Randomize offsets between restarts; as every program so far: No program impo ... | 100% of 17 (kappa 1.00) | - |
| A46: Every program so far: Every program fixes the final array length N before the final optimi | Fixed N before optimization; Jointly optimize N with heights; Nested variable-depth grids; Free knot count parameter; Upsample to finer grid ... | 92% of 102 (kappa 0.80) | - |
| A48: Every program so far: No program explicitly parameterizes the flat top/plateau of f or f*f | Emergent plateau, no explicit parameteri; Explicit flat-top plus tails; Force equal top-k knots; Constrain plateau width directly; Comb/ramp/spike structured profiles ... | 93% of 99 (kappa 0.89) | - |
| A49: Every program so far: No program regularizes roughness of h in the final objective; smooth | No final roughness penalty; Total-variation penalty on h; Spline-knot representation of h; Monotone tails on h; Learned or spectral surrogate ... | 97% of 102 (kappa 0.93) | - |
| A50: Every program so far: All optimize a dense per-cell height vector; no low-dimensional para | as every program so far: All optimize a ; Represent h by cubic-spline control poin; Use Fourier/cosine coefficients as the o; Use a Gaussian-mixture or piecewise-line | 100% of 6 (kappa 1.00) | - |
| A51: Every program so far: All allow h to be asymmetric; none imposes even symmetry or optimize | as every program so far: All allow h to ; Enforce h[i]=h[N-1-i] and optimize half ; Optimize full array but symmetrize every; Alternate symmetric and asymmetric optim | 100% of 6 (kappa 1.00) | - |
| A52: How is the final array length N chosen relative to the search (fixed up front vs. grown/re | Grows N via _refine_local resampling/ups; Fixed N; no length-growth refinement | 67% of 3 (kappa 0.00) | - |
| A53: How is the array length N (resolution) chosen and refined during the search? | Fixed N throughout; no upsampling ladder; Upsampling ladder (7999→11999→15999→1999 | 100% of 3 (kappa 1.00) | - |
| A54: How is the array length N chosen and varied during the search (fixed vs. grown/shrunk acro | Grows N across phases (upsampling/refine; Keeps N fixed throughout | 100% of 1 (kappa 1.00) | - |
| A55: Every program so far: The overall scale of h is left free during optimization; no constrai | as every program so far: The overall sca; Constrain sum(h)=1 throughout the search; Constrain max(h)=1 throughout the search; Optimize an explicit scale variable sepa | 100% of 1 (kappa 1.00) | - |

Interacting decisions in the last fit: ('A48', 'A52')

### Explorations chosen from the map (12: 11 builds, 1 flips)

| Track | Kind | Opened | Target | Built (read back) | Experiments | Best | Race | Hill |
|---|---|---|---|---|---|---|---|---|
| T2 | build | 1 | A11 -> L-BFGS with Anderson accelerat | 1/1 | 49 | 0.876175 | finished at 48 | on H2 |
| T3 | flip | 1 | A9 -> Alternating projection: push f | 1/1 | 3 | 0.723900 | paused at 6 | on H3 |
| T4 | build | 2 | A13 -> Average-pool a finer construct | 1/1 | 48 | 0.859588 | finished at 48 | top H3 |
| T5 | build | 3 | A16 -> Perturb along the gradient of  | 1/1 | 32 | 0.864890 | paused at 32 | founder H4 |
| T6 | build | 4 | A14 -> Spike plus smaller comb peaks | 1/1 | 77 | 0.904629 | paused at 48 | founder H9 |
| T7 | build | 7 | A10 -> Fixed mild smooth max | 1/1 | 51 | 0.879823 | finished at 48 | founder H6 |
| T8 | build | 39 | A19 -> Force even symmetry of h | 1/1 | 6 | 0.723887 | paused at 6 | founder H8 |
| T9 | build | 53 | A20 -> Use no regularization | - | 83 | 0.941033 | running at 12 | top H2 |
| T10 | build | 90 | A10 -> Level-transition lags | 1/1 | 34 | 0.872670 | running at 24 | on H6 |
| T11 | build | 101 | A33 -> Min-max plateau-gap surrogate | 1/1 | 35 | 0.863481 | running at 24 | on H6 |
| T12 | build | 102 | A14 -> Regular small-big-small triple | 0/1 | 26 | 0.862501 | running at 24 | founder H14 |
| T13 | build | 104 | A20 -> Add an L2 penalty on heights | 0/1 | 27 | 0.917218 | running at 24 | founder H15 |

### Discoveries (programs at the same design that scored too differently: what differs?)

- generation 36, p0196 vs p0195: How is the final returned array selected from the search trajectory (best-R seen vs final iterate, and at which resolution)? (A27, new)
- generation 92, p0020 vs p0044: How is the search's exploration budget allocated between local refinement and global restructuring (i.e., what is the outer-loop move that generates new trial shapes)? (A38, new)
- generation 96, p0566 vs p0565: How is the final solution selected/returned from the search (best-R iterate vs. a distinct alternative construction)? (A40, new)
- generation 108, p0017 vs p0078: How does the search generate new candidate solutions to escape local optima (what is the perturbation/restart mechanism)? (A41, new)
- generation 152, p0736 vs p0735: How is the final array length N chosen relative to the search (fixed up front vs. grown/refined during the search)? (A52, new)
- generation 156, p0259 vs p0336: How is the array length N (resolution) chosen and refined during the search? (A53, new)
- generation 160, p0875 vs p0874: How is the array length N chosen and varied during the search (fixed vs. grown/shrunk across phases)? (A54, new)
