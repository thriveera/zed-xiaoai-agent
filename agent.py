"""
XiaoAI ACP Agent for Zed Editor
An Agent Client Protocol (ACP) server connecting Zed to the XiaoAI model router.

Author: thriveera (https://github.com/thriveera)
License: MIT
"""

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
    """Fetches real-time model catalog and exact token pricing from XiaoAI router."""
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
