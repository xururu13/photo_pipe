# Google Photos Auto-Uploader

Автоматическая загрузка фотографий из подпапок в Google Photos с созданием альбомов.

## Что делает скрипт

```
export/
├── 2025-02-15_Wedding/        →  Альбом "2025-02-15_Wedding"
│   ├── IMG_001.jpg                  IMG_001.jpg
│   └── IMG_002.jpg                  IMG_002.jpg
├── 2025-03-01_Birthday/       →  Альбом "2025-03-01_Birthday"
│   ├── IMG_010.jpg                  IMG_010.jpg
│   └── IMG_011.jpg                  IMG_011.jpg
```

Каждая подпапка → альбом в Google Photos. Имя папки = название альбома.

---

## Установка

### 1. Python-зависимости

```bash
pip install -r requirements.txt
```

### 2. Настройка Google Cloud Console (один раз)

Это нужно для получения OAuth2-ключей, чтобы скрипт мог работать с твоим аккаунтом.

1. Открой [Google Cloud Console](https://console.cloud.google.com/)
2. Создай новый проект (или выбери существующий)
3. Включи **Photos Library API**:
   - Перейди в **APIs & Services → Library**
   - Найди «Photos Library API»
   - Нажми **Enable**
4. Создай OAuth2 credentials:
   - Перейди в **APIs & Services → Credentials**
   - Нажми **+ Create Credentials → OAuth client ID**
   - Если просит настроить Consent Screen:
     - User Type: **External**
     - App name: любое (например, «Photo Uploader»)
     - Email: твой email
     - Scopes: добавь `photoslibrary` (или пропусти — скрипт запросит сам)
     - Test users: добавь свой email
     - Сохрани
   - Тип приложения: **Desktop app**
   - Имя: любое
   - Нажми **Create**
5. Скачай JSON-файл — кнопка **Download JSON** (⬇️)
6. Переименуй его в `credentials.json` и положи рядом со скриптом

### 3. Первый запуск

```bash
python google_photos_upload.py ~/Photos/export --dry-run
```

При первом запуске (без `--dry-run`) откроется браузер для авторизации.
Разреши доступ — токен сохранится в `token.json`, повторная авторизация не потребуется.

---

## Использование

### Посмотреть план (без загрузки)

```bash
python google_photos_upload.py ~/Photos/export --dry-run
```

### Загрузить всё

```bash
python google_photos_upload.py ~/Photos/export
```

### Повторный запуск (пропустит уже загруженные)

```bash
python google_photos_upload.py ~/Photos/export --skip-existing
```

Это поведение по умолчанию — скрипт ведёт лог загруженных файлов
в файле `.gphotos_uploaded.json` внутри папки экспорта.

### Обнаружение дубликатов

При загрузке скрипт проверяет содержимое альбома в Google Photos по имени файла.
Если файл с таким именем уже есть, показывается сравнение и предлагается выбор:

```
⚠️  Дубликат найден: IMG_001.jpg
     Локальный:  2025-02-15 14:30  |    4.2 MB  |  4032×3024
     Удалённый:  2025-02-15 14:30  |         —  |  4032×3024
     [S]kip / [R]eplace / Re[n]ame?
```

- **S** — пропустить файл
- **R** — удалить старый из альбома и загрузить новый
- **N** — задать новое имя и загрузить под ним

### Загрузить всё заново (игнорировать лог)

```bash
python google_photos_upload.py ~/Photos/export --no-skip-existing
```

### Указать другой путь к credentials

```bash
python google_photos_upload.py ~/Photos/export --credentials ~/keys/my_creds.json
```

---

## Интеграция с Capture One

Настрой в Capture One экспорт обработанных фотографий в подпапки по событиям:

```
~/Photos/export/
├── {дата}_{событие}/
│   └── *.jpg
```

Затем запускай скрипт после экспорта — вручную или по cron/launchd.

### Пример cron-задачи (каждый час)

```bash
crontab -e
# Добавить строку:
0 * * * * cd /path/to/script && python google_photos_upload.py ~/Photos/export >> upload.log 2>&1
```

### Пример launchd (macOS)

Создай `~/Library/LaunchAgents/com.gphotos.uploader.plist` — 
он будет запускать скрипт при появлении новых файлов в папке экспорта.

---

## Поддерживаемые форматы

**Фото:** JPG, JPEG, PNG, GIF, WebP, HEIC, HEIF, BMP, TIFF, AVIF

**RAW:** RAF (Fujifilm), CR2/CR3 (Canon), NEF (Nikon), ARW (Sony), DNG, ORF, RW2, PEF, SRW

**Видео:** MP4, MOV, AVI, MKV, M4V, 3GP, WMV, MPG

---

## Ограничения Google Photos API

- Фото до 200 MB, видео до 10 GB
- До 50 элементов за один batchCreate-запрос (скрипт разбивает автоматически)
- Фотографии, загруженные через API, могут редактироваться только приложением, которое их загрузило (не через веб-интерфейс Google Photos)
- Квота: 10,000 запросов в день (хватает на ~5,000 фото/день с запасом)

---

## Устранение проблем

| Проблема | Решение |
|----------|---------|
| `credentials.json не найден` | Скачай из Google Cloud Console (шаг 2.5) |
| `Access denied` при авторизации | Добавь свой email в Test Users (шаг 2.4) |
| `Photos Library API has not been enabled` | Включи API в Cloud Console (шаг 2.3) |
| `Quota exceeded` | Подожди до завтра или увеличь квоту в Console |
| Токен истёк | Удали `token.json` и запусти заново |
