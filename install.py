"""
Zed XiaoAI Agent - Automated One-Step Installer & Manager
Configures dependencies, encrypted credential storage, sync preferences, and registers the agent in Zed.

Author: thriveera (https://github.com/thriveera)
"""

import os
import sys
import json
import shutil
import platform
import subprocess
import urllib.request
import getpass

def log(msg):
    print(f"[*] {msg}")

def ok(msg):
    print(f"[+] {msg}")

def warn(msg):
    print(f"[!] {msg}")

def err(msg):
    print(f"[ERROR] {msg}")

def get_zed_settings_path():
    system = platform.system()
    home = os.path.expanduser("~")
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return os.path.join(appdata, "Zed", "settings.json")
    elif system == "Darwin":
        p1 = os.path.join(home, "Library", "Application Support", "Zed", "settings.json")
        if os.path.exists(p1):
            return p1
        return os.path.join(home, ".config", "zed", "settings.json")
    else:
        return os.path.join(home, ".config", "zed", "settings.json")
    return None

def uninstall():
    print("=" * 65)
    print("⚡ Zed XiaoAI External Agent - Удаление агента из Zed")
    print("=" * 65)
    settings_path = get_zed_settings_path()
    if not settings_path or not os.path.exists(settings_path):
        err(f"Файл настроек Zed не найден: {settings_path}")
        return

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)

        if "agent_servers" in settings and "XiaoAI Agent" in settings["agent_servers"]:
            del settings["agent_servers"]["XiaoAI Agent"]
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            ok("XiaoAI Agent успешно удалён из Zed settings.json!")
        else:
            log("XiaoAI Agent не был зарегистрирован в settings.json.")
    except Exception as e:
        err(f"Ошибка при обновлении settings.json: {e}")

    try:
        import keyring
        keyring.delete_password("xiaoai-agent", "api_key")
        ok("API-ключ успешно стёрт из системного хранилища (Keyring).")
    except Exception:
        pass

    agent_dir = os.path.dirname(os.path.abspath(__file__))
    for f in ["config.json", "models_cache.json", ".env"]:
        fp = os.path.join(agent_dir, f)
        if os.path.exists(fp):
            try:
                os.remove(fp)
            except Exception:
                pass

    print("\n🎉 Деинсталляция завершена.")

def main():
    if "--uninstall" in sys.argv or "-u" in sys.argv:
        uninstall()
        return

    print("=" * 65)
    print("⚡ Zed XiaoAI External Agent v1.1.1 - Автоматическая установка")
    print("=" * 65)
    print("Автор: thriveera (https://github.com/thriveera)")
    print("-" * 65)

    # 1. Check Python version
    if sys.version_info < (3, 10):
        err(f"Требуется Python 3.10 или новее. Ваша версия: {platform.python_version()}")
        sys.exit(1)
    ok(f"Python: {platform.python_version()} ({platform.system()} {platform.machine()})")

    # 2. Install dependencies
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    req_file = os.path.join(agent_dir, "requirements.txt")
    if os.path.exists(req_file):
        log("Установка и проверка зависимостей (agent-client-protocol, pydantic, keyring)...")
        res = subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file, "--quiet"])
        if res.returncode != 0:
            warn("pip завершился с предупреждением, но мы продолжим.")
        else:
            ok("Зависимости установлены.")

    import keyring

    # 3. Secure API Key Configuration
    print("\n--- [ 1. Настройка безопасного ключа XiaoAI ] ---")
    current_key = keyring.get_password("xiaoai-agent", "api_key") or os.environ.get("XIAOAI_API_KEY", "")
    
    if current_key:
        masked = current_key[:7] + "..." + current_key[-4:] if len(current_key) > 12 else "***"
        log(f"Обнаружен ранее сохранённый ключ в локальном Keyring: {masked}")
        ans = input("Использовать этот ключ? [Y/n]: ").strip().lower()
        if ans in ("", "y", "yes", "д", "да"):
            api_key = current_key
        else:
            api_key = input("Введите ваш API-ключ XiaoAI: ").strip()
    else:
        api_key = input("Введите ваш API-ключ XiaoAI: ").strip()

    if not api_key:
        warn("Ключ не был введён. Агент запустится, но для работы потребуется настроить ключ.")
    else:
        # Validate key
        log("Проверка ключа на сервере XiaoAI...")
        try:
            req = urllib.request.Request(
                "https://ai.itisxiao.cc/v1/models",
                headers={"Authorization": f"Bearer {api_key}", "User-Agent": "Zed-XiaoAI-Agent/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                ok("API-ключ успешно прошёл валидацию!")
        except Exception as e:
            warn(f"Не удалось проверить ключ на сервере ({e}), но ключ будет сохранён.")

        # Save to OS Keyring (encrypted vault)
        try:
            keyring.set_password("xiaoai-agent", "api_key", api_key)
            ok("Ключ надёжно зашифрован и сохранён в системном хранилище паролей (Keyring/Credential Manager)!")
        except Exception as e:
            warn(f"Ошибка сохранения в Keyring: {e}. Сохраняем в локальный .env файл...")
            with open(os.path.join(agent_dir, ".env"), "w", encoding="utf-8") as env_f:
                env_f.write(f"XIAOAI_API_KEY={api_key}\n")

    # 4. Sync frequency configuration
    print("\n--- [ 2. Режим синхронизации моделей, контекста и цен ] ---")
    print("Выберите частоту синхронизации с роутером XiaoAI:")
    print("  1. При каждом запуске агента (Автоматически, рекомендуется)")
    print("  2. Каждые 6 часов")
    print("  3. Каждые 24 часа")
    print("  4. Только вручную (по команде /sync в чате)")
    sync_choice = input("Ваш выбор [1-4, по умолчанию 1]: ").strip()
    sync_map = {"1": "startup", "2": "6h", "3": "24h", "4": "manual"}
    chosen_sync = sync_map.get(sync_choice, "startup")

    cfg_path = os.path.join(agent_dir, "config.json")
    try:
        with open(cfg_path, "w", encoding="utf-8") as cf:
            json.dump({"sync_interval": chosen_sync, "last_sync": 0}, cf, indent=2, ensure_ascii=False)
        ok(f"Режим синхронизации установлен: {chosen_sync}")
    except Exception as e:
        warn(f"Не удалось записать config.json: {e}")

    # 5. Configure Zed settings.json
    print("\n--- [ 3. Подключение к редактору Zed ] ---")
    settings_path = get_zed_settings_path()
    if not settings_path:
        err("Не удалось определить путь к настройкам Zed.")
        sys.exit(1)

    log(f"Файл настроек Zed: {settings_path}")
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)

    settings = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
            # Backup
            bak_path = settings_path + ".xiaoai_bak"
            shutil.copyfile(settings_path, bak_path)
            log(f"Создана резервная копия настроек: {bak_path}")
        except Exception as e:
            warn(f"Ошибка чтения существующего settings.json: {e}")

    if "agent_servers" not in settings:
        settings["agent_servers"] = {}

    agent_script = os.path.join(agent_dir, "agent.py")
    settings["agent_servers"]["XiaoAI Agent"] = {
        "type": "custom",
        "command": sys.executable,
        "args": [agent_script]
    }

    try:
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        ok("XiaoAI Agent успешно зарегистрирован в Zed settings.json!")
    except Exception as e:
        err(f"Не удалось записать settings.json: {e}")
        sys.exit(1)

    print("\n" + "=" * 65)
    print("🎉 УСТАНОВКА УСПЕШНО ЗАВЕРШЕНА!")
    print("=" * 65)
    print("Как начать пользоваться:")
    print("1. Откройте или перезапустите Zed.")
    print("2. Откройте панель ассистента: сочетание клавиш [ Ctrl + ? ] (или Cmd + ?).")
    print("3. В выпадающем списке выбора агента переключитесь на 'XiaoAI Agent'.")
    print("4. Выбирайте любую модель из роутера XiaoAI (цены указаны прямо на кнопке выбора)!")
    print("\nДля удаления агента запустите: python install.py --uninstall")
    print("=" * 65)

if __name__ == "__main__":
    main()
