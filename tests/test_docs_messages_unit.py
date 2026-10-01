"""Every message a user can meet is quoted in the document that owns it.

A user holding an error message searches the documents for its text, so "raises
`ValueError`" is not documentation of it. This reads the source rather than a list:
every exception raised with a message in `src/` and `examples/`, every
`fail(...)` and `print(..., file=sys.stderr)` of an example script, and every
warning line the `warn_*` functions build. Each must appear in its owning document
inside one code span, with example values where the message has placeholders:
the literal pieces in order, anything between them.

`scripts/` is left out on purpose: those are the maintainer's tools, and their
messages name the fix to a person already reading the script.
"""

from __future__ import annotations

import ast
import re
from typing import Iterator, NamedTuple

import pytest

from doc_files import ROOT

pytestmark = pytest.mark.fast

#: The document that owns each source file's messages.
OWNERS = {
    "src/jobcheck/engine.py": "interfaces.md",
    "src/jobcheck/paths.py": "configuration.md",
    "src/jobcheck/registry.py": "interfaces.md",
    "src/jobcheck/views.py": "interfaces.md",
    "src/jobcheck/results.py": "interfaces.md",
    "src/jobcheck/rules.py": "configuration.md",
    "src/jobcheck/tables.py": "interfaces.md",
    "examples/main.py": "cli.md",
    "examples/bundle_main.py": "cli.md",
    "examples/run_from_config.py": "cli.md",
}

#: Functions whose messages belong to another document than their file's.
FUNCTION_OWNERS = {
    ("src/jobcheck/registry.py", "_setup_paths"): "configuration.md",
    ("src/jobcheck/registry.py", "load_setup"): "configuration.md",
    ("src/jobcheck/registry.py", "warn_blocking_rules"): "configuration.md",
}

#: A literal piece shorter than this is a joint ("rule ", ": ", " in "), not text a
#: reader searches for; a message with no longer piece only wraps another message.
SHORTEST_PIECE = 6


class Message(NamedTuple):
    source: str
    line: int
    pieces: list[str]

    @property
    def label(self) -> str:
        return f"{self.source}:{self.line}"


def _pieces(node: ast.expr) -> list[str] | None:
    """The literal text of a message, split where a value is formatted in."""

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.JoinedStr):
        pieces, current = [], ""
        for value in node.values:
            if isinstance(value, ast.Constant):
                current += str(value.value)
            else:
                pieces.append(current)
                current = ""
        return pieces + [current]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _pieces(node.left), _pieces(node.right)
        if left is None and right is None:
            return None
        return (left or [""]) + (right or [""])
    return None


def _message_argument(call: ast.Call) -> ast.expr | None:
    """The argument holding the text: the first with any literal in it."""

    for argument in call.args:
        pieces = _pieces(argument)
        if pieces and any(piece.strip() for piece in pieces):
            return argument
    return None


def _is_warning_append(call: ast.Call) -> bool:
    return (isinstance(call.func, ast.Attribute) and call.func.attr == "append"
            and isinstance(call.func.value, ast.Name) and call.func.value.id == "warnings")


def _is_user_output(call: ast.Call) -> bool:
    if isinstance(call.func, ast.Name) and call.func.id == "fail":
        return True
    if isinstance(call.func, ast.Name) and call.func.id == "print":
        return any(keyword.arg == "file" and ast.unparse(keyword.value) == "sys.stderr"
                   for keyword in call.keywords)
    return _is_warning_append(call)


def _messages_in(source: str) -> Iterator[tuple[str | None, Message]]:
    """(enclosing function, message) for every message *source* can show a user."""

    tree = ast.parse((ROOT / source).read_text(encoding="utf-8"))
    functions = [node for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]

    def enclosing(line: int) -> str | None:
        inside = [f for f in functions if f.lineno <= line <= (f.end_lineno or f.lineno)]
        return min(inside, key=lambda f: f.end_lineno or 0).name if inside else None

    for node in ast.walk(tree):
        call = None
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            call = node.exc
        elif isinstance(node, ast.Call) and _is_user_output(node):
            call = node
        if call is None:
            continue
        argument = _message_argument(call)
        if argument is None:
            continue
        pieces = [" ".join(piece.split()) for piece in _pieces(argument) or []]
        yield enclosing(call.lineno), Message(source, call.lineno, pieces)


def messages_by_owner() -> dict[str, list[Message]]:
    owned: dict[str, list[Message]] = {}
    for source, default in OWNERS.items():
        for function, message in _messages_in(source):
            owner = FUNCTION_OWNERS.get((source, function or ""), default)
            owned.setdefault(owner, []).append(message)
    return owned


def _pattern(message: Message) -> re.Pattern[str] | None:
    # The punctuation around a value -- `: ` after a file name, `.` after a type --
    # is the joint, not the text; a document shows the message without its prefix.
    kept = [piece.strip(" :;,.") for piece in message.pieces]
    kept = [piece for piece in kept if len(piece) >= SHORTEST_PIECE]
    if not kept:
        return None
    return re.compile(".*?".join(re.escape(piece) for piece in kept))


def _code_spans(document: str) -> list[str]:
    text = (ROOT / "docs" / document).read_text(encoding="utf-8")
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return [" ".join(span.split()) for span in re.findall(r"`([^`]+)`", text)]


def test_every_source_file_that_can_speak_to_a_user_has_an_owner() -> None:
    """A new module or example script must be given a document, not skipped."""

    speaking = {
        str(path.relative_to(ROOT))
        for directory in ("src/jobcheck", "examples")
        for path in (ROOT / directory).glob("*.py")
        if any(True for _ in _messages_in(str(path.relative_to(ROOT))))
    }
    assert speaking - set(OWNERS) == set()


@pytest.mark.parametrize("document", sorted(set(OWNERS.values())))
def test_every_message_is_quoted_in_the_document_that_owns_it(document: str) -> None:
    spans = _code_spans(document)
    missing = []
    for message in messages_by_owner().get(document, []):
        pattern = _pattern(message)
        if pattern is not None and not any(pattern.search(span) for span in spans):
            missing.append(f"{message.label}: {' {} '.join(message.pieces).strip()}")
    assert missing == [], f"{document} quotes none of:\n" + "\n".join(missing)


def test_the_scan_finds_messages_in_every_form_they_are_written() -> None:
    """Pinned so a scan that quietly finds nothing cannot pass the test above."""

    owned = messages_by_owner()
    found = {message.label.split(":")[0] for messages in owned.values() for message in messages}
    assert set(OWNERS) - found == {"examples/bundle_main.py"} or set(OWNERS) - found == set()
    texts = [" ".join(m.pieces) for messages in owned.values() for m in messages]
    assert any("on_error must be" in text for text in texts)  # a raise
    assert any("a run prints at least one" in text for text in texts)  # fail(...)
    assert any("is outside the frame" in text for text in texts)  # print to stderr
    assert any("switches off" in text or "never applies" in text or "overrul" in text
               for text in texts)  # a warning line
