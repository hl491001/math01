# -*- coding: utf-8 -*-
"""元启发式层：遗传算法 + 模拟退火，为 CP-SAT 提供可行上界与热启动 Hint。
解码口径与正文聚合模型一致：双设备取 max 完工、编组并行转场、设备提前释放。"""
import random, math, time, sys
from solver import build_ops, trans, TYPES
sys.stdout.reconfigure(encoding="utf-8")

# 推荐参数（由 tune_params.py 在 Q2 上网格搜索后确定，此处为默认）
DEFAULT_GA = {"pop_size": 150, "gens": 800, "pm": 0.2, "seed": 0}
DEFAULT_SA = {"T0": 4000.0, "Tend": 1e-2, "alpha": 0.97, "iters": 400, "seed": 0}


def make_template(jobs):
    tpl = []
    for w in range(len(jobs)):
        tpl += [w] * len(jobs[w])
    return tpl


def decode_full(chrom, ops, jobs, bases):
    """串行解码，返回 (makespan, 各工序开工时刻列表)。"""
    free = {t: 0 for t in TYPES}
    loc = {t: None for t in TYPES}
    ptr = [0] * len(jobs)
    done = [0] * len(jobs)
    starts = [0] * len(ops)
    cmax = 0
    for w in chrom:
        o = jobs[w][ptr[w]]; ptr[w] += 1
        ws = ops[o]["ws"]; dur = ops[o]["dur"]
        start = done[w]
        for t in dur:
            if loc[t] is None:
                ready = free[t] + max(trans(b, ws) for b in bases)
            else:
                ready = free[t] + trans(loc[t], ws)
            start = max(start, ready)
        for t in dur:
            free[t] = start + dur[t]; loc[t] = ws
        comp = start + max(dur.values())
        done[w] = comp; starts[o] = start; cmax = max(cmax, comp)
    return cmax, starts


def extract_routes(starts, ops, n_depot):
    """由开工时刻反推各资源访问序，生成 AddCircuit 弧 Hint（1=选中）。"""
    routes = {}
    for t in TYPES:
        users = sorted([i for i, o in enumerate(ops) if t in o["dur"]],
                       key=lambda i: starts[i])
        if not users:
            continue
        arcs = {}
        arcs[(n_depot, users[0])] = 1
        for a, b in zip(users, users[1:]):
            arcs[(a, b)] = 1
        arcs[(users[-1], n_depot)] = 1
        routes[t] = arcs
    return routes


def pox(p1, p2, nw):
    jset = set(random.sample(range(nw), random.randint(1, nw - 1)))
    child = [g if g in jset else None for g in p1]
    fill = [g for g in p2 if g not in jset]
    k = 0
    for i in range(len(child)):
        if child[i] is None:
            child[i] = fill[k]; k += 1
    return child


def ga(ops, jobs, bases, pop_size=150, gens=800, pm=0.2, seed=0):
    random.seed(seed)
    nw = len(jobs); tpl = make_template(jobs)
    pop = [random.sample(tpl, len(tpl)) for _ in range(pop_size)]
    fit = [decode_full(c, ops, jobs, bases)[0] for c in pop]
    bi = min(range(pop_size), key=lambda i: fit[i])
    bc, bf = pop[bi][:], fit[bi]
    for _ in range(gens):
        npop, nfit = [bc[:]], [bf]
        while len(npop) < pop_size:
            a = pop[min(random.sample(range(pop_size), 3), key=lambda i: fit[i])]
            b = pop[min(random.sample(range(pop_size), 3), key=lambda i: fit[i])]
            c = pox(a, b, nw)
            if random.random() < pm:
                i, j = random.sample(range(len(c)), 2); c[i], c[j] = c[j], c[i]
            npop.append(c); nfit.append(decode_full(c, ops, jobs, bases)[0])
        pop, fit = npop, nfit
        i = min(range(pop_size), key=lambda j: fit[j])
        if fit[i] < bf:
            bf, bc = fit[i], pop[i][:]
    return bf, bc, decode_full(bc, ops, jobs, bases)[1]


def sa(ops, jobs, bases, chrom=None, T0=4000.0, Tend=1e-2, alpha=0.97, iters=400, seed=0):
    random.seed(seed)
    tpl = make_template(jobs)
    cur = chrom[:] if chrom else random.sample(tpl, len(tpl))
    cur_f = decode_full(cur, ops, jobs, bases)[0]
    best, best_f = cur[:], cur_f
    T = T0
    while T > Tend:
        for _ in range(iters):
            nb = cur[:]
            if random.random() < 0.5:
                i, j = random.sample(range(len(nb)), 2); nb[i], nb[j] = nb[j], nb[i]
            else:
                i = random.randrange(len(nb)); g = nb.pop(i)
                nb.insert(random.randrange(len(nb) + 1), g)
            f = decode_full(nb, ops, jobs, bases)[0]
            if f <= cur_f or random.random() < math.exp((cur_f - f) / T):
                cur, cur_f = nb, f
                if f < best_f:
                    best, best_f = nb[:], f
        T *= alpha
    return best_f, best, decode_full(best, ops, jobs, bases)[1]


def run_metaheuristic(ops, jobs, bases, ga_params=None, sa_params=None):
    """GA 求初解 → SA 局部改良，返回 (上界, starts, chrom, 耗时秒)。"""
    ga_params = ga_params or DEFAULT_GA
    sa_params = sa_params or DEFAULT_SA
    t0 = time.perf_counter()
    gf, gchrom, gstarts = ga(ops, jobs, bases, **ga_params)
    sf, schrom, sstarts = sa(ops, jobs, bases, chrom=gchrom, **sa_params)
    elapsed = time.perf_counter() - t0
    if sf <= gf:
        return sf, sstarts, schrom, elapsed
    return gf, gstarts, gchrom, elapsed
