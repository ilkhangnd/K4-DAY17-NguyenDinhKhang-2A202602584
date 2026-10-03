from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import LabConfig, load_config
from memory_store import estimate_tokens
from model_provider import build_chat_model


@dataclass
class SessionState:
    messages: list[dict[str, str]] = field(default_factory=list)
    token_usage: int = 0
    prompt_tokens_processed: int = 0


class BaselineAgent:
    """Student TODO: implement Agent A.

    Requirements:
    - Within-session memory only
    - No persistent `User.md`
    - Should forget long-term facts across new threads
    """

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.sessions: dict[str, SessionState] = {}

        self.langchain_agent = None
        # A missing key is an explicit offline configuration, not an error.
        if not self.force_offline and self.config.model.api_key:
            self.langchain_agent = self._maybe_build_langchain_agent()

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: return the agent response and token accounting.

        Pseudocode:
        - If a live agent exists, call the live path.
        - Otherwise use a deterministic offline path.
        """

        if self.langchain_agent is not None:
            try:
                result = self.langchain_agent.invoke(message)
                content = getattr(result, "content", str(result))
                return {"response": str(content), "answer": str(content), "agent_tokens": estimate_tokens(str(content)), "prompt_tokens": estimate_tokens(message)}
            except Exception:
                # Preserve a usable lab even when a configured remote provider
                # is unavailable at runtime.
                pass
        return self._reply_offline(thread_id, message)

    def token_usage(self, thread_id: str) -> int:
        return self.sessions.get(thread_id, SessionState()).token_usage

    def prompt_token_usage(self, thread_id: str) -> int:
        return self.sessions.get(thread_id, SessionState()).prompt_tokens_processed

    def compaction_count(self, thread_id: str) -> int:
        # Baseline has no compact memory.
        return 0

    def _reply_offline(self, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: implement a simple offline behavior.

        Suggested behavior:
        - Store the new user message in the session
        - Generate a short deterministic reply
        - Update token counts
        - Never remember facts across different thread ids
        """

        session = self.sessions.setdefault(thread_id, SessionState())
        session.messages.append({"role": "user", "content": message})

        # Baseline carries its full same-thread transcript into every turn.
        prompt_tokens = sum(estimate_tokens(item["content"]) for item in session.messages)
        response = "Mình đã nhận được thông tin trong cuộc trò chuyện hiện tại."
        if "?" in message:
            response = "Mình chỉ dựa trên ngữ cảnh của thread hiện tại; hãy cung cấp lại thông tin nếu cần."

        agent_tokens = estimate_tokens(response)
        session.prompt_tokens_processed += prompt_tokens
        session.token_usage += agent_tokens
        session.messages.append({"role": "assistant", "content": response})
        return {
            "response": response,
            "answer": response,
            "agent_tokens": agent_tokens,
            "prompt_tokens": prompt_tokens,
        }

    def _maybe_build_langchain_agent(self):
        """Student TODO: optionally wire `create_agent` + `InMemorySaver` here.

        Use `build_chat_model(self.config.model)` so the baseline can run with any supported provider.
        """

        return build_chat_model(self.config.model)
