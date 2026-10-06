"""Players share one interface: choose(state) -> (move, info).

`info` is a dict the UI can show (e.g. the AI's win estimate and move preferences).
"""

from __future__ import annotations

import random

import numpy as np

from .engine import State, legal_moves, play


class RandomPlayer:
    name = "random"

    def __init__(self, seed=None):
        self.rng = random.Random(seed)

    def choose(self, state: State):
        return self.rng.choice(legal_moves(state)), {}


class MinimaxPlayer:
    """Alpha-beta search on captured-seed difference. depth=1 is a plain greedy player."""

    def __init__(self, depth: int = 3, seed=None):
        self.depth = depth
        self.rng = random.Random(seed)
        self.name = "greedy" if depth == 1 else f"minimax-{depth}"

    def _score(self, s: State, me: int) -> float:
        if s.over:
            return 1000.0 * (1 if s.winner == me else -1 if s.winner == 1 - me else 0) + s.scores[me] - s.scores[1 - me]
        return s.scores[me] - s.scores[1 - me]

    def _search(self, s: State, depth: int, alpha: float, beta: float, me: int) -> float:
        if depth == 0 or s.over:
            return self._score(s, me)
        maximizing = s.to_move == me
        best = -1e9 if maximizing else 1e9
        for m in legal_moves(s):
            v = self._search(play(s, m), depth - 1, alpha, beta, me)
            if maximizing:
                best = max(best, v)
                alpha = max(alpha, v)
            else:
                best = min(best, v)
                beta = min(beta, v)
            if beta <= alpha:
                break
        return best

    def choose(self, state: State):
        me = state.to_move
        moves = legal_moves(state)
        self.rng.shuffle(moves)
        scored = [(self._search(play(state, m), self.depth - 1, -1e9, 1e9, me), m) for m in moves]
        best = max(v for v, _ in scored)
        return next(m for v, m in scored if v == best), {}


class AlphaZeroPlayer:
    def __init__(self, checkpoint: str, sims: int = 200, seed=None):
        from .mcts import MCTS
        from .net import load_numpy_net
        net, self.rules, self.meta = load_numpy_net(checkpoint)
        self.mcts = MCTS(net, sims=sims, rng=np.random.default_rng(seed))
        self.name = f"alphazero({self.meta.get('iteration', '?')}, {sims} sims)"

    def choose(self, state: State):
        root = self.mcts.search(state)
        move = self.mcts.choose(root, temperature=0.0)
        n = state.rules.pits
        visits = [0] * n
        for m, c in root.children.items():
            visits[m] = c.n
        best = root.children[move]
        win_prob = (best.q() + 1) / 2          # child q is from the mover's view
        return move, {"visits": visits, "win_prob": round(win_prob, 3)}


def make_player(spec: str, seed=None):
    """'random', 'greedy', 'minimax-4', or a path to a .pt checkpoint (optionally 'path@sims')."""
    if spec == "random":
        return RandomPlayer(seed)
    if spec == "greedy":
        return MinimaxPlayer(1, seed)
    if spec.startswith("minimax"):
        return MinimaxPlayer(int(spec.split("-")[1]) if "-" in spec else 3, seed)
    path, _, sims = spec.partition("@")
    return AlphaZeroPlayer(path, int(sims) if sims else 200, seed)


def play_game(p0, p1, rules, first: int = 0):
    """Play one game; returns the final state. p0 is player 1 (bottom row)."""
    s = State.initial(rules, first)
    players = (p0, p1)
    while not s.over:
        m, _ = players[s.to_move].choose(s)
        s = play(s, m)
    return s


def match(a, b, rules, games: int = 20):
    """Play `games` games, alternating who starts. Returns (a_wins, b_wins, draws)."""
    aw = bw = d = 0
    for g in range(games):
        if g % 2 == 0:
            s = play_game(a, b, rules)
            w = s.winner
        else:
            s = play_game(b, a, rules)
            w = {0: 1, 1: 0, -1: -1}[s.winner]
        if w == 0:
            aw += 1
        elif w == 1:
            bw += 1
        else:
            d += 1
    return aw, bw, d
