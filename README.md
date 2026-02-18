## Пайплайн импорта и обработки фотографий Fuji X‑S20 + Capture One + Google Photos

1. Import: SD → ~/Pictures/Import/<YY-MM Event>
2. Cull (рейтинг 1-5): cull/cull.py ~/Pictures/Import/<<YY-MM Event>> → XMP файлы
3. Capture One: Import ~/Raw/Event/ → фильтр по рейтингу ≥3★ + C1 Cull Mode
4. Capture One: Process & Export
``` 
вариант:
Capture One → Styles → Create Style (ваш авто-пресет: Exposure +1, Contrast +10,  Clarity +15, Fuji Nostalgic Neg)
Process Recipe: Apply Style → JPG 2048px → Output folder "~/Pictures/Export/<YY-MM Event>"
Batch Job → Select все RAF → Process All (параллельно 8 потоков)
```
5. Export to google.photoes: gphoto_export/gphoto_export.py ~/Pictures/Export/
