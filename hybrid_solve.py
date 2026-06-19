# -*- coding: utf-8 -*-
"""两层混合求解：GA/SA 求可行上界 → CP-SAT Hint 热启动精确证明。"""
import sys, time
from solver import solve, build_ops, G1, POOL, PRICE
from heuristic import run_metaheuristic, extract_routes, DEFAULT_GA, DEFAULT_SA
from validate import validate
sys.stdout.reconfigure(encoding="utf-8")


def solve_hybrid(counts, workshops, bases, ga_params=None, sa_params=None,
                 time_limit=120, cold_time_limit=None, log=False):
    """返回混合求解全过程指标。"""
    ga_params = ga_params or DEFAULT_GA
    sa_params = sa_params or DEFAULT_SA
    cold_time_limit = cold_time_limit or time_limit
    ops, jobs = build_ops(counts, workshops)
    n = len(ops)
    depot = n

    ub, starts, chrom, meta_time = run_metaheuristic(ops, jobs, bases, ga_params, sa_params)
    ok, msg, _ = validate(starts, ops, jobs, bases)
    routes = extract_routes(starts, ops, depot)
    hints = {"starts": starts, "cmax": ub, "routes": routes}

    cold = solve(counts, workshops, bases, time_limit=cold_time_limit, log=log)
    hot = solve(counts, workshops, bases, time_limit=time_limit, hints=hints, log=log)

    return {
        "ub": ub, "chrom": chrom, "meta_time": meta_time,
        "meta_feasible": ok, "meta_msg": msg,
        "cold": cold, "hot": hot,
        "optimal": hot["cmax"],
        "gap_ub": (ub - hot["cmax"]) if hot["cmax"] is not None else None,
    }


def print_hybrid(tag, r):
    print(f"\n===== {tag} 混合求解 =====")
    print(f"  元启发式上界: {r['ub']} s (可行={r['meta_feasible']}, 耗时={r['meta_time']:.1f}s)")
    print(f"  CP-SAT 冷启动: Cmax={r['cold']['cmax']} status={r['cold']['status']} "
          f"耗时={r['cold']['solve_time']:.1f}s")
    print(f"  CP-SAT 热启动: Cmax={r['hot']['cmax']} status={r['hot']['status']} "
          f"耗时={r['hot']['solve_time']:.1f}s")
    if r['cold']['solve_time'] > 0:
        ratio = r['cold']['solve_time'] / max(r['hot']['solve_time'], 0.01)
        print(f"  加速比(冷/热): {ratio:.2f}x")
    if r['gap_ub'] is not None:
        print(f"  上界间隙: {r['gap_ub']} s")


if __name__ == "__main__":
    ALL = ["A", "B", "C", "D", "E"]
    r2 = solve_hybrid(G1, ALL, ["G1"], time_limit=120)
    print_hybrid("Q2", r2)
    r3 = solve_hybrid(POOL, ALL, ["G1", "G2"], time_limit=180)
    print_hybrid("Q3", r3)
    cc = dict(POOL); cc["polish"] += 3; cc["sensor"] += 3
    r4 = solve_hybrid(cc, ALL, ["G1", "G2"], time_limit=60)
    print_hybrid("Q4", r4)
    # Q4 全枚举（购置组合）
    print("\n===== Q4 购置枚举（混合求解）=====")
    best = None
    for kp in range(0, 5):
        for ks in range(0, 5):
            cost = kp * PRICE["polish"] + ks * PRICE["sensor"]
            if cost > 500000: continue
            cc2 = dict(POOL); cc2["polish"] += kp; cc2["sensor"] += ks
            rh = solve_hybrid(cc2, ALL, ["G1", "G2"], time_limit=40, cold_time_limit=40)
            cm = rh["optimal"]
            if cm is None: continue
            print(f"  polish+{kp} sensor+{ks} cost={cost} Cmax={cm} ({rh['hot']['status']})")
            key = (cm, cost)
            if best is None or key < best[0]:
                best = (key, kp, ks, rh)
    if best:
        (cm, cost), kp, ks, rh = best
        print(f"\n>>> Q4 best: polish+{kp}, sensor+{ks}, cost={cost}, Cmax={cm}")
