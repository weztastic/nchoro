"""Self-play and evaluation workers (run in separate processes)."""

from __future__ import annotations

import numpy as np

from .engine import Rules, State, play, result_for
from .mcts import MCTS
from .net import NumpyNet, UniformNet, encode
from .players import MinimaxPlayer, match


def _net(weights, rules):
    return NumpyNet(weights) if weights is not None else UniformNet(rules)


def selfplay_worker(task):
    """Play games against itself. Returns (samples, game_stats)."""
    weights, rules_d, games, sims, temp_moves, seed = task
    rules = Rules.from_dict(rules_d)
    rng = np.random.default_rng(seed)
    mcts = MCTS(_net(weights, rules), sims=sims, rng=rng)
    xs, pis, zs, stats = [], [], [], []
    for _ in range(games):
        s = State.initial(rules)
        hist = []
        while not s.over:
            root = mcts.search(s, noise=True)
            hist.append((encode(s), MCTS.visit_policy(root, rules.pits), s.to_move))
            temp = 1.0 if s.move_count < temp_moves else 0.0
            s = play(s, mcts.choose(root, temp))
        for x, pi, player in hist:
            xs.append(x)
            pis.append(pi)
            zs.append(result_for(s, player))
        stats.append({"winner": s.winner, "length": s.move_count, "scores": s.scores[:],
                      "move_limit": s.end_reason == "move limit reached"})
    return (np.array(xs), np.array(pis), np.array(zs, dtype=np.float32)), stats


class _AZ:
    def __init__(self, weights, rules, sims, seed):
        self.mcts = MCTS(_net(weights, rules), sims=sims, rng=np.random.default_rng(seed))

    def choose(self, s):
        return self.mcts.choose(self.mcts.search(s)), {}


def eval_worker(task):
    """Play the network against a baseline. Returns (opponent, az_wins, opp_wins, draws)."""
    weights, rules_d, opponent, games, sims, seed = task
    rules = Rules.from_dict(rules_d)
    opp = MinimaxPlayer(1 if opponent == "greedy" else int(opponent.split("-")[1]), seed)
    return (opponent, *match(_AZ(weights, rules, sims, seed), opp, rules, games))
