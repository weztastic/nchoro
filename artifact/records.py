"""Check and summarise game records that testers pasted to you.

    .venv/bin/python artifact/records.py records.txt        # one or more files
    pbpaste | .venv/bin/python artifact/records.py          # straight from the clipboard
    .venv/bin/python artifact/records.py games.csv          # CSV download of the Google Sheet

Every line starting with NCHORO-RECORD is replayed through the engine under the current
rules. A record whose moves are illegal or whose score doesn't match is reported, not counted.
"""

import collections
import csv
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from build import rules_id  # noqa: E402
from nchoro.engine import Rules, State, legal_moves, play  # noqa: E402

RULES_FILE = os.path.join(os.path.dirname(HERE), "models", "nchoro", "rules.json")


def replay(rec, rules):
    s = State.initial(rules)
    for tok in rec["moves"].split():
        player, pit = int(tok[0]) - 1, "abcdef".index(tok[1])
        if s.over or s.to_move != player or pit not in legal_moves(s):
            return f"illegal move {tok}"
        s = play(s, pit)
    if not s.over and rec["status"] == "finished":
        return "game not finished after its moves"
    if s.over:
        hs = rec["humanSide"] - 1
        if [s.scores[hs], s.scores[1 - hs]] != [rec["scores"]["human"], rec["scores"]["ai"]]:
            return f"score mismatch: replay gives {s.scores[hs]}-{s.scores[1 - hs]}"
    return None


def main():
    with open(RULES_FILE) as f:
        rules = Rules.from_dict(json.load(f))
    current = rules_id(rules)
    text = "".join(open(p).read() for p in sys.argv[1:]) if sys.argv[1:] else sys.stdin.read()
    recs, seen = [], set()
    if text.lstrip().startswith("received_at,"):        # CSV export of the Google Sheet
        for row in csv.DictReader(io.StringIO(text)):
            rec = {"status": row["status"], "result": row["result"], "humanSide": int(row["human_side"] or 0),
                   "level": row["level"], "rulesId": row["rules_id"], "moves": row["moves"],
                   "moveCount": int(row["move_count"] or 0), "startedAt": row["started_at"] or row["received_at"],
                   "scores": {"human": int(row["human_score"] or 0), "ai": int(row["ai_score"] or 0)}}
            key = (rec["startedAt"], rec["moves"])
            if key not in seen:
                seen.add(key)
                recs.append(rec)
        text = ""
    for line in text.splitlines():
        if "NCHORO-RECORD " not in line:
            continue
        try:
            rec = json.loads(line.split("NCHORO-RECORD ", 1)[1])
        except json.JSONDecodeError:
            print("skipped a damaged record line")
            continue
        key = (rec.get("startedAt"), rec.get("moves"))
        if key in seen:
            continue
        seen.add(key)
        recs.append(rec)

    good, abandoned = [], 0
    for r in recs:
        if r.get("rulesId") != current:
            print(f"- {r['startedAt']}: played under other rules ({r.get('rulesId')}), not checked")
            continue
        if r["status"] != "finished":
            abandoned += 1
            continue
        problem = replay(r, rules)
        if problem:
            print(f"- {r['startedAt']}: REJECTED, {problem}")
        else:
            good.append(r)

    print(f"\n{len(good)} verified finished game(s) under the current rules ({current}); {abandoned} abandoned")
    if not good:
        return
    by = collections.defaultdict(lambda: collections.Counter())
    for r in good:
        by[(r["level"], "first" if r["humanSide"] == 1 else "second")][r["result"]] += 1
    print(f"\n{'AI strength':<12}{'human moved':<13}{'won':>5}{'drew':>6}{'lost':>6}")
    for (level, side), c in sorted(by.items()):
        print(f"{level:<12}{side:<13}{c['human']:>5}{c['draw']:>6}{c['ai']:>6}")
    print(f"\naverage length {sum(r['moveCount'] for r in good) / len(good):.0f} moves")


if __name__ == "__main__":
    main()
