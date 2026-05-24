"""Tests for grammar-constrained answer field streaming (FIX_PLAN2 step B2)."""

from core.inference.agent_answer_stream import AgentAnswerStreamParser


def _feed(parser: AgentAnswerStreamParser, *chunks: str) -> list[str]:
    out: list[str] = []
    for chunk in chunks:
        out.extend(parser.feed(chunk))
    return out


def test_stream_parser_chunked_spanish_answer():
    parser = AgentAnswerStreamParser()
    tokens = _feed(
        parser,
        '{"action":"answer","answer":"Hola',
        " mundo",
        '"}',
    )
    assert "".join(tokens) == "Hola mundo"
    assert parser.raw.endswith('"}')


def test_stream_parser_whitespace_in_prefix():
    parser = AgentAnswerStreamParser()
    tokens = _feed(parser, '{ "action" : "answer" , "answer" : "Sí', '"}')
    assert "".join(tokens) == "Sí"


def test_stream_parser_json_escapes():
    parser = AgentAnswerStreamParser()
    tokens = _feed(parser, '{"action":"answer","answer":"línea1\\n', 'línea2\\""}')
    assert "".join(tokens) == 'línea1\nlínea2"'


def test_stream_parser_tool_response_emits_nothing():
    parser = AgentAnswerStreamParser()
    tokens = _feed(
        parser,
        '{"action":"tool","tool":"get_upcoming_events","args":{}}',
    )
    assert tokens == []
    assert not parser.streamed_answer
