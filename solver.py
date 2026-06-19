# -*- coding: utf-8 -*-
"""2026 校赛 B 题：聚合柔性作业车间调度（带跨车间转运）的 CP-SAT 精确求解。
覆盖问题一~问题四的统一求解框架。"""
import math, sys, itertools, time
from ortools.sat.python import cp_model
sys.stdout.reconfigure(encoding="utf-8")

CEIL = math.ceil

# ---------- 基础数据 ----------
# 设备类型键
TYPES = ["arm", "wash", "fill", "sensor", "polish"]
NAME = {"arm": "自动化输送臂", "wash": "工业清洗机", "fill": "精密灌装机",
        "sensor": "自动传感多功能机", "polish": "高速抛光机"}
PRICE = {"arm": 50000, "wash": 40000, "fill": 35000, "sensor": 80000, "polish": 75000}
# 单班组台数
G1 = {"arm": 4, "wash": 5, "fill": 5, "sensor": 1, "polish": 1}

# 工序：(编号, 车间, {类型: (效率 m3/h, 工程量 m3)})
RAW = [
    ("A1", "A", {"fill": (200, 300), "arm": (250, 300)}),
    ("A2", "A", {"polish": (100, 500), "wash": (250, 500)}),
    ("A3", "A", {"sensor": (100, 500)}),
    ("B1", "B", {"wash": (100, 120)}),
    ("B2", "B", {"fill": (200, 1500), "arm": (300, 1500)}),
    ("B3", "B", {"fill": (350, 360)}),
    ("B4", "B", {"polish": (120, 360), "sensor": (100, 360)}),
    ("C1", "C", {"wash": (250, 720), "arm": (250, 720)}),
    ("C2", "C", {"fill": (350, 720)}),
    ("C3", "C", {"fill": (200, 360), "arm": (250, 360)}),
    ("C4", "C", {"polish": (120, 400), "wash": (100, 400)}),
    ("C5", "C", {"sensor": (100, 400)}),
    ("D1", "D", {"wash": (250, 600)}),
    ("D2", "D", {"fill": (200, 800), "arm": (300, 800)}),
    ("D3", "D", {"fill": (350, 450)}),
    ("D4", "D", {"polish": (120, 1500), "sensor": (300, 1500)}),
    ("D5", "D", {"sensor": (300, 1500)}),
    ("D6", "D", {"polish": (100, 700)}),
    ("E1", "E", {"wash": (250, 1000)}),
    ("E2", "E", {"fill": (350, 600)}),
    ("E3", "E", {"sensor": (300, 600), "wash": (100, 600)}),
]

# 车间内工序顺序（含 C 车间 C3-C5 重复 3 遍）
ORDER = {
    "A": ["A1", "A2", "A3"],
    "B": ["B1", "B2", "B3", "B4"],
    "C": ["C1", "C2", "C3", "C4", "C5", "C3", "C4", "C5", "C3", "C4", "C5"],
    "D": ["D1", "D2", "D3", "D4", "D5", "D6"],
    "E": ["E1", "E2", "E3"],
}

# 距离表（米），无向
DIST = {}
def _d(a, b, v): DIST[(a, b)] = v; DIST[(b, a)] = v
for a, b, v in [("G1","A",400),("G1","B",620),("G1","C",460),("G1","D",710),("G1","E",400),
                ("G2","A",500),("G2","B",460),("G2","C",620),("G2","D",680),("G2","E",550),
                ("A","B",1020),("A","C",1050),("A","D",900),("A","E",1400),
                ("B","C",1100),("B","D",1630),("B","E",720),
                ("C","D",520),("C","E",850),("D","E",1030)]:
    _d(a, b, v)
SPEED = 2  # m/s

def trans(w1, w2):
    if w1 == w2: return 0
    return CEIL(DIST[(w1, w2)] / SPEED)

# ---------- 构造工序展开列表（带时长） ----------
def build_ops(counts, workshops):
    """counts: 每类设备总台数; workshops: 需整修车间列表。
    返回 ops 列表，每项 dict: id,name,ws,dur(每类秒数),precedes 链接由 jobs 给出。"""
    raw = {r[0]: r for r in RAW}
    ops = []
    jobs = []  # 每个车间一条工序链(ops 下标序列)
    for w in workshops:
        chain = []
        for code in ORDER[w]:
            _, ws, reqs = raw[code]
            dur = {}
            for t, (eff, vol) in reqs.items():
                dur[t] = CEIL(vol / (eff * counts[t]) * 3600)
            idx = len(ops)
            ops.append({"id": code, "ws": ws, "dur": dur, "k": len(ops)})
            chain.append(idx)
        jobs.append(chain)
    return ops, jobs

# ---------- CP-SAT 求解 ----------
def solve(counts, workshops, bases, time_limit=60, log=False, hints=None):
    """bases: 车间初始转运取的基地集合(单班组 ['G1']; 双班组 ['G1','G2'] 取 max)。
    hints: 可选热启动字典 {"starts": [...], "cmax": int, "routes": {t: {(i,j): 0/1}}}，
           仅作搜索引导，不裁剪最优解。"""
    ops, jobs = build_ops(counts, workshops)
    n = len(ops)
    depot = n
    H = sum(max(o["dur"].values()) for o in ops) + 50000  # 时间上界
    m = cp_model.CpModel()
    S = [m.NewIntVar(0, H, f"S{i}") for i in range(n)]
    E = [m.NewIntVar(0, H, f"E{i}") for i in range(n)]
    for i, o in enumerate(ops):
        md = max(o["dur"].values())
        m.Add(E[i] == S[i] + md)
    # 车间内工序先后
    for chain in jobs:
        for a, b in zip(chain, chain[1:]):
            m.Add(S[b] >= E[a])
    # 每类设备(聚合为一台超级机器)的路由：circuit + 转运
    arc_lit = {}  # (t, i, j) -> BoolVar
    for t in TYPES:
        users = [i for i, o in enumerate(ops) if t in o["dur"]]
        if not users: continue
        arcs = []
        for i in users:
            b0 = m.NewBoolVar(f"arc_{t}_dep_{i}")
            arcs.append((depot, i, b0)); arc_lit[(t, depot, i)] = b0
            init = max(trans(base, ops[i]["ws"]) for base in bases)
            m.Add(S[i] >= init).OnlyEnforceIf(b0)
            b1 = m.NewBoolVar(f"arc_{t}_{i}_dep")
            arcs.append((i, depot, b1)); arc_lit[(t, i, depot)] = b1
            for j in users:
                if i == j: continue
                b = m.NewBoolVar(f"arc_{t}_{i}_{j}")
                arcs.append((i, j, b)); arc_lit[(t, i, j)] = b
                m.Add(S[j] >= S[i] + ops[i]["dur"][t] + trans(ops[i]["ws"], ops[j]["ws"])).OnlyEnforceIf(b)
        m.AddCircuit(arcs)
    Cmax = m.NewIntVar(0, H, "Cmax")
    for i in range(n):
        m.Add(Cmax >= E[i])
    m.Minimize(Cmax)
    used_hints = False
    if hints:
        used_hints = True
        for i, s in enumerate(hints["starts"]):
            m.AddHint(S[i], int(s))
            m.AddHint(E[i], int(s) + max(ops[i]["dur"].values()))
        m.AddHint(Cmax, int(hints["cmax"]))
        for t, arcs in hints.get("routes", {}).items():
            for (i, j), val in arcs.items():
                key = (t, i, j)
                if key in arc_lit:
                    m.AddHint(arc_lit[key], int(val))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 8
    if log: solver.parameters.log_search_progress = True
    t0 = time.perf_counter()
    st = solver.Solve(m)
    solve_time = time.perf_counter() - t0
    res = {"status": solver.StatusName(st), "cmax": solver.Value(Cmax) if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
           "obj_bound": solver.BestObjectiveBound, "ops": ops, "solve_time": solve_time, "used_hints": used_hints}
    if res["cmax"] is not None:
        sched = []
        for i, o in enumerate(ops):
            sched.append({"id": o["id"], "ws": o["ws"], "start": solver.Value(S[i]),
                          "end": solver.Value(E[i]), "dur": {t: o["dur"][t] for t in o["dur"]}})
        res["sched"] = sched
    return res

def show(tag, res):
    print(f"\n===== {tag} : status={res['status']} Cmax={res['cmax']} =====")

POOL = {t: 2 * G1[t] for t in TYPES}  # 双班组合并台数

if __name__ == "__main__":
    ALL = ["A", "B", "C", "D", "E"]
    r1 = solve(G1, ["A"], ["G1"], time_limit=20)
    show("Q1 (A only)", r1)
    from hybrid_solve import solve_hybrid, print_hybrid
    r2 = solve_hybrid(G1, ALL, ["G1"], time_limit=120)
    print_hybrid("Q2", r2)
    r3 = solve_hybrid(POOL, ALL, ["G1", "G2"], time_limit=180)
    print_hybrid("Q3", r3)
    best = None
    for kp in range(0, 5):
        for ks in range(0, 5):
            cost = kp * PRICE["polish"] + ks * PRICE["sensor"]
            if cost > 500000: continue
            cc = dict(POOL); cc["polish"] += kp; cc["sensor"] += ks
            rh = solve_hybrid(cc, ALL, ["G1", "G2"], time_limit=40, cold_time_limit=40)
            r = rh["hot"]
            if r["cmax"] is None: continue
            print(f"  buy polish+{kp} sensor+{ks} cost={cost} Cmax={r['cmax']} ({r['status']})")
            key = (r["cmax"], cost)
            if best is None or key < best[0]:
                best = (key, kp, ks, rh)
    (cm, cost), kp, ks, r4 = best
    print(f"\n>>> Q4 best: polish+{kp}, sensor+{ks}, cost={cost}, Cmax={cm}")
