"""Tests for conversation memory and query expansion."""
import sys
from pathlib import Path
import pytest
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_memory_add_and_retrieve(tmp_path):
    from src.conversation.memory import ConversationMemory
    db = tmp_path / "test.db"
    mem = ConversationMemory(db_path=db)

    mem.add_turn("user", "What is Dijkstra?")
    mem.add_turn("assistant", "Dijkstra is a shortest-path algorithm. [lecture.pdf:7]")

    history = mem.get_history(max_turns=10)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


def test_memory_pin(tmp_path):
    from src.conversation.memory import ConversationMemory
    db = tmp_path / "test_pin.db"
    mem = ConversationMemory(db_path=db)

    turn_id = mem.add_turn("assistant", "Important answer about graphs.")
    mem.pin_turn(turn_id)

    pinned = mem.get_pinned()
    assert len(pinned) == 1
    assert pinned[0]["id"] == turn_id
    assert pinned[0]["is_pinned"] is True


def test_memory_new_session(tmp_path):
    from src.conversation.memory import ConversationMemory
    db = tmp_path / "test_session.db"
    mem = ConversationMemory(db_path=db)
    orig_sid = mem.session_id

    mem.add_turn("user", "Question in session 1")
    new_sid = mem.new_session(name="Session 2")

    assert mem.session_id == new_sid
    assert new_sid != orig_sid

    # New session should have empty history
    history = mem.get_history()
    assert len(history) == 0


def test_query_expander_no_expansion():
    from src.conversation.query_expander import needs_expansion, expand_query
    query = "What is the time complexity of Dijkstra's algorithm with a binary heap?"
    assert not needs_expansion(query)
    result = expand_query(query, [])
    assert result == query


def test_query_expander_with_context():
    from src.conversation.query_expander import expand_query
    history = [
        {"role": "user", "content": "What is Dijkstra?"},
        {"role": "assistant", "content": "**Dijkstra** is a shortest-path algorithm [lecture.pdf:7]."},
    ]
    query = "How does it handle negative edges?"
    result = expand_query(query, history)
    # Should expand "it" to Dijkstra or similar
    assert result != query or "Dijkstra" in result or len(result) > len(query)


def test_session_state_update():
    from src.conversation.memory import ConversationMemory
    from src.conversation.session import SessionManager
    import tempfile, os

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    try:
        mem = ConversationMemory(db_path=db_path)
        mgr = SessionManager(mem)

        chunks = [{"source_file": "lecture.pdf", "page_number": 5, "text": "content",
                   "metadata": {"source_file": "lecture.pdf"}}]
        mgr.update_from_answer("What is Quicksort?", "Quicksort is a divide-and-conquer algorithm.", chunks, [])

        assert "lecture.pdf" in mgr.state.docs_referenced
    finally:
        try:
            mem._conn.close()
        except:
            pass
        if db_path.exists():
            db_path.unlink()
