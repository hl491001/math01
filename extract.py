# -*- coding: utf-8 -*-
"""抽取各问最优解的逐设备调度明细，按设备类型给出有序时间线，供结果表使用。"""
import sys
from solver import solve, G1, POOL, TYPES, NAME, trans
sys.stdout.reconfigure(encoding="utf-8")

def hhmmss(s):
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

def timeline(res, label, bases):
    print(f"\n################ {label}  Cmax={res['cmax']} ################")
    sched = {s["id"]+"_"+str(k): s for k, s in enumerate(res["sched"])}
    items = res["sched"]
    for t in TYPES:
        users = [s for s in items if t in s["dur"]]
        if not users: continue
        users.sort(key=lambda s: s["start"])
        print(f"\n--- {NAME[t]} ({t}) ---")
        prev_ws = None
        for s in users:
            d = s["dur"][t]
            st, en = s["start"], s["start"] + d
            mv = ""
            if prev_ws is None:
                init = max(trans(b, s["ws"]) for b in bases)
                mv = f"[init->{s['ws']} 转运{init}s]"
            elif prev_ws != s["ws"]:
                mv = f"[{prev_ws}->{s['ws']} 转运{trans(prev_ws,s['ws'])}s]"
            print(f"  {s['ws']}-{s['id']:>3}  {hhmmss(st)} -> {hhmmss(en)}  dur={d:>6}s {mv}")
            prev_ws = s["ws"]

ALL = ["A", "B", "C", "D", "E"]
r1 = solve(G1, ["A"], ["G1"], 20); timeline(r1, "Q1", ["G1"])
r2 = solve(G1, ALL, ["G1"], 120); timeline(r2, "Q2", ["G1"])
r3 = solve(POOL, ALL, ["G1", "G2"], 180); timeline(r3, "Q3", ["G1", "G2"])
cc = dict(POOL); cc["polish"] += 3; cc["sensor"] += 3
r4 = solve(cc, ALL, ["G1", "G2"], 60); timeline(r4, "Q4 (polish+3,sensor+3)", ["G1", "G2"])
