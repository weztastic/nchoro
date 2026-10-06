"""Policy/value network.

Training uses PyTorch. Self-play and play use a NumPy copy of the same weights:
for a network this small, evaluating one position in NumPy takes microseconds,
while a PyTorch/GPU call costs far more in overhead.
"""

from __future__ import annotations

import numpy as np

from .engine import Rules, State

BUCKETS = 16          # one-hot pit counts 0..15 (15 = "15 or more")


def input_size(rules: Rules) -> int:
    return 2 * rules.pits * (BUCKETS + 1) + 3


def encode(state: State) -> np.ndarray:
    """Features from the point of view of the player to move (their row first)."""
    r = state.rules
    n = r.pits
    me = state.to_move
    board = state.board
    order = list(range(me * n, me * n + n)) + list(range((1 - me) * n, (1 - me) * n + n))
    x = np.zeros(input_size(r), dtype=np.float32)
    total = r.total_seeds
    for k, i in enumerate(order):
        c = board[i]
        x[k * BUCKETS + min(c, BUCKETS - 1)] = 1.0
        x[2 * n * BUCKETS + k] = c / r.seeds / 4.0
    tail = 2 * n * (BUCKETS + 1)
    x[tail] = state.scores[me] / total
    x[tail + 1] = state.scores[1 - me] / total
    x[tail + 2] = state.move_count / r.max_moves
    return x


class NumpyNet:
    """Forward pass of PolicyValueNet using plain NumPy."""

    def __init__(self, weights: dict):
        self.layers = [(weights[f"body.{i}.weight"].T.copy(), weights[f"body.{i}.bias"])
                       for i in range(0, 2 * weights["_depth"], 2)]
        self.pw, self.pb = weights["policy.weight"].T.copy(), weights["policy.bias"]
        self.vw, self.vb = weights["value.weight"].T.copy(), weights["value.bias"]

    def __call__(self, x: np.ndarray):
        h = x
        for w, b in self.layers:
            h = np.maximum(h @ w + b, 0.0)
        logits = h @ self.pw + self.pb
        value = np.tanh(h @ self.vw + self.vb)
        return logits, value


class UniformNet:
    """Stand-in before any training: uniform policy, value 0."""

    def __init__(self, rules: Rules):
        self.n = rules.pits

    def __call__(self, x):
        return np.zeros(self.n, dtype=np.float32), np.zeros(1, dtype=np.float32)


# --------------------------------------------------------------------------- torch side

def build_torch_net(rules: Rules, hidden: int = 256, depth: int = 3):
    import torch.nn as nn

    class PolicyValueNet(nn.Module):
        def __init__(self):
            super().__init__()
            layers, d = [], input_size(rules)
            for _ in range(depth):
                layers += [nn.Linear(d, hidden), nn.ReLU()]
                d = hidden
            self.body = nn.Sequential(*layers)
            self.policy = nn.Linear(hidden, rules.pits)
            self.value = nn.Linear(hidden, 1)
            self.depth = depth

        def forward(self, x):
            h = self.body(x)
            return self.policy(h), self.value(h).tanh().squeeze(-1)

    return PolicyValueNet()


def torch_to_numpy(net) -> dict:
    w = {k: v.detach().cpu().numpy() for k, v in net.state_dict().items()}
    w["_depth"] = net.depth
    return w


def save_checkpoint(path, net, rules: Rules, meta: dict):
    import torch
    torch.save({"state_dict": net.state_dict(), "rules": rules.to_dict(),
                "hidden": net.policy.in_features, "depth": net.depth, "meta": meta}, path)


def load_checkpoint(path):
    """Returns (torch_net, rules, meta)."""
    import torch
    ck = torch.load(path, map_location="cpu", weights_only=False)
    rules = Rules.from_dict(ck["rules"])
    net = build_torch_net(rules, ck["hidden"], ck["depth"])
    net.load_state_dict(ck["state_dict"])
    net.eval()
    return net, rules, ck.get("meta", {})


def load_numpy_net(path):
    """Returns (NumpyNet, rules, meta) — no PyTorch needed at play time beyond loading."""
    net, rules, meta = load_checkpoint(path)
    return NumpyNet(torch_to_numpy(net)), rules, meta
