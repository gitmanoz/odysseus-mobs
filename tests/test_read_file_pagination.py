"""Legacy read pagination reconciled with bounded reads and source provenance."""
import asyncio
import json

import pytest

from src.agent_tools.filesystem_tools import ReadFileTool
from src.tool_execution import format_tool_result


def reader(tmp_path, monkeypatch, text, budget=20):
    import src.tool_execution as execution
    import src.agent_tools.filesystem_tools as filesystem
    source = tmp_path / 'fixture.txt'
    source.write_text(text, encoding='utf-8')
    monkeypatch.setattr(execution, '_resolve_tool_path', lambda _: str(source))
    monkeypatch.setattr(filesystem, 'MAX_READ_CHARS', budget)
    def read(**args):
        return asyncio.run(ReadFileTool().execute(json.dumps({'path':'fixture.txt', **args}), {}))
    return read


def test_read_pages_reconstruct_unicode_content_without_missing_or_repeating_lines(tmp_path, monkeypatch):
    text = ''.join(f'ação {n}\n' for n in range(12))
    read = reader(tmp_path, monkeypatch, text)
    pages = []; offset = 1
    for _ in range(20):
        page = read(offset=offset)
        pages.append(page['output'])
        assert len(page['output']) <= 20
        assert page['source_reference']['start_line'] == offset
        assert not page['partial_line']
        if not page['has_more']:
            assert page['next_offset'] is None
            break
        assert page['next_offset'] > offset
        assert f"offset={page['next_offset']}" in format_tool_result('read', page)
        offset = page['next_offset']
    else:
        pytest.fail('Pagination failed to terminate')
    assert ''.join(pages) == text


@pytest.mark.parametrize('offset,limit,expected,more,next_offset', [
    (1, 1, 'one\n', True, 2), (2, 1, 'two\n', True, 3),
    (3, 1, 'three', False, None), (9, 1, '', False, None),
])
def test_explicit_ranges_keep_exact_content_and_truthful_eof(tmp_path, monkeypatch, offset, limit, expected, more, next_offset):
    page = reader(tmp_path, monkeypatch, 'one\ntwo\nthree')(offset=offset, limit=limit)
    assert page['output'] == expected
    assert page['has_more'] is more
    assert page['next_offset'] == next_offset


def test_oversized_line_is_explicitly_incomplete_and_does_not_offer_a_lossy_resume(tmp_path, monkeypatch):
    page = reader(tmp_path, monkeypatch, 'x' * 60 + '\nnext\n')()
    assert page['output'] == 'x' * 20
    assert page['partial_line'] and page['has_more']
    assert page['next_offset'] is None
    assert page['lines_read'] == 0
    assert 'cannot resume' in format_tool_result('read', page)


def test_offset_can_skip_a_long_line_without_losing_the_following_line(tmp_path, monkeypatch):
    page = reader(tmp_path, monkeypatch, 'x' * 60 + '\nnext\n')(offset=2)
    assert page['output'] == 'next\n'
    assert not page['has_more']


def test_empty_and_exact_budget_eof_are_not_reported_as_truncated(tmp_path, monkeypatch):
    for text in ('', 'x' * 20):
        page = reader(tmp_path, monkeypatch, text)()
        assert page['output'] == text
        assert not page['has_more'] and not page['partial_line']
