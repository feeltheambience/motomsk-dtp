"""Чертежи брелоков: срезы моделей OpenSCAD по высоте -> лист A4 с размерами.
Запуск из папки obedience-keychains: python3 tools/drawings.py"""
import os, re, subprocess, tempfile
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.path import Path
from matplotlib.patches import PathPatch, Rectangle

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE, DARK, BLACK, WHITE = "#4a78b5", "#2f5690", "#222222", "#f4f4f4"

MODELS = [
    dict(file="1_dumbbell.scad", mod="dumbbell", title="№1  Апорт-гантель с кличкой",
         layers=[("S(1.0)", BASE), ("S(6.5)", DARK), ("difference(){S(5.4);S(6.5);}", WHITE)],
         hole=(-22.5, 7.4, 4.2),
         stack=[("перекладина", 0, 5, BASE), ("блины", 5, 7, DARK), ("кличка", 5, 5.8, WHITE)],
         notes=["Смена цвета: 5.0 мм (кличка)", "Пазы на блинах: глубина 0.6 мм",
                "Длина клички: до ~8 символов", "Параметры: NAME, PLATE_*, BAR_*"]),
    dict(file="2_paw_hand.scad", mod="tag", title="№2  Ладонь + лапа + команда",
         layers=[("S(1.0)", BASE), ("S(3.5)", WHITE)],
         hole=(0, 21.5, 4.2),
         stack=[("основа", 0, 3, BASE), ("рельеф", 3, 4.2, WHITE)],
         notes=["Смена цвета: 3.0 мм", "Оборот: кличка зеркально, глубина 0.6 мм",
                "COMMAND: FUSS! / PLATZ! / SITZ! / HIER! / РЯДОМ!", "Параметры: COMMAND, NAME, D"]),
    dict(file="3_border_collie.scad", mod="keychain", title="№3  Бордер-колли с гантелью",
         layers=[("S(1.0)", BASE), ("S(3.2)", BLACK), ("S(4.1)", WHITE)],
         hole=(25, 30, 4.2),
         stack=[("основа", 0, 2.6, BASE), ("собака", 2.6, 3.8, BLACK), ("отметины", 3.8, 4.4, WHITE)],
         notes=["Смена цвета: 2.6 мм (чёрный), 3.8 мм (белый)", "Отметины выключаются: MARKINGS = false",
                "Кличка на планке, до ~10 символов", "Глаз — отверстие Ø1.6 в слое собаки"]),
    dict(file="4_cones.scad", mod="tag", title="№4  Посыл в квадрат (конусы)",
         layers=[("S(1.0)", BASE), ("S(3.5)", WHITE)],
         hole=(0, 19.5, 4.2),
         stack=[("основа", 0, 3, BASE), ("рельеф", 3, 4.2, WHITE)],
         notes=["Смена цвета: 3.0 мм", "Собака в квадрате: DOG_IN_SQUARE",
                "Полосы на конусах — прорези до основы", "Параметры: NAME, W, H"]),
]

def slice_paths(scad, mod, expr):
    with tempfile.TemporaryDirectory() as d:
        src, out = os.path.join(d, "s.scad"), os.path.join(d, "s.svg")
        open(src, "w").write(
            f"use <{os.path.join(ROOT, scad)}>\n"
            f"module S(z) {{ projection(cut=true) translate([0,0,-z]) {mod}(); }}\n{expr};\n")
        subprocess.run(["openscad", "-q", "-o", out, src], check=True)
        svg = open(out).read()
    verts, codes = [], []
    for d in re.findall(r'd="([^"]+)"', svg):
        for cmd, x, y in re.findall(r"([MLz])?\s*(-?[\d.e+-]+),(-?[\d.e+-]+)", d):
            verts.append((float(x), -float(y)))
            codes.append(Path.MOVETO if cmd == "M" else Path.LINETO)
    return Path(verts, codes) if verts else None

def dim(ax, p1, p2, off, text, horiz=True):
    (x1, y1), (x2, y2) = p1, p2
    kw = dict(color="#333", lw=0.6)
    if horiz:
        y = off
        ax.plot([x1, x1], [y1, y], **kw); ax.plot([x2, x2], [y2, y], **kw)
        ax.annotate("", (x1, y), (x2, y), arrowprops=dict(arrowstyle="<->", lw=0.7))
        ax.text((x1 + x2) / 2, y - 1.0, text, ha="center", va="top", fontsize=9)
    else:
        x = off
        ax.plot([x1, x], [y1, y1], **kw); ax.plot([x2, x], [y2, y2], **kw)
        ax.annotate("", (x, y1), (x, y2), arrowprops=dict(arrowstyle="<->", lw=0.7))
        ax.text(x - 1.0, (y1 + y2) / 2, text, ha="right", va="center", rotation=90, fontsize=9)

def sheet(m):
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.suptitle(f"Брелок obedience {m['title']}", fontsize=15, fontweight="bold", x=0.05, ha="left")
    ax = fig.add_axes([0.04, 0.08, 0.6, 0.82])
    paths = [(slice_paths(m["file"], m["mod"], e), c) for e, c in m["layers"]]
    for p, c in paths:
        if p is not None:
            ax.add_patch(PathPatch(p, facecolor=c, edgecolor="#111", lw=0.5))
    ext = paths[0][0].get_extents()
    x0, y0, x1, y1 = ext.x0, ext.y0, ext.x1, ext.y1
    dim(ax, (x0, y0), (x1, y0), y0 - 5, f"{x1 - x0:.1f}")
    dim(ax, (x0, y0), (x0, y1), x0 - 5, f"{y1 - y0:.1f}", horiz=False)
    hx, hy, hd = m["hole"]
    ax.plot([hx - hd, hx + hd], [hy, hy], color="#c0392b", lw=0.6, ls="-.")
    ax.plot([hx, hx], [hy - hd, hy + hd], color="#c0392b", lw=0.6, ls="-.")
    ax.annotate(f"Ø{hd} сквозное", (hx + hd / 2 * 0.7, hy + hd / 2 * 0.7), (hx + 4, y1 + 4),
                fontsize=9, color="#c0392b", arrowprops=dict(arrowstyle="-", color="#c0392b", lw=0.6))
    dim(ax, (hx, hy), (x1, y1), x1 + 6, f"{y1 - hy:.1f}", horiz=False)
    ax.set_xlim(x0 - 12, x1 + 22); ax.set_ylim(y0 - 10, y1 + 8)
    ax.set_aspect("equal"); ax.axis("off")
    ax.text(x0 - 12, y0 - 10, "Вид сверху, М 1:1 в мм (масштаб листа не 1:1 — размеры по цифрам)",
            fontsize=8, color="#666")

    # слои по высоте: цветная таблица
    sx = fig.add_axes([0.68, 0.56, 0.28, 0.3]); sx.axis("off")
    sx.text(0, 1, "Слои по высоте (снизу вверх)", fontsize=11, fontweight="bold", va="top")
    top = max(st[2] for st in m["stack"])
    for i, (name, z0, z1, c) in enumerate(m["stack"]):
        y = 0.78 - i * 0.2
        sx.add_patch(Rectangle((0, y - 0.06), 0.12, 0.12, facecolor=c, edgecolor="#111", lw=0.6,
                               transform=sx.transAxes))
        sx.text(0.17, y, f"{z0:g} – {z1:g} мм   {name}", va="center", fontsize=10.5)

    tx = fig.add_axes([0.68, 0.08, 0.28, 0.36]); tx.axis("off")
    lines = [f"Габарит: {x1 - x0:.1f} × {y1 - y0:.1f} × {top:g} мм", *m["notes"], "",
             "Печать: сопло 0.4, слой 0.2, 3 периметра,", "заполнение 30–40 %, PETG или PLA,",
             "без поддержек, лицом вверх.", "", f"Исходник: {m['file']}"]
    tx.text(0, 1, "\n".join(lines), va="top", fontsize=9.5, linespacing=1.5)
    return fig

if __name__ == "__main__":
    out = os.path.join(ROOT, "drawings")
    os.makedirs(out, exist_ok=True)
    with PdfPages(os.path.join(out, "obedience_keychains.pdf")) as pdf:
        for m in MODELS:
            fig = sheet(m)
            pdf.savefig(fig)
            fig.savefig(os.path.join(out, m["file"].replace(".scad", ".png")), dpi=110)
            plt.close(fig)
    print("ok", out)
