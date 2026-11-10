"""
XiaoAI ACP Agent for Zed Editor
An Agent Client Protocol (ACP) server connecting Zed to the XiaoAI model router.
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
DEFAULT_KEY = os.environ.get("XIAOAI_API_KEY", "")


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
    """Fetches real-time model catalog from XiaoAI router."""
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
        self.api_key = DEFAULT_KEY
        self.models_catalog: List[Dict[str, Any]] = []
        self.current_model = "xgg/gpt-6.1-sol"
        self.current_mode = "code"
        self.session_history: Dict[str, List[Dict[str, str]]] = {}

    def on_connect(self, conn: acp.Client) -> None:
        self.conn = conn

    def get_api_key(self) -> str:
        return os.environ.get("XIAOAI_API_KEY", self.api_key)

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
                version="1.0.0",
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
        # Extract user text
        user_text = ""
        for block in prompt:
            if hasattr(block, "text"):
                user_text += block.text
            elif isinstance(block, dict) and "text" in block:
                user_text += block["text"]

        user_text = user_text.strip()

        # Handle built-in slash commands
        if user_text.startswith("/sync"):
            await self.send_text_chunk(session_id, "🔄 Опрашиваю роутер XiaoAI и обновляю каталог моделей...\n")
            self.refresh_models()
            cnt = len(self.models_catalog)
            await self.send_text_chunk(session_id, f"✅ Каталог успешно обновлен! Всего моделей доступно: {cnt}.\n")
            if self.conn:
                await self.conn.session_update(
                    session_id=session_id,
                    update=ConfigOptionUpdate(config_options=self.build_config_options())
                )
            return PromptResponse(stop_reason="end_turn")

        if user_text.startswith("/status"):
            key = self.get_api_key()
            if not key:
                await self.send_text_chunk(session_id, "⚠️ API-ключ XIAOAI_API_KEY не установлен.\n")
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
                    await self.send_text_chunk(session_id, f"🟢 Статус XiaoAI: Ключ активен. {bal}\nТекущая модель: `{self.current_model}`\n")
            except Exception as e:
                await self.send_text_chunk(session_id, f"❌ Ошибка проверки ключа: {e}\n")
            return PromptResponse(stop_reason="end_turn")

        if user_text.startswith("/models"):
            await self.send_text_chunk(session_id, "📋 **Доступные модели XiaoAI:**\n\n")
            for m in self.models_catalog:
                await self.send_text_chunk(session_id, f"- **`{m['id']}`** — {m['name']} *(контекст: {m.get('context', 'N/A')})*\n")
            return PromptResponse(stop_reason="end_turn")

        # Regular Chat Turn
        history = self.session_history.setdefault(session_id, [])
        history.append({"role": "user", "content": user_text})

        # Prepend system instruction based on mode
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
                "Пожалуйста, задайте переменную окружения `XIAOAI_API_KEY` или укажите её в файле `.env`.\n"
            )
            return PromptResponse(stop_reason="end_turn")

        # Make streaming request to XiaoAI
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
                # Thought / Reasoning stream
                thought = delta.get("reasoning_content") or delta.get("thought")
                if thought:
                    await self.send_thought_chunk(session_id, thought)

                # Content stream
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
