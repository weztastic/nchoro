# Nchoro Amarachi style rules (as implemented)

Defaults in `nchoro/engine.py` (`Rules()`). Items marked ⚠ are provisional — see `OPEN_QUESTIONS.md`.

## Setup
1. Board: 2 rows of 6 pits. Each player owns the row nearest to them.
2. 4 seeds in every pit (48 in total).

## Your turn
3. **You choose which pit to start from:** any non-empty pit on your own side. Take all its seeds and sow them counter-clockwise, one per pit.
4. On a full lap (12 or more seeds), the starting pit gets a seed too — nothing is skipped.
5. **Instant capture:** whenever a seed you sow (other than the last) brings a pit to **exactly 4**, that pit's **owner** takes the 4 seeds immediately — on your side that's you, on your opponent's side it's them. Sowing then carries on; the pit is now empty.
6. Look at where the **last seed of the lap** landed:
   - pit (yours **or** your opponent's) now holds **exactly 4** → **you** capture those 4, turn **ends**;
   - pit was empty (now 1) → turn **ends**, no capture;
   - otherwise (now 2, 3, 5 or more) → pick up all its seeds and keep sowing from the next pit (**relay**).

## Passing
7. If the player whose turn it is has no seeds on their side, they can't play: the **other player plays again** (for as long as that side stays empty).
8. ⚠ No obligation to feed an opponent whose row is empty.

## End of game
9. At the end of a turn, if **4 or fewer seeds** are left on the board, the game ends.
10. Each player takes the seeds remaining on their own side.
11. Most seeds wins. 24–24 is a draw.

## Safety limits (for the computer, not traditional)
12. ⚠ A turn that relays for 200 laps is cut off and simply ends. Endless relays are proven to exist — see `OPEN_QUESTIONS.md`.
13. A game that reaches 300 moves (passes not counted) ends; seeds on the board go to whoever's side they're on.

## Switchable options (for experiments)

| Option | Default | Alternatives |
|---|---|---|
| `sowing` | `relay` | `single` (one lap, then the turn ends) |
| `capture_counts` | `(4,)` | any set, e.g. `(2, 3)` for Oware |
| `capture_side` | `both` | `opponent`, `own` |
| `capture_chain` | off | on: also capture preceding pits holding a capture count |
| `instant_capture` | on | off: pits passing through 4 stay on the board |
| `skip_origin` | off | on: a full lap skips the pit it started from |
| `sweep_own` | off | on: at turn end, also take your own pits you changed to 4 |
| `pits` / `seeds` | 6 / 4 | anything |
| `feeding` | off | on |
| `end_at` | 4 | game ends with this many seeds or fewer left |
| `max_laps` / `max_moves` | 200 / 300 | anything |
