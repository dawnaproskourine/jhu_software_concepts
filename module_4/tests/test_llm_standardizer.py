"""Tests for llm_standardizer — pure functions and mocked LLM calls."""

import json

import pytest

import llm_standardizer as llm
from llm_standardizer import (
    _read_lines,
    _split_fallback,
    _best_match,
    _post_normalize_program,
    _post_normalize_university,
    CANON_UNIS,
    CANON_PROGS,
)


# =====================================================================
# _read_lines
# =====================================================================

def test_read_lines_file_not_found():
    assert _read_lines("/nonexistent/path.txt") == []


# =====================================================================
# _split_fallback
# =====================================================================

def test_split_fallback_comma():
    prog, uni = _split_fallback("CS, MIT")
    assert prog == "Cs"
    assert uni == "Mit"


def test_split_fallback_at_separator():
    prog, uni = _split_fallback("Physics at Stanford")
    assert prog == "Physics"
    assert "Stanford" in uni


def test_split_fallback_no_university():
    prog, uni = _split_fallback("Physics")
    assert prog == "Physics"
    assert uni == "Unknown"


def test_split_fallback_mcgill_abbrev():
    prog, uni = _split_fallback("Info, McG")
    # re.fullmatch sets uni = "McGill University", then .title() makes "Mcgill University"
    assert "mcgill" in uni.lower()


def test_split_fallback_ubc_abbrev():
    prog, uni = _split_fallback("Math, UBC")
    assert uni == "University of British Columbia"


def test_split_fallback_empty():
    prog, uni = _split_fallback("")
    assert prog == ""
    assert uni == "Unknown"


# =====================================================================
# _best_match
# =====================================================================

def test_best_match_empty_candidates():
    assert _best_match("something", []) is None


def test_best_match_empty_name():
    assert _best_match("", ["something"]) is None


def test_best_match_no_close_match():
    assert _best_match("zzzzzzzzz", ["apple", "banana"]) is None


def test_best_match_finds_close():
    result = _best_match("Computer Scienec", CANON_PROGS, cutoff=0.80)
    assert result is not None
    assert "Computer Science" in result


# =====================================================================
# _post_normalize_program
# =====================================================================

def test_post_normalize_program_common_fix():
    assert _post_normalize_program("Comp Sci") == "Computer Science"


def test_post_normalize_program_canonical():
    if "Computer Science" in CANON_PROGS:
        assert _post_normalize_program("Computer Science") == "Computer Science"


def test_post_normalize_program_fuzzy():
    result = _post_normalize_program("Computr Science")
    assert "Computer Science" in result


# =====================================================================
# _post_normalize_university
# =====================================================================

def test_post_normalize_uni_abbrev():
    assert _post_normalize_university("MIT") == "Massachusetts Institute of Technology"


def test_post_normalize_uni_spelling_fix():
    result = _post_normalize_university("McGiill University")
    assert result == "McGill University"


def test_post_normalize_uni_strip_parens():
    result = _post_normalize_university("Massachusetts Institute of Technology (MIT)")
    assert result == "Massachusetts Institute of Technology"


def test_post_normalize_uni_uc_campus():
    result = _post_normalize_university("UC Berkeley")
    assert result == "University of California, Berkeley"


def test_post_normalize_uni_canonical():
    if "Stanford University" in CANON_UNIS:
        assert _post_normalize_university("Stanford University") == "Stanford University"


def test_post_normalize_uni_fuzzy():
    result = _post_normalize_university("Standford University")
    assert "Stanford" in result


def test_post_normalize_uni_empty_unknown():
    assert _post_normalize_university("") == "Unknown"


# =====================================================================
# _load_llm (mock the heavy dependencies)
# =====================================================================

def test_load_llm_returns_singleton(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(llm, "_LLM", sentinel)
    from llm_standardizer import _load_llm
    assert _load_llm() is sentinel


def test_load_llm_downloads(monkeypatch):
    monkeypatch.setattr(llm, "_LLM", None)

    monkeypatch.setattr(
        llm, "hf_hub_download",
        lambda repo_id, filename, local_dir: "/fake/model.gguf",
    )

    fake_llm = object()
    monkeypatch.setattr(
        llm, "Llama",
        lambda model_path, n_ctx, n_threads, n_gpu_layers, verbose: fake_llm,
    )

    from llm_standardizer import _load_llm
    result = _load_llm()
    assert result is fake_llm
    # Clean up singleton
    monkeypatch.setattr(llm, "_LLM", None)


# =====================================================================
# standardize (mock the LLM call)
# =====================================================================

def test_standardize_valid_json(monkeypatch):
    fake_response = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "standardized_program": "Physics",
                    "standardized_university": "MIT",
                })
            }
        }]
    }

    class FakeLLM:
        def create_chat_completion(self, **kw):
            return fake_response

    monkeypatch.setattr(llm, "_load_llm", lambda: FakeLLM())

    from llm_standardizer import standardize
    result = standardize("Physics, MIT")
    assert "standardized_program" in result
    assert "standardized_university" in result
    # Post-normalization should expand "MIT"
    assert result["standardized_university"] == "Massachusetts Institute of Technology"


def test_standardize_invalid_json_fallback(monkeypatch):
    class FakeLLM:
        def create_chat_completion(self, **kw):
            return {
                "choices": [{
                    "message": {"content": "this is not json at all"}
                }]
            }

    monkeypatch.setattr(llm, "_load_llm", lambda: FakeLLM())

    from llm_standardizer import standardize
    result = standardize("Physics, MIT")
    assert "standardized_program" in result
    assert "standardized_university" in result