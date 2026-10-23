# Helix v7: what exploration did

## v7-s1

- Generations 191-223: best 0.941229688 -> 0.941243010 (p0502, track T11); the main track now: L7.
- Exploration levels: level 0: 4 generations, level 1: 2 generations, level 2: 27 generations.
- Planned experiments by slot: main 43, track 36, revive 7, backtrack 7, bold 6.

### Records (2)

| Gen | Best | Program | Its role | Its slot | Track |
|---|---|---|---|---|---|
| 191 | 0.941240825 | p0297 | deep | main | L7 |
| 192 | 0.941242923 | p0302 | deep | main | L7 |

### Side tracks opened (20)

| Track | Kind | Opened | From | Experiments | Its best | Last gain |
|---|---|---|---|---|---|---|
| T11 | revive F190 | 195 | p0314 | 27 | 0.941243 (p0321) | 195 |
| T12 | backtrack | 197 | p0218 | 3 | 0.941184 (p0341) | 198 |
| T13 | bold | 197 | p0001 | 3 | 0.725574 (p0349) | 199 |
| T14 | revive F5 | 198 | p0336 | 2 | 0.941243 (p0342) | 198 |
| T15 | backtrack | 200 | p0204 | 2 | 0.941100 (p0355) | 200 |
| T16 | bold | 202 | p0001 | 4 | 0.880990 (p0390) | 205 |
| T17 | revive F222 | 203 | p0351 | 2 | 0.941243 (p0373) | 203 |
| T18 | backtrack | 204 | p0196 | 3 | 0.940995 (p0389) | 205 |
| T19 | bold | 206 | p0001 | 2 | - | 206 |
| T20 | revive F289 | 208 | p0405 | 2 | 0.941243 (p0411) | 208 |
| T21 | backtrack | 210 | p0211 | 4 | 0.940456 (p0443) | 213 |
| T22 | bold | 210 | p0001 | 3 | 0.863873 (p0432) | 211 |
| T23 | revive F293 | 212 | p0405 | 2 | 0.941243 (p0436) | 212 |
| T24 | backtrack | 214 | p0209 | 3 | 0.941154 (p0457) | 215 |
| T25 | bold | 215 | p0001 | 3 | 0.842660 (p0462) | 216 |
| T26 | revive F361 | 216 | p0405 | 3 | 0.941243 (p0468) | 217 |
| T27 | backtrack | 218 | p0297 | 2 | 0.941241 (p0476) | 218 |
| T28 | bold | 220 | p0001 | 4 | 0.878554 (p0501) | 222 |
| T29 | revive F50 | 220 | p0478 | 2 | 0.941243 (p0487) | 220 |
| T30 | backtrack | 222 | p0234 | 2 | 0.941232 (p0503) | 222 |

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
| 204 | 0.941243010 |  | 11 / 1 | 2 | main, track:T17, backtrack | 0.941243 | T17 paused (no gain on its own best); T18 opened (a backtrack to p0196) |
| 205 | 0.941243010 |  | 12 / 1 | 2 | main, track:T18, track:T16 | 0.940995 | T16 gained (0.770635 -> 0.880990); T18 gained (0.940993 -> 0.940995) |
| 206 | 0.941243010 |  | 13 / 1 | 2 | main, track:T16, bold | 0.880990 | L3 gained (0.909017 -> 0.909020); T16 paused (no gain on its own best); T19 opened (a bold experiment from p0001) |
| 207 | 0.941243010 |  | 14 / 1 | 2 | main, track:T19, track:T18 | 0.940995 | T18 paused (no gain on its own best); T19 paused (no gain on its own best) |
| 208 | 0.941243010 |  | 15 / 1 | 2 | main, track:L3, revive | 0.941243 | L3 gained (0.909020 -> 0.909093); T20 opened (a revive of F289 on p0405) |
| 209 | 0.941243010 |  | 16 / 1 | 2 | main, track:T20, track:L3 | 0.941243 | L3 paused (no gain on its own best); T20 paused (no gain on its own best) |
| 210 | 0.941243010 |  | 17 / 1 | 2 | main, backtrack, bold | 0.940434 | T21 opened (a backtrack to p0211); T22 opened (a bold experiment from p0001) |
| 211 | 0.941243010 |  | 18 / 1 | 2 | main, track:T21, track:T22 | 0.940450 | T21 gained (0.940434 -> 0.940450); T22 gained (0.666667 -> 0.863873) |
| 212 | 0.941243010 |  | 19 / 1 | 2 | main, track:T22, revive | 0.941243 | T22 paused (no gain on its own best); T23 opened (a revive of F293 on p0405) |
| 213 | 0.941243010 |  | 20 / 1 | 2 | main, track:T23, track:T21 | 0.941243 | T21 gained (0.940450 -> 0.940456); T23 paused (no gain on its own best) |
| 214 | 0.941243010 |  | 21 / 1 | 2 | main, track:T21, backtrack | 0.941146 | T21 paused (no gain on its own best); T24 opened (a backtrack to p0209) |
| 215 | 0.941243010 |  | 22 / 1 | 2 | main, track:T24, bold | 0.941154 | T24 gained (0.941146 -> 0.941154); T25 opened (a bold experiment from p0001) |
| 216 | 0.941243010 |  | 23 / 1 | 2 | main, track:T25, revive | 0.842660 | T26 opened (a revive of F361 on p0405) |
| 217 | 0.941243010 |  | 24 / 1 | 2 | main, track:T25, track:T26 | 0.941243 | T25 paused (no gain on its own best) |
| 218 | 0.941243010 |  | 25 / 1 | 2 | main, track:T26, backtrack | 0.941243 | T26 paused (no gain on its own best); T27 opened (a backtrack to p0297) |
| 219 | 0.941243010 |  | 26 / 1 | 2 | main, track:T27, track:T24 | 0.941241 | T24 paused (no gain on its own best); T27 paused (no gain on its own best) |
| 220 | 0.941243010 |  | 27 / 1 | 2 | main, bold, revive | 0.941243 | T28 opened (a bold experiment from p0001); T29 opened (a revive of F50 on p0478) |
| 221 | 0.941243010 |  | 28 / 1 | 2 | main, track:T29, track:T28 | 0.941243 | T28 gained (0.783587 -> 0.878080); T29 paused (no gain on its own best) |
| 222 | 0.941243010 |  | 29 / 1 | 2 | main, track:T28, backtrack | 0.941232 | T28 gained (0.878080 -> 0.878554); T30 opened (a backtrack to p0234) |
| 223 | 0.941243010 |  | 30 / 1 | 2 | main, track:T30, track:T28 | 0.941232 | T28 paused (no gain on its own best); T30 paused (no gain on its own best) |
