"""
XiaoAI Agent for Zed - Graphical Installer
A standalone Windows GUI installer for setting up the XiaoAI ACP Agent in Zed.

Author: thriveera (https://github.com/thriveera)
"""

import os
import sys
import json
import shutil
import threading
import urllib.request
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    import keyring
except ImportError:
    keyring = None

DARK_BG = "#13161c"
CARD_BG = "#1c212c"
CARD_BORDER = "#2b3242"
TEXT_MAIN = "#e6edf3"
TEXT_MUTED = "#8b949e"
ACCENT_BLUE = "#58a6ff"
ACCENT_GREEN = "#238636"
ACCENT_GREEN_HOVER = "#2ea043"

AGENT_CODE = """\"\"\"
XiaoAI ACP Agent for Zed Editor
An Agent Client Protocol (ACP) server connecting Zed to the XiaoAI model router.

Author: thriveera (https://github.com/thriveera)
License: MIT
\"\"\"

import os
import sys
import json
import asyncio
import urllib.request
from typing import Any, Dict, List, Optional

import acp
from acp.schema import (
    InitializeRequest, InitializeResponse, Implementation,
    NewSessionRequest, NewSessionResponse,
    PromptRequest, PromptResponse,
    SetSessionConfigOptionSelectRequest, SetSessionConfigOptionBooleanRequest,
    SetSessionConfigOptionResponse,
    SetSessionModeRequest, SetSessionModeResponse,
    SessionConfigOptionSelect, SessionConfigSelectOption,
    SessionMode, SessionModeState,
    AgentMessageChunk, AgentThoughtChunk, TextContentBlock,
    ConfigOptionUpdate
)


def load_env_file():
    \"\"\"Loads environment variables from .env file if present in the agent directory.\"\"\"
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(agent_dir, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip('"').strip("'")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass


load_env_file()

DEFAULT_BASE_URL = os.environ.get("XIAOAI_BASE_URL", "https://ai.itisxiao.cc/v1")


def get_secure_api_key() -> str:
    \"\"\"
    Retrieves the API key securely.
    Priority:
    1. OS Encrypted Keyring (Windows Credential Locker / macOS Keychain / Linux SecretService)
    2. Environment variable XIAOAI_API_KEY
    \"\"\"
    try:
        import keyring
        key = keyring.get_password("xiaoai-agent", "api_key")
        if key and key.strip():
            return key.strip()
    except Exception:
        pass

    env_key = os.environ.get("XIAOAI_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    return ""


def set_secure_api_key(key: str) -> bool:
    \"\"\"Stores the API key into the OS encrypted credential store.\"\"\"
    try:
        import keyring
        keyring.set_password("xiaoai-agent", "api_key", key.strip())
        return True
    except Exception as e:
        print(f"Error saving to keyring: {e}", file=sys.stderr)
        return False


FALLBACK_MODELS = [
    {"id": "xgg/gpt-6.1-sol", "name": "GPT 6.1 Sol", "price": "$0.08 / 1M токенов", "short_price": "$0.08/1M", "context": 400000},
    {"id": "xgg/gpt-6-astra", "name": "GPT 6 Astra", "price": "$0.20 / 1M токенов", "short_price": "$0.20/1M", "context": 400000},
    {"id": "xgg/gpt-6-sol", "name": "GPT 6 Sol", "price": "$0.08 / 1M токенов", "short_price": "$0.08/1M", "context": 400000},
    {"id": "xgg/gpt-6-luna", "name": "GPT 6 Luna", "price": "$0.0035 / 1M токенов", "short_price": "$0.0035/1M", "context": 400000},
    {"id": "free/gpt-4o-mini", "name": "ChatGPT 4o mini [Free]", "price": "Бесплатно", "short_price": "Free", "context": 1000000},
    {"id": "test/selena-ai", "name": "SelenaAI [Experimental]", "price": "$0.01 / 1M токенов", "short_price": "$0.01/1M", "context": 1048576},
    {"id": "muse/muse", "name": "Muse Spark 1.3", "price": "$0.01 / 1M токенов", "short_price": "$0.01/1M", "context": 256000},
    {"id": "claude/fable", "name": "Claude Fable", "price": "$0.25 / 1M токенов", "short_price": "$0.25/1M", "context": 200000},
    {"id": "claude/opus", "name": "Claude Opus", "price": "$0.10 / 1M токенов", "short_price": "$0.10/1M", "context": 200000},
    {"id": "claude/sonnet", "name": "Claude Sonnet", "price": "$0.08 / 1M токенов", "short_price": "$0.08/1M", "context": 200000},
    {"id": "claude/haiku", "name": "Claude Haiku", "price": "$0.03 / 1M токенов", "short_price": "$0.03/1M", "context": 200000},
    {"id": "free/deepseek-flash", "name": "DeepSeek Flash [Free]", "price": "Бесплатно", "short_price": "Free", "context": 1000000},
    {"id": "free/deepseek-v4-pro", "name": "DeepSeek V4 Pro [Free]", "price": "Бесплатно", "short_price": "Free", "context": 1000000},
    {"id": "free/kimi-k3", "name": "Kimi K3 [Free]", "price": "Бесплатно", "short_price": "Free", "context": 1000000},
    {"id": "free/qwen3.8-flash", "name": "Qwen 3.8 Flash [Free]", "price": "Бесплатно", "short_price": "Free", "context": 1000000},
    {"id": "free/qwen3.8-max", "name": "Qwen 3.8 Max [Free]", "price": "Бесплатно", "short_price": "Free", "context": 1000000},
    {"id": "free/glm-5.3", "name": "GLM 5.3 [Free]", "price": "Бесплатно", "short_price": "Free", "context": 1000000},
    {"id": "free/glm-5.3-prime", "name": "GLM 5.3 Prime [Free]", "price": "Бесплатно", "short_price": "Free", "context": 1000000},
    {"id": "free/GLM-5.3-Flash", "name": "GLM 5.3 Flash [Free]", "price": "Бесплатно", "short_price": "Free", "context": 1000000},
    {"id": "free/muse-spark-open", "name": "Muse Spark Open [Free]", "price": "Бесплатно", "short_price": "Free", "context": 1000000},
]


def fetch_xiaoai_catalog(base_url: str, api_key: str) -> List[Dict[str, Any]]:
    \"\"\"Fetches real-time model catalog and exact token pricing from XiaoAI router.\"\"\"
    if not api_key:
        return FALLBACK_MODELS

    root_url = base_url.rstrip("/v1").rstrip("/")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Zed-XiaoAI-Agent/1.0"
    }

    # 1. Fetch exact context limits from opencode endpoint
    contexts = {}
    try:
        req_oc = urllib.request.Request(f"{root_url}/api/key/models?format=opencode", headers=headers)
        with urllib.request.urlopen(req_oc, timeout=8) as r:
            oc_data = json.loads(r.read().decode())
            for mid, info in oc_data.items():
                contexts[mid] = info.get("limit", {}).get("context", 200000)
    except Exception:
        pass

    # 2. Fetch models with pricing multipliers from /api/key/models
    try:
        req_m = urllib.request.Request(f"{root_url}/api/key/models", headers=headers)
        with urllib.request.urlopen(req_m, timeout=8) as r:
            data = json.loads(r.read().decode())
            models = data.get("models", [])
            results = []
            for m in models:
                mid = m["id"]
                raw_name = m.get("name") or mid
                mult = float(m.get("multiplier", 0.0))
                if mult == 0.0:
                    price_str = "Бесплатно ($0.00 / 1M)"
                    short_price = "Free"
                else:
                    price_val = f"${mult:.4f}".rstrip("0").rstrip(".")
                    price_str = f"{price_val} / 1M токенов"
                    short_price = f"{price_val}/1M"

                ctx = contexts.get(mid, 200000)
                results.append({
                    "id": mid,
                    "name": raw_name,
                    "price": price_str,
                    "short_price": short_price,
                    "multiplier": mult,
                    "context": ctx
                })
            if results:
                return results
    except Exception:
        pass

    # 3. Fallback to /v1/models if /api/key/models is unavailable
    try:
        req_v1 = urllib.request.Request(f"{base_url}/models", headers=headers)
        with urllib.request.urlopen(req_v1, timeout=8) as r:
            data = json.loads(r.read().decode())["data"]
            results = []
            for m in data:
                mid = m["id"]
                results.append({
                    "id": mid,
                    "name": m.get("name") or mid,
                    "price": "По тарифу XiaoAI",
                    "short_price": "XiaoAI",
                    "context": m.get("context_input", 200000)
                })
            if results:
                return results
    except Exception:
        pass

    return FALLBACK_MODELS


class XiaoAiAgent(acp.Agent):
    def __init__(self):
        super().__init__()
        self.conn: Optional[acp.Client] = None
        self.base_url = DEFAULT_BASE_URL
        self.models_catalog: List[Dict[str, Any]] = []
        self.current_model = "xgg/gpt-6.1-sol"
        self.current_mode = "code"
        self.session_history: Dict[str, List[Dict[str, str]]] = {}

    def on_connect(self, conn: acp.Client) -> None:
        self.conn = conn

    def get_api_key(self) -> str:
        return get_secure_api_key()

    def refresh_models(self):
        key = self.get_api_key()
        self.models_catalog = fetch_xiaoai_catalog(self.base_url, key)
        if not any(m["id"] == self.current_model for m in self.models_catalog) and self.models_catalog:
            self.current_model = self.models_catalog[0]["id"]

    def build_config_options(self) -> List[SessionConfigOptionSelect]:
        options = []
        for m in self.models_catalog:
            price_tag = m.get("short_price") or m.get("price", "")
            clean_name = m["name"]
            display_title = f"{clean_name} · [{price_tag}]"
            ctx = m.get("context", 200000)
            ctx_str = f"{ctx // 1000}k" if isinstance(ctx, int) and ctx >= 1000 else str(ctx)
            desc = f"Прайс: {m.get('price', 'N/A')} | Контекст: {ctx_str} токенов"

            options.append(
                SessionConfigSelectOption(
                    value=m["id"],
                    name=display_title,
                    description=desc
                )
            )

        return [
            SessionConfigOptionSelect(
                id="model",
                name="Model",
                description="Выбранная модель XiaoAI (с ценой за 1M токенов)",
                category="model",
                current_value=self.current_model,
                options=options
            )
        ]

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities=None,
        client_info=None,
        **kwargs: Any,
    ) -> InitializeResponse:
        self.refresh_models()
        return InitializeResponse(
            protocol_version=protocol_version,
            agent_info=Implementation(
                name="xiaoai-agent",
                version="1.0.3",
                title="XiaoAI Agent"
            )
        )

    async def new_session(
        self,
        cwd: str,
        additional_directories: Optional[List[str]] = None,
        mcp_servers: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> NewSessionResponse:
        import uuid
        session_id = str(uuid.uuid4())
        self.session_history[session_id] = []
        self.refresh_models()

        modes = SessionModeState(
            current_mode_id="code",
            available_modes=[
                SessionMode(id="code", name="Code", description="Full coding assistant mode"),
                SessionMode(id="ask", name="Ask", description="Q&A and architectural advice"),
                SessionMode(id="plan", name="Plan", description="Step-by-step task decomposition")
            ]
        )

        return NewSessionResponse(
            session_id=session_id,
            modes=modes,
            config_options=self.build_config_options()
        )

    async def set_session_mode(self, session_id: str, mode_id: str, **kwargs: Any) -> SetSessionModeResponse:
        self.current_mode = mode_id
        return SetSessionModeResponse()

    async def set_config_option(
        self, config_id: str, session_id: str, value: Any, **kwargs: Any
    ) -> SetSessionConfigOptionResponse:
        if config_id == "model":
            self.current_model = str(value)
        return SetSessionConfigOptionResponse(config_options=self.build_config_options())

    async def send_text_chunk(self, session_id: str, text: str):
        if not self.conn:
            return
        await self.conn.session_update(
            session_id=session_id,
            update=AgentMessageChunk(content=TextContentBlock(type="text", text=text))
        )

    async def send_thought_chunk(self, session_id: str, text: str):
        if not self.conn:
            return
        await self.conn.session_update(
            session_id=session_id,
            update=AgentThoughtChunk(content=TextContentBlock(type="text", text=text))
        )

    async def prompt(self, session_id: str, prompt: List[Any], **kwargs: Any) -> PromptResponse:
        user_text = ""
        for block in prompt:
            if hasattr(block, "text"):
                user_text += block.text
            elif isinstance(block, dict) and "text" in block:
                user_text += block["text"]

        user_text = user_text.strip()

        # Slash command: /setkey <key>
        if user_text.startswith("/setkey"):
            parts = user_text.split(maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                new_key = parts[1].strip()
                if set_secure_api_key(new_key):
                    await self.send_text_chunk(session_id, "🔒 API-ключ успешно сохранён в зашифрованное хранилище системы (Keyring)!\n")
                    self.refresh_models()
                    if self.conn:
                        await self.conn.session_update(
                            session_id=session_id,
                            update=ConfigOptionUpdate(config_options=self.build_config_options())
                        )
                else:
                    await self.send_text_chunk(session_id, "❌ Не удалось сохранить ключ в хранилище системы.\n")
            else:
                await self.send_text_chunk(session_id, "Использование: `/setkey <ваш_ключ>`\n")
            return PromptResponse(stop_reason="end_turn")

        # Slash command: /sync
        if user_text.startswith("/sync"):
            await self.send_text_chunk(session_id, "🔄 Опрашиваю роутер XiaoAI и обновляю каталог и прайс-лист...\n")
            self.refresh_models()
            cnt = len(self.models_catalog)
            await self.send_text_chunk(session_id, f"✅ Каталог успешно обновлен! Всего моделей доступно: {cnt}.\n")
            if self.conn:
                await self.conn.session_update(
                    session_id=session_id,
                    update=ConfigOptionUpdate(config_options=self.build_config_options())
                )
            return PromptResponse(stop_reason="end_turn")

        # Slash command: /status
        if user_text.startswith("/status"):
            key = self.get_api_key()
            if not key:
                await self.send_text_chunk(session_id, "⚠️ API-ключ не найден. Используйте `/setkey <ключ>` для его сохранения в защищённое хранилище.\n")
                return PromptResponse(stop_reason="end_turn")
            root_url = self.base_url.rstrip("/v1").rstrip("/")
            try:
                req = urllib.request.Request(f"{root_url}/key/{key}", headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    html = r.read().decode()
                    import re
                    bal = "Активен"
                    m = re.search(r"Account balance.*?<span>(.*?)</span>", html, re.DOTALL)
                    if m:
                        bal = f"Баланс: {m.group(1).strip()}"
                    await self.send_text_chunk(session_id, f"🟢 **Статус XiaoAI:** Ключ активен. {bal}\nТекущая модель: `{self.current_model}`\nХранилище: Зашифрованное (Keyring/OS Vault)\n")
            except Exception as e:
                await self.send_text_chunk(session_id, f"❌ Ошибка проверки ключа: {e}\n")
            return PromptResponse(stop_reason="end_turn")

        # Slash command: /models
        if user_text.startswith("/models"):
            await self.send_text_chunk(session_id, "### 📋 Официальный прайс-лист моделей XiaoAI\n\n")
            await self.send_text_chunk(session_id, "Тарификация роутера: **1 M = 1 000 000 токенов = $1.00 base**.\n\n")
            await self.send_text_chunk(session_id, "| Модель | Прайс за 1M токенов | Контекст | ID модели |\n")
            await self.send_text_chunk(session_id, "|:---|:---:|:---:|:---|\n")
            for m in self.models_catalog:
                ctx = m.get("context", 200000)
                ctx_str = f"{ctx // 1000}k" if isinstance(ctx, int) and ctx >= 1000 else str(ctx)
                price = m.get("price", "N/A")
                await self.send_text_chunk(session_id, f"| **{m['name']}** | `{price}` | {ctx_str} | `{m['id']}` |\n")
            return PromptResponse(stop_reason="end_turn")

        # Regular Chat Turn
        history = self.session_history.setdefault(session_id, [])
        history.append({"role": "user", "content": user_text})

        system_prompts = {
            "code": "You are XiaoAI Agent, an expert AI programming assistant inside the Zed editor. Provide clean, well-tested code and direct solutions.",
            "ask": "You are XiaoAI Agent inside the Zed editor. Answer questions clearly, accurately, and conceptually.",
            "plan": "You are XiaoAI Agent inside the Zed editor. Formulate structured, step-by-step plans and actionable tasks."
        }
        sys_msg = system_prompts.get(self.current_mode, system_prompts["code"])
        payload_messages = [{"role": "system", "content": sys_msg}] + history[-12:]

        key = self.get_api_key()
        if not key:
            await self.send_text_chunk(
                session_id,
                "⚠️ **Ошибка:** API-ключ XiaoAI не обнаружен.\n"
                "Вы можете сохранить его прямо в чате командой:\n"
                "`/setkey <ваш_ключ>` (он будет надёжно зашифрован в хранилище системы).\n"
            )
            return PromptResponse(stop_reason="end_turn")

        try:
            req_data = json.dumps({
                "model": self.current_model,
                "messages": payload_messages,
                "stream": True
            }).encode("utf-8")

            endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
            req = urllib.request.Request(
                endpoint,
                data=req_data,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Zed/1.27.0"
                }
            )

            assistant_reply = []
            loop = asyncio.get_event_loop()

            def perform_stream():
                chunks = []
                with urllib.request.urlopen(req, timeout=60) as resp:
                    for line in resp:
                        line = line.decode("utf-8", errors="replace").strip()
                        if line.startswith("data: "):
                            raw_data = line[6:]
                            if raw_data == "[DONE]":
                                break
                            try:
                                c = json.loads(raw_data)
                                if c.get("choices"):
                                    delta = c["choices"][0].get("delta", {})
                                    chunks.append(delta)
                            except Exception:
                                pass
                return chunks

            stream_chunks = await loop.run_in_executor(None, perform_stream)

            for delta in stream_chunks:
                thought = delta.get("reasoning_content") or delta.get("thought")
                if thought:
                    await self.send_thought_chunk(session_id, thought)

                content = delta.get("content")
                if content:
                    assistant_reply.append(content)
                    await self.send_text_chunk(session_id, content)

            full_reply = "".join(assistant_reply)
            history.append({"role": "assistant", "content": full_reply})

        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            await self.send_text_chunk(
                session_id,
                f"❌ **Ошибка XiaoAI API ({e.code}):** {e.reason}\n`{err_body}`\n"
            )
        except Exception as e:
            await self.send_text_chunk(
                session_id,
                f"❌ **Не удалось выполнить запрос:** {e}\n"
            )

        return PromptResponse(stop_reason="end_turn")


async def main():
    agent = XiaoAiAgent()
    await acp.run_agent(agent)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
"""

class InstallerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("XiaoAI Agent · Установщик и управление для Zed")
        self.geometry("660x620")
        self.resizable(False, False)
        self.configure(bg=DARK_BG)

        # Center on screen
        self.eval("tk::PlaceWindow . center")

        self.key_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Готов к работе")
        self.install_dir_var = tk.StringVar(
            value=os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), ".zed", "agents", "xiaoai-agent")
        )
        self.key_visible = False

        # Auto-load existing key from local Windows Credential Vault (Keyring)
        if keyring:
            try:
                existing = keyring.get_password("xiaoai-agent", "api_key")
                if existing:
                    self.key_var.set(existing)
                    self.status_var.set("Обнаружен ранее сохранённый ключ из локального хранилища Windows")
            except Exception:
                pass

        self.setup_ui()
        self.refresh_zed_status()

    def setup_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", background=DARK_BG, foreground=TEXT_MAIN, font=("Segoe UI", 10))
        style.configure("Card.TFrame", background=CARD_BG, relief="flat")
        style.configure("Primary.TButton", font=("Segoe UI", 11, "bold"), background=ACCENT_GREEN, foreground="#ffffff", borderwidth=0, padding=10)
        style.map("Primary.TButton", background=[("active", ACCENT_GREEN_HOVER), ("disabled", "#194a24")])
        
        style.configure("Danger.TButton", font=("Segoe UI", 10, "bold"), background="#b62324", foreground="#ffffff", borderwidth=0, padding=10)
        style.map("Danger.TButton", background=[("active", "#d9383a"), ("disabled", "#491717")])

        style.configure("Small.TButton", font=("Segoe UI", 9), background="#2b3242", foreground=TEXT_MAIN, borderwidth=0, padding=5)
        style.map("Small.TButton", background=[("active", "#3b4458")])

        main = ttk.Frame(self, padding=20)
        main.pack(fill=tk.BOTH, expand=True)

        # Header Banner
        header = ttk.Frame(main)
        header.pack(fill=tk.X, pady=(0, 14))

        title_lbl = tk.Label(header, text="⚡ XiaoAI External Agent", font=("Segoe UI", 18, "bold"), fg=ACCENT_BLUE, bg=DARK_BG)
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(header, text="Установка, настройка и удаление роутера XiaoAI для редактора Zed", font=("Segoe UI", 10), fg=TEXT_MUTED, bg=DARK_BG)
        sub_lbl.pack(anchor="w", pady=(2, 0))

        author_lbl = tk.Label(header, text="Автор проекта: thriveera", font=("Segoe UI", 9, "italic"), fg="#6e7681", bg=DARK_BG)
        author_lbl.pack(anchor="w")

        # Step 1: Zed Status Card
        card_zed = ttk.Frame(main, style="Card.TFrame", padding=12)
        card_zed.pack(fill=tk.X, pady=(0, 10))

        lbl_zed_title = tk.Label(card_zed, text="1. Статус редактора Zed:", font=("Segoe UI", 10, "bold"), fg="#79c0ff", bg=CARD_BG)
        lbl_zed_title.pack(anchor="w")

        self.lbl_zed_status = tk.Label(card_zed, text="Поиск Zed...", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=CARD_BG)
        self.lbl_zed_status.pack(anchor="w", pady=(2, 0))

        self.lbl_agent_status = tk.Label(card_zed, text="", font=("Segoe UI", 9, "bold"), fg=TEXT_MUTED, bg=CARD_BG)
        self.lbl_agent_status.pack(anchor="w", pady=(2, 0))

        # Step 2: Install Path Card
        card_path = ttk.Frame(main, style="Card.TFrame", padding=12)
        card_path.pack(fill=tk.X, pady=(0, 10))

        lbl_path_title = tk.Label(card_path, text="2. Папка установки агента:", font=("Segoe UI", 10, "bold"), fg="#79c0ff", bg=CARD_BG)
        lbl_path_title.pack(anchor="w", pady=(0, 4))

        path_row = ttk.Frame(card_path, style="Card.TFrame")
        path_row.pack(fill=tk.X)

        entry_path = tk.Entry(path_row, textvariable=self.install_dir_var, font=("Consolas", 9), bg="#12161f", fg=TEXT_MAIN, insertbackground="white", relief="flat")
        entry_path.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 8))

        btn_browse = ttk.Button(path_row, text="Обзор...", style="Small.TButton", command=self.browse_dir)
        btn_browse.pack(side=tk.RIGHT)

        # Step 3: API Key Card
        card_key = ttk.Frame(main, style="Card.TFrame", padding=12)
        card_key.pack(fill=tk.X, pady=(0, 14))

        lbl_key_title = tk.Label(card_key, text="3. API-ключ XiaoAI (шифруется в Windows Credential Vault):", font=("Segoe UI", 10, "bold"), fg="#79c0ff", bg=CARD_BG)
        lbl_key_title.pack(anchor="w", pady=(0, 4))

        key_row = ttk.Frame(card_key, style="Card.TFrame")
        key_row.pack(fill=tk.X)

        self.entry_key = tk.Entry(key_row, textvariable=self.key_var, show="•", font=("Consolas", 10), bg="#12161f", fg=ACCENT_BLUE, insertbackground="white", relief="flat")
        self.entry_key.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 8))

        self.btn_eye = ttk.Button(key_row, text="👁️", width=3, style="Small.TButton", command=self.toggle_eye)
        self.btn_eye.pack(side=tk.LEFT, padx=(0, 6))

        btn_test = ttk.Button(key_row, text="🔍 Проверить", style="Small.TButton", command=self.test_key)
        btn_test.pack(side=tk.RIGHT)

        self.lbl_key_hint = tk.Label(card_key, text="🔒 Ключ надёжно сохраняется в локальном хранилище паролей Windows (DPAPI).", font=("Segoe UI", 8), fg="#6e7681", bg=CARD_BG)
        self.lbl_key_hint.pack(anchor="w", pady=(4, 0))

        # Action Buttons Frame
        btn_box = ttk.Frame(main)
        btn_box.pack(fill=tk.X, pady=(0, 8))

        self.btn_install = ttk.Button(btn_box, text="🚀 Установить / Обновить в Zed", style="Primary.TButton", command=self.install_clicked)
        self.btn_install.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        self.btn_uninstall = ttk.Button(btn_box, text="🗑️ Удалить из Zed", style="Danger.TButton", command=self.uninstall_clicked)
        self.btn_uninstall.pack(side=tk.RIGHT)

        # Status Bar
        self.status_lbl = tk.Label(main, textvariable=self.status_var, font=("Segoe UI", 9), fg=TEXT_MUTED, bg=DARK_BG)
        self.status_lbl.pack(anchor="w")

    def get_zed_settings_path(self):
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return os.path.join(appdata, "Zed", "settings.json")
        return ""

    def refresh_zed_status(self):
        settings_path = self.get_zed_settings_path()
        has_zed = os.path.exists(settings_path) if settings_path else False

        if has_zed:
            self.lbl_zed_status.config(text=f"✓ Настройки Zed: {settings_path}", fg="#3fb950")
            try:
                with open(settings_path, "r", encoding="utf-8") as sf:
                    data = json.load(sf)
                if "agent_servers" in data and "XiaoAI Agent" in data["agent_servers"]:
                    self.lbl_agent_status.config(text="● Статус агента: УСТАНОВЛЕН И АКТИВЕН В ZED", fg="#3fb950")
                    self.btn_uninstall.config(state="normal")
                else:
                    self.lbl_agent_status.config(text="○ Статус агента: НЕ УСТАНОВЛЕН В ZED", fg="#d29922")
            except Exception:
                self.lbl_agent_status.config(text="⚠️ Ошибка чтения settings.json", fg="#f85149")
        else:
            self.lbl_zed_status.config(text="⚠️ Папка настроек Zed будет создана автоматически при установке", fg="#d29922")
            self.lbl_agent_status.config(text="○ Статус агента: НЕ УСТАНОВЛЕН", fg="#8b949e")

    def toggle_eye(self):
        self.key_visible = not self.key_visible
        self.entry_key.config(show="" if self.key_visible else "•")

    def browse_dir(self):
        chosen = filedialog.askdirectory(initialdir=self.install_dir_var.get())
        if chosen:
            self.install_dir_var.set(chosen)

    def test_key(self):
        k = self.key_var.get().strip()
        if not k:
            messagebox.showwarning("Внимание", "Сначала введите API-ключ")
            return
        self.status_var.set("Проверка ключа на сервере XiaoAI...")
        self.status_lbl.config(fg=ACCENT_BLUE)

        def worker():
            try:
                req = urllib.request.Request(
                    "https://ai.itisxiao.cc/v1/models",
                    headers={"Authorization": f"Bearer {k}", "User-Agent": "Zed-XiaoAI-Agent/1.0"}
                )
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = json.loads(r.read().decode())
                    cnt = len(data.get("data", []))

                # Check balance
                bal = "Активен"
                try:
                    req_b = urllib.request.Request(f"https://ai.itisxiao.cc/key/{k}", headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req_b, timeout=8) as rb:
                        m = re.search(r"Account balance.*?<span>(.*?)</span>", rb.read().decode(), re.DOTALL)
                        if m:
                            bal = f"Баланс: {m.group(1).strip()}"
                except Exception:
                    pass

                self.after(0, lambda: self.on_test_success(cnt, bal))
            except Exception as e:
                self.after(0, lambda: self.on_test_err(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def on_test_success(self, cnt, bal):
        msg = f"✓ Ключ активен! Доступно моделей: {cnt}. {bal}"
        self.status_var.set(msg)
        self.status_lbl.config(fg="#3fb950")
        messagebox.showinfo("Успех", f"Ключ XiaoAI успешно прошёл проверку!\n\n{bal}\nМоделей в роутере: {cnt}")

    def on_test_err(self, err_text):
        self.status_var.set(f"❌ Ошибка проверки ключа: {err_text}")
        self.status_lbl.config(fg="#f85149")
        messagebox.showerror("Ошибка ключа", f"Не удалось проверить ключ на сервере:\n{err_text}")

    def install_clicked(self):
        k = self.key_var.get().strip()
        if not k:
            if not messagebox.askyesno("Ключ не введён", "API-ключ не введён. Продолжить установку без ключа? (Его можно будет ввести позже)"):
                return

        target_dir = self.install_dir_var.get().strip()
        if not target_dir:
            messagebox.showwarning("Ошибка", "Укажите папку установки")
            return

        self.btn_install.config(state="disabled")
        self.status_var.set("Установка агента и настройка Zed...")

        def worker():
            try:
                # 1. Create directory and write agent.py
                os.makedirs(target_dir, exist_ok=True)
                agent_path = os.path.join(target_dir, "agent.py")
                with open(agent_path, "w", encoding="utf-8") as f:
                    f.write(AGENT_CODE)

                # Write requirements
                req_path = os.path.join(target_dir, "requirements.txt")
                with open(req_path, "w", encoding="utf-8") as f:
                    f.write("agent-client-protocol>=1.0.0\npydantic>=2.7.0\nkeyring>=24.0.0\n")

                # 2. Store key in Keyring securely
                if k and keyring:
                    try:
                        keyring.set_password("xiaoai-agent", "api_key", k)
                    except Exception as e:
                        print("Keyring save error:", e)

                # 3. Update Zed settings.json
                settings_path = self.get_zed_settings_path()
                if not settings_path:
                    raise RuntimeError("Не удалось определить путь к настройкам Zed")

                os.makedirs(os.path.dirname(settings_path), exist_ok=True)

                settings = {}
                if os.path.exists(settings_path):
                    try:
                        with open(settings_path, "r", encoding="utf-8") as sf:
                            settings = json.load(sf)
                        # backup
                        shutil.copyfile(settings_path, settings_path + ".xiaoai_bak")
                    except Exception:
                        pass

                if "agent_servers" not in settings:
                    settings["agent_servers"] = {}

                settings["agent_servers"]["XiaoAI Agent"] = {
                    "type": "custom",
                    "command": "python",
                    "args": [agent_path]
                }

                with open(settings_path, "w", encoding="utf-8") as sf:
                    json.dump(settings, sf, indent=2, ensure_ascii=False)

                self.after(0, self.on_install_success)
            except Exception as e:
                self.after(0, lambda: self.on_install_fail(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def on_install_success(self):
        self.btn_install.config(state="normal")
        self.refresh_zed_status()
        self.status_var.set("🎉 Установка успешно завершена!")
        self.status_lbl.config(fg="#3fb950")

        ans = messagebox.askyesno(
            "Готово!",
            "XiaoAI Agent успешно установлен и подключен к Zed!\n\n"
            "Инструкция:\n"
            "1. Откройте Zed.\n"
            "2. Нажмите Ctrl + ? (панель агента).\n"
            "3. В селекторе выберите 'XiaoAI Agent'.\n"
            "4. Выбирайте любую модель XiaoAI!\n\n"
            "Хотите запустить Zed прямо сейчас?"
        )
        if ans:
            self.open_zed()

    def on_install_fail(self, err_text):
        self.btn_install.config(state="normal")
        self.status_var.set(f"❌ Ошибка установки: {err_text}")
        self.status_lbl.config(fg="#f85149")
        messagebox.showerror("Ошибка установки", f"Произошла ошибка при установке:\n{err_text}")

    def uninstall_clicked(self):
        settings_path = self.get_zed_settings_path()
        if not settings_path or not os.path.exists(settings_path):
            messagebox.showinfo("Инфо", "Файл настроек Zed не найден.")
            return

        if not messagebox.askyesno("Удаление агента", "Вы уверены, что хотите удалить XiaoAI Agent из редактора Zed?"):
            return

        try:
            with open(settings_path, "r", encoding="utf-8") as sf:
                settings = json.load(sf)

            if "agent_servers" in settings and "XiaoAI Agent" in settings["agent_servers"]:
                del settings["agent_servers"]["XiaoAI Agent"]

            with open(settings_path, "w", encoding="utf-8") as sf:
                json.dump(settings, sf, indent=2, ensure_ascii=False)

            # Ask about deleting stored key
            if keyring:
                try:
                    if keyring.get_password("xiaoai-agent", "api_key"):
                        if messagebox.askyesno("Удаление ключа", "Удалить также сохранённый API-ключ из системного хранилища паролей (Keyring)?"):
                            keyring.delete_password("xiaoai-agent", "api_key")
                            self.key_var.set("")
                except Exception:
                    pass

            # Optionally remove files
            target_dir = self.install_dir_var.get().strip()
            if target_dir and os.path.exists(target_dir):
                if messagebox.askyesno("Файлы агента", f"Удалить также папку с файлами агента?\n{target_dir}"):
                    shutil.rmtree(target_dir, ignore_errors=True)

            self.refresh_zed_status()
            self.status_var.set("XiaoAI Agent успешно удалён из Zed.")
            self.status_lbl.config(fg="#d29922")
            messagebox.showinfo("Успешно", "XiaoAI Agent был полностью отключен и удалён из Zed!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось выполнить удаление:\n{str(e)}")

    def open_zed(self):
        try:
            subprocess.Popen(["zed"], shell=True)
        except Exception:
            pass
        self.destroy()

if __name__ == "__main__":
    app = InstallerGUI()
    app.mainloop()
