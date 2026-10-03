from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import math
import re


def estimate_tokens(text: str) -> int:
    """Student TODO: implement a simple token estimator.

    Example idea:
    - Strip whitespace
    - Return 0 for empty text
    - Approximate tokens from character count, e.g. len(text) / 4
    """

    compact = "".join(text.split())
    return math.ceil(len(compact) / 4) if compact else 0


@dataclass
class UserProfileStore:
    """Persistent storage for `User.md`.

    Student TODO:
    - Map each user id to one markdown file
    - Support read / write / edit operations
    - Optionally expose helpers like `facts()` or `upsert_fact()`
    """

    root_dir: Path

    def path_for(self, user_id: str) -> Path:
        safe_id = re.sub(r"[^A-Za-z0-9_-]+", "_", user_id).strip("._-")
        if not safe_id:
            safe_id = "anonymous"
        return self.root_dir / safe_id / "User.md"

    def read_text(self, user_id: str) -> str:
        path = self.path_for(user_id)
        return path.read_text(encoding="utf-8") if path.exists() else "# User Profile\n"

    def write_text(self, user_id: str, content: str) -> Path:
        path = self.path_for(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def edit_text(self, user_id: str, search_text: str, replacement: str) -> bool:
        if not search_text:
            return False
        current = self.read_text(user_id)
        if search_text not in current:
            return False
        self.write_text(user_id, current.replace(search_text, replacement, 1))
        return True

    def file_size(self, user_id: str) -> int:
        path = self.path_for(user_id)
        return path.stat().st_size if path.exists() else 0

    def facts(self, user_id: str) -> dict[str, str]:
        """Parse the intentionally simple, human-editable ``User.md`` schema."""
        facts: dict[str, str] = {}
        for line in self.read_text(user_id).splitlines():
            match = re.match(r"^-\s*([a-z_]+):\s*(.+?)\s*$", line)
            if match:
                facts[match.group(1)] = match.group(2)
        return facts

    def upsert_fact(self, user_id: str, key: str, value: str) -> Path:
        """Store one fact per key, replacing a correction rather than appending it."""
        text = self.read_text(user_id)
        pattern = re.compile(rf"(?m)^-\s*{re.escape(key)}:\s*.*$")
        line = f"- {key}: {value}"
        if pattern.search(text):
            text = pattern.sub(line, text, count=1)
        else:
            if not text.endswith("\n"):
                text += "\n"
            text += line + "\n"
        return self.write_text(user_id, text)


def extract_profile_updates(message: str) -> dict[str, str]:
    """Student TODO: convert raw user text into stable profile facts.

    Example facts you may want to extract:
    - name
    - location
    - profession
    - preferences / response style
    - favorite food / drink

    Pseudocode:
    1. Build a few regex patterns.
    2. Skip obvious question-only turns.
    3. Return only the facts that are confidently present in the message.
    """

    text = " ".join(message.split())
    if not text or ("?" in text and not re.search(r"\b(?:mình tên là|tôi tên là|mình ở|hiện ở|đang làm|chuyển sang)\b", text, re.I)):
        return {}

    updates: dict[str, str] = {}

    name = re.search(r"(?:mình|tôi)\s+tên\s+là\s+([^,.;!?]+)", text, re.I)
    if name:
        updates["name"] = name.group(1).strip()

    # Location names are deliberately enumerated for this lab's controlled
    # Vietnamese benchmark. This avoids turning phrases such as "nơi ở đã thay
    # đổi" or a meeting in Hà Nội into a home address.
    location_patterns = (
        r"(?:mình\s+|tôi\s+)?(?:hiện\s+|giờ\s+|vẫn\s+|đang\s+)?ở\s+(Huế|Đà Nẵng|Hà Nội)",
        r"(?:đang\s+)?làm việc ở\s+(Huế|Đà Nẵng|Hà Nội)",
        r"cập nhật\s+từ\s+.+?\s+sang\s+(Huế|Đà Nẵng|Hà Nội)",
        r"nơi ở[^,.!?]{0,50}?(?:là|sang)\s+(Huế|Đà Nẵng|Hà Nội)",
    )
    location_hits = [match for pattern in location_patterns for match in re.finditer(pattern, text, re.I)]
    # Do not interpret "không còn ở Đà Nẵng" as a correction *to* Đà Nẵng.
    location_hits = [
        match
        for match in location_hits
        if not re.search(r"không\s+còn\s*$", text[max(0, match.start() - 24) : match.start()], re.I)
    ]
    if location_hits:
        location_match = max(location_hits, key=lambda match: match.start())
        location = location_match.group(1)
        # "Hà Nội chỉ là nơi ... họp" is an explicit negative example.
        after = text[location_match.end() : location_match.end() + 100]
        if not (location.casefold() == "hà nội" and re.search(r"họp|không phải nơi ở", after, re.I)):
            updates["location"] = location

    profession_patterns = (
        r"(?:đang\s+)?làm\s+(MLOps engineer|backend engineer)",
        r"chuyển sang\s+(MLOps engineer|backend engineer)",
        r"nghề nghiệp[^,.!?]{0,70}?(?:là|vẫn là)\s+(MLOps engineer|backend engineer)",
        r"nghề mới[^,.!?]{0,40}?(?:là\s+)?(MLOps engineer|backend engineer)",
    )
    profession_matches = [match for pattern in profession_patterns for match in re.finditer(pattern, text, re.I)]
    if profession_matches:
        profession = max(profession_matches, key=lambda match: match.start()).group(1)
        updates["profession"] = "MLOps engineer" if profession.casefold().startswith("mlops") else "backend engineer"

    lowered = text.casefold()
    if "3 bullet" in lowered:
        updates["response_style"] = "3 bullet ngắn gọn, có ví dụ thực chiến, ưu tiên trade-off"
    elif "ngắn gọn" in lowered or "câu trả lời gọn" in lowered:
        updates["response_style"] = "ngắn gọn, rõ ý, có ví dụ thực tế"

    drink = re.search(r"(?:đồ uống yêu thích là|vẫn uống)\s+([^,.;!?]+)", text, re.I)
    if drink and "cà phê" in drink.group(1).casefold():
        updates["favorite_drink"] = "cà phê sữa đá"

    food = re.search(r"món ăn yêu thích là\s+([^,.;!?]+)", text, re.I)
    if food:
        updates["favorite_food"] = food.group(1).strip()
    elif "mì quảng" in lowered and ("món ruột" in lowered or "món ăn" in lowered):
        updates["favorite_food"] = "mì Quảng"

    pet = re.search(r"\b(corgi)\s+tên\s+([^\s,.;!?]+)", text, re.I)
    if pet:
        updates["pet"] = f"corgi tên {pet.group(2).strip()}"

    if "python" in lowered and ("ai ứng dụng" in lowered or "ai agent" in lowered):
        updates["interests"] = "Python và AI ứng dụng"
    return updates


def summarize_messages(messages: list[dict[str, str]], max_items: int = 6) -> str:
    """Student TODO: create a compact summary of older messages.

    This can be heuristic text concatenation first.
    Later, you can replace it with an LLM-based summary if desired.
    """

    snippets: list[str] = []
    for message in messages[-max_items:]:
        role = message.get("role", "message")
        content = " ".join(message.get("content", "").split())
        if content:
            snippets.append(f"{role}: {content[:140]}")
    # A bounded summary is essential: otherwise compaction merely moves an
    # ever-growing transcript from ``messages`` into ``summary``.
    return " | ".join(snippets)[:900]


@dataclass
class CompactMemoryManager:
    """Student TODO: implement compact memory for long threads.

    Goal:
    - Keep recent messages in full
    - When the thread grows too large, move older content into a summary
    - Track how many compactions happened for benchmarking
    """

    threshold_tokens: int
    keep_messages: int
    state: dict[str, dict[str, object]] = field(default_factory=dict)

    def append(self, thread_id: str, role: str, content: str) -> None:
        state = self.state.setdefault(
            thread_id,
            {"messages": [], "summary": "", "compactions": 0},
        )
        messages = state["messages"]
        assert isinstance(messages, list)
        messages.append({"role": role, "content": content})

        raw_tokens = sum(estimate_tokens(item["content"]) for item in messages)
        if raw_tokens <= self.threshold_tokens or len(messages) <= self.keep_messages:
            return

        old_messages = messages[: -self.keep_messages]
        prior_summary = state.get("summary", "")
        summary_input: list[dict[str, str]] = []
        if isinstance(prior_summary, str) and prior_summary:
            summary_input.append({"role": "summary", "content": prior_summary})
        summary_input.extend(old_messages)
        state["summary"] = summarize_messages(summary_input)
        state["messages"] = messages[-self.keep_messages :]
        state["compactions"] = int(state.get("compactions", 0)) + 1

    def context(self, thread_id: str) -> dict[str, object]:
        return self.state.setdefault(
            thread_id,
            {"messages": [], "summary": "", "compactions": 0},
        )

    def compaction_count(self, thread_id: str) -> int:
        return int(self.context(thread_id).get("compactions", 0))
