#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
watch.py — тестовая оболочка для проверки детекции игроков.

Скармливаете ссылку на YouTube (или локальный видеофайл) — оболочка
подсвечивает людей, определяет команду по цвету формы и отдельно
помечает судей. Есть пауза, перемотка и покадровый просмотр.

Примеры:
    python watch.py https://www.youtube.com/watch?v=jx4aFSTklTA \
        --team "Красные:red" --team "Синие:blue" --ref yellow

    python watch.py round.mp4 --team "A:black" --team "B:green" --every 3

Управление в окне:
    ПРОБЕЛ      пауза / продолжить
    A / D (←/→) перемотка -5 / +5 сек
    Z / X       перемотка -30 / +30 сек
    .           шаг на один кадр (в паузе)
    R           фильтр: все → только судьи → только игроки
    T           вкл/выкл детекцию (сырое видео)
    [ / ]       скорость воспроизведения
    Q / ESC     выход
"""

import argparse
import re
import sys
import time
from collections import Counter, deque
from pathlib import Path

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Цвета команд
# ---------------------------------------------------------------------------

# BGR-значения "эталонных" цветов, которые можно называть по имени
NAMED_COLORS = {
    "red": (40, 40, 220), "красный": (40, 40, 220),
    "blue": (220, 90, 30), "синий": (220, 90, 30),
    "green": (60, 180, 60), "зеленый": (60, 180, 60), "зелёный": (60, 180, 60),
    "yellow": (40, 220, 230), "желтый": (40, 220, 230), "жёлтый": (40, 220, 230),
    "orange": (30, 140, 255), "оранжевый": (30, 140, 255),
    "purple": (200, 60, 160), "фиолетовый": (200, 60, 160),
    "white": (235, 235, 235), "белый": (235, 235, 235),
    "black": (25, 25, 25), "черный": (25, 25, 25), "чёрный": (25, 25, 25),
}

UNKNOWN_BGR = (160, 160, 160)
REF_BGR = (255, 255, 255)


def parse_color(text):
    """'red' | 'красный' | '#rrggbb' -> BGR-кортеж."""
    text = text.strip().lower()
    if text in NAMED_COLORS:
        return NAMED_COLORS[text]
    m = re.fullmatch(r"#?([0-9a-f]{6})", text)
    if m:
        v = m.group(1)
        r, g, b = int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
        return (b, g, r)
    raise argparse.ArgumentTypeError(
        f"не понял цвет '{text}'. Доступно: {', '.join(sorted(set(NAMED_COLORS)))} или #rrggbb"
    )


def parse_team(text):
    """'Имя:цвет' или просто 'цвет' -> (имя, BGR)."""
    if ":" in text:
        name, color = text.split(":", 1)
        name = name.strip()
    else:
        name, color = text.strip(), text
    return name, parse_color(color)


class ColorRef:
    """Эталон цвета формы: хроматический (по тону) или чёрный/белый (по яркости)."""

    def __init__(self, name, bgr, is_ref=False):
        self.name = name
        self.bgr = bgr
        self.is_ref = is_ref
        h, s, v = cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2HSV)[0][0]
        self.hue = int(h)
        if s < 60 and v < 100:
            self.kind = "black"
        elif s < 60 and v > 160:
            self.kind = "white"
        else:
            self.kind = "hue"

    def score(self, H, S, V):
        """Доля пикселей торса, похожих на этот эталон (0..1)."""
        if self.kind == "hue":
            dh = np.abs(H.astype(np.int16) - self.hue)
            dh = np.minimum(dh, 180 - dh)
            match = (S > 70) & (V > 60) & (dh <= 14)
        elif self.kind == "black":
            match = (V < 70) & (S < 130)
        else:  # white
            match = (S < 60) & (V > 170)
        return float(np.mean(match))


def classify_team(frame, xyxy, refs, min_score=0.12):
    """Определяет команду по цвету верхней части бокса. Возвращает ColorRef или None."""
    x1, y1, x2, y2 = (int(v) for v in xyxy)
    w, h = x2 - x1, y2 - y1
    if w < 6 or h < 10:
        return None
    # торс: центральная полоса, без ног и краёв (там фон)
    tx1 = x1 + int(0.2 * w)
    tx2 = x2 - int(0.2 * w)
    ty1 = y1 + int(0.1 * h)
    ty2 = y1 + int(0.6 * h)
    crop = frame[max(ty1, 0):max(ty2, 1), max(tx1, 0):max(tx2, 1)]
    if crop.size == 0:
        return None
    if crop.shape[0] > 48 or crop.shape[1] > 48:
        crop = cv2.resize(crop, (32, 32), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[..., 0].ravel(), hsv[..., 1].ravel(), hsv[..., 2].ravel()
    best, best_score = None, 0.0
    for ref in refs:
        sc = ref.score(H, S, V)
        if sc > best_score:
            best, best_score = ref, sc
    if best is not None and best_score >= min_score:
        return best
    return None


# ---------------------------------------------------------------------------
# Источник видео
# ---------------------------------------------------------------------------

def resolve_source(src, cache_dir, max_height):
    """Локальный путь — как есть; YouTube-ссылка — скачиваем через yt-dlp в кэш."""
    if Path(src).exists():
        return str(src)
    if not re.match(r"https?://", src):
        sys.exit(f"Файл не найден и это не ссылка: {src}")

    try:
        import yt_dlp
    except ImportError:
        sys.exit("Для скачивания с YouTube нужен yt-dlp: pip install yt-dlp")

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    # видео без звука (звук для теста не нужен, cv2 его всё равно не играет)
    fmt = (
        f"bestvideo[height<={max_height}][ext=mp4]/"
        f"best[height<={max_height}][ext=mp4]/"
        f"best[height<={max_height}]/best"
    )
    opts = {
        "format": fmt,
        "outtmpl": str(cache_dir / "%(id)s_%(height)sp.%(ext)s"),
        "noplaylist": True,
        "quiet": False,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(src, download=False)
        path = Path(ydl.prepare_filename(info))
        if path.exists():
            print(f"[кэш] уже скачано: {path}")
        else:
            print(f"[yt-dlp] скачиваю {info.get('title', src)} ...")
            ydl.download([src])
        if not path.exists():
            sys.exit(f"yt-dlp отработал, но файла нет: {path}")
        return str(path)


# ---------------------------------------------------------------------------
# Детектор
# ---------------------------------------------------------------------------

class Detector:
    """YOLO + встроенный ByteTrack. Возвращает [(xyxy, track_id), ...]."""

    def __init__(self, model_path, conf, imgsz):
        from ultralytics import YOLO
        self.model = YOLO(model_path)
        self.conf = conf
        self.imgsz = imgsz

    def detect(self, frame):
        res = self.model.track(
            frame, classes=[0], conf=self.conf, imgsz=self.imgsz,
            persist=True, verbose=False, tracker="bytetrack.yaml",
        )[0]
        out = []
        if res.boxes is None:
            return out
        ids = res.boxes.id
        for i, box in enumerate(res.boxes.xyxy.cpu().numpy()):
            tid = int(ids[i]) if ids is not None else -1
            out.append((box, tid))
        return out

    def reset_tracker(self):
        try:
            for t in self.model.predictor.trackers:
                t.reset()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Отрисовка
# ---------------------------------------------------------------------------

def draw_detections(frame, dets, labels, filter_mode):
    counts = Counter()
    for (xyxy, tid) in dets:
        ref = labels.get(tid)
        counts[ref.name if ref else "?"] += 1
        if filter_mode == "refs" and (ref is None or not ref.is_ref):
            continue
        if filter_mode == "players" and ref is not None and ref.is_ref:
            continue
        x1, y1, x2, y2 = (int(v) for v in xyxy)
        if ref is None:
            color, tag, thick = UNKNOWN_BGR, "?", 1
        elif ref.is_ref:
            color, tag, thick = REF_BGR, "СУДЬЯ", 3
        else:
            color, tag, thick = ref.bgr, ref.name, 2
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thick)
        text = f"{tag}" + (f" #{tid}" if tid >= 0 else "")
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_COMPLEX, 0.45, 1)
        cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 4, y1), color, -1)
        cv2.putText(frame, text, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_COMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
    return counts


def draw_hud(frame, counts, refs, pos_s, dur_s, speed, paused, filter_mode, det_on):
    lines = []
    total = sum(counts.values())
    parts = [f"{r.name}: {counts.get(r.name, 0)}" for r in refs]
    parts.append(f"?: {counts.get('?', 0)}")
    lines.append(f"Людей: {total}   " + "   ".join(parts))
    state = "ПАУЗА" if paused else f"x{speed:g}"
    fmode = {"all": "все", "refs": "только судьи", "players": "только игроки"}[filter_mode]
    det = "вкл" if det_on else "ВЫКЛ"
    lines.append(
        f"{time.strftime('%M:%S', time.gmtime(pos_s))} / "
        f"{time.strftime('%M:%S', time.gmtime(dur_s))}   [{state}]   "
        f"фильтр: {fmode}   детекция: {det}"
    )
    lines.append("ПРОБЕЛ пауза | A/D +-5с | Z/X +-30с | . кадр | R фильтр | T детекция | [ ] скорость | Q выход")
    y = 22
    for line in lines:
        cv2.putText(frame, line, (10, y), cv2.FONT_HERSHEY_COMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(frame, line, (10, y), cv2.FONT_HERSHEY_COMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        y += 24


# ---------------------------------------------------------------------------
# Главный цикл
# ---------------------------------------------------------------------------

KEYS_LEFT = {ord("a"), ord("A"), 81, 2424832, 65361}
KEYS_RIGHT = {ord("d"), ord("D"), 83, 2555904, 65363}


def main():
    p = argparse.ArgumentParser(
        description="Тестовый просмотр видео с подсветкой игроков по командам",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("source", help="ссылка на YouTube или путь к видеофайлу")
    p.add_argument("--team", action="append", default=[], metavar="ИМЯ:ЦВЕТ",
                   help="команда, например 'Красные:red' или 'B:#3050ff' (можно несколько раз)")
    p.add_argument("--ref", metavar="ЦВЕТ", default=None,
                   help="цвет формы судей, например yellow или orange")
    p.add_argument("--model", default="yolov8n.pt",
                   help="веса YOLO (по умолчанию yolov8n.pt, скачается сам)")
    p.add_argument("--conf", type=float, default=0.3, help="порог уверенности детектора")
    p.add_argument("--imgsz", type=int, default=640, help="размер входа сети (480 быстрее, 960 точнее)")
    p.add_argument("--every", type=int, default=2,
                   help="детекция каждого N-го кадра (больше = быстрее на слабом железе)")
    p.add_argument("--max-height", type=int, default=720, help="максимальное качество скачивания с YouTube")
    p.add_argument("--cache-dir", default="video_cache", help="куда складывать скачанные ролики")
    p.add_argument("--save", metavar="OUT.MP4", default=None, help="записать размеченное видео в файл")
    p.add_argument("--no-window", action="store_true", help="без окна (только --save, для серверов)")
    p.add_argument("--max-frames", type=int, default=None, help="обработать не больше N кадров (для тестов)")
    args = p.parse_args()

    refs = [ColorRef(name, bgr) for name, bgr in (parse_team(t) for t in args.team)]
    if args.ref:
        refs.append(ColorRef("СУДЬЯ", parse_color(args.ref), is_ref=True))
    if not refs:
        print("Команды не заданы — подсвечиваю всех людей одним цветом "
              "(пример: --team 'A:red' --team 'B:blue' --ref yellow)")

    path = resolve_source(args.source, args.cache_dir, args.max_height)
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        sys.exit(f"Не смог открыть видео: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    dur_s = (cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) / fps

    print("[YOLO] загружаю модель (при первом запуске скачаются веса)...")
    detector = Detector(args.model, args.conf, args.imgsz)

    writer = None
    if args.save:
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        writer = cv2.VideoWriter(args.save, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    window = not args.no_window
    if window:
        cv2.namedWindow("drone-vision", cv2.WINDOW_NORMAL)

    votes = {}          # track_id -> deque последних меток команды
    labels = {}         # track_id -> ColorRef (сглаженная метка)
    dets = []
    paused = False
    step = False
    speed = 1.0
    filter_mode = "all"
    det_on = True
    frame_idx = 0
    frame = None
    annotated = None

    def do_seek(delta_s):
        nonlocal dets, paused
        pos = cap.get(cv2.CAP_PROP_POS_MSEC) + delta_s * 1000
        pos = max(0.0, min(pos, dur_s * 1000 - 500))
        cap.set(cv2.CAP_PROP_POS_MSEC, pos)
        votes.clear()
        labels.clear()
        dets = []
        detector.reset_tracker()

    t_frame = time.time()
    while True:
        advanced = False
        if not paused or step:
            ok, frame = cap.read()
            step = False
            if not ok:
                if args.max_frames or args.no_window:
                    break
                paused = True  # конец ролика — стоим на последнем кадре
            else:
                advanced = True
                frame_idx += 1
                if det_on and (frame_idx % max(args.every, 1) == 0 or not dets):
                    dets = detector.detect(frame)
                    for (xyxy, tid) in dets:
                        ref = classify_team(frame, xyxy, refs) if refs else None
                        votes.setdefault(tid, deque(maxlen=15)).append(
                            ref.name if ref else None)
                        # сглаживание: команда = самая частая метка за последние кадры
                        top = Counter(votes[tid]).most_common(1)[0][0]
                        labels[tid] = next((r for r in refs if r.name == top), None)

        if frame is None:
            break
        if advanced or annotated is None:
            annotated = frame.copy()
            counts = Counter()
            if det_on:
                counts = draw_detections(annotated, dets, labels, filter_mode)
            draw_hud(annotated, counts, refs,
                     cap.get(cv2.CAP_PROP_POS_MSEC) / 1000, dur_s,
                     speed, paused, filter_mode, det_on)
            if writer and advanced:
                writer.write(annotated)

        if args.max_frames and frame_idx >= args.max_frames:
            break

        if window:
            cv2.imshow("drone-vision", annotated)
            # выдерживаем темп воспроизведения
            target_dt = 1.0 / (fps * speed)
            wait_ms = max(1, int((target_dt - (time.time() - t_frame)) * 1000))
            key = cv2.waitKeyEx(wait_ms if not paused else 50)
            t_frame = time.time()
            if key in (27, ord("q"), ord("Q")):
                break
            elif key == ord(" "):
                paused = not paused
            elif key in KEYS_LEFT:
                do_seek(-5)
            elif key in KEYS_RIGHT:
                do_seek(+5)
            elif key in (ord("z"), ord("Z")):
                do_seek(-30)
            elif key in (ord("x"), ord("X")):
                do_seek(+30)
            elif key == ord("."):
                step = True
            elif key in (ord("r"), ord("R")):
                filter_mode = {"all": "refs", "refs": "players", "players": "all"}[filter_mode]
                annotated = None  # перерисовать
            elif key in (ord("t"), ord("T")):
                det_on = not det_on
                annotated = None
            elif key == ord("["):
                speed = max(0.25, speed / 2)
            elif key == ord("]"):
                speed = min(4.0, speed * 2)
            if cv2.getWindowProperty("drone-vision", cv2.WND_PROP_VISIBLE) < 1:
                break

    cap.release()
    if writer:
        writer.release()
        print(f"[запись] размеченное видео: {args.save}")
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
