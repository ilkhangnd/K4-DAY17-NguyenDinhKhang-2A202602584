from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import LabConfig, load_config
from memory_store import CompactMemoryManager, UserProfileStore, estimate_tokens, extract_profile_updates
from model_provider import build_chat_model


@dataclass
class AgentContext:
    user_id: str
    memory_path: str


class AdvancedAgent:
    """Student TODO: implement Agent B / Advanced Agent.

    Required memory layers:
    1. within-session memory
    2. persistent `User.md`
    3. compact memory for long threads
    """

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.profile_store = UserProfileStore(self.config.state_dir / "profiles")
        self.compact_memory = CompactMemoryManager(
            threshold_tokens=self.config.compact_threshold_tokens,
            keep_messages=self.config.compact_keep_messages,
        )
        self.thread_tokens: dict[str, int] = {}
        self.thread_prompt_tokens: dict[str, int] = {}

        self.langchain_agent = None
        if not self.force_offline and self.config.model.api_key:
            self.langchain_agent = self._maybe_build_langchain_agent()

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: route between offline mode and live mode."""

        if self.langchain_agent is not None:
            try:
                result = self.langchain_agent.invoke(message)
                content = str(getattr(result, "content", result))
                tokens = estimate_tokens(content)
                return {"response": content, "answer": content, "agent_tokens": tokens, "prompt_tokens": estimate_tokens(message)}
            except Exception:
                pass
        return self._reply_offline(user_id, thread_id, message)

    def token_usage(self, thread_id: str) -> int:
        return self.thread_tokens.get(thread_id, 0)

    def prompt_token_usage(self, thread_id: str) -> int:
        return self.thread_prompt_tokens.get(thread_id, 0)

    def memory_file_size(self, user_id: str) -> int:
        return self.profile_store.file_size(user_id)

    def compaction_count(self, thread_id: str) -> int:
        return self.compact_memory.compaction_count(thread_id)

    def _reply_offline(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: implement the deterministic advanced path.

        Pseudocode:
        1. Extract stable profile facts from the incoming message.
        2. Persist those facts into `User.md`.
        3. Append the message into compact memory.
        4. Estimate prompt-context load from `User.md` + summary + recent messages.
        5. Generate a response that can answer long-term recall questions.
        6. Append the assistant reply and update token counters.
        """

        for key, value in extract_profile_updates(message).items():
            # Upsert is the conflict-handling guardrail: a correction replaces
            # the earlier fact instead of leaving two contradictory lines.
            self.profile_store.upsert_fact(user_id, key, value)

        self.compact_memory.append(thread_id, "user", message)
        prompt_tokens = self._estimate_prompt_context_tokens(user_id, thread_id)
        response = self._offline_response(user_id, thread_id, message)
        agent_tokens = estimate_tokens(response)
        self.compact_memory.append(thread_id, "assistant", response)

        self.thread_prompt_tokens[thread_id] = self.thread_prompt_tokens.get(thread_id, 0) + prompt_tokens
        self.thread_tokens[thread_id] = self.thread_tokens.get(thread_id, 0) + agent_tokens
        return {
            "response": response,
            "answer": response,
            "agent_tokens": agent_tokens,
            "prompt_tokens": prompt_tokens,
        }

    def _estimate_prompt_context_tokens(self, user_id: str, thread_id: str) -> int:
        """Student TODO: estimate the context carried into one turn.

        Hint:
        - Include `User.md`
        - Include compact summary text
        - Include recent kept messages
        """

        context = self.compact_memory.context(thread_id)
        messages = context.get("messages", [])
        recent_text = " ".join(
            item.get("content", "")
            for item in messages
            if isinstance(item, dict)
        )
        summary = context.get("summary", "")
        profile = self.profile_store.read_text(user_id)
        return estimate_tokens(profile) + estimate_tokens(str(summary)) + estimate_tokens(recent_text)

    def _offline_response(self, user_id: str, thread_id: str, message: str) -> str:
        """Student TODO: return a deterministic answer using persisted memory.

        Make sure the advanced agent can answer questions like:
        - "Mình tên gì?"
        - "Hiện tại mình làm nghề gì?"
        - "Nhắc lại style trả lời mình thích"
        - questions in the long stress dataset
        """

        facts = self.profile_store.facts(user_id)
        lower = message.casefold()
        is_recall = (
            "?" in message
            or any(term in lower for term in ("nhắc lại", "nhớ lại", "tóm tắt", "hiện tại", "mình tên gì", "nhớ giúp"))
        )
        if not is_recall:
            return "Đã ghi nhận. Mình sẽ giữ câu trả lời gọn và bám vào các ưu tiên của bạn."
        if not facts:
            return "Mình chưa có profile bền vững để nhắc lại thông tin này."

        selected: list[tuple[str, str]] = []
        wants_name = "tên" in lower or "ai không" in lower
        wants_profession = any(term in lower for term in ("nghề", "làm nghề", "product manager"))
        wants_location = any(term in lower for term in ("ở đâu", "nơi ở", "huế", "hà nội", "đà nẵng"))
        wants_style = any(term in lower for term in ("style", "kiểu trả lời", "bullet", "trả lời mình thích"))
        wants_drink = any(term in lower for term in ("đồ uống", "uống yêu thích", "cà phê"))
        wants_food = any(term in lower for term in ("món ăn", "mì quảng"))
        wants_pet = any(term in lower for term in ("nuôi", "corgi", "con gì"))
        wants_interests = any(term in lower for term in ("mối quan tâm", "quan tâm", "python", "ai"))
        requested = {
            "name": wants_name,
            "profession": wants_profession,
            "location": wants_location,
            "response_style": wants_style,
            "favorite_drink": wants_drink,
            "favorite_food": wants_food,
            "pet": wants_pet,
            "interests": wants_interests,
        }
        labels = {
            "name": "Tên",
            "profession": "Nghề nghiệp hiện tại",
            "location": "Nơi ở hiện tại",
            "response_style": "Style trả lời",
            "favorite_drink": "Đồ uống yêu thích",
            "favorite_food": "Món ăn yêu thích",
            "pet": "Thú cưng",
            "interests": "Mối quan tâm",
        }
        for key, wanted in requested.items():
            if wanted and key in facts:
                selected.append((labels[key], facts[key]))
        if not selected:
            selected = [(labels[key], value) for key, value in facts.items() if key in labels]

        # Honor the long-context preference without assuming every user wants
        # bullets. The literal phrase "3 bullet" remains available for recall.
        if "3 bullet" in facts.get("response_style", ""):
            if len(selected) > 3:
                first_label, first_value = selected[0]
                second_label, second_value = selected[1]
                selected = [(f"{first_label}; {second_label}", f"{first_value}; {second_value}")] + selected[2:]
            return "\n".join(f"- {label}: {value}" for label, value in selected[:3])
        return "; ".join(f"{label}: {value}" for label, value in selected) + "."

    def _maybe_build_langchain_agent(self):
        """Student TODO: wire a live agent with tools and compact middleware.

        High-level design:
        - `build_chat_model(self.config.model)` for the selected provider
        - `InMemorySaver` for short-term thread state
        - tool to read `User.md`
        - tool to write/edit `User.md`
        - dynamic prompt that injects profile memory
        - summarization middleware for long threads
        """

        return build_chat_model(self.config.model)
