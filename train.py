"""AlphaZero self-play training for Nchoro Amarachi style.

    .venv/bin/python train.py                       # default rules, run name "nchoro"
    .venv/bin/python train.py --run quick --iterations 5 --games 48 --sims 50
    .venv/bin/python train.py --run single --sowing single   # train a rule variant
    .venv/bin/python train.py --run nchoro --resume  # continue where it stopped

Each iteration: self-play games -> train the network on them -> test against baselines.
Checkpoints and a log.csv go to models/<run>/.
"""

import argparse
import csv
import json
import os
import time
from multiprocessing import Pool

import numpy as np
import torch
import torch.nn.functional as F

from nchoro.cli import add_rules_args, rules_from_args
from nchoro.engine import Rules
from nchoro.net import build_torch_net, load_checkpoint, save_checkpoint, torch_to_numpy
from nchoro.selfplay import eval_worker, selfplay_worker


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", default="nchoro", help="name of the run (folder under models/)")
    p.add_argument("--iterations", type=int, default=40)
    p.add_argument("--games", type=int, default=192, help="self-play games per iteration")
    p.add_argument("--sims", type=int, default=100, help="MCTS simulations per move in self-play")
    p.add_argument("--temp-moves", type=int, default=20, help="explore (sample moves) for the first N moves")
    p.add_argument("--window", type=int, default=6, help="train on the last N iterations of games")
    p.add_argument("--epochs", type=float, default=2.0, help="passes over the newest games per iteration")
    p.add_argument("--batch", type=int, default=512)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--hidden", type=int, default=256)
    p.add_argument("--depth", type=int, default=3)
    p.add_argument("--eval-games", type=int, default=40, help="games vs each baseline per iteration (0 = skip)")
    p.add_argument("--eval-sims", type=int, default=100)
    p.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    p.add_argument("--device", default="auto", help="auto | mps | cpu | cuda")
    p.add_argument("--resume", action="store_true")
    add_rules_args(p)
    a = p.parse_args()

    out = os.path.join("models", a.run)
    os.makedirs(out, exist_ok=True)
    device = a.device if a.device != "auto" else (
        "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")

    start_iter = 1
    latest = os.path.join(out, "latest.pt")
    if a.resume and os.path.exists(latest):
        net, rules, meta = load_checkpoint(latest)
        start_iter = meta["iteration"] + 1
        print(f"resuming {a.run} from iteration {meta['iteration']}")
    else:
        rules = rules_from_args(a)
        net = build_torch_net(rules, a.hidden, a.depth)
        with open(os.path.join(out, "rules.json"), "w") as f:
            json.dump(rules.to_dict(), f, indent=2)
    net.to(device)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=1e-4)

    print(f"rules: {rules.describe()}")
    print(f"device: {device}, self-play workers: {a.workers}")

    log_path = os.path.join(out, "log.csv")
    new_log = not os.path.exists(log_path) or not a.resume
    log_f = open(log_path, "w" if new_log else "a", newline="")
    log = csv.writer(log_f)
    if new_log:
        log.writerow(["iteration", "seconds", "positions", "policy_loss", "value_loss",
                      "p1_win", "p2_win", "draw", "avg_length", "move_limit",
                      "vs_greedy", "vs_minimax3"])

    buffer = []
    rng = np.random.default_rng()
    with Pool(a.workers) as pool:
        for it in range(start_iter, start_iter + a.iterations):
            t0 = time.time()
            net.eval()
            # iteration 1 uses the untrained network; MCTS still learns from game results
            weights = torch_to_numpy(net.cpu())
            net.to(device)

            # ---- self-play
            per = [a.games // a.workers + (1 if i < a.games % a.workers else 0) for i in range(a.workers)]
            tasks = [(weights, rules.to_dict(), g, a.sims, a.temp_moves, int(rng.integers(1 << 31)))
                     for g in per if g]
            results = pool.map(selfplay_worker, tasks)
            xs = np.concatenate([r[0][0] for r in results])
            pis = np.concatenate([r[0][1] for r in results])
            zs = np.concatenate([r[0][2] for r in results])
            stats = [s for r in results for s in r[1]]
            buffer.append((xs, pis, zs))
            buffer = buffer[-a.window:]

            n = len(stats)
            p1 = sum(s["winner"] == 0 for s in stats) / n
            p2 = sum(s["winner"] == 1 for s in stats) / n
            dr = sum(s["winner"] == -1 for s in stats) / n
            avg_len = sum(s["length"] for s in stats) / n
            limit = sum(s["move_limit"] for s in stats) / n
            t_play = time.time() - t0

            # ---- train
            X = torch.from_numpy(np.concatenate([b[0] for b in buffer])).to(device)
            P = torch.from_numpy(np.concatenate([b[1] for b in buffer])).to(device)
            Z = torch.from_numpy(np.concatenate([b[2] for b in buffer])).to(device)
            steps = max(1, int(a.epochs * len(xs) / a.batch))
            net.train()
            pl_sum = vl_sum = 0.0
            for _ in range(steps):
                idx = torch.randint(0, len(X), (a.batch,), device=device)
                logits, v = net(X[idx])
                pl = -(P[idx] * F.log_softmax(logits, dim=1)).sum(dim=1).mean()
                vl = F.mse_loss(v, Z[idx])
                opt.zero_grad()
                (pl + vl).backward()
                opt.step()
                pl_sum += pl.item()
                vl_sum += vl.item()
            net.eval()
            t_train = time.time() - t0 - t_play

            # ---- evaluate against fixed baselines
            weights = torch_to_numpy(net.cpu())
            net.to(device)
            scores = {}
            if a.eval_games:
                half = max(2, a.eval_games // a.workers // 2 * 2)
                etasks = []
                for opp in ("greedy", "minimax-3"):
                    left = a.eval_games
                    while left > 0:
                        g = min(half, left)
                        etasks.append((weights, rules.to_dict(), opp, g, a.eval_sims, int(rng.integers(1 << 31))))
                        left -= g
                for opp, w, l, d in pool.map(eval_worker, etasks):
                    tw, tl, td = scores.get(opp, (0, 0, 0))
                    scores[opp] = (tw + w, tl + l, td + d)

            def score(opp):
                if opp not in scores:
                    return ""
                w, l, d = scores[opp]
                return round((w + 0.5 * d) / (w + l + d), 3)

            dt = time.time() - t0
            meta = {"iteration": it, "args": vars(a)}
            save_checkpoint(latest, net, rules, meta)
            save_checkpoint(os.path.join(out, f"iter_{it:03d}.pt"), net, rules, meta)
            log.writerow([it, round(dt, 1), len(xs), round(pl_sum / steps, 4), round(vl_sum / steps, 4),
                          round(p1, 3), round(p2, 3), round(dr, 3), round(avg_len, 1), round(limit, 3),
                          score("greedy"), score("minimax-3")])
            log_f.flush()
            vs = "  ".join(f"vs {o}: {score(o):.0%}" for o in ("greedy", "minimax-3") if o in scores)
            print(f"iter {it:3d} | {dt:5.0f}s (play {t_play:.0f}s, train {t_train:.0f}s) | "
                  f"loss p {pl_sum / steps:.3f} v {vl_sum / steps:.3f} | "
                  f"P1 {p1:.0%} P2 {p2:.0%} draw {dr:.0%} | len {avg_len:.0f} | {vs}", flush=True)


if __name__ == "__main__":
    main()
