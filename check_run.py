"""Print only noteworthy events in the overnight run (empty output = nothing to report)."""
import os, re, subprocess, time

D = "models/nchoro_long"
seen_f = os.path.join(D, ".reported_lines")
log = open(os.path.join(D, "overnight.log")).read().splitlines()
seen = int(open(seen_f).read()) if os.path.exists(seen_f) else 1
for line in log[seen:]:
    print("NEW:", line)                       # hourly match results, stop, final analysis
open(seen_f, "w").write(str(len(log)))

running = subprocess.run(["pgrep", "-f", "overnight.py"], capture_output=True).returncode == 0
done = any("final analysis written" in l for l in log)
if done:
    print("DONE: run finished")
elif not running:
    print("PROBLEM: overnight process is not running")
else:
    tl = os.path.join(D, "train.log")
    age = time.time() - os.path.getmtime(tl)
    if age > 300 and not any("training stopped" in l for l in log):
        print(f"PROBLEM: no training progress for {age / 60:.0f} minutes (Mac asleep?)")
    last = [l for l in open(tl).read().splitlines() if l.startswith("iter")][-5:]
    vals = [int(m) for l in last for m in re.findall(r"minimax-3: (\d+)%", l)]
    if vals and max(vals) < 70:
        print("WARNING: score vs minimax-3 below 70% for 5 iterations:", last[-1])
