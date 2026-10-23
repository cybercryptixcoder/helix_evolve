# Helix v7: what exploration did

## v7-s1

- Generations 191-203: best 0.941229688 -> 0.941243010 (p0372, track T11); the main track now: L7.
- Exploration levels: level 0: 4 generations, level 1: 2 generations, level 2: 7 generations.
- Planned experiments by slot: main 23, track 9, revive 3, backtrack 2, bold 2.

### Records (2)

| Gen | Best | Program | Its role | Its slot | Track |
|---|---|---|---|---|---|
| 191 | 0.941240825 | p0297 | deep | main | L7 |
| 192 | 0.941242923 | p0302 | deep | main | L7 |

### Side tracks opened (7)

| Track | Kind | Opened | From | Experiments | Its best | Last gain |
|---|---|---|---|---|---|---|
| T11 | revive F190 | 195 | p0314 | 9 | 0.941243 (p0321) | 195 |
| T12 | backtrack | 197 | p0218 | 3 | 0.941184 (p0341) | 198 |
| T13 | bold | 197 | p0001 | 3 | 0.725574 (p0349) | 199 |
| T14 | revive F5 | 198 | p0336 | 2 | 0.941243 (p0342) | 198 |
| T15 | backtrack | 200 | p0204 | 2 | 0.941100 (p0355) | 200 |
| T16 | bold | 202 | p0001 | 2 | 0.770635 (p0377) | 203 |
| T17 | revive F222 | 203 | p0351 | 1 | 0.941243 (p0373) | 203 |

### Generation by generation

| Gen | Best | Record | Stall / typical | Level | Slots | Explorations' best | Track events |
|---|---|---|---|---|---|---|---|
| 191 | 0.941240825 | yes | 0 / 1 | 0 | main, main, main |  |  |
| 192 | 0.941242923 | yes | 0 / 1 | 0 | main, main, main |  |  |
| 193 | 0.941242924 |  | 0 / 1 | 0 | main, main, main |  |  |
| 194 | 0.941242954 |  | 1 / 1 | 0 | main, main, main |  |  |
| 195 | 0.941242971 |  | 2 / 1 | 1 | main, main, revive | 0.941243 | T11 opened (a revive of F190 on p0314) |
| 196 | 0.941242982 |  | 3 / 1 | 1 | main, main, track:T11 | 0.941243 | T11 paused (no gain on its own best) |
| 197 | 0.941242985 |  | 4 / 1 | 2 | main, backtrack, bold | 0.941172 | T12 opened (a backtrack to p0218); T13 opened (a bold experiment from p0001) |
| 198 | 0.941242992 |  | 5 / 1 | 2 | main, track:T12, revive | 0.941243 | T12 gained (0.941172 -> 0.941184); T14 opened (a revive of F5 on p0336) |
| 199 | 0.941243007 |  | 6 / 1 | 2 | main, track:T14, track:T13 | 0.941243 | L9 gained (0.756045 -> 0.876953); T14 paused (no gain on its own best) |
| 200 | 0.941243007 |  | 7 / 1 | 2 | main, track:T13, backtrack | 0.941100 | L9 gained (0.876953 -> 0.881781); T13 paused (no gain on its own best); T15 opened (a backtrack to p0204) |
| 201 | 0.941243007 |  | 8 / 1 | 2 | main, track:T15, track:T12 | 0.941184 | T12 paused (no gain on its own best); T15 paused (no gain on its own best) |
| 202 | 0.941243007 |  | 9 / 1 | 2 | main, track:L9, bold | 0.881781 | L9 paused (no gain on its own best); T16 opened (a bold experiment from p0001) |
| 203 | 0.941243010 |  | 10 / 1 | 2 | main, track:T16, revive | 0.941243 | T17 opened (a revive of F222 on p0351) |
