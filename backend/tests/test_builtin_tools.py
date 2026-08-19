"""Tool argument handling, tested without a database.

These paths return before touching the session, so they run everywhere. That
matters: the previous version of _parse_source_type was broken for every valid
input, and the bug hid because it was only covered by DB tests that skip.
"""

from __future__ import annotations

import pytest

from parallax.ai.builtin_tools import _parse_source_type, registry
from parallax.ai.tools import ToolContext
from parallax.db.models.document import SourceType


@pytest.fixture
def no_db_ctx() -> ToolContext:
    """A context whose session would explode if touched - these paths must not."""
    return ToolContext(session=None)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [s.value for s in SourceType])
def test_every_valid_source_type_parses_to_its_enum(value: str) -> None:
    # Regression: SourceType is a StrEnum, so an "enum or error string" return
    # made isinstance(x, str) true for valid values and every one looked like an
    # error.
    parsed, error = _parse_source_type(value)
    assert parsed == SourceType(value)
    assert error is None


@pytest.mark.parametrize("value", [None, ""])
def test_absent_source_type_means_no_filter(value: str | None) -> None:
    assert _parse_source_type(value) == (None, None)


def test_unknown_source_type_yields_an_error_and_no_filter() -> None:
    parsed, error = _parse_source_type("tweets")
    assert parsed is None
    assert error is not None
    assert "unknown source_type" in error
    # The model needs to know what it *should* have said.
    for valid in SourceType:
        assert valid.value in error


async def test_count_documents_rejects_bad_type_before_touching_the_db(
    no_db_ctx: ToolContext,
) -> None:
    result = await registry.call("count_documents", '{"source_type": "nope"}', no_db_ctx)
    assert "unknown source_type" in result


async def test_list_documents_rejects_bad_type_before_touching_the_db(
    no_db_ctx: ToolContext,
) -> None:
    result = await registry.call("list_documents", '{"source_type": "nope"}', no_db_ctx)
    assert "unknown source_type" in result
