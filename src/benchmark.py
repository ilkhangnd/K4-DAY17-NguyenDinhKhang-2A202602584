from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import load_config


@dataclass
class BenchmarkRow:
    agent_name: str
    agent_tokens_only: int
    prompt_tokens_processed: int
    recall_score: float
    response_quality: float
    memory_growth_bytes: int
    compactions: int


def load_conversations(path: Path) -> list[dict[str, Any]]:
    """Student TODO: read JSON conversations from disk."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return payload


def recall_points(answer: str, expected: list[str]) -> float:
    """Student TODO: return 0 / 0.5 / 1 depending on how many expected facts appear."""

    if not expected:
        return 1.0
    answer_folded = answer.casefold()
    hits = sum(item.casefold() in answer_folded for item in expected)
    if hits == 0:
        return 0.0
    return 1.0 if hits == len(expected) else 0.5


def heuristic_quality(answer: str, expected: list[str]) -> float:
    """Student TODO: add a lightweight quality score for offline mode."""

    # The offline score is intentionally small and symmetric: correctness is
    # dominant, while a non-empty concise response earns a little credit.
    if not answer.strip():
        return 0.0
    return round(0.25 + 0.75 * recall_points(answer, expected), 2)


def run_agent_benchmark(agent_name: str, agent, conversations: list[dict[str, Any]], config) -> BenchmarkRow:
    """Student TODO: evaluate one agent over many conversations.

    Pseudocode:
    1. Feed all turns to the agent.
    2. Track `agent tokens only`.
    3. Track `prompt tokens processed`.
    4. Ask recall questions in a fresh thread.
    5. Compute average recall and quality.
    6. Record memory file growth and compaction count.
    """

    total_agent_tokens = 0
    total_prompt_tokens = 0
    total_compactions = 0
    recall_scores: list[float] = []
    quality_scores: list[float] = []
    user_ids: set[str] = set()

    for conversation in conversations:
        conversation_id = str(conversation["id"])
        user_id = str(conversation["user_id"])
        user_ids.add(user_id)
        for message in conversation.get("turns", []):
            agent.reply(user_id, conversation_id, str(message))

        # Cost metrics describe the conversation workload. Recall questions
        # are held-out evaluation probes and always use a fresh thread.
        total_agent_tokens += agent.token_usage(conversation_id)
        total_prompt_tokens += agent.prompt_token_usage(conversation_id)
        total_compactions += agent.compaction_count(conversation_id)

        recall_thread = f"{conversation_id}--recall"
        for item in conversation.get("recall_questions", []):
            answer = agent.reply(user_id, recall_thread, str(item["question"]))["response"]
            expected = list(item.get("expected_contains", []))
            recall_scores.append(recall_points(answer, expected))
            quality_scores.append(heuristic_quality(answer, expected))

    memory_growth = sum(
        getattr(agent, "memory_file_size", lambda _user_id: 0)(user_id)
        for user_id in user_ids
    )
    return BenchmarkRow(
        agent_name=agent_name,
        agent_tokens_only=total_agent_tokens,
        prompt_tokens_processed=total_prompt_tokens,
        recall_score=round(sum(recall_scores) / len(recall_scores), 2) if recall_scores else 0.0,
        response_quality=round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else 0.0,
        memory_growth_bytes=memory_growth,
        compactions=total_compactions,
    )


def format_rows(rows: list[BenchmarkRow]) -> str:
    """Student TODO: print a markdown table or tabulated output."""

    headers = [
        "Agent",
        "Agent tokens only",
        "Prompt tokens processed",
        "Cross-session recall",
        "Response quality",
        "Memory growth (bytes)",
        "Compactions",
    ]
    values = [
        [
            row.agent_name,
            row.agent_tokens_only,
            row.prompt_tokens_processed,
            f"{row.recall_score:.2f}",
            f"{row.response_quality:.2f}",
            row.memory_growth_bytes,
            row.compactions,
        ]
        for row in rows
    ]
    try:
        from tabulate import tabulate

        return tabulate(values, headers=headers, tablefmt="github")
    except ImportError:
        widths = [max(len(str(column)) for column in [header, *(row[index] for row in values)]) for index, header in enumerate(headers)]
        render = lambda row: "| " + " | ".join(str(value).ljust(widths[index]) for index, value in enumerate(row)) + " |"
        return "\n".join([render(headers), render(["-" * width for width in widths]), *(render(row) for row in values)])


def main() -> None:
    """Student TODO: run both benchmark suites.

    Required benchmark sections:
    - Standard benchmark from `data/conversations.json`
    - Long-context stress benchmark from `data/advanced_long_context.json`

    Compare:
    - Baseline
    - Advanced

    Keep the same output columns as the solved lab:
    - Agent tokens only
    - Prompt tokens processed
    - Cross-session recall
    - Response quality
    - Memory growth (bytes)
    - Compactions
    """

    config = load_config(Path(__file__).resolve().parent.parent)

    standard = load_conversations(config.data_dir / "conversations.json")
    stress = load_conversations(config.data_dir / "advanced_long_context.json")

    def compare(conversations: list[dict[str, Any]]) -> list[BenchmarkRow]:
        baseline = BaselineAgent(config, force_offline=True)
        advanced = AdvancedAgent(config, force_offline=True)
        return [
            run_agent_benchmark("Baseline", baseline, conversations, config),
            run_agent_benchmark("Advanced", advanced, conversations, config),
        ]

    print("Standard Benchmark")
    print(format_rows(compare(standard)))
    print()
    print("Long-Context Stress Benchmark")
    print(format_rows(compare(stress)))


if __name__ == "__main__":
    main()
