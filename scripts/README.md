# Scripts

Скрипти для збірки та підтримки платформи.

## manager.py

Головний CLI для управління платформою. Запускати з кореня проекту.

```bash
python manager.py list
python manager.py build -a wishlist -v 1.0.7
python manager.py build -a app1 -a app2 -v 1.0.0
python manager.py build --all -v 1.0.8
python manager.py client -n myapp_bootstrap
python manager.py clean [--full]
python manager.py full -a wishlist -v 1.0.7
python manager.py admin -p <пароль>
python manager.py db reset
python manager.py run
```

## rebuild.py

Повна перезбірка: clean + build + client. Делегує до `manager.py full`.

## Додавання нового застосунку

1. Створити `runtime_logic/apps/<app_id>/` зі структурою як у wishlist
2. Додати `entrypoints/runtime_entry.py` та `src/`
3. Збирати: `python manager.py build -a <app_id> -v 1.0.0`
