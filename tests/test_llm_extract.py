"""Tests for LLM-powered real-time extraction."""

from unittest.mock import MagicMock

from crossagentmemory.llm import LLMResponse
from crossagentmemory.llm_extract import (
    extract_and_store,
    extract_memories_from_conversation,
    extract_memories_from_text,
    extract_temporal_facts,
)


class MockEngine:
    def __init__(self):
        self._memories = []
        self._seq = 0

    def store(self, entry):
        self._seq += 1
        entry.id = self._seq
        self._memories.append(entry)
        return self._seq


def _make_client(response_text: str):
    client = MagicMock()
    client.is_available.return_value = True
    client.chat.return_value = LLMResponse(
        text=response_text, model="gpt-4o-mini", provider="openai"
    )
    return client


def test_extract_memories_from_text_basic():
    response = """[
        {
            "content": "Chose PostgreSQL for the database",
            "category": "decision",
            "confidence": 0.95,
            "tags": "database,postgres"
        },
        {
            "content": "Implemented JWT authentication",
            "category": "action",
            "confidence": 0.9,
            "tags": "auth,jwt"
        }
    ]"""
    client = _make_client(response)
    entries = extract_memories_from_text(
        "We decided to use PostgreSQL and implemented JWT auth.",
        project="my-proj",
        session_id="sess-1",
        client=client,
    )

    assert len(entries) == 2
    assert entries[0].content == "Chose PostgreSQL for the database"
    assert entries[0].category == "decision"
    assert entries[0].project == "my-proj"
    assert entries[0].session_id == "sess-1"
    assert entries[1].category == "action"


def test_extract_memories_from_text_no_llm():
    client = MagicMock()
    client.is_available.return_value = False
    entries = extract_memories_from_text("some text", client=client)
    assert entries == []


def test_extract_memories_from_text_malformed_json():
    client = _make_client("not valid json")
    entries = extract_memories_from_text("some text", client=client)
    assert entries == []


def test_extract_memories_from_conversation():
    response = """[
        {
            "content": "User wants dark mode",
            "category": "preference",
            "confidence": 0.8,
            "tags": "ui,dark-mode"
        }
    ]"""
    client = _make_client(response)
    messages = [
        {"role": "user", "content": "Can we add dark mode?"},
        {"role": "assistant", "content": "Sure, I'll implement a dark mode toggle."},
    ]
    entries = extract_memories_from_conversation(messages, project="ui-proj", client=client)
    assert len(entries) == 1
    assert "dark mode" in entries[0].content.lower()


def test_extract_temporal_facts():
    response = """[
        {
            "content": "Used Redux for state management",
            "category": "decision",
            "confidence": 0.9,
            "valid_from": "2024-01-01T00:00:00+00:00",
            "valid_until": "2024-03-15T00:00:00+00:00",
            "tags": "state,redux"
        },
        {
            "content": "Switched to Zustand",
            "category": "decision",
            "confidence": 0.9,
            "valid_from": "2024-03-15T00:00:00+00:00",
            "valid_until": "",
            "tags": "state,zustand"
        }
    ]"""
    client = _make_client(response)
    entries = extract_temporal_facts(
        "We used Redux until March 2024, then switched to Zustand.",
        project="frontend",
        client=client,
    )

    assert len(entries) == 2
    assert entries[0].content == "Used Redux for state management"
    assert entries[0].valid_from == "2024-01-01T00:00:00+00:00"
    assert entries[0].valid_until == "2024-03-15T00:00:00+00:00"
    assert entries[1].content == "Switched to Zustand"
    assert entries[1].valid_from == "2024-03-15T00:00:00+00:00"
    assert entries[1].valid_until == ""


def test_extract_and_store():
    response = """[
        {"content": "Fact one", "category": "fact", "confidence": 0.8, "tags": "test"}
    ]"""
    client = _make_client(response)
    engine = MockEngine()
    ids = extract_and_store(
        "Some text to extract from",
        engine,
        project="test-proj",
        client=client,
    )
    assert len(ids) == 1
    assert ids[0] == 1
    assert engine._memories[0].content == "Fact one"


def test_extract_and_store_temporal():
    response = """[
        {
            "content": "Old stack",
            "category": "fact",
            "confidence": 0.8,
            "valid_from": "2023-01-01T00:00:00+00:00",
            "valid_until": "2023-12-31T00:00:00+00:00",
            "tags": "test"
        }
    ]"""
    client = _make_client(response)
    engine = MockEngine()
    ids = extract_and_store(
        "We used the old stack in 2023.",
        engine,
        project="test-proj",
        use_temporal=True,
        client=client,
    )
    assert len(ids) == 1
    assert engine._memories[0].valid_from == "2023-01-01T00:00:00+00:00"
