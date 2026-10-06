# Overnight training — 4–5 Oct 2026

**Question:** how much stronger does the AI get with about 3 more hours of self-play?
**Short answer:** not measurably. It may even have got slightly worse. The online page was not changed.

## Setup
- Started from the published model (iteration 60, about 10 minutes of training) under the current rules
  (instant capture by the owner, the last seed's 4 goes to the mover, no skip, game ends at 4 or fewer seeds).
- Trained 23:28–02:28: iterations 61 → 601, 384 games per iteration, 400 simulations per move, 6 random moves per game.
  (A first attempt with 20 random moves ran 22:56–23:26 and was stopped; it is kept in `models/nchoro_long_t20/`.)
- At every whole hour: 10 games, newest model vs published model, 200 simulations each,
  5 random 2-move openings, each played twice with colours swapped.

## Hourly matches (new vs published)

| Hour | Iteration | New wins | Draws | Published wins | Avg margin (seeds) |
|---|---|---|---|---|---|
| 1 | 285 | 5 | 1 | 4 | +0.2 |
| 2 | 445 | 5 | 2 | 3 | −3.4 |
| 3 | 601 | 4 | 2 | 4 | −1.4 |
| **Total** | | **14** | **5** | **11** | **−1.5** |

Over 30 games this is a tie. For 10 games, a real improvement would look like 8–2 or better; nothing came close.

Against the fixed test opponent (minimax looking 3 moves ahead, 20 games per iteration), the score drifted
**down** from about 90% to 65–82% over the night. That is noisy, but it points the same way: no progress, possibly a small decline.

## Why it stalled
The training games became completely one-sided: **player 2 won 96–99% of them all night**. Even with only
6 random moves, any imprecision in the early game seems to hand the game to player 2. The network learned
that almost perfectly (its value error fell to 0.007), and it now judges the opening position as lost for player 1.

When every move looks equally lost, the network stops telling them apart. You can see this in the opening:

| | Player 1's opening preferences (a–f) | Player 1 win estimate from the start |
|---|---|---|
| Published (10 min) | a 53%, b 19%, d 15%, e 6%, c 4%, f 3% | 4% |
| After 3 hours | a 18%, b 16%, c 18%, d 16%, e 16%, f 17% (no preference) | 0% |

So the extra hours mostly taught the AI "player 1 loses", not how to play better.

## What it says about the game
- **Strong play from varied openings looks even.** With 2 random opening moves and then strong play from both sides, the
  final model splits 41% / 41% / 18% draws over 300 games (the published model: 39% / 33% / 28%).
- **Imprecise play strongly favours player 2.** With a little randomness in the first few moves, player 2 wins almost every game.
- **The AI believes the starting position is lost for player 1.** If that is right, perfect play would favour player 2.
  This is not proven: the AI's own results from random openings contradict it. Treat it as a warning sign worth checking
  with human testers. Each tester record says who moved first.
- Endless relays did not occur in any of the 600 analysis games. 5% of the published model's games hit the 300-move limit;
  the new model's games hit it 0% of the time.

## Recommendations
1. **Keep the online version as it is.** The overnight model is not better.
2. **Before training longer, change the learning target.** Today the network only learns win/draw/loss. When one side
   almost always wins, that gives no signal. Learning the **final score margin** as well ("lose by 2" beats "lose by 12")
   is the standard fix for this. It is a small change to `train.py` and `selfplay.py`.
3. **Use bigger test matches** (40+ games) when comparing models, so small differences can be seen.
4. **For the rules:** if testers also find that moving second is a big advantage, consider a balancing rule, for example
   the loser of the previous game starts, or player 1's first turn is restricted. The AI can test these variants.

Files: `models/nchoro_long/` (hour_1–3 checkpoints, `matches.csv`, `train.log`, `analysis_final.txt`).
