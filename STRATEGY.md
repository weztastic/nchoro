# Nchoro Amarachi style: strategy guide

Based on 300 games the published AI (iteration 60) played against itself under the current rules
(instant capture by the owner, the last seed's 4 goes to the mover, no skip, game ends at 4 or fewer seeds).
Results: 101 player-1 wins, 131 player-2 wins, 68 draws. At about 9,700 real decisions, the move the AI chose
was compared with the moves it rejected.

These are **tendencies of a fairly strong AI, not proven perfect play**. The AI had about 10 minutes of training
and has known blind spots (see `OVERNIGHT_SUMMARY.md`). Tester games are the best check on whether these tips hold for people.

## For both players

1. **Count before you sow.** Every move is fully predictable, including where a relay ends. The AI consistently
   prefers moves that relay further (about one extra lap compared with the alternatives), aiming for a last seed
   that makes exactly 4. This is the main skill in the game.
2. **Don't hand your opponent 4s.** Before you sow, check whether your seeds pass through an opponent's pit
   holding 3. That pit becomes 4, and your opponent takes it during your turn. When a safe alternative exists,
   the AI avoids such gifts about 60–65% of the time. It only accepts a gift when the move gains more elsewhere.
3. **Keep your own 3s as traps.** A pit on your side holding 3 pays you 4 the moment your opponent sows into it.
   The AI rarely plays from a 3-seed pit (13–17% of the times it could), far less often than from pits of other sizes (25–50%).
4. **Starve your opponent.** The AI's chosen moves leave the opponent about 0.7 more empty pits and fewer seeds
   than the alternatives would, and keep its own side fuller. When your opponent's side is empty, they pass and
   you play again.
5. **Capture usually, but not always.** The AI captures when it can 60–74% of the time. It sometimes passes up a
   capture for a better position.

## As player 1: play patiently and accurately

- **Mistakes cost player 1 more.** Small inaccuracies early on hand the game to player 2. In training games
  with a little randomness, player 2 won over 90%.
- **Build up before you grab.** Player 1's AI takes available captures less often (60%) and puts more weight on
  keeping its seeds and starving player 2.
- **Favourite pit: d** (chosen 59% of the times it's available). It rarely plays **f** (7%).
- **Always take the extra turn** when you can empty player 2's side. The AI did so every time (30 of 30).

## As player 2: punish mistakes

- **Take your chances.** Player 2's AI captures more readily (74%) and almost always picks the move with the
  best immediate result (94%).
- **Let player 1 make the mistakes.** Your advantage comes from player 1's inaccuracies, so take what they hand you.
- **Favourite pit: c** (chosen 60% of the times it's available). It rarely plays **e** or **f**.

## What doesn't work

No simple board pattern predicted the winner. Early in the game (moves 6–16), eventual winners and losers had
almost the same number of seeds, empty pits and 3s on their side. The only clear difference was the score so far.
There is no easy formula: **careful counting turn by turn beats any general rule**.

## Raw numbers

| | Player 1 | Player 2 |
|---|---|---|
| Picks the best immediate net capture | 88% | 94% |
| Captures when a capture is available | 60% | 74% |
| Avoids gifting when a no-gift move exists | 59% | 65% |
| Extra laps vs. the average alternative | +1.0 | +1.2 |
| Extra empty opponent pits vs. alternative | +0.8 | +0.7 |
| Most-played pit (share when available) | d (59%) | c (60%) |
| Least-played pit | f (7%) | e (12%), f (14%) |
| Plays a pit holding exactly 3 | 13% | 17% |

Analysis script: kept in the session scratchpad. Ask Claude to rerun it after any rule change or retraining.
