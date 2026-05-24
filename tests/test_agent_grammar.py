from core.inference.agent_grammar import build_agent_response_grammar, grammar_base_path


def test_grammar_base_file_exists():
    assert grammar_base_path().is_file()


def test_build_agent_response_grammar_includes_authorized_tools():
    grammar = build_agent_response_grammar(("create_calendar_event", "get_upcoming_events"))
    assert '"create_calendar_event"' in grammar
    assert '"get_upcoming_events"' in grammar
    assert "answer-response" in grammar
    assert "tool-response" in grammar


def test_build_agent_response_grammar_allows_utf8_in_strings():
    grammar = build_agent_response_grammar(("read_file",))
    assert r'[^"\\\x00-\x09\x0B-\x1F]' in grammar


def test_build_agent_response_grammar_without_tools_is_answer_only():
    grammar = build_agent_response_grammar(())
    assert "root ::= answer-response" in grammar
    assert "root ::= answer-response | tool-response" not in grammar
