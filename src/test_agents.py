from __future__ import annotations

from pathlib import Path

from agent_advanced import AdvancedAgent
from agent_baseline import BaselineAgent
from config import LabConfig
from memory_store import CompactMemoryManager, UserProfileStore
from model_provider import ProviderConfig


def make_config(tmp_path: Path):
    """Student TODO: build an isolated config for tests."""

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    offline_model = ProviderConfig("openai", "gpt-4o-mini", 0.0)
    return LabConfig(
        base_dir=tmp_path,
        data_dir=tmp_path / "data",
        state_dir=state_dir,
        compact_threshold_tokens=80,
        compact_keep_messages=2,
        model=offline_model,
        judge_model=offline_model,
    )


def test_user_markdown_read_write_edit(tmp_path: Path) -> None:
    """Student TODO: verify `User.md` can be created, updated, and edited."""

    store = UserProfileStore(tmp_path / "profiles")
    path = store.write_text("dungct", "# User Profile\n- location: Huế\n")
    assert path.exists()
    assert "Huế" in store.read_text("dungct")
    assert store.edit_text("dungct", "Huế", "Đà Nẵng") is True
    assert "Đà Nẵng" in store.read_text("dungct")


def test_compact_trigger(tmp_path: Path) -> None:
    """Student TODO: verify long threads trigger compaction."""

    manager = CompactMemoryManager(threshold_tokens=20, keep_messages=2)
    for index in range(6):
        manager.append("long-thread", "user", f"message {index} " + "x" * 80)
    assert manager.compaction_count("long-thread") > 0
    assert len(manager.context("long-thread")["messages"]) <= 2


def test_cross_session_recall(tmp_path: Path) -> None:
    """Student TODO: verify advanced remembers across sessions and baseline does not."""

    config = make_config(tmp_path)
    advanced = AdvancedAgent(config, force_offline=True)
    baseline = BaselineAgent(config, force_offline=True)
    advanced.reply("dungct", "first", "Mình tên là DũngCT.")
    baseline.reply("dungct", "first", "Mình tên là DũngCT.")

    assert "DũngCT" in advanced.reply("dungct", "second", "Mình tên gì?")["response"]
    assert "DũngCT" not in baseline.reply("dungct", "second", "Mình tên gì?")["response"]


def test_compact_reduces_prompt_load_on_long_thread(tmp_path: Path) -> None:
    """Student TODO: compare prompt load of baseline vs advanced on a long thread."""

    config = make_config(tmp_path)
    advanced = AdvancedAgent(config, force_offline=True)
    baseline = BaselineAgent(config, force_offline=True)
    long_message = "Thông tin dài để kiểm tra compact memory. " * 12
    for index in range(10):
        advanced.reply("dungct", "long", f"{index}: {long_message}")
        baseline.reply("dungct", "long", f"{index}: {long_message}")

    assert advanced.compaction_count("long") > 0
    assert advanced.prompt_token_usage("long") < baseline.prompt_token_usage("long")
