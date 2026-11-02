# Odysseus Trails: автопубликация в Instagram

Каждый день в 18:00 по Хараре GitHub сам публикует в @odysseus.trails следующий пост из `queue.json`: фото из `photos/` и подпись на русском и английском.

## Что нужно сделать один раз
1. **Ключ Instagram.** На developers.facebook.com: Create App → Business → продукт Instagram → «API setup with Instagram login» → Add account (odysseus.trails) → Generate token.
2. **Секреты.** Settings → Secrets and variables → Actions → New repository secret:
   - `IG_USER_ID`: Instagram User ID
   - `IG_ACCESS_TOKEN`: токен
   - по желанию `TG_BOT_TOKEN` и `TG_CHAT_ID`, чтобы получать отчёт в Telegram
3. **Фото.** Положите в `photos/` файлы с именами из `queue.json`: `01_rhinos.jpg` и так далее. Подготовить их можно скриптом `prepare_photos.py`, он подгоняет размер и пропорции и удаляет геометки.

## Проверка
Actions → «Публикация в Instagram» → Run workflow (по умолчанию стоит галочка «Только проверка»).

## Важно
Токен живёт 60 дней. Перед истечением обновите секрет `IG_ACCESS_TOKEN`: Generate token ещё раз.
