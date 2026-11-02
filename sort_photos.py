#!/usr/bin/env python3
"""
Разбирает загруженные фото: находит в корне репозитория и в photos/ любые
картинки (jpg, jpeg, png, heic) с любыми именами, узнаёт по содержимому,
какому посту очереди они соответствуют, и сохраняет как photos/<файл из очереди>.jpg:
JPEG, до 1440 px, пропорции в рамках Instagram, без геометок и EXIF.
Исходник после этого удаляется (в публичном репозитории не остаются GPS-данные).
"""
import os, json, glob
from PIL import Image, ImageOps
try:
    import pillow_heif; pillow_heif.register_heif_opener()
except ImportError:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
PH = os.path.join(BASE, "photos")
os.makedirs(PH, exist_ok=True)
q = json.load(open(os.path.join(BASE, "queue.json"), encoding="utf-8"))
targets = {it["file"] for it in q}
EXT = (".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp")
LIMIT = 95   # макс. расхождение отпечатков из 256
MARGIN = 25  # насколько лучший кандидат должен опережать второго


def dhash(im, n=16):
    g = im.convert("L").resize((n + 1, n), Image.LANCZOS)
    p = list(g.get_flattened_data()) if hasattr(g, "get_flattened_data") else list(g.getdata())
    return "".join("1" if p[r*(n+1)+c] > p[r*(n+1)+c+1] else "0" for r in range(n) for c in range(n))


def dist(a, b):
    return sum(x != y for x, y in zip(a, b))


def fit(im, trim=None):
    if trim:  # срезать края с впечатанной датой фотоаппарата
        w, h = im.size
        im = im.crop((int(w*trim.get("left", 0)), int(h*trim.get("top", 0)),
                      w - int(w*trim.get("right", 0)), h - int(h*trim.get("bottom", 0))))
    w, h = im.size; r = w / h
    if r < 0.8:
        nh = int(w / 0.8); t = (h - nh) // 2; im = im.crop((0, t, w, t + nh))
    elif r > 1.91:
        nw = int(h * 1.91); l = (w - nw) // 2; im = im.crop((l, 0, l + nw, h))
    if im.width > 1440:
        im = im.resize((1440, round(im.height * 1440 / im.width)), Image.LANCZOS)
    return im


cands = [f for d in (BASE, PH) for f in glob.glob(os.path.join(d, "*"))
         if f.lower().endswith(EXT) and os.path.basename(f) not in targets]
changed = False
for f in cands:
    try:
        im = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
    except Exception as e:
        print("не открылось:", os.path.basename(f), e); continue
    h = dhash(im)
    ranked = sorted(q, key=lambda it: dist(h, it["ref_hash"]))
    best = ranked[0]; d = dist(h, best["ref_hash"]); d2 = dist(h, ranked[1]["ref_hash"])
    if d > LIMIT or d2 - d < MARGIN:
        print(f"не узнано: {os.path.basename(f)} (ближайшее {best['file']}, {d})"); continue
    fit(im, best.get("trim")).save(os.path.join(PH, best["file"]), "JPEG", quality=92)  # без EXIF
    os.remove(f); changed = True
    print(f"{os.path.basename(f)} → photos/{best['file']} (совпадение {256-d}/256)")

missing = [it["file"] for it in q if it["status"] == "pending" and not os.path.exists(os.path.join(PH, it["file"]))]
print("Не хватает фото:", ", ".join(missing) if missing else "нет, все на месте")
