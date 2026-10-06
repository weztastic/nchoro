"""Long training run with hourly matches against a fixed baseline.

    caffeinate -i .venv/bin/python overnight.py --hours 3

Copies the baseline run (default models/nchoro) to models/<run>, keeps training there, and at
every whole hour plays --games matches of the newest model against the baseline. The baseline
folder is never written to. Results go to models/<run>/matches.csv and overnight.log.
"""

import argparse
import csv
import os
import random
import shutil
import subprocess
import sys
import time
from multiprocessing import Pool

import numpy as np

from nchoro.engine import State, legal_moves, play
from nchoro.mcts import MCTS
from nchoro.net import load_numpy_net


def match_game(task):
    """One game between two checkpoints after a shared random opening. Returns (new_score, old_score)."""
    new_path, old_path, new_side, opening_seed, opening_moves, sims, seed = task
    nets = {}
    for side, path in ((new_side, new_path), (1 - new_side, old_path)):
        net, rules, _ = load_numpy_net(path)
        nets[side] = MCTS(net, sims=sims, rng=np.random.default_rng(seed + side))
    rng = random.Random(opening_seed)
    s = State.initial(rules)
    while not s.over:
        if s.move_count < opening_moves:
            m = rng.choice(legal_moves(s))
        else:
            mcts = nets[s.to_move]
            m = mcts.choose(mcts.search(s))
        s = play(s, m)
    return s.scores[new_side], s.scores[1 - new_side], s.move_count


def run_match(new_path, old_path, games, sims, opening_moves, hour):
    tasks = []
    for g in range(games):
        opening = 1000 * hour + g // 2          # each opening is played twice, colours swapped
        tasks.append((new_path, old_path, g % 2, opening, opening_moves, sims, 7919 * hour + g))
    with Pool(min(games, os.cpu_count() or 2)) as pool:
        return pool.map(match_game, tasks)


def log(msg, path):
    line = time.strftime("%H:%M ") + msg
    print(line, flush=True)
    with open(path, "a") as f:
        f.write(line + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--hours", type=int, default=3)
    p.add_argument("--baseline-run", default="nchoro")
    p.add_argument("--run", default="nchoro_long")
    p.add_argument("--games", type=int, default=10, help="matches per hour")
    p.add_argument("--match-sims", type=int, default=200)
    p.add_argument("--opening", type=int, default=2, help="random opening moves before both AIs play")
    p.add_argument("--train-sims", type=int, default=400)
    p.add_argument("--train-games", type=int, default=384)
    p.add_argument("--temp-moves", type=int, default=6, help="random (exploratory) moves at the start of each training game")
    a = p.parse_args()

    base_dir, out = os.path.join("models", a.baseline_run), os.path.join("models", a.run)
    if os.path.exists(out):
        sys.exit(f"{out} already exists; pick another --run")
    os.makedirs(out)
    for f in ("latest.pt", "rules.json", "log.csv"):
        shutil.copy(os.path.join(base_dir, f), os.path.join(out, f))
    baseline = os.path.join(out, "baseline.pt")
    shutil.copy(os.path.join(base_dir, "latest.pt"), baseline)
    logf = os.path.join(out, "overnight.log")

    train = subprocess.Popen(
        [sys.executable, "train.py", "--run", a.run, "--resume", "--iterations", "100000",
         "--sims", str(a.train_sims), "--games", str(a.train_games), "--eval-games", "20",
         "--temp-moves", str(a.temp_moves),
         "--workers", str(max(1, (os.cpu_count() or 2) - 2))],
        stdout=open(os.path.join(out, "train.log"), "w"), stderr=subprocess.STDOUT)
    log(f"training started (pid {train.pid}, {a.temp_moves} random moves per game); "
        f"matches every hour for {a.hours}h", logf)

    with open(os.path.join(out, "matches.csv"), "w", newline="") as f:
        csv.writer(f).writerow(["hour", "iteration", "new_wins", "draws", "old_wins", "avg_margin", "avg_length"])

    start = time.time()
    try:
        for hour in range(1, a.hours + 1):
            time.sleep(max(0, start + hour * 3600 - time.time()))
            snap = os.path.join(out, f"hour_{hour}.pt")
            shutil.copy(os.path.join(out, "latest.pt"), snap)
            _, _, meta = load_numpy_net(snap)
            res = run_match(snap, baseline, a.games, a.match_sims, a.opening, hour)
            w = sum(n > o for n, o, _ in res)
            d = sum(n == o for n, o, _ in res)
            l = len(res) - w - d
            margin = sum(n - o for n, o, _ in res) / len(res)
            length = sum(m for _, _, m in res) / len(res)
            with open(os.path.join(out, "matches.csv"), "a", newline="") as f:
                csv.writer(f).writerow([hour, meta.get("iteration"), w, d, l, round(margin, 2), round(length, 1)])
            log(f"hour {hour} (iteration {meta.get('iteration')}): new {w} wins, {d} draws, "
                f"{l} losses vs published; avg margin {margin:+.1f} seeds", logf)
    finally:
        train.terminate()
        train.wait()
        log("training stopped", logf)

    final = os.path.join(out, f"hour_{a.hours}.pt")
    with open(os.path.join(out, "analysis_final.txt"), "w") as f:
        subprocess.run([sys.executable, "analyze.py", final, baseline, "--games", "300"], stdout=f, check=True)
    log("final analysis written", logf)


if __name__ == "__main__":
    main()
