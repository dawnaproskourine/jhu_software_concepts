"""
LLM-based standardization for program and university names.

Uses TinyLlama via llama_cpp to parse and standardize the combined
program/university strings from GradCafe data. Falls back to rule-based
parsing if LLM output is invalid.
"""

import json
import os
import re
import difflib
from typing import Dict, List, Tuple

from huggingface_hub import hf_hub_download
from llama_cpp import Llama

# Model configuration
MODEL_REPO = "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF"
MODEL_FILE = "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
N_THREADS = os.cpu_count() or 2
N_CTX = 2048
N_GPU_LAYERS = 0  # CPU-only

# Paths to canonical name lists (relative to this file)
_DIR = os.path.dirname(os.path.abspath(__file__))
CANON_UNIS_PATH = os.path.join(_DIR, "canon_universities.txt")
CANON_PROGS_PATH = os.path.join(_DIR, "canon_programs.txt")

# Regex to extract JSON object from LLM output
JSON_OBJ_RE = re.compile(r"\{.*?\}", re.DOTALL)


def _read_lines(path: str) -> List[str]:
    """Read non-empty, stripped lines from a file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip()]
    except FileNotFoundError:
        return []


# Load canonical lists
CANON_UNIS = _read_lines(CANON_UNIS_PATH)
CANON_PROGS = _read_lines(CANON_PROGS_PATH)

# Abbreviation expansions for universities
ABBREV_UNI: Dict[str, str] = {
    r"(?i)^mcg(\.|ill)?$": "McGill University",
    r"(?i)^(ubc|u\.?b\.?c\.?)$": "University of British Columbia",
    r"(?i)^uoft$": "University of Toronto",
    r"(?i)^cuny$": "The City University of New York",
    r"(?i)^duke$": "Duke University",
    r"(?i)^mit$": "Massachusetts Institute of Technology",
    r"(?i)^cmu$": "Carnegie Mellon University",
    r"(?i)^jhu$": "Johns Hopkins University",
}

# Common spelling/formatting fixes
COMMON_UNI_FIXES: Dict[str, str] = {
    "McGiill University": "McGill University",
    "Mcgill University": "McGill University",
    "University Of British Columbia": "University of British Columbia",
    "Massachusetts Institute of Technology (MIT)": "Massachusetts Institute of Technology",
    "University of Alabama At Birmingham": "University of Alabama at Birmingham",
}

COMMON_PROG_FIXES: Dict[str, str] = {
    "Mathematic": "Mathematics",
    "Info Studies": "Information Studies",
    "Comp Sci": "Computer Science",
    "CS": "Computer Science",
}

# Few-shot prompt for the LLM
SYSTEM_PROMPT = (
    "You are a data cleaning assistant. Standardize degree program and university "
    "names.\n\n"
    "Rules:\n"
    "- Input provides a single string under key `program` that may contain both "
    "program and university.\n"
    "- Split into (program name, university name).\n"
    "- Trim extra spaces and commas.\n"
    '- Expand obvious abbreviations (e.g., "McG" -> "McGill University", '
    '"UBC" -> "University of British Columbia").\n'
    "- Use Title Case for program; use official capitalization for university "
    "names (e.g., \"University of X\").\n"
    '- Ensure correct spelling (e.g., "McGill", not "McGiill").\n'
    '- If university cannot be inferred, return "Unknown".\n\n'
    "Return JSON ONLY with keys:\n"
    "  standardized_program, standardized_university\n"
)

FEW_SHOTS: List[Tuple[Dict[str, str], Dict[str, str]]] = [
    (
        {"program": "Information Studies, McGill University"},
        {
            "standardized_program": "Information Studies",
            "standardized_university": "McGill University",
        },
    ),
    (
        {"program": "Information, McG"},
        {
            "standardized_program": "Information Studies",
            "standardized_university": "McGill University",
        },
    ),
    (
        {"program": "Mathematics, University Of British Columbia"},
        {
            "standardized_program": "Mathematics",
            "standardized_university": "University of British Columbia",
        },
    ),
]

# Singleton LLM instance
_LLM: Llama | None = None


def _load_llm() -> Llama:
    """Download (or reuse cached) GGUF model and initialize llama.cpp."""
    global _LLM
    if _LLM is not None:
        return _LLM

    model_path = hf_hub_download(
        repo_id=MODEL_REPO,
        filename=MODEL_FILE,
        local_dir=os.path.join(_DIR, "models"),
        local_dir_use_symlinks=False,
        force_filename=MODEL_FILE,
    )

    _LLM = Llama(
        model_path=model_path,
        n_ctx=N_CTX,
        n_threads=N_THREADS,
        n_gpu_layers=N_GPU_LAYERS,
        verbose=False,
    )
    return _LLM


def _split_fallback(text: str) -> Tuple[str, str]:
    """Rule-based parser as fallback if LLM returns non-JSON."""
    s = re.sub(r"\s+", " ", (text or "")).strip().strip(",")
    parts = [p.strip() for p in re.split(r",| at | @ ", s) if p.strip()]
    prog = parts[0] if parts else ""
    uni = parts[1] if len(parts) > 1 else ""

    # Expand common abbreviations
    if re.fullmatch(r"(?i)mcg(ill)?(\.)?", uni or ""):
        uni = "McGill University"
    if re.fullmatch(r"(?i)(ubc|u\.?b\.?c\.?|university of british columbia)", uni or ""):
        uni = "University of British Columbia"

    # Title-case program; normalize 'Of' -> 'of' for universities
    prog = prog.title()
    if uni:
        uni = re.sub(r"\bOf\b", "of", uni.title())
    else:
        uni = "Unknown"
    return prog, uni


def _best_match(name: str, candidates: List[str], cutoff: float = 0.86) -> str | None:
    """Fuzzy match using difflib."""
    if not name or not candidates:
        return None
    matches = difflib.get_close_matches(name, candidates, n=1, cutoff=cutoff)
    return matches[0] if matches else None


def _post_normalize_program(prog: str) -> str:
    """Apply fixes, title case, and canonical/fuzzy mapping to program."""
    p = (prog or "").strip()
    p = COMMON_PROG_FIXES.get(p, p)
    p = p.title()
    if p in CANON_PROGS:
        return p
    match = _best_match(p, CANON_PROGS, cutoff=0.84)
    return match or p


def _post_normalize_university(uni: str) -> str:
    """Expand abbreviations, apply fixes, and canonical mapping to university."""
    u = (uni or "").strip()

    # Check abbreviations
    for pat, full in ABBREV_UNI.items():
        if re.fullmatch(pat, u):
            u = full
            break

    # Apply common spelling fixes
    u = COMMON_UNI_FIXES.get(u, u)

    # Strip trailing parenthetical abbreviations like "(UCLA)"
    u = re.sub(r"\s*\([A-Za-z]+\)\s*$", "", u).strip()

    # Normalize 'Of' -> 'of'
    if u:
        u = re.sub(r"\bOf\b", "of", u.title())

    # Canonical or fuzzy match
    if u in CANON_UNIS:
        return u
    match = _best_match(u, CANON_UNIS, cutoff=0.86)
    return match or u or "Unknown"


def standardize(program_text: str) -> Dict[str, str]:
    """
    Standardize a program/university string using the LLM.

    Args:
        program_text: Raw program string (e.g., "Computer Science, MIT")

    Returns:
        Dict with 'standardized_program' and 'standardized_university' keys
    """
    llm = _load_llm()

    # Build chat messages with few-shot examples
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for x_in, x_out in FEW_SHOTS:
        messages.append({"role": "user", "content": json.dumps(x_in, ensure_ascii=False)})
        messages.append({"role": "assistant", "content": json.dumps(x_out, ensure_ascii=False)})
    messages.append({"role": "user", "content": json.dumps({"program": program_text}, ensure_ascii=False)})

    # Call LLM
    out = llm.create_chat_completion(
        messages=messages,
        temperature=0.0,
        max_tokens=128,
        top_p=1.0,
    )

    text = (out["choices"][0]["message"]["content"] or "").strip()

    # Parse JSON response
    try:
        match = JSON_OBJ_RE.search(text)
        obj = json.loads(match.group(0) if match else text)
        std_prog = str(obj.get("standardized_program", "")).strip()
        std_uni = str(obj.get("standardized_university", "")).strip()
    except Exception:
        # Fall back to rule-based parsing
        std_prog, std_uni = _split_fallback(program_text)

    # Post-process with canonical mappings
    std_prog = _post_normalize_program(std_prog)
    std_uni = _post_normalize_university(std_uni)

    return {
        "standardized_program": std_prog,
        "standardized_university": std_uni,
    }