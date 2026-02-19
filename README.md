## Пайплайн импорта и обработки фотографий Fuji X‑S20 + Capture One + Google Photos

1. Import: SD → ~/Pictures/Import/<YY-MM Event>
2. Cull (рейтинг 1-5): `photo_cull/cull.py ~/Pictures/Import/<YY-MM Event>` → XMP-сайдкары
3. Capture One: Import ~/Raw/Event/ → фильтр по рейтингу ≥3★ + C1 Cull Mode
4. Capture One: Process & Export
```
вариант:
Capture One → Styles → Create Style (ваш авто-пресет: Exposure +1, Contrast +10, Clarity +15, Fuji Nostalgic Neg)
Process Recipe: Apply Style → JPG 2048px → Output folder "~/Pictures/Export/<YY-MM Event>"
Batch Job → Select все RAF → Process All (параллельно 8 потоков)
```
5. Export to Google Photos: `photo_export/google_photos_upload.py ~/Pictures/Export/`

### Быстрый старт

```bash
# Активировать venv
source .venv/bin/activate

# Установить зависимости
pip install -r photo_cull/requirements.txt -r photo_export/requirements.txt

# Отбор фотографий (алгоритмический, dry-run)
python3 photo_cull/cull.py ~/Pictures/Import/25-01_Event --dry-run

# Отбор через AI (Ollama llava, dry-run)
python3 photo_cull/cull.py ~/Pictures/Import/25-01_Event --ai-cull --dry-run

# Загрузка в Google Photos (dry-run)
python3 photo_export/google_photos_upload.py ~/Pictures/Export --dry-run
```

### Установка Ollama (для `--ai-cull`)

`--ai-cull` использует локальную vision-модель через [Ollama](https://ollama.com). Установка:

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Запуск сервера
brew services start ollama   # macOS (фоновый сервис)
ollama serve                 # или вручную

# Скачать модель llava (~4.7 GB)
ollama pull llava

# Проверить
ollama list
```

Другие vision-модели (передаются через `--ollama-model`):
- `llava` — по умолчанию, ~4.7 GB, хороший баланс скорости и качества
- `llava:13b` — точнее, но медленнее (~8 GB)
- `llava-llama3` — новее, лучше следует JSON-инструкциям
