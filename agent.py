"""
XiaoAI ACP Agent for Zed Editor
An Agent Client Protocol (ACP) server connecting Zed to the XiaoAI model router.

Author: thriveera (https://github.com/thriveera)
License: MIT
"""

import os
import sys
import json
import time
import re
import asyncio
import urllib.request
import platform
from typing import Any, Dict, List, Optional

import acp
from acp.schema import (
    InitializeRequest, InitializeResponse, Implementation,
    AgentCapabilities, PromptCapabilities, McpCapabilities,
    NewSessionRequest, NewSessionResponse,
    PromptRequest, PromptResponse,
    SetSessionConfigOptionSelectRequest, SetSessionConfigOptionBooleanRequest,
    SetSessionConfigOptionResponse,
    SetSessionModeRequest, SetSessionModeResponse,
    SessionConfigOptionSelect, SessionConfigSelectOption,
    SessionMode, SessionModeState,
    AgentMessageChunk, AgentThoughtChunk, TextContentBlock, UsageUpdate,
    ConfigOptionUpdate
)


def load_env_file():
    """Loads environment variables from .env file if present in the agent directory."""
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
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(AGENT_DIR, "config.json")
CACHE_FILE = os.path.join(AGENT_DIR, "models_cache.json")


def load_agent_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"sync_interval": "startup", "last_sync": 0}


def save_agent_config(cfg: Dict[str, Any]):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def clean_model_name(name: str) -> str:
    """Removes promotional notes in parentheses to display a clean, elegant name."""
    name = re.sub(r'\s*\([^)]*(?:cheaper|latest|cheapest|world|new)[^)]*\)', '', name, flags=re.IGNORECASE)
    return name.strip()


def get_secure_api_key() -> str:
    """
    Retrieves the API key securely.
    Priority:
    1. OS Encrypted Keyring (Windows Credential Locker / macOS Keychain / Linux SecretService)
    2. Environment variable XIAOAI_API_KEY
    """
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
    """Stores the API key into the OS encrypted credential store."""
    try:
        import keyring
        keyring.set_password("xiaoai-agent", "api_key", key.strip())
        return True
    except Exception as e:
        print(f"Error saving to keyring: {e}", file=sys.stderr)
        return False


FALLBACK_MODELS = [
    {"id": "xgg/gpt-6.1-sol", "name": "GPT 6.1 Sol", "clean_name": "GPT 6.1 Sol", "price": "$0.08 / 1M токенов", "short_price": "$0.08 / 1M", "context": 400000},
    {"id": "xgg/gpt-6-astra", "name": "GPT 6 Astra", "clean_name": "GPT 6 Astra", "price": "$0.20 / 1M токенов", "short_price": "$0.20 / 1M", "context": 400000},
    {"id": "xgg/gpt-6-sol", "name": "GPT 6 Sol", "clean_name": "GPT 6 Sol", "price": "$0.08 / 1M токенов", "short_price": "$0.08 / 1M", "context": 400000},
    {"id": "xgg/gpt-6-luna", "name": "GPT 6 Luna", "clean_name": "GPT 6 Luna", "price": "$0.0035 / 1M токенов", "short_price": "$0.0035 / 1M", "context": 400000},
    {"id": "free/gpt-4o-mini", "name": "ChatGPT 4o mini", "clean_name": "ChatGPT 4o mini", "price": "Free", "short_price": "Free", "context": 1000000},
    {"id": "test/selena-ai", "name": "SelenaAI", "clean_name": "SelenaAI", "price": "$0.01 / 1M токенов", "short_price": "$0.01 / 1M", "context": 1048576},
    {"id": "muse/muse", "name": "Muse Spark 1.3", "clean_name": "Muse Spark 1.3", "price": "$0.01 / 1M токенов", "short_price": "$0.01 / 1M", "context": 256000},
    {"id": "claude/fable", "name": "Claude Fable", "clean_name": "Claude Fable", "price": "$0.25 / 1M токенов", "short_price": "$0.25 / 1M", "context": 200000},
    {"id": "claude/opus", "name": "Claude Opus", "clean_name": "Claude Opus", "price": "$0.10 / 1M токенов", "short_price": "$0.10 / 1M", "context": 200000},
    {"id": "claude/sonnet", "name": "Claude Sonnet", "clean_name": "Claude Sonnet", "price": "$0.08 / 1M токенов", "short_price": "$0.08 / 1M", "context": 200000},
    {"id": "claude/haiku", "name": "Claude Haiku", "clean_name": "Claude Haiku", "price": "$0.03 / 1M токенов", "short_price": "$0.03 / 1M", "context": 200000},
    {"id": "free/deepseek-flash", "name": "DeepSeek Flash", "clean_name": "DeepSeek Flash", "price": "Free", "short_price": "Free", "context": 1000000},
    {"id": "free/deepseek-v4-pro", "name": "DeepSeek V4 Pro", "clean_name": "DeepSeek V4 Pro", "price": "Free", "short_price": "Free", "context": 1000000},
    {"id": "free/kimi-k3", "name": "Kimi K3", "clean_name": "Kimi K3", "price": "Free", "short_price": "Free", "context": 1000000},
    {"id": "free/qwen3.8-flash", "name": "Qwen 3.8 Flash", "clean_name": "Qwen 3.8 Flash", "price": "Free", "short_price": "Free", "context": 1000000},
    {"id": "free/qwen3.8-max", "name": "Qwen 3.8 Max", "clean_name": "Qwen 3.8 Max", "price": "Free", "short_price": "Free", "context": 1000000},
    {"id": "free/glm-5.3", "name": "GLM 5.3", "clean_name": "GLM 5.3", "price": "Free", "short_price": "Free", "context": 1000000},
    {"id": "free/glm-5.3-prime", "name": "GLM 5.3 Prime", "clean_name": "GLM 5.3 Prime", "price": "Free", "short_price": "Free", "context": 1000000},
    {"id": "free/GLM-5.3-Flash", "name": "GLM 5.3 Flash", "clean_name": "GLM 5.3 Flash", "price": "Free", "short_price": "Free", "context": 1000000},
    {"id": "free/muse-spark-open", "name": "Muse Spark Open", "clean_name": "Muse Spark Open", "price": "Free", "short_price": "Free", "context": 1000000},
]


def fetch_xiaoai_catalog(base_url: str, api_key: str) -> List[Dict[str, Any]]:
    """Fetches real-time model catalog, context window, and exact token pricing from XiaoAI router."""
    if not api_key:
        return FALLBACK_MODELS

    root_url = base_url.rstrip("/v1").rstrip("/")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Zed-XiaoAI-Agent/1.0"
    }

    # 1. Fetch exact context limits and output limits from opencode endpoint
    model_limits = {}
    try:
        req_oc = urllib.request.Request(f"{root_url}/api/key/models?format=opencode", headers=headers)
        with urllib.request.urlopen(req_oc, timeout=8) as r:
            oc_data = json.loads(r.read().decode())
            for mid, info in oc_data.items():
                lim = info.get("limit", {})
                model_limits[mid] = {
                    "context": lim.get("context", 200000),
                    "output": lim.get("output", 32000),
                    "reasoning": info.get("reasoning", True)
                }
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
                c_name = clean_model_name(raw_name)
                mult = float(m.get("multiplier", 0.0))
                if mult == 0.0:
                    price_str = "Free ($0.00 / 1M)"
                    short_price = "Free"
                else:
                    price_val = f"${mult:.4f}".rstrip("0").rstrip(".")
                    price_str = f"{price_val} / 1M токенов"
                    short_price = f"{price_val} / 1M"

                m_info = model_limits.get(mid, {"context": 200000, "output": 32000, "reasoning": True})
                results.append({
                    "id": mid,
                    "name": raw_name,
                    "clean_name": c_name,
                    "price": price_str,
                    "short_price": short_price,
                    "multiplier": mult,
                    "context": m_info["context"],
                    "output": m_info["output"],
                    "reasoning": m_info["reasoning"]
                })
            if results:
                # Save to cache file
                try:
                    with open(CACHE_FILE, "w", encoding="utf-8") as cf:
                        json.dump(results, cf, indent=2, ensure_ascii=False)
                except Exception:
                    pass
                return results
    except Exception:
        pass

    # 3. Try to read from local cache file if available
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as cf:
                cached = json.load(cf)
                if cached:
                    return cached
        except Exception:
            pass

    return FALLBACK_MODELS


class XiaoAiAgent(acp.Agent):
    def __init__(self):
        super().__init__()
        self.conn: Optional[acp.Client] = None
        self.base_url = DEFAULT_BASE_URL
        self.config = load_agent_config()
        self.sync_interval = self.config.get("sync_interval", "startup")
        self.models_catalog: List[Dict[str, Any]] = []
        self.current_model = "xgg/gpt-6.1-sol"
        self.current_mode = "code"
        self.session_history: Dict[str, List[Dict[str, str]]] = {}
        self.session_cwds: Dict[str, str] = {}
        self.session_usage: Dict[str, int] = {}
        self.thinking_level = self.config.get("thinking_level", "high")
        self.custom_thinking_budget: Optional[int] = self.config.get("custom_thinking_budget")
        self.mode = self.config.get("mode", "yolo")

    def on_connect(self, conn: acp.Client) -> None:
        self.conn = conn

    def get_api_key(self) -> str:
        return get_secure_api_key()

    def should_sync(self, force: bool = False) -> bool:
        if force:
            return True
        if self.sync_interval == "startup":
            return True
        if self.sync_interval == "manual":
            return len(self.models_catalog) == 0
        now = time.time()
        last_sync = self.config.get("last_sync", 0)
        if self.sync_interval == "6h":
            return (now - last_sync) > 6 * 3600 or len(self.models_catalog) == 0
        if self.sync_interval == "24h":
            return (now - last_sync) > 24 * 3600 or len(self.models_catalog) == 0
        return True

    def refresh_models(self, force: bool = False):
        key = self.get_api_key()
        if self.should_sync(force):
            self.models_catalog = fetch_xiaoai_catalog(self.base_url, key)
            self.config["last_sync"] = int(time.time())
            save_agent_config(self.config)
        elif not self.models_catalog:
            # Load from cache or fallback
            if os.path.exists(CACHE_FILE):
                try:
                    with open(CACHE_FILE, "r", encoding="utf-8") as cf:
                        self.models_catalog = json.load(cf)
                except Exception:
                    self.models_catalog = FALLBACK_MODELS
            else:
                self.models_catalog = FALLBACK_MODELS

        if not any(m["id"] == self.current_model for m in self.models_catalog) and self.models_catalog:
            self.current_model = self.models_catalog[0]["id"]

    def build_config_options(self) -> List[SessionConfigOptionSelect]:
        model_options = []
        for m in self.models_catalog:
            price_tag = m.get("short_price") or m.get("price", "")
            c_name = m.get("clean_name") or clean_model_name(m.get("name", m["id"]))
            
            # The title displayed on the model selection button in Zed:
            display_title = f"{c_name} — {price_tag}"
            
            ctx = m.get("context", 200000)
            ctx_str = f"{ctx // 1000}k" if isinstance(ctx, int) and ctx >= 1000 else str(ctx)
            desc = f"Прайс: {m.get('price', 'N/A')} | Контекст: {ctx_str} токенов"

            model_options.append(
                SessionConfigSelectOption(
                    value=m["id"],
                    name=display_title,
                    description=desc
                )
            )

        sync_options = [
            SessionConfigSelectOption(
                value="startup",
                name="🔄 При каждом запуске агента (Авто)",
                description="Автоматически синхронизировать модели, контекст и прайсы при каждом запуске агента"
            ),
            SessionConfigSelectOption(
                value="6h",
                name="⏱️ Каждые 6 часов",
                description="Автоматически обновлять каталог и прайсы каждые 6 часов"
            ),
            SessionConfigSelectOption(
                value="24h",
                name="📅 Каждые 24 часа",
                description="Автоматически обновлять каталог и прайсы один раз в сутки"
            ),
            SessionConfigSelectOption(
                value="manual",
                name="✋ Вручную (/sync в чате)",
                description="Обновлять каталог только при вызове команды /sync"
            )
        ]

        # Determine model output capacity
        cur_output = 32000
        for m in self.models_catalog:
            if m["id"] == self.current_model:
                cur_output = m.get("output", 32000)
                break

        max_label = f"Max ({cur_output // 1000}k)" if cur_output >= 1000 else f"Max ({cur_output})"

        thinking_options = [
            SessionConfigSelectOption(
                value="off",
                name="Off (0)",
                description="Отключить рассуждения (максимальная скорость и экономия токенов)"
            ),
            SessionConfigSelectOption(
                value="minimal",
                name="Minimal (1k)",
                description="Минимальный уровень рассуждений (~1 024 токена)"
            ),
            SessionConfigSelectOption(
                value="low",
                name="Low (2k)",
                description="Базовый уровень рассуждений (~2 048 токенов)"
            ),
            SessionConfigSelectOption(
                value="medium",
                name="Medium (8k)",
                description="Сбалансированная глубина рассуждений (~8 192 токена)"
            ),
            SessionConfigSelectOption(
                value="high",
                name="High (16k)",
                description="Глубокое рассуждение для сложных задач (~16 384 токена)"
            ),
            SessionConfigSelectOption(
                value="ultra",
                name="Ultra (32k)",
                description="Ультра-глубокое рассуждение и верификация (~32 768 токенов)"
            ),
            SessionConfigSelectOption(
                value="max",
                name=max_label,
                description=f"Максимально допустимый лимит генерации модели (~{cur_output} токенов)"
            )
        ]

        if self.custom_thinking_budget:
            thinking_options.insert(1, SessionConfigSelectOption(
                value=f"custom_{self.custom_thinking_budget}",
                name=f"Custom ({self.custom_thinking_budget})",
                description=f"Пользовательский бюджет: {self.custom_thinking_budget} токенов"
            ))

        mode_options = [
            SessionConfigSelectOption(
                value="default",
                name="Default",
                description="Стандартный режим диалога"
            ),
            SessionConfigSelectOption(
                value="auto_edit",
                name="Auto Edit",
                description="Автоматическое применение предложенных правок"
            ),
            SessionConfigSelectOption(
                value="yolo",
                name="YOLO",
                description="Максимальная автономность агента без лишних подтверждений"
            )
        ]

        return [
            SessionConfigOptionSelect(
                id="model",
                name="Model",
                description="Выбор модели с актуальной ценой за 1M токенов",
                category="model",
                current_value=self.current_model,
                options=model_options
            ),
            SessionConfigOptionSelect(
                id="thinking_level",
                name="Thinking Level",
                description="Уровень рассуждений нейросети (Thinking / Reasoning Effort)",
                category="thought_level",
                current_value=self.thinking_level,
                options=thinking_options
            ),
            SessionConfigOptionSelect(
                id="mode",
                name="Mode",
                description="Режим работы агента",
                category="mode",
                current_value=self.mode,
                options=mode_options
            ),
            SessionConfigOptionSelect(
                id="sync_interval",
                name="Sync Interval",
                description="Частота автообновления каталога моделей, контекста и цен",
                category="model_config",
                current_value=self.sync_interval,
                options=sync_options
            )
        ]

    def get_user_instructions(self, session_id: str) -> Optional[str]:
        """Loads user-defined custom instructions / system prompt from Zed settings or workspace rules."""
        # 1. Check workspace .zed/instructions.md or instructions.md
        cwd = self.session_cwds.get(session_id)
        if cwd and os.path.exists(cwd):
            for rel in [".zed/instructions.md", "instructions.md", ".zed/rules", ".rules"]:
                candidate = os.path.join(cwd, rel)
                if os.path.isfile(candidate):
                    try:
                        with open(candidate, "r", encoding="utf-8") as f:
                            content = f.read().strip()
                            if content:
                                return content
                    except Exception:
                        pass

        # 2. Check Zed global settings.json
        settings_path = None
        system = platform.system()
        home = os.path.expanduser("~")
        if system == "Windows":
            appdata = os.environ.get("APPDATA")
            if appdata:
                settings_path = os.path.join(appdata, "Zed", "settings.json")
        elif system == "Darwin":
            p1 = os.path.join(home, "Library", "Application Support", "Zed", "settings.json")
            settings_path = p1 if os.path.exists(p1) else os.path.join(home, ".config", "zed", "settings.json")
        else:
            settings_path = os.path.join(home, ".config", "zed", "settings.json")

        if settings_path and os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    s = json.load(f)
                    for key in ["custom_instructions", "system_prompt"]:
                        if key in s and isinstance(s[key], str) and s[key].strip():
                            return s[key].strip()
                    for parent in ["assistant", "agent"]:
                        if parent in s and isinstance(s[parent], dict):
                            for key in ["custom_instructions", "system_prompt", "instructions"]:
                                if key in s[parent] and isinstance(s[parent][key], str) and s[parent][key].strip():
                                    return s[parent][key].strip()
            except Exception:
                pass
        return None

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
            agent_capabilities=AgentCapabilities(
                prompt_capabilities=PromptCapabilities(
                    embedded_context=True,
                    image=True
                ),
                mcp_capabilities=McpCapabilities(
                    http=True,
                    sse=True,
                    acp=True
                )
            ),
            agent_info=Implementation(
                name="xiaoai-agent",
                version="1.1.5",
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
        self.session_cwds[session_id] = cwd
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
        elif config_id == "thinking_level":
            val_str = str(value)
            self.thinking_level = val_str
            if val_str.startswith("custom_"):
                try:
                    self.custom_thinking_budget = int(val_str.split("_")[1])
                except Exception:
                    pass
            else:
                self.custom_thinking_budget = None
            self.config["thinking_level"] = self.thinking_level
            self.config["custom_thinking_budget"] = self.custom_thinking_budget
            save_agent_config(self.config)
        elif config_id == "mode":
            self.mode = str(value)
            self.config["mode"] = self.mode
            save_agent_config(self.config)
        elif config_id == "sync_interval":
            self.sync_interval = str(value)
            self.config["sync_interval"] = self.sync_interval
            save_agent_config(self.config)
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
        text_parts = []
        for block in prompt:
            if hasattr(block, "text") and block.text:
                text_parts.append(block.text)
            elif hasattr(block, "resource"):
                res = block.resource
                if hasattr(res, "text") and res.text:
                    tag = getattr(res, "uri", "Resource")
                    uri_tag = f"[{tag}]\n" if tag else ""
                    text_parts.append(f"{uri_tag}{res.text}")
            elif isinstance(block, dict):
                if "text" in block and block["text"]:
                    text_parts.append(block["text"])
                elif "resource" in block and isinstance(block["resource"], dict):
                    res = block["resource"]
                    if "text" in res and res["text"]:
                        tag = res.get("uri", "Resource")
                        uri_tag = f"[{tag}]\n" if "uri" in res else ""
                        text_parts.append(f"{uri_tag}{res['text']}")
                elif "content" in block and isinstance(block["content"], str):
                    text_parts.append(block["content"])

        user_text = "\n\n".join(text_parts).strip()

        # Slash command: /setkey <key>
        if user_text.startswith("/setkey"):
            parts = user_text.split(maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                new_key = parts[1].strip()
                if set_secure_api_key(new_key):
                    await self.send_text_chunk(session_id, "🔒 API-ключ успешно сохранён в зашифрованное хранилище системы (Keyring)!\n")
                    self.refresh_models(force=True)
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
            await self.send_text_chunk(session_id, "🔄 Опрашиваю роутер XiaoAI и обновляю каталог, контекст и прайсы моделей...\n")
            self.refresh_models(force=True)
            cnt = len(self.models_catalog)
            await self.send_text_chunk(session_id, f"✅ Каталог успешно обновлен! Всего моделей доступно: {cnt}.\n")
            if self.conn:
                await self.conn.session_update(
                    session_id=session_id,
                    update=ConfigOptionUpdate(config_options=self.build_config_options())
                )
            return PromptResponse(stop_reason="end_turn")

        # Slash command: /thinking or /reasoning <val>
        if user_text.startswith("/thinking") or user_text.startswith("/reasoning"):
            parts = user_text.split(maxsplit=1)
            if len(parts) > 1 and parts[1].strip():
                arg = parts[1].strip().lower()
                if arg.isdigit():
                    num = int(arg)
                    self.custom_thinking_budget = num
                    self.thinking_level = f"custom_{num}"
                    await self.send_text_chunk(session_id, f"💡 Установлен точный бюджет размышлений: **{num} токенов**.\n")
                elif arg in ["off", "minimal", "low", "medium", "high", "ultra", "max"]:
                    self.thinking_level = arg
                    self.custom_thinking_budget = None
                    await self.send_text_chunk(session_id, f"💡 Уровень рассуждений переключен на: **{arg.capitalize()}**.\n")
                else:
                    await self.send_text_chunk(session_id, "Использование: `/thinking <off|minimal|low|medium|high|ultra|max|число_токенов>`\n")
                
                self.config["thinking_level"] = self.thinking_level
                self.config["custom_thinking_budget"] = self.custom_thinking_budget
                save_agent_config(self.config)
                if self.conn:
                    await self.conn.session_update(
                        session_id=session_id,
                        update=ConfigOptionUpdate(config_options=self.build_config_options())
                    )
            else:
                curr = f"{self.custom_thinking_budget} токенов" if self.custom_thinking_budget else self.thinking_level
                await self.send_text_chunk(session_id, f"💡 Текущий режим рассуждений: **{curr}**\nДля изменения используйте селектор внизу или команду `/thinking <число>`.\n")
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
                    bal = "Активен"
                    m = re.search(r"Account balance.*?<span>(.*?)</span>", html, re.DOTALL)
                    if m:
                        bal = f"Баланс: {m.group(1).strip()}"
                    sync_labels = {
                        "startup": "При каждом запуске (Авто)",
                        "6h": "Каждые 6 часов",
                        "24h": "Каждые 24 часа",
                        "manual": "Только вручную (/sync)"
                    }
                    sync_txt = sync_labels.get(self.sync_interval, self.sync_interval)
                    await self.send_text_chunk(session_id, f"🟢 **Статус XiaoAI:** Ключ активен. {bal}\nТекущая модель: `{self.current_model}`\nРежим синхронизации: `{sync_txt}`\nХранилище ключа: Зашифрованное (Keyring/OS Vault)\n")
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
                c_name = m.get("clean_name") or clean_model_name(m.get("name", m["id"]))
                await self.send_text_chunk(session_id, f"| **{c_name}** | `{price}` | {ctx_str} | `{m['id']}` |\n")
            return PromptResponse(stop_reason="end_turn")

        # Regular Chat Turn
        history = self.session_history.setdefault(session_id, [])
        history.append({"role": "user", "content": user_text})

        # Forward user custom instructions if configured by the user in Zed, otherwise pure router mode
        payload_messages = []
        user_instructions = self.get_user_instructions(session_id)
        if user_instructions:
            payload_messages.append({"role": "system", "content": user_instructions})
        payload_messages.extend(history[-20:])

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
            payload_dict = {
                "model": self.current_model,
                "messages": payload_messages,
                "stream": True,
                "stream_options": {"include_usage": True}
            }
            # Map thinking level to exact budgets and reasoning effort
            budget_map = {
                "minimal": 1024,
                "low": 2048,
                "medium": 8192,
                "high": 16384,
                "ultra": 32768,
                "max": 64000
            }
            effort_map = {
                "minimal": "low",
                "low": "low",
                "medium": "medium",
                "high": "high",
                "ultra": "high",
                "max": "high"
            }

            if self.thinking_level != "off":
                if self.custom_thinking_budget:
                    b_val = self.custom_thinking_budget
                    eff = "high" if b_val >= 16000 else ("medium" if b_val >= 5000 else "low")
                else:
                    b_val = budget_map.get(self.thinking_level, 8192)
                    eff = effort_map.get(self.thinking_level, "medium")

                payload_dict["reasoning_effort"] = eff
                if "claude" in self.current_model.lower():
                    payload_dict["thinking"] = {"type": "enabled", "budget_tokens": b_val}

            req_data = json.dumps(payload_dict).encode("utf-8")

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
            token_stats = {"total_tokens": 0}

            def perform_stream():
                chunks = []
                try:
                    resp = urllib.request.urlopen(req, timeout=60)
                except urllib.error.HTTPError as e:
                    # If upstream model does not support reasoning_effort/thinking, automatically fallback
                    if e.code == 400 and ("reasoning_effort" in payload_dict or "thinking" in payload_dict):
                        fallback_dict = {
                            "model": self.current_model,
                            "messages": payload_messages,
                            "stream": True,
                            "stream_options": {"include_usage": True}
                        }
                        req_fb = urllib.request.Request(
                            endpoint,
                            data=json.dumps(fallback_dict).encode("utf-8"),
                            headers={
                                "Authorization": f"Bearer {key}",
                                "Content-Type": "application/json",
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Zed-XiaoAI-Agent/1.0"
                            }
                        )
                        resp = urllib.request.urlopen(req_fb, timeout=60)
                    else:
                        raise

                with resp:
                    for line in resp:
                        line = line.decode("utf-8", errors="replace").strip()
                        if line.startswith("data: "):
                            raw_data = line[6:]
                            if raw_data == "[DONE]":
                                break
                            try:
                                c = json.loads(raw_data)
                                if c.get("usage"):
                                    token_stats["total_tokens"] = c["usage"].get("total_tokens", token_stats["total_tokens"])
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

            # Update context usage gauge in Zed
            ctx_size = 200000
            for m in self.models_catalog:
                if m["id"] == self.current_model:
                    ctx_size = m.get("context", 200000)
                    break

            if token_stats["total_tokens"] > 0:
                self.session_usage[session_id] = token_stats["total_tokens"]
            else:
                self.session_usage[session_id] = self.session_usage.get(session_id, 0) + (len(user_text) + len(full_reply)) // 4

            if self.conn:
                try:
                    await self.conn.session_update(
                        session_id=session_id,
                        update=UsageUpdate(
                            used=self.session_usage[session_id],
                            size=ctx_size
                        )
                    )
                except Exception:
                    pass

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
