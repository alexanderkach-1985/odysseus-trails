#!/usr/bin/env python3
"""
Odysseus Trails — помощник публикаций в Instagram.

Каждый запуск публикует ОДИН следующий пост из queue.json, у которого
date <= сегодня и status == "pending". Запускается по cron раз в день.

Публикация через официальный Instagram API (Instagram Login):
  1) POST /{ig-user-id}/media         -> контейнер
  2) POST /{ig-user-id}/media_publish -> пост
Фото должно лежать по публичному https-адресу (PUBLIC_BASE_URL/файл.jpg).

Команды:
  python3 publisher.py            — опубликовать пост на сегодня
  python3 publisher.py --dry-run  — показать, что будет опубликовано, без публикации
  python3 publisher.py --status   — показать очередь
  python3 publisher.py --refresh-token — продлить токен (раз в ~50 дней, cron делает сам)
"""
import json, os, sys, time, datetime, urllib.request, urllib.parse, urllib.error

BASE = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(BASE, "queue.json")
LOG = os.path.join(BASE, "publisher.log")


def load_env():
    path = os.path.join(BASE, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


load_env()
API_VER = os.environ.get("IG_API_VERSION", "v26.0")
IG_USER_ID = os.environ.get("IG_USER_ID", "")
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "").strip().strip('"').strip()
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")      # необязательно: отчёт в Telegram
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "")
# Ключи Instagram Login начинаются с "IG", ключи системного пользователя
# (Unified login / бизнес-портфолио) — с "EA" и работают через graph.facebook.com
GRAPH = (f"https://graph.facebook.com/{API_VER}" if TOKEN.startswith("EA")
         else f"https://graph.instagram.com/{API_VER}")


def log(msg):
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def notify(text):
    if not (TG_BOT_TOKEN and TG_CHAT_ID):
        return
    try:
        data = urllib.parse.urlencode({"chat_id": TG_CHAT_ID, "text": text}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage", data, timeout=20)
    except Exception as e:
        log(f"Telegram: не отправлено ({e})")


def api(method, path, params):
    params = dict(params, access_token=TOKEN)
    url = f"{GRAPH}/{path}"
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code}: {e.read().decode(errors='replace')}")


def load_queue():
    return json.load(open(QUEUE, encoding="utf-8"))


def save_queue(q):
    tmp = QUEUE + ".tmp"
    json.dump(q, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.replace(tmp, QUEUE)


def next_item(q):
    """Следующий по порядку пост, для которого фото уже загружено.
    Посты без фото (вы их удалили из подборки) просто пропускаются."""
    # не чаще одного поста за 6 часов (защита от двойного запуска)
    last = max((i.get("published_at", "") for i in q), default="")
    if last:
        try:
            if datetime.datetime.now() - datetime.datetime.fromisoformat(last) < datetime.timedelta(hours=6):
                return None
        except ValueError:
            pass
    for item in q:
        if item["status"] == "pending" and os.path.exists(os.path.join(BASE, "photos", item["file"])):
            return item
    return None


def publish(item, dry=False):
    url = f"{PUBLIC_BASE_URL}/{urllib.parse.quote(item['file'])}"
    if not os.path.exists(os.path.join(BASE, "photos", item["file"])):
        raise RuntimeError(f"нет файла photos/{item['file']}")
    if dry:
        log(f"[dry-run] День {item['day']}: {url}\n{item['caption']}")
        return None
    c = api("POST", f"{IG_USER_ID}/media", {"image_url": url, "caption": item["caption"]})
    cid = c["id"]
    # ждём, пока Instagram обработает фото
    for _ in range(20):
        st = api("GET", cid, {"fields": "status_code"}).get("status_code")
        if st == "FINISHED":
            break
        if st == "ERROR":
            raise RuntimeError("Instagram не смог обработать фото (status ERROR)")
        time.sleep(6)
    p = api("POST", f"{IG_USER_ID}/media_publish", {"creation_id": cid})
    return p["id"]


def refresh_token():
    r = urllib.request.urlopen(
        "https://graph.instagram.com/refresh_access_token?"
        + urllib.parse.urlencode({"grant_type": "ig_refresh_token", "access_token": TOKEN}), timeout=30)
    new = json.loads(r.read().decode())["access_token"]
    path = os.path.join(BASE, ".env")
    lines = open(path, encoding="utf-8").read().splitlines()
    lines = [f"IG_ACCESS_TOKEN={new}" if l.startswith("IG_ACCESS_TOKEN=") else l for l in lines]
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    log("Токен продлён на 60 дней")


def main():
    args = sys.argv[1:]
    if "--refresh-token" in args:
        refresh_token(); return
    if "--check" in args:
        if not TOKEN:
            sys.exit("Секрет IG_ACCESS_TOKEN не найден")
        log(f"Ключ: {len(TOKEN)} символов, начинается на {TOKEN[:2]!r}, сервер {GRAPH}")
        me = api("GET", IG_USER_ID, {"fields": "username,media_count"})
        log(f"Ключ работает: аккаунт @{me.get('username')}, постов: {me.get('media_count')}")
        return
    q = load_queue()
    if "--status" in args:
        for i in q:
            has = "фото есть" if os.path.exists(os.path.join(BASE, "photos", i["file"])) else "нет фото"
            print(f"{i['day']:>2}. {i['status']:<9} {has:<9} {i['file']}")
        return
    dry = "--dry-run" in args
    if not dry and not (IG_USER_ID and TOKEN and PUBLIC_BASE_URL):
        sys.exit("Не заданы IG_USER_ID, IG_ACCESS_TOKEN или PUBLIC_BASE_URL")
    item = next_item(q)
    if not item:
        log("Публиковать нечего: недавно уже был пост или нет загруженных фото"); return
    try:
        media_id = publish(item, dry)
        if dry:
            return
        item["status"] = "published"
        item["media_id"] = media_id
        item["published_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        save_queue(q)
        log(f"Опубликован день {item['day']} ({item['file']}), id {media_id}")
        notify(f"✅ Odysseus Trails: опубликован день {item['day']} — {item['caption'].splitlines()[0]}")
    except Exception as e:
        log(f"ОШИБКА день {item['day']}: {e}")
        notify(f"⚠️ Odysseus Trails: не удалось опубликовать день {item['day']}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
