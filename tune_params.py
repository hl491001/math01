# -*- coding: utf-8 -*-
"""Q2 上网格搜索 GA/SA 参数，输出调参表与冷/热启动对比数据。"""
import sys, itertools, json
from solver import solve, G1
from heuristic import run_metaheuristic, extract_routes
sys.stdout.reconfigure(encoding="utf-8")

ALL = ["A", "B", "C", "D", "E"]
BASES = ["G1"]
OPTIMAL = 144880
COLD_LIMIT = 120
HOT_LIMIT = 120

GA_GRID = {
    "pop_size": [80, 150, 200],
    "gens": [400, 800],
    "pm": [0.15, 0.2],
}
SA_GRID = {
    "T0": [3000.0, 4000.0],
    "alpha": [0.95, 0.97],
    "iters": [300, 400],
}
SA_FIXED = {"Tend": 1e-2, "seed": 0}
GA_FIXED = {"seed": 0}


def tune():
    from solver import build_ops
    ops, jobs = build_ops(G1, ALL)
    depot = len(ops)
    rows = []
    ga_keys = list(GA_GRID.keys())
    sa_keys = list(SA_GRID.keys())
    for ga_vals in itertools.product(*GA_GRID.values()):
        ga_p = dict(zip(ga_keys, ga_vals)); ga_p.update(GA_FIXED)
        for sa_vals in itertools.product(*SA_GRID.values()):
            sa_p = dict(zip(sa_keys, sa_vals)); sa_p.update(SA_FIXED)
            ub, starts, _, meta_t = run_metaheuristic(ops, jobs, BASES, ga_p, sa_p)
            routes = extract_routes(starts, ops, depot)
            hints = {"starts": starts, "cmax": ub, "routes": routes}
            cold = solve(G1, ALL, BASES, time_limit=COLD_LIMIT)
            hot = solve(G1, ALL, BASES, time_limit=HOT_LIMIT, hints=hints)
            gap = ub - OPTIMAL
            speedup = cold["solve_time"] / max(hot["solve_time"], 0.01)
            rows.append({
                "ga": ga_p, "sa": sa_p,
                "ub": ub, "gap": gap, "meta_time": meta_t,
                "cold_time": cold["solve_time"], "hot_time": hot["solve_time"],
                "speedup": speedup,
            })
            print(f"GA pop={ga_p['pop_size']} gens={ga_p['gens']} pm={ga_p['pm']} | "
                  f"SA T0={sa_p['T0']} alpha={sa_p['alpha']} iters={sa_p['iters']} | "
                  f"ub={ub} gap={gap} meta={meta_t:.1f}s cold={cold['solve_time']:.1f}s "
                  f"hot={hot['solve_time']:.1f}s speedup={speedup:.2f}x", flush=True)
    # 推荐：makespan 优先，耗时次之
    rows.sort(key=lambda r: (r["gap"], r["meta_time"] + r["hot_time"]))
    best = rows[0]
    print("\n===== 推荐参数 =====")
    print("GA:", best["ga"])
    print("SA:", best["sa"])
    print(f"上界={best['ub']} 间隙={best['gap']} 冷={best['cold_time']:.1f}s 热={best['hot_time']:.1f}s "
          f"加速={best['speedup']:.2f}x")
    with open("tune_results.json", "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "recommended": best}, f, ensure_ascii=False, indent=2)
    return rows, best


def cold_hot_table():
    """Q2/Q3/Q4 冷/热启动对比（用推荐参数）。"""
    from hybrid_solve import solve_hybrid
    from solver import POOL, PRICE
    results = []
    r2 = solve_hybrid(G1, ALL, BASES, time_limit=120)
    results.append(("Q2", r2))
    r3 = solve_hybrid(POOL, ALL, ["G1", "G2"], time_limit=180)
    results.append(("Q3", r3))
    cc = dict(POOL); cc["polish"] += 3; cc["sensor"] += 3
    r4 = solve_hybrid(cc, ALL, ["G1", "G2"], time_limit=60)
    results.append(("Q4", r4))
    print("\n===== 冷/热启动对比表 =====")
    for tag, r in results:
        cold_t = r["cold"]["solve_time"]
        hot_t = r["hot"]["solve_time"]
        sp = cold_t / max(hot_t, 0.01)
        print(f"{tag}: 冷={cold_t:.1f}s 热={hot_t:.1f}s 加速={sp:.2f}x 最优={r['optimal']}")
    with open("cold_hot.json", "w", encoding="utf-8") as f:
        json.dump({tag: {"cold": r["cold"]["solve_time"], "hot": r["hot"]["solve_time"],
                         "optimal": r["optimal"], "ub": r["ub"]} for tag, r in results},
                  f, ensure_ascii=False, indent=2)
    return results


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--quick", action="store_true", help="仅跑推荐参数冷/热对比")
    args = p.parse_args()
    if args.quick:
        cold_hot_table()
    else:
        tune()
        cold_hot_table()
