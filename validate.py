# -*- coding: utf-8 -*-
"""调度方案可行性校验器（独立于求解器，用于杜绝"看起来短但不可行"的解）。
检查四类约束：
  1) 车间内工序先后：后序开工 >= 前序完工（完工取双设备较晚者）；
  2) 同类设备不重叠：同一类型设备的各占用区间两两不相交；
  3) 转运充足：同类相邻作业跨车间时，间隔 >= 转运时间；首作业 >= 由基地出发的转运；
  4) 双设备完工：工序完工 = 两类设备结束时间的较大值。
适用于 CP-SAT、遗传算法、模拟退火三种来源的解。"""
import sys
from solver import build_ops, trans, TYPES, NAME
sys.stdout.reconfigure(encoding="utf-8")


def validate(starts, ops, jobs, bases):
    """starts: 按工序下标给出的开工时刻列表。
    返回 (是否可行, 违规明细列表, makespan)。"""
    n = len(ops)
    end = [starts[i] + max(ops[i]["dur"].values()) for i in range(n)]  # 双设备取较晚者
    vio = []

    # (1) 车间内工序先后
    for chain in jobs:
        for a, b in zip(chain, chain[1:]):
            if starts[b] < end[a]:
                vio.append(f"先后违规: {ops[a]['id']}(完工{end[a]}) -> {ops[b]['id']}(开工{starts[b]})")

    # (2)(3) 各类设备：不重叠 + 转运充足
    for t in TYPES:
        users = [i for i in range(n) if t in ops[i]["dur"]]
        users.sort(key=lambda i: starts[i])
        if users:
            init = max(trans(base, ops[users[0]]["ws"]) for base in bases)
            if starts[users[0]] < init:
                vio.append(f"初始转运不足[{NAME[t]}]: 首作业{ops[users[0]]['id']}开工{starts[users[0]]}<需{init}")
        for x, y in zip(users, users[1:]):
            x_end = starts[x] + ops[x]["dur"][t]              # 该设备完成本职的时刻
            if starts[y] < x_end:
                vio.append(f"设备重叠[{NAME[t]}]: {ops[x]['id']} 与 {ops[y]['id']} 时间重叠")
            else:
                need = x_end + trans(ops[x]["ws"], ops[y]["ws"])
                if starts[y] < need:
                    vio.append(f"转运不足[{NAME[t]}]: {ops[x]['id']}({ops[x]['ws']})->"
                               f"{ops[y]['id']}({ops[y]['ws']}) 间隔不足，需到{need}实到{starts[y]}")

    return (len(vio) == 0, vio, max(end))


def validate_result(res, counts, workshops, bases):
    """校验 solver.solve 返回的 CP-SAT 解。"""
    ops, jobs = build_ops(counts, workshops)
    starts = [s["start"] for s in res["sched"]]   # sched 与 build_ops 同序
    return validate(starts, ops, jobs, bases)


if __name__ == "__main__":
    from solver import solve, G1, POOL, PRICE
    ALL = ["A", "B", "C", "D", "E"]
    cases = [
        ("Q2", G1, ALL, ["G1"]),
        ("Q3", POOL, ALL, ["G1", "G2"]),
    ]
    cc = dict(POOL); cc["polish"] += 3; cc["sensor"] += 3
    cases.append(("Q4", cc, ALL, ["G1", "G2"]))
    for tag, counts, ws, bases in cases:
        res = solve(counts, ws, bases, time_limit=120)
        ok, vio, cmax = validate_result(res, counts, ws, bases)
        print(f"{tag}: CP-SAT Cmax={res['cmax']} 校验makespan={cmax} 可行={ok} 违规数={len(vio)}")
        for v in vio[:5]:
            print("   -", v)
