"""AlphaZero-style Monte Carlo Tree Search (PUCT)."""

from __future__ import annotations

import math

import numpy as np

from .engine import State, legal_moves, play, result_for
from .net import encode


class Node:
    __slots__ = ("state", "prior", "mover", "children", "n", "w", "moves", "terminal_value")

    def __init__(self, state: State, prior: float, mover: int = -1):
        self.state = state                 # None until first visited (created lazily)
        self.prior = prior
        self.mover = mover                 # player who made the move into this node
        self.children = None               # dict move -> Node once expanded
        self.n = 0
        self.w = 0.0                       # total value, from the view of the player who moved INTO this node
        self.moves = None
        self.terminal_value = None

    def q(self) -> float:
        return self.w / self.n if self.n else 0.0


class MCTS:
    def __init__(self, net, sims: int = 200, c_puct: float = 1.5,
                 dirichlet_alpha: float = 0.6, dirichlet_frac: float = 0.25, rng=None):
        self.net = net
        self.sims = sims
        self.c_puct = c_puct
        self.alpha = dirichlet_alpha
        self.frac = dirichlet_frac
        self.rng = rng or np.random.default_rng()

    def _evaluate(self, node: Node) -> float:
        """Expand `node`; return its value from the view of the player to move there."""
        s = node.state
        if s.over:
            node.terminal_value = result_for(s, s.to_move)
            return node.terminal_value
        moves = legal_moves(s)
        logits, value = self.net(encode(s))
        lg = logits[moves]
        p = np.exp(lg - lg.max())
        p /= p.sum()
        node.moves = moves
        node.children = {m: Node(None, float(pm), s.to_move) for m, pm in zip(moves, p)}
        return float(value[0])

    def search(self, state: State, noise: bool = False) -> Node:
        root = Node(state, 1.0)
        self._evaluate(root)
        if root.children is None:
            return root
        if noise and len(root.moves) > 1:
            eta = self.rng.dirichlet([self.alpha] * len(root.moves))
            for (m, child), e in zip(root.children.items(), eta):
                child.prior = (1 - self.frac) * child.prior + self.frac * e

        for _ in range(self.sims):
            node, path = root, [root]
            while node.children is not None:
                sqrt_n = math.sqrt(node.n + 1)
                best, best_score = None, -1e9
                for child in node.children.values():
                    score = child.q() + self.c_puct * child.prior * sqrt_n / (1 + child.n)
                    if score > best_score:
                        best, best_score = child, score
                if best.state is None:
                    move = next(m for m, c in node.children.items() if c is best)
                    best.state = play(node.state, move)
                node = best
                path.append(node)
                if node.terminal_value is not None:
                    break

            if node.terminal_value is not None:
                v = node.terminal_value
            else:
                v = self._evaluate(node)
            # v is from the view of the player to move at the leaf. Players don't always
            # alternate (a player whose side is empty passes), so credit each node by its mover.
            leaf_player = node.state.to_move
            for nd in path:
                nd.n += 1
                nd.w += v if nd.mover == leaf_player else -v
        return root

    @staticmethod
    def visit_policy(root: Node, pits: int) -> np.ndarray:
        pi = np.zeros(pits, dtype=np.float32)
        for m, c in root.children.items():
            pi[m] = c.n
        return pi / pi.sum()

    def choose(self, root: Node, temperature: float = 0.0) -> int:
        moves = list(root.children)
        visits = np.array([root.children[m].n for m in moves], dtype=np.float64)
        if temperature <= 1e-3:
            best = np.flatnonzero(visits == visits.max())
            return moves[int(self.rng.choice(best))]
        p = visits ** (1.0 / temperature)
        return moves[int(self.rng.choice(len(moves), p=p / p.sum()))]
