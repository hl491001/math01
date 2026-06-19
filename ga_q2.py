# -*- coding: utf-8 -*-
"""问题二：遗传算法(GA)——调用统一元启发式模块。"""
import sys
from solver import build_ops, G1
from heuristic import ga, DEFAULT_GA
sys.stdout.reconfigure(encoding="utf-8")

WORKSHOPS = ["A", "B", "C", "D", "E"]
OPS, JOBS = build_ops(G1, WORKSHOPS)

if __name__ == "__main__":
    p = DEFAULT_GA.copy()
    best_f, best_c, starts = ga(OPS, JOBS, ["G1"], **p)
    print("GA 最优 makespan =", best_f, "s")
    print("(CP-SAT 精确最优 = 144880 s)")
