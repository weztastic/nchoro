"""The browser version (artifact/engine.js) must play exactly like the Python engine.

Replays random games through both engines and compares every trace and state,
and compares network outputs on real positions. Needs `node` on the PATH.
"""

import glob
import json
import os
import random
import shutil
import subprocess

import numpy as np
import pytest

from nchoro.engine import Rules, State, legal_moves, play
from nchoro.net import NumpyNet, encode, load_checkpoint, torch_to_numpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "artifact", "engine.js")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

NODE_REPLAY = """
const N = require(process.argv[1]);
const games = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = games.map(g => {
  const rules = N.makeRules(g.rules);
  let s = N.initial(rules);
  return g.moves.map(m => {
    const legal = N.legalMoves(s);
    const trace = [];
    s = N.play(s, m, trace);
    return { legal, trace, board: s.board, scores: s.scores, to_move: s.toMove, winner: s.winner };
  });
});
process.stdout.write(JSON.stringify(out));
"""

NODE_NET = """
const N = require(process.argv[1]);
const inp = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const dec = b => new Float32Array(new Uint8Array(Buffer.from(b, 'base64')).buffer);
const L = l => ({ in: l.in, out: l.out, w: dec(l.w), b: dec(l.b) });
const W = inp.weights;
const net = N.makeNet({ layers: W.layers.map(L), policy: L(W.policy), value: L(W.value) });
const rules = N.makeRules(W.rules);
const out = inp.states.map(st => {
  const s = Object.assign(N.initial(rules), st);
  const x = N.encode(s);
  const r = net(x);
  return { x: Array.from(x), logits: Array.from(r.logits), value: r.value };
});
process.stdout.write(JSON.stringify(out));
"""


def node(script, payload):
    res = subprocess.run(["node", "-e", script, ENGINE], input=json.dumps(payload),
                         capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def random_games(rules, count, seed):
    rng = random.Random(seed)
    games = []
    for _ in range(count):
        s, moves, steps = State.initial(rules), [], []
        while not s.over:
            legal = legal_moves(s)
            m = rng.choice(legal)
            trace = []
            s = play(s, m, trace)
            moves.append(m)
            steps.append({"legal": legal, "trace": trace, "board": s.board, "scores": s.scores,
                          "to_move": s.to_move, "winner": s.winner})
        games.append((moves, steps))
    return games


@pytest.mark.parametrize("rules", [
    Rules(),
    Rules(sowing="single", capture_counts=(2, 3), capture_side="opponent", capture_chain=True,
          instant_capture=False, skip_origin=True),
    Rules(feeding=True, end_at=0, max_laps=50),
    Rules(instant_capture=False, skip_origin=True, sweep_own=True),
], ids=["default", "oware-like", "feeding", "previous-rules"])
def test_js_engine_replays_python_games_identically(rules):
    games = random_games(rules, 150, seed=42)
    payload = [{"rules": rules.to_dict(), "moves": moves} for moves, _ in games]
    js = node(NODE_REPLAY, payload)
    for (moves, py_steps), js_steps in zip(games, js):
        assert js_steps == py_steps


def test_js_network_matches_python():
    ckpts = sorted(glob.glob(os.path.join(ROOT, "models", "*", "latest.pt")))
    if not ckpts:
        pytest.skip("no trained model")
    import sys
    sys.path.insert(0, os.path.join(ROOT, "artifact"))
    from build import export_weights
    weights = export_weights(ckpts[0])
    net, rules, _ = load_checkpoint(ckpts[0])
    np_net = NumpyNet(torch_to_numpy(net))
    states = []
    for _, steps in random_games(rules, 5, seed=7):
        for st in steps[::3]:
            if st["winner"] is None:
                states.append(st)
    payload = {"weights": weights,
               "states": [{"board": s["board"], "scores": s["scores"], "toMove": s["to_move"],
                           "moveCount": i} for i, s in enumerate(states)]}
    js = node(NODE_NET, payload)
    for i, (s, j) in enumerate(zip(states, js)):
        st = State(rules, s["board"], s["scores"], s["to_move"], i)
        x = encode(st)
        np.testing.assert_allclose(j["x"], x, rtol=0, atol=1e-7)
        logits, value = np_net(x)
        np.testing.assert_allclose(j["logits"], logits, atol=1e-4)
        assert abs(j["value"] - float(value[0])) < 1e-4
