"""Game-design statistics from strong self-play.

    .venv/bin/python analyze.py models/nchoro/latest.pt
    .venv/bin/python analyze.py models/nchoro/latest.pt models/single/latest.pt --games 400

The AI plays itself at full strength, with random first moves (--random-opening) so
games differ. Reports first-player advantage, draws, game length, relays and how games end.
"""

import argparse
import os
import random
import statistics
from multiprocessing import Pool

import numpy as np

from nchoro.engine import State, legal_moves, play
from nchoro.mcts import MCTS
from nchoro.net import load_numpy_net


def worker(task):
    path, games, sims, opening, seed = task
    net, rules, _ = load_numpy_net(path)
    rng = random.Random(seed)
    mcts = MCTS(net, sims=sims, rng=np.random.default_rng(seed))
    out = []
    for _ in range(games):
        s = State.initial(rules)
        laps, caps, cutoffs = [], [0, 0], 0
        while not s.over:
            if s.move_count < opening:
                m = rng.choice(legal_moves(s))
            else:
                m = mcts.choose(mcts.search(s))
            mover = s.to_move
            trace = []
            s = play(s, m, trace)
            laps.append(sum(e["type"] == "pickup" for e in trace))
            caps[mover] += sum(e["type"] == "capture" for e in trace)
            cutoffs += any(e["type"] == "lap_limit" for e in trace)
        out.append({"winner": s.winner, "length": s.move_count, "scores": s.scores,
                    "laps": statistics.mean(laps), "max_laps": max(laps), "captures": caps,
                    "cutoffs": cutoffs, "end": "move limit" if s.end_reason == "move limit reached" else "seeds ran out"})
    return out


def report(path, games, sims, opening, workers):
    _, rules, meta = load_numpy_net(path)
    per = [games // workers + (1 if i < games % workers else 0) for i in range(workers)]
    tasks = [(path, g, sims, opening, 1000 + i) for i, g in enumerate(per) if g]
    with Pool(len(tasks)) as pool:
        res = [r for chunk in pool.map(worker, tasks) for r in chunk]
    n = len(res)
    pct = lambda k: sum(k(r) for r in res) / n
    margin = [r["scores"][0] - r["scores"][1] for r in res]
    print(f"\n== {path}  (iteration {meta.get('iteration', '?')})")
    print(f"   rules: {rules.describe()}")
    print(f"   {n} games, {sims} sims/move, first {opening} moves random")
    print(f"   Player 1 wins {pct(lambda r: r['winner'] == 0):6.1%}")
    print(f"   Player 2 wins {pct(lambda r: r['winner'] == 1):6.1%}")
    print(f"   Draws         {pct(lambda r: r['winner'] == -1):6.1%}")
    print(f"   Avg score P1-P2: {statistics.mean(margin):+.1f} seeds (spread ±{statistics.pstdev(margin):.1f})")
    print(f"   Game length: avg {statistics.mean(r['length'] for r in res):.0f} moves, "
          f"max {max(r['length'] for r in res)}")
    print(f"   Laps per turn: avg {statistics.mean(r['laps'] for r in res):.2f}, "
          f"longest {max(r['max_laps'] for r in res)}")
    print(f"   Captures per game: P1 {statistics.mean(r['captures'][0] for r in res):.1f}, "
          f"P2 {statistics.mean(r['captures'][1] for r in res):.1f}")
    print(f"   Ended by seeds running out {pct(lambda r: r['end'] == 'seeds ran out'):.0%}, "
          f"by move limit {pct(lambda r: r['end'] == 'move limit'):.0%}; "
          f"endless relays cut off: {sum(r['cutoffs'] for r in res)}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("checkpoints", nargs="+")
    p.add_argument("--games", type=int, default=200)
    p.add_argument("--sims", type=int, default=200)
    p.add_argument("--random-opening", type=int, default=2, help="number of random opening moves for variety")
    p.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = p.parse_args()
    for path in a.checkpoints:
        report(path, a.games, a.sims, a.random_opening, a.workers)


if __name__ == "__main__":
    main()
