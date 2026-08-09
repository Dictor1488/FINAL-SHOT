# Розробка INQ Final Shot

Цей файл містить технічні нотатки про проєкт. Користувацький опис мода знаходиться в кореневому `README.md`.

## Структура репозиторію

```text
FINAL-SHOT/
├─ python/gui/mods/        Python-код мода
├─ as3/
│  ├─ libs/                локальні WoT SWC-бібліотеки
│  └─ src_flash/src/       актуальний бойовий Scaleform viewer
├─ resources/              локалізації пакета
├─ docs/                   технічна документація
├─ .github/workflows/      CI та створення релізів
├─ build.py                формування .wotmod
├─ build.example.json      приклад локального build.json
├─ LICENSE
└─ README.md               опис мода для гравця
```

## Runtime-модулі

У `.wotmod` входять тільки модулі, перелічені в `PYTHON_SOURCES` у `build.py`:

- `mod_inq_final_shot.py` — базовий контролер бою та історії отриманого урону.
- `mod_zz_inq_final_shot_health.py` — події зміни HP.
- `mod_zzz_inq_final_shot_impacts.py` — точні 3D-точки `showDamageFromShot`.
- `mod_zzzzz_inq_final_shot_battle_viewer.py` — післясмертний бойовий overlay.
- `mod_zzzzzzz_inq_final_shot_stable_markers.py` — стабільна прив'язка та проєкція міток.
- `mod_zzzzzzzz_inq_final_shot_observer_visibility.py` — видимість тільки на власному знищеному танку.
- `mod_zzzzzzzzz_inq_final_shot_runtime_fix.py` — актуальні runtime-виправлення, визначення смертельного пострілу та прив'язка attacker ID.

Префікси `zz...` забезпечують потрібний порядок завантаження через ScriptLoader.

Стара `FinalShotPanelBattle` і її Python-патчі видалені: поточна версія використовує тільки `FinalShotBattleViewer`.

## AS3 / SWC

Для збірки використовується тільки:

```text
as3/src_flash/src/com/inq/finalshot/FinalShotBattleViewer.as
```

WoT SWC-бібліотеки вже зберігаються локально в `as3/libs`. Workflow більше не checkout-ить інший репозиторій для отримання SWC.

Apache Flex SDK зберігається в GitHub Actions cache. Він завантажується тільки якщо сумісного кешу ще немає.

## CI та реліз

Pull request і push у `main` виконують перевірочну збірку.

Готовий файл не завантажується як Actions Artifact. Для тегів `v*` та ручного `workflow_dispatch` workflow створює або оновлює GitHub Release і прикріплює до нього готовий `.wotmod`.

Перед публікацією workflow додатково перевіряє вміст `.wotmod`: актуальний `FinalShotBattleViewer.swf` повинен бути всередині, а застарілий `FinalShotPanelBattle.swf` — відсутній.

## Перевірка в клієнті

Для runtime-помилок основним джерелом є `python.log`. Під час перевірки важливо дивитися саме на останній запуск клієнта і рядки з `inq.final_shot` або `com.inq.final_shot`.
