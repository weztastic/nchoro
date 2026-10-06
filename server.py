"""Local web UI: play against the computer or watch AIs play.

    .venv/bin/python server.py            # then open http://localhost:8000
"""

import argparse
import glob
import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nchoro.engine import Rules, State, legal_moves, play
from nchoro.players import make_player

ROOT = os.path.dirname(os.path.abspath(__file__))
BASELINES = [("random", "Random"), ("greedy", "Greedy (best capture now)"),
             ("minimax-3", "Minimax depth 3"), ("minimax-5", "Minimax depth 5")]

games = {}
players_cache = {}
lock = threading.Lock()


def list_players():
    out = [{"id": "human", "label": "Human"}]
    out += [{"id": i, "label": l} for i, l in BASELINES]
    for path in sorted(glob.glob(os.path.join(ROOT, "models", "*", "latest.pt"))):
        run = os.path.basename(os.path.dirname(path))
        try:
            with open(os.path.join(os.path.dirname(path), "rules.json")) as f:
                rules = Rules.from_dict(json.load(f))
            desc = rules.describe()
        except OSError:
            rules, desc = None, ""
        out.append({"id": os.path.relpath(path, ROOT), "label": f"AlphaZero: {run}",
                    "rules": rules.to_dict() if rules else None, "rules_text": desc})
    return out


def get_player(spec, sims):
    key = (spec, sims)
    if key not in players_cache:
        players_cache[key] = make_player(spec if not spec.endswith(".pt") else os.path.join(ROOT, spec) + f"@{sims}")
    return players_cache[key]


def new_game(body):
    specs = [body.get("p1", "human"), body.get("p2", "minimax-3")]
    sims = int(body.get("sims", 200))
    rules = Rules.from_dict(body["rules"]) if body.get("rules") else Rules()
    players = []
    for spec in specs:
        if spec == "human":
            players.append(None)
            continue
        p = get_player(spec, sims)
        if hasattr(p, "rules"):          # AlphaZero players only know the rules they trained on
            if body.get("rules") and p.rules != rules:
                raise ValueError(f"{p.name} was trained on different rules: {p.rules.describe()}")
            rules = p.rules
        players.append(p)
    gid = uuid.uuid4().hex[:8]
    games[gid] = {"state": State.initial(rules), "players": players, "specs": specs}
    return {"id": gid, "state": games[gid]["state"].to_dict(), "rules_text": rules.describe()}


def move(body):
    g = games[body["id"]]
    s = g["state"]
    if s.over:
        raise ValueError("game is over")
    player = g["players"][s.to_move]
    info = {}
    if player is None:
        if body.get("pit") is None:
            raise ValueError("waiting for a human move")
        m = int(body["pit"])
    else:
        m, info = player.choose(s)
    trace = []
    before = s.to_dict()
    g["state"] = play(s, m, trace)
    return {"player": s.to_move, "move": m, "info": info, "trace": trace,
            "before": before, "state": g["state"].to_dict()}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(os.path.join(ROOT, "web", "index.html"), "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif self.path == "/api/players":
            self._send(200, list_players())
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        try:
            with lock:
                if self.path == "/api/new":
                    self._send(200, new_game(body))
                elif self.path == "/api/move":
                    self._send(200, move(body))
                else:
                    self._send(404, {"error": "not found"})
        except (ValueError, KeyError) as e:
            self._send(400, {"error": str(e)})

    def log_message(self, *args):
        pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8000)
    a = p.parse_args()
    print(f"Nchoro Amarachi style UI on http://localhost:{a.port}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
