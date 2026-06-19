# -*- coding: utf-8 -*-
"""混合求解对照：纯 CP-SAT / 混合(GA+SA+Hint) / 仅 GA 上界。
对问题二/三/四分别输出对照表，并用 validate.py 校验可行性。"""
import sys
from solver import solve, build_ops, G1, POOL, PRICE
from heuristic import run_metaheuristic, DEFAULT_GA, DEFAULT_SA
from validate import validate
sys.stdout.reconfigure(encoding="utf-8")


def compare_case(tag, counts, workshops, bases, exact):
    ops, jobs = build_ops(counts, workshops)
    ub, starts, _, meta_t = run_metaheuristic(ops, jobs, bases)
    gok, _, _ = validate(starts, ops, jobs, bases)
    cold = solve(counts, workshops, bases, time_limit=120)
    from heuristic import extract_routes
    depot = len(ops)
    routes = extract_routes(starts, ops, depot)
    hints = {"starts": starts, "cmax": ub, "routes": routes}
    hot = solve(counts, workshops, bases, time_limit=120, hints=hints)
    print(f"{tag}: 上界(GA+SA)={ub}(可行={gok}, {meta_t:.1f}s) | "
          f"冷启动={cold['cmax']}({cold['solve_time']:.1f}s) | "
          f"热启动={hot['cmax']}({hot['solve_time']:.1f}s, {hot['status']}) | "
          f"间隙={ub - exact}")
    return {"tag": tag, "ub": ub, "exact": exact, "gap": ub - exact,
            "cold_time": cold["solve_time"], "hot_time": hot["solve_time"],
            "feasible": gok, "status": hot["status"]}


if __name__ == "__main__":
    ALL = ["A", "B", "C", "D", "E"]
    cc = dict(POOL); cc["polish"] += 3; cc["sensor"] += 3
    print("===== 表 C 混合求解结果对照 =====")
    compare_case("Q2", G1, ALL, ["G1"], 144880)
    compare_case("Q3", POOL, ALL, ["G1", "G2"], 73575)
    compare_case("Q4", cc, ALL, ["G1", "G2"], 32608)
