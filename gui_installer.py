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
    try:
        import keyring
        keyring.set_password("xiaoai-agent", "api_key", key.strip())
        return True
    except Exception as e:
        print(f"Error saving to keyring: {e}", file=sys.stderr)
        return False

FALLBACK_MODELS = [
    {"id": "xgg/gpt-6.1-sol", "name": "GPT 6.1 Sol (XiaoAI)", "context": 400000},
    {"id": "xgg/gpt-6-astra", "name": "GPT 6 Astra (XiaoAI)", "context": 400000},
    {"id": "xgg/gpt-6-sol", "name": "GPT 6 Sol (XiaoAI)", "context": 400000},
    {"id": "xgg/gpt-6-luna", "name": "GPT 6 Luna (XiaoAI)", "context": 400000},
    {"id": "free/gpt-4o-mini", "name": "ChatGPT 4o mini [Free] (XiaoAI)", "context": 1000000},
    {"id": "claude/sonnet", "name": "Claude Sonnet (XiaoAI)", "context": 200000},
    {"id": "claude/opus", "name": "Claude Opus (XiaoAI)", "context": 200000},
    {"id": "claude/haiku", "name": "Claude Haiku (XiaoAI)", "context": 200000},
    {"id": "claude/fable", "name": "Claude Fable (XiaoAI)", "context": 200000},
    {"id": "free/deepseek-flash", "name": "DeepSeek Flash [Free] (XiaoAI)", "context": 1000000},
    {"id": "free/deepseek-v4-pro", "name": "DeepSeek V4 Pro [Free] (XiaoAI)", "context": 1000000},
    {"id": "free/kimi-k3", "name": "Kimi K3 [Free] (XiaoAI)", "context": 1000000},
    {"id": "free/qwen3.8-flash", "name": "Qwen 3.8 Flash [Free] (XiaoAI)", "context": 1000000},
    {"id": "free/qwen3.8-max", "name": "Qwen 3.8 Max [Free] (XiaoAI)", "context": 1000000},
    {"id": "free/glm-5.3", "name": "GLM 5.3 [Free] (XiaoAI)", "context": 1000000},
    {"id": "free/glm-5.3-prime", "name": "GLM 5.3 Prime [Free] (XiaoAI)", "context": 1000000},
    {"id": "free/GLM-5.3-Flash", "name": "GLM 5.3 Flash [Free] (XiaoAI)", "context": 1000000},
    {"id": "muse/muse", "name": "Muse Spark 1.3 (XiaoAI)", "context": 256000},
    {"id": "free/muse-spark-open", "name": "Muse Spark Open [Free] (XiaoAI)", "context": 1000000},
    {"id": "test/selena-ai", "name": "SelenaAI [Experimental] (XiaoAI)", "context": 1048576},
]

def fetch_xiaoai_catalog(base_url: str, api_key: str) -> List[Dict[str, Any]]:
    if not api_key:
        return FALLBACK_MODELS
    root_url = base_url.rstrip("/v1").rstrip("/")
    try:
        req = urllib.request.Request(
            f"{root_url}/api/key/models?format=opencode",
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": "Zed-XiaoAI-Agent/1.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
            results = []
            for mid, info in data.items():
                name = info.get("name") or mid
                ctx = info.get("limit", {}).get("context", 200000)
                results.append({"id": mid, "name": name, "context": ctx})
            if results:
                return results
    except Exception:
        pass
    try:
        req = urllib.request.Request(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": "Zed-XiaoAI-Agent/1.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())["data"]
            results = []
            for m in data:
                results.append({
                    "id": m["id"],
                    "name": m.get("name") or m["id"],
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
        options = [
            SessionConfigSelectOption(
                value=m["id"],
                name=m["name"],
                description=f"Max context: {m.get('context', 'unknown')} tokens"
            )
            for m in self.models_catalog
        ]
        return [
            SessionConfigOptionSelect(
                id="model",
                name="Model",
                description="Selected XiaoAI Model",
                category="model",
                current_value=self.current_model,
                options=options
            )
        ]

    async def initialize(self, protocol_version: int, client_capabilities=None, client_info=None, **kwargs: Any) -> InitializeResponse:
        self.refresh_models()
        return InitializeResponse(
            protocol_version=protocol_version,
            agent_info=Implementation(
                name="xiaoai-agent",
                version="1.0.1",
                title="XiaoAI Agent"
            )
        )

    async def new_session(self, cwd: str, additional_directories: Optional[List[str]] = None, mcp_servers: Optional[List[Any]] = None, **kwargs: Any) -> NewSessionResponse:
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

    async def set_config_option(self, config_id: str, session_id: str, value: Any, **kwargs: Any) -> SetSessionConfigOptionResponse:
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

        if user_text.startswith("/setkey"):
            parts = user_text.split(maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                new_key = parts[1].strip()
                if set_secure_api_key(new_key):
                    await self.send_text_chunk(session_id, "🔒 API-ключ успешно сохранён в зашифрованное хранилище системы (Keyring)!\\n")
                    self.refresh_models()
                    if self.conn:
                        await self.conn.session_update(
                            session_id=session_id,
                            update=ConfigOptionUpdate(config_options=self.build_config_options())
                        )
                else:
                    await self.send_text_chunk(session_id, "❌ Не удалось сохранить ключ в хранилище системы.\\n")
            else:
                await self.send_text_chunk(session_id, "Использование: `/setkey <ваш_ключ>`\\n")
            return PromptResponse(stop_reason="end_turn")

        if user_text.startswith("/sync"):
            await self.send_text_chunk(session_id, "🔄 Опрашиваю роутер XiaoAI и обновляю каталог моделей...\\n")
            self.refresh_models()
            cnt = len(self.models_catalog)
            await self.send_text_chunk(session_id, f"✅ Каталог успешно обновлен! Всего моделей доступно: {cnt}.\\n")
            if self.conn:
                await self.conn.session_update(
                    session_id=session_id,
                    update=ConfigOptionUpdate(config_options=self.build_config_options())
                )
            return PromptResponse(stop_reason="end_turn")

        if user_text.startswith("/status"):
            key = self.get_api_key()
            if not key:
                await self.send_text_chunk(session_id, "⚠️ API-ключ не найден. Используйте `/setkey <ключ>` для сохранения.\\n")
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
                    await self.send_text_chunk(session_id, f"🟢 **Статус XiaoAI:** Ключ активен. {bal}\\nТекущая модель: `{self.current_model}`\\n")
            except Exception as e:
                await self.send_text_chunk(session_id, f"❌ Ошибка проверки ключа: {e}\\n")
            return PromptResponse(stop_reason="end_turn")

        if user_text.startswith("/models"):
            await self.send_text_chunk(session_id, "📋 **Доступные модели XiaoAI:**\\n\\n")
            for m in self.models_catalog:
                await self.send_text_chunk(session_id, f"- **`{m['id']}`** — {m['name']} *(контекст: {m.get('context', 'N/A')})*\\n")
            return PromptResponse(stop_reason="end_turn")

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
                "⚠️ **Ошибка:** API-ключ XiaoAI не обнаружен.\\nИспользуйте `/setkey <ваш_ключ>` прямо в этом чате.\\n"
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
                f"❌ **Ошибка XiaoAI API ({e.code}):** {e.reason}\\n`{err_body}`\\n"
            )
        except Exception as e:
            await self.send_text_chunk(
                session_id,
                f"❌ **Не удалось выполнить запрос:** {e}\\n"
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
        self.title("XiaoAI Agent · Установщик для Zed")
        self.geometry("640x580")
        self.resizable(False, False)
        self.configure(bg=DARK_BG)

        # Center on screen
        self.eval("tk::PlaceWindow . center")

        self.key_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ожидание ввода ключа...")
        self.install_dir_var = tk.StringVar(
            value=os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), ".zed", "agents", "xiaoai-agent")
        )
        self.key_visible = False

        # Try to read existing key from keyring
        if keyring:
            try:
                existing = keyring.get_password("xiaoai-agent", "api_key")
                if existing:
                    self.key_var.set(existing)
            except Exception:
                pass

        self.setup_ui()

    def setup_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", background=DARK_BG, foreground=TEXT_MAIN, font=("Segoe UI", 10))
        style.configure("Card.TFrame", background=CARD_BG, relief="flat")
        style.configure("Primary.TButton", font=("Segoe UI", 11, "bold"), background=ACCENT_GREEN, foreground="#ffffff", borderwidth=0, padding=10)
        style.map("Primary.TButton", background=[("active", ACCENT_GREEN_HOVER), ("disabled", "#194a24")])
        style.configure("Small.TButton", font=("Segoe UI", 9), background="#2b3242", foreground=TEXT_MAIN, borderwidth=0, padding=5)
        style.map("Small.TButton", background=[("active", "#3b4458")])

        main = ttk.Frame(self, padding=20)
        main.pack(fill=tk.BOTH, expand=True)

        # Header Banner
        header = ttk.Frame(main)
        header.pack(fill=tk.X, pady=(0, 16))

        title_lbl = tk.Label(header, text="⚡ XiaoAI External Agent", font=("Segoe UI", 18, "bold"), fg=ACCENT_BLUE, bg=DARK_BG)
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(header, text="Автоматическая установка и интеграция роутера XiaoAI в редактор Zed", font=("Segoe UI", 10), fg=TEXT_MUTED, bg=DARK_BG)
        sub_lbl.pack(anchor="w", pady=(2, 0))

        author_lbl = tk.Label(header, text="Автор проекта: thriveera", font=("Segoe UI", 9, "italic"), fg="#6e7681", bg=DARK_BG)
        author_lbl.pack(anchor="w")

        # Step 1: Zed Status Card
        card_zed = ttk.Frame(main, style="Card.TFrame", padding=12)
        card_zed.pack(fill=tk.X, pady=(0, 12))

        appdata = os.environ.get("APPDATA", "")
        zed_settings = os.path.join(appdata, "Zed", "settings.json") if appdata else ""
        has_zed = os.path.exists(zed_settings)

        lbl_zed_title = tk.Label(card_zed, text="1. Статус редактора Zed:", font=("Segoe UI", 10, "bold"), fg="#79c0ff", bg=CARD_BG)
        lbl_zed_title.pack(anchor="w")

        zed_status_text = f"✓ Обнаружен: {zed_settings}" if has_zed else "⚠️ Папка настроек Zed будет создана автоматически"
        zed_status_fg = "#3fb950" if has_zed else "#d29922"
        lbl_zed_status = tk.Label(card_zed, text=zed_status_text, font=("Segoe UI", 9), fg=zed_status_fg, bg=CARD_BG)
        lbl_zed_status.pack(anchor="w", pady=(2, 0))

        # Step 2: Install Path Card
        card_path = ttk.Frame(main, style="Card.TFrame", padding=12)
        card_path.pack(fill=tk.X, pady=(0, 12))

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
        card_key.pack(fill=tk.X, pady=(0, 16))

        lbl_key_title = tk.Label(card_key, text="3. API-ключ XiaoAI (будет зашифрован в Keyring):", font=("Segoe UI", 10, "bold"), fg="#79c0ff", bg=CARD_BG)
        lbl_key_title.pack(anchor="w", pady=(0, 4))

        key_row = ttk.Frame(card_key, style="Card.TFrame")
        key_row.pack(fill=tk.X)

        self.entry_key = tk.Entry(key_row, textvariable=self.key_var, show="•", font=("Consolas", 10), bg="#12161f", fg=ACCENT_BLUE, insertbackground="white", relief="flat")
        self.entry_key.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 8))

        self.btn_eye = ttk.Button(key_row, text="👁️", width=3, style="Small.TButton", command=self.toggle_eye)
        self.btn_eye.pack(side=tk.LEFT, padx=(0, 6))

        btn_test = ttk.Button(key_row, text="🔍 Проверить", style="Small.TButton", command=self.test_key)
        btn_test.pack(side=tk.RIGHT)

        self.lbl_key_hint = tk.Label(card_key, text="🔒 Ключ шифруется Windows Credential Vault (DPAPI) и защищён от утечек.", font=("Segoe UI", 8), fg="#6e7681", bg=CARD_BG)
        self.lbl_key_hint.pack(anchor="w", pady=(4, 0))

        # Install Action Button
        self.btn_install = ttk.Button(main, text="🚀 Установить XiaoAI Agent в Zed", style="Primary.TButton", command=self.install_clicked)
        self.btn_install.pack(fill=tk.X, pady=(0, 8))

        # Status Bar
        self.status_lbl = tk.Label(main, textvariable=self.status_var, font=("Segoe UI", 9), fg=TEXT_MUTED, bg=DARK_BG)
        self.status_lbl.pack(anchor="w")

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
                        import re
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
                appdata = os.environ.get("APPDATA", "")
                settings_path = os.path.join(appdata, "Zed", "settings.json")
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

                # Configure without plaintext key!
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
        self.status_var.set("🎉 Установка успешно завершена!")
        self.status_lbl.config(fg="#3fb950")
        self.btn_install.config(text="✓ Успешно установлено в Zed", state="disabled")

        btn_open_zed = ttk.Button(self, text="🚀 Запустить Zed Editor", style="Primary.TButton", command=self.open_zed)
        btn_open_zed.pack(fill=tk.X, padx=20, pady=(0, 10))

        messagebox.showinfo(
            "Готово!",
            "XiaoAI Agent успешно установлен и подключен к Zed!\n\n"
            "Инструкция:\n"
            "1. Откройте Zed.\n"
            "2. Нажмите Ctrl + ? (панель агента).\n"
            "3. В селекторе агентов выберите 'XiaoAI Agent'.\n"
            "4. Выбирайте любую модель из выпадающего списка!"
        )

    def on_install_fail(self, err_text):
        self.btn_install.config(state="normal")
        self.status_var.set(f"❌ Ошибка установки: {err_text}")
        self.status_lbl.config(fg="#f85149")
        messagebox.showerror("Ошибка установки", f"Произошла ошибка при установке:\n{err_text}")

    def open_zed(self):
        try:
            subprocess.Popen(["zed"], shell=True)
        except Exception:
            pass
        self.destroy()

if __name__ == "__main__":
    app = InstallerGUI()
    app.mainloop()
