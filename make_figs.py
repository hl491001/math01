# -*- coding: utf-8 -*-
"""生成论文图表：Q2/Q3/Q4 甘特图、资源载荷热力图、设备利用率热力图、问题四购置收益热力图。
图片输出至 figs/ 目录。"""
import os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from solver import build_ops, solve, G1, POOL, PRICE, TYPES, NAME
sys.stdout.reconfigure(encoding="utf-8")

# ----- 中文字体（不可用则回退英文标签） -----
ZH = True
for f in ["Microsoft YaHei", "SimHei", "SimSun", "KaiTi"]:
    try:
        matplotlib.font_manager.findfont(f, fallback_to_default=False)
        plt.rcParams["font.sans-serif"] = [f]; plt.rcParams["axes.unicode_minus"] = False
        break
    except Exception:
        continue
else:
    ZH = False

EN = {"arm": "Arm", "wash": "Washer", "fill": "Filler", "sensor": "Sensor", "polish": "Polisher"}
def lab(t): return NAME[t] if ZH else EN[t]

ALL = ["A", "B", "C", "D", "E"]
WS_COLOR = {"A": "#4E79A7", "B": "#59A14F", "C": "#E15759", "D": "#F28E2B", "E": "#9C6ADE"}
os.makedirs("figs", exist_ok=True)


def gantt(res, title, path):
    sched = res["sched"]
    fig, ax = plt.subplots(figsize=(11, 4.2))
    for yi, t in enumerate(TYPES):
        for s in sched:
            if t in s["dur"]:
                x0 = s["start"] / 3600.0; w = s["dur"][t] / 3600.0
                ax.broken_barh([(x0, w)], (yi * 10 + 1, 8),
                               facecolors=WS_COLOR[s["ws"]], edgecolor="white", linewidth=0.5)
                if w * 3600 >= 2500:
                    ax.text(x0 + w / 2, yi * 10 + 5, s["id"], ha="center", va="center",
                            fontsize=6.5, color="white")
    ax.set_yticks([yi * 10 + 5 for yi in range(len(TYPES))])
    ax.set_yticklabels([lab(t) for t in TYPES])
    ax.set_xlabel("时间 / h" if ZH else "Time / h")
    ax.set_title(title)
    ax.set_xlim(0, max(s["end"] for s in sched) / 3600.0 * 1.02)
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    ax.legend(handles=[Patch(facecolor=WS_COLOR[w], label=("%s车间" % w) if ZH else ("WS %s" % w)) for w in ALL],
              ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.16), fontsize=8, frameon=False)
    fig.tight_layout(); fig.savefig(path, dpi=150, bbox_inches="tight"); plt.close(fig)
    print("saved", path)


def load_heatmap(path):
    ops, _ = build_ops(G1, ALL)
    M = np.zeros((len(TYPES), len(ALL)))
    for o in ops:
        wj = ALL.index(o["ws"])
        for t in o["dur"]:
            M[TYPES.index(t), wj] += o["dur"][t]
    M /= 3600.0
    fig, ax = plt.subplots(figsize=(7, 4))
    im = ax.imshow(M, cmap="YlOrRd", aspect="auto")
    ax.set_xticks(range(len(ALL))); ax.set_xticklabels([("%s车间" % w) if ZH else w for w in ALL])
    ax.set_yticks(range(len(TYPES))); ax.set_yticklabels([lab(t) for t in TYPES])
    for i in range(len(TYPES)):
        for j in range(len(ALL)):
            if M[i, j] > 0:
                ax.text(j, i, f"{M[i, j]:.1f}", ha="center", va="center", fontsize=8,
                        color="black" if M[i, j] < M.max() * 0.6 else "white")
    ax.set_title("各类设备在各车间的作业载荷 / h（单班组）" if ZH else "Resource load by workshop / h")
    fig.colorbar(im, ax=ax, label="作业载荷 / h" if ZH else "load / h")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)
    print("saved", path)


def util_heatmap(path):
    cc = dict(POOL); cc["polish"] += 3; cc["sensor"] += 3
    cases = [("Q2", G1, ["G1"]), ("Q3", POOL, ["G1", "G2"]), ("Q4", cc, ["G1", "G2"])]
    M = np.zeros((len(TYPES), len(cases)))
    for cj, (tag, counts, bases) in enumerate(cases):
        ops, _ = build_ops(counts, ALL)
        res = solve(counts, ALL, bases, time_limit=120)
        cmax = res["cmax"]
        busy = {t: 0 for t in TYPES}
        for o in ops:
            for t in o["dur"]:
                busy[t] += o["dur"][t]
        for ti, t in enumerate(TYPES):
            M[ti, cj] = busy[t] / cmax * 100.0
    fig, ax = plt.subplots(figsize=(6, 4))
    im = ax.imshow(M, cmap="Blues", aspect="auto", vmin=0, vmax=100)
    ax.set_xticks(range(len(cases))); ax.set_xticklabels([c[0] for c in cases])
    ax.set_yticks(range(len(TYPES))); ax.set_yticklabels([lab(t) for t in TYPES])
    for i in range(len(TYPES)):
        for j in range(len(cases)):
            ax.text(j, i, f"{M[i, j]:.0f}%", ha="center", va="center", fontsize=8,
                    color="black" if M[i, j] < 60 else "white")
    ax.set_title("设备利用率（忙时/总工期）" if ZH else "Utilization (busy/makespan)")
    fig.colorbar(im, ax=ax, label="利用率 / %" if ZH else "util / %")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)
    print("saved", path)


def buy_heatmap(path):
    KP, KS = 5, 5
    M = np.full((KP, KS), np.nan)
    for kp in range(KP):
        for ks in range(KS):
            if kp * PRICE["polish"] + ks * PRICE["sensor"] > 500000:
                continue
            cc = dict(POOL); cc["polish"] += kp; cc["sensor"] += ks
            M[kp, ks] = solve(cc, ALL, ["G1", "G2"], time_limit=40)["cmax"] / 3600.0
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    cmap = plt.cm.viridis.copy(); cmap.set_bad("#cccccc")
    im = ax.imshow(M, cmap=cmap, aspect="auto", origin="lower")
    ax.set_xlabel("增购自动传感多功能机台数" if ZH else "Sensor added")
    ax.set_ylabel("增购高速抛光机台数" if ZH else "Polisher added")
    ax.set_xticks(range(KS)); ax.set_yticks(range(KP))
    for kp in range(KP):
        for ks in range(KS):
            if not np.isnan(M[kp, ks]):
                ax.text(ks, kp, f"{M[kp, ks]:.1f}", ha="center", va="center", fontsize=8,
                        color="white" if M[kp, ks] > np.nanmin(M) + (np.nanmax(M) - np.nanmin(M)) * 0.5 else "black")
    ax.plot(3, 3, marker="*", color="red", markersize=18)   # 最优方案 (+3,+3)
    ax.set_title("购置组合对总工期的影响 / h（灰=超预算，星=最优）" if ZH else "Makespan vs purchase / h")
    fig.colorbar(im, ax=ax, label="总工期 / h" if ZH else "makespan / h")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)
    print("saved", path)


if __name__ == "__main__":
    r2 = solve(G1, ALL, ["G1"], time_limit=120)
    r3 = solve(POOL, ALL, ["G1", "G2"], time_limit=180)
    cc = dict(POOL); cc["polish"] += 3; cc["sensor"] += 3
    r4 = solve(cc, ALL, ["G1", "G2"], time_limit=60)
    gantt(r2, "问题二 调度甘特图（Cmax=144880 s）" if ZH else "Q2 Gantt", "figs/gantt_q2.png")
    gantt(r3, "问题三 调度甘特图（Cmax=73575 s）" if ZH else "Q3 Gantt", "figs/gantt_q3.png")
    gantt(r4, "问题四 调度甘特图（Cmax=32608 s）" if ZH else "Q4 Gantt", "figs/gantt_q4.png")
    load_heatmap("figs/load_heatmap.png")
    util_heatmap("figs/util_heatmap.png")
    buy_heatmap("figs/buy_heatmap.png")
    print("ZH font:", ZH)
