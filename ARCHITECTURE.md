# Архітектура

## Загальна схема

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Bootstrap exe   │────▶│  Backend (API)   │────▶│  Runtime package │
│  (клієнт)        │     │  ліцензії,       │     │  (зашифрований   │
│                  │     │  маніфести,      │     │   zip + manifest)│
└────────┬────────┘     │  пакети          │     └────────┬────────┘
         │              └──────────────────┘              │
         │  license_key + hwid                             │
         │  → check → manifest → download                  │
         ▼                                                 ▼
┌─────────────────┐                              ┌─────────────────┐
│  .runtime_data/  │                              │  Розпакування,  │
│  bootstrap DB   │                              │  запуск runtime  │
│  (encrypted)     │                              │  (в памʼяті)    │
└─────────────────┘                              └─────────────────┘
```

1. Користувач запускає bootstrap exe, вводить ліцензійний ключ
2. Клієнт перевіряє ліцензію на сервері (ключ + HWID)
3. При успіху отримує маніфест і завантажує runtime-пакет
4. Пакет розпаковується в памʼяті, запускається логіка застосунку
5. Локальні дані (налаштування, cookies, логи) зберігаються в зашифрованій БД

## Платформа

Один репозиторій містить:

| Компонент | Призначення |
|-----------|-------------|
| `backend/` | FastAPI, API ліцензій, маніфестів, пакетів, admin |
| `client/` | Bootstrap loader, збірка в exe |
| `admin/` | Веб-панель управління |
| `shared/` | Криптографія, контракти маніфесту |
| `runtime_logic/build_tools/` | Збірка runtime-пакетів |

## Застосунки (apps)

Кожен застосунок — це папка в `runtime_logic/apps/<app_id>/`:

```
runtime_logic/apps/<app_id>/
├── src/
│   ├── entrypoints/
│   │   └── runtime_entry.py   # def run_runtime(context)
│   └── app/
│       ├── core/              # Оркестрація, контекст
│       ├── services/          # Зберігання, логи
│       ├── ui/                # Інтерфейс
│       └── ...
├── icon.ico
└── README.md
```

Застосунки можна тримати в цьому ж репо або винести в окремі репозиторії (git submodules).

## Потік даних

- **Bootstrap state** — license_key, server_url, channel — зберігається локально в зашифрованій SQLite
- **Runtime data** — аккаунти, cookies, логи, налаштування — у зашифрованій БД застосунку
- **Сервер** — не зберігає паролі користувачів; зберігає ліцензії, маніфести, пакети

## Збірка

```bash
python manager.py list                    # Доступні застосунки
python manager.py build -a wishlist -v 1.0.7
python manager.py client -n wishlist_bootstrap
python manager.py full -a wishlist -v 1.0.7   # Повна перезбірка
```

Результат:

- `backend/packages/` — runtime-пакети (zip + manifest)
- `dist/<name>.exe` — bootstrap-клієнт
