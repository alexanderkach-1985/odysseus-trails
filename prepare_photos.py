#!/usr/bin/env python3
"""
Готовит фото к публикации: переводит в JPEG, уменьшает до 1440 px по ширине
и подрезает пропорции в допустимый для Instagram диапазон (от 4:5 до 1.91:1).

Использование:
  python3 prepare_photos.py исходная_папка
Файлы в исходной папке должны называться так же, как в queue.json
(01_rhinos.jpg / .heic / .png ...). Результат — в папке photos/.
Нужен Pillow (pip install pillow; для HEIC ещё pillow-heif).
"""
import os, sys, json
from PIL import Image, ImageOps
try:
    import pillow_heif; pillow_heif.register_heif_opener()
except ImportError:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else "."
out = os.path.join(BASE, "photos"); os.makedirs(out, exist_ok=True)
queue = json.load(open(os.path.join(BASE, "queue.json"), encoding="utf-8"))
files = {os.path.splitext(f)[0]: f for f in os.listdir(src)}

for item in queue:
    stem = os.path.splitext(item["file"])[0]
    if stem not in files:
        print("нет исходника:", stem); continue
    im = ImageOps.exif_transpose(Image.open(os.path.join(src, files[stem]))).convert("RGB")
    w, h = im.size; r = w / h
    if r < 0.8:       # слишком вытянуто по вертикали -> 4:5
        nh = int(w / 0.8); top = (h - nh) // 2; im = im.crop((0, top, w, top + nh))
    elif r > 1.91:    # слишком широкое -> 1.91:1
        nw = int(h * 1.91); left = (w - nw) // 2; im = im.crop((left, 0, left + nw, h))
    if im.width > 1440:
        im = im.resize((1440, round(im.height * 1440 / im.width)), Image.LANCZOS)
    im.save(os.path.join(out, item["file"]), "JPEG", quality=92)
    print("готово:", item["file"], im.size)
