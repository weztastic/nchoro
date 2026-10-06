"""Shared command-line flags for rule variants."""

from .engine import Rules


def add_rules_args(p):
    g = p.add_argument_group("rules (defaults = Nchoro Amarachi style as described in RULES.md)")
    g.add_argument("--pits", type=int, default=6, help="pits per side")
    g.add_argument("--seeds", type=int, default=4, help="seeds per pit at the start")
    g.add_argument("--sowing", choices=["relay", "single"], default="relay")
    g.add_argument("--capture", default="4", help="comma-separated capture counts, e.g. 4 or 2,3")
    g.add_argument("--capture-side", choices=["both", "opponent", "own"], default="both")
    g.add_argument("--chain", action="store_true", help="also capture preceding pits holding a capture count")
    g.add_argument("--feeding", action="store_true", help="must feed an opponent whose row is empty")
    g.add_argument("--end-at", type=int, default=4, help="game ends with this many seeds or fewer left")
    g.add_argument("--max-laps", type=int, default=200)
    g.add_argument("--max-moves", type=int, default=300)


def rules_from_args(a) -> Rules:
    return Rules(pits=a.pits, seeds=a.seeds, sowing=a.sowing,
                 capture_counts=tuple(int(c) for c in a.capture.split(",")),
                 capture_side=a.capture_side, capture_chain=a.chain, feeding=a.feeding, end_at=a.end_at,
                 max_laps=a.max_laps, max_moves=a.max_moves)
