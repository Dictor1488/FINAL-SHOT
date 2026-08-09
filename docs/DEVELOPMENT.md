# Розробка INQ Final Shot

Цей файл містить технічні нотатки про проєкт. Користувацький опис мода знаходиться в кореневому `README.md`.

## Структура репозиторію

```text
FINAL-SHOT/
├─ python/                 Python-код мода
│  └─ gui/mods/
├─ as3/                    бойовий Flash/Scaleform інтерфейс
│  ├─ libs/                локальні SWC-бібліотеки для збірки
│  └─ src_flash/
├─ resources/              локалізації та ресурси пакета
├─ docs/                   технічна документація
├─ .github/workflows/      автоматична збірка
├─ build.py                збірка .wotmod
├─ build.example.json      приклад конфігурації збірки
├─ LICENSE
└─ README.md               опис мода для гравця
```

## Основні частини

- `mod_inq_final_shot.py` — базовий контролер бою та даних про попадання.
- `mod_zz_inq_final_shot_health.py` — події зміни HP і дані про атакуючого.
- `mod_zzz_inq_final_shot_impacts.py` — збереження точних точок попадання по машині.
- `mod_zzzzz_inq_final_shot_battle_viewer.py` — післясмертний бойовий overlay.
- `mod_zzzzzzz_inq_final_shot_stable_markers.py` — прив'язка та проєкція міток із мінімальним навантаженням.
- `mod_zzzzzzzz_inq_final_shot_observer_visibility.py` — показ міток тільки під час спостереження за власним знищеним танком.
- `mod_zzzzzzzzz_inq_final_shot_runtime_fix.py` — сумісність поточної бойової логіки та визначення смертельного попадання.

Префікси `zz...` зараз зберігають необхідний порядок завантаження модулів ScriptLoader. Їх не слід перейменовувати окремо без одночасної зміни залежностей.

## Збірка

GitHub Actions компілює Python 2.7 та AS3, після чого `build.py` формує `.wotmod`.

SWC-бібліотеки зберігаються в `as3/libs`, а Flex SDK кешується workflow, тому звичайні повторні збірки не повинні завантажувати SDK заново.

## Перевірка в клієнті

Для runtime-помилок основним джерелом є `python.log`. Під час перевірки важливо дивитися саме на останній запуск клієнта і рядки з `inq.final_shot` або `com.inq.final_shot`.
