"""A protected context must consume the input budget exactly once."""

from copy import deepcopy

import pytest

from src.context_compactor import trim_for_context
from src.model_context import estimate_tokens


@pytest.mark.parametrize("authority_size", [4000, 12000])
@pytest.mark.parametrize("reserve", [512, 2048])
def test_history_trim_preserves_current_request_that_fits_with_authorities(authority_size, reserve):
    authority = {"role": "system", "content": "A" * authority_size, "_protected": True}
    current = {"role": "user", "content": "Execute python -m pytest -q tests/test_probe.py. " * 20}
    messages = [
        authority,
        {"role": "user", "content": "old user history " * 600},
        {"role": "assistant", "content": "old response " * 600},
        current,
    ]
    before = deepcopy(messages)
    capacity = estimate_tokens([authority, current]) + reserve + 32

    result = trim_for_context(messages, capacity, reserve_tokens=reserve)

    assert next(m for m in result if m.get("_protected")) == authority
    assert [m for m in result if m["role"] == "user"][-1] == current
    assert estimate_tokens(result) <= capacity - reserve
    assert messages == before


def test_truly_oversized_current_request_still_has_visible_truncation():
    authority = {"role": "system", "content": "A" * 4000, "_protected": True}
    current = {"role": "user", "content": "huge pasted request " * 1000}
    result = trim_for_context([authority, current], 1800, reserve_tokens=512)

    assert next(m for m in result if m.get("_protected")) == authority
    reduced = [m for m in result if m["role"] == "user"][-1]["content"]
    assert reduced != current["content"]
    assert "Odysseus kept the beginning and end." in reduced
