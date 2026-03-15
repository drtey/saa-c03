#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import random
import re
import sys
import difflib
import json
import tkinter as tk
from tkinter import messagebox
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from domain_classifier import classify_all_questions, get_domain_info, DOMAINS


# ==========
# Config (tu path)
# ==========
BASE_DIR = "/home/drtey/develop/roadmap26/saa-c03/quiz"
QUESTIONS_PATH = os.path.join(BASE_DIR, "questions.txt")
SOLUTIONS_PATH = os.path.join(BASE_DIR, "solutions.txt")
STATS_PATH = os.path.join(BASE_DIR, "quiz_stats.json")

# AWS-like: 65 total = 50 scored + 15 unscored
EXAM_TOTAL_DEFAULT = 65
SCORED_DEFAULT = 50

# Umbral "tipo 70%"
PASS_PERCENT_SCORED = 0.70

# Passing real AWS (scaled 100-1000)
AWS_PASS_SCALED = 720

# Exam time limit (130 minutes like real exam)
EXAM_TIME_MINUTES = 130
EXAM_TIME_SECONDS = EXAM_TIME_MINUTES * 60


# ==========
# Model
# ==========
@dataclass
class Question:
    qnum: int
    text: str
    options: Dict[str, str]  # A..E
    choose_n: int = 1


# ==========
# Parsing questions.txt
# ==========
_Q_HEADER_RE = re.compile(r"^\s*Question\s*#\s*(\d+)\b.*$", re.IGNORECASE)
_OPT_RE = re.compile(r"^\s*([A-E])\.\s+(.*)\s*$")
_CHOOSE_RE = re.compile(r"(?:\(|\b)Choose\s+(two|three|four|five|2|3|4|5)(?:\)|\b)", re.IGNORECASE)
_WORD2N = {"two": 2, "three": 3, "four": 4, "five": 5, "2": 2, "3": 3, "4": 4, "5": 5}


def parse_questions(path: str) -> Dict[int, Question]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"No existe questions file: {path}")

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [ln.rstrip("\n") for ln in f]

    out: Dict[int, Question] = {}

    cur_num: Optional[int] = None
    cur_text: List[str] = []
    cur_opts: Dict[str, str] = {}
    cur_choose = 1
    last_opt: Optional[str] = None

    def flush():
        nonlocal cur_num, cur_text, cur_opts, cur_choose, last_opt
        if cur_num is None:
            return
        text = "\n".join(cur_text).strip()
        if text and len(cur_opts) >= 2:
            out[cur_num] = Question(qnum=cur_num, text=text, options=dict(cur_opts), choose_n=cur_choose)
        cur_num, cur_text, cur_opts, cur_choose, last_opt = None, [], {}, 1, None

    for line in lines:
        m = _Q_HEADER_RE.match(line)
        if m:
            flush()
            cur_num = int(m.group(1))
            continue

        if cur_num is None:
            continue

        cm = _CHOOSE_RE.search(line)
        if cm:
            cur_choose = _WORD2N.get(cm.group(1).lower(), cur_choose)

        om = _OPT_RE.match(line)
        if om:
            k = om.group(1).upper()
            cur_opts[k] = om.group(2).strip()
            last_opt = k
            continue

        if last_opt and (line.startswith("  ") or line.startswith("\t")) and line.strip():
            cur_opts[last_opt] = (cur_opts[last_opt] + " " + line.strip()).strip()
            continue

        cur_text.append(line)

    flush()
    return out


# ==========
# Parsing solutions.txt (ROBUSTO)
# ==========
_LINE_START_RE = re.compile(r"^\s*(\d+)\s*[\]\.\)\:-]\s*(.*)$")
_BLOCK_START_RE = re.compile(r"^\s*(\d+)\s*[\]\.\)]\s*.*$")
_ANS_MARK_ANY_RE = re.compile(r"\b(ans(?:wer)?|correct\s*answer)\b\s*[:\-]\s*(.*)$", re.IGNORECASE)


def _norm(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9 :/_\-\.\,]", "", s)
    return s


def _letters_from_tail_if_compact(tail: str) -> Optional[Set[str]]:
    t = tail.strip().upper()
    if not t:
        return None
    if re.fullmatch(r"[A-E\s,\/&\-\+]+", t):
        letters = set(re.findall(r"[A-E]", t))
        if 1 <= len(letters) <= 3:
            return letters
    return None


# ==========
# Helper functions for parsing solutions.txt (multiple formats)
# ==========

def split_into_blocks(lines: List[str]) -> Dict[int, List[str]]:
    r"""
    Split solutions.txt into blocks by question number.

    Each block starts with a line matching: ^\s*\d+\s*[\]\.\)\:-]

    Returns:
        Dict[qnum, list_of_lines_in_block]
    """
    blocks: Dict[int, List[str]] = {}
    current_qnum: Optional[int] = None
    current_lines: List[str] = []

    for line in lines:
        m = _BLOCK_START_RE.match(line)
        if m:
            # Save previous block (only if not already exists - don't overwrite)
            if current_qnum is not None and current_lines:
                if current_qnum not in blocks:  # Don't overwrite existing blocks
                    blocks[current_qnum] = current_lines
            # Start new block
            new_qnum = int(m.group(1))
            # Only start new block if this qnum doesn't exist yet
            if new_qnum not in blocks:
                current_qnum = new_qnum
                current_lines = [line]
            else:
                # Block already exists, skip this duplicate
                current_qnum = None
                current_lines = []
        elif current_qnum is not None:
            current_lines.append(line)

    # Save last block
    if current_qnum is not None and current_lines:
        if current_qnum not in blocks:
            blocks[current_qnum] = current_lines

    return blocks


def is_test_format(block_lines: List[str]) -> bool:
    """
    Check if block is Format 4 (test format with 4+ indented options).

    Format 4 example:
        172] [Question text]
        Which action should the solutions architect take?

            A. Configure a CloudFront signed URL.
            B. Configure a CloudFront signed cookie.
            C. Configure a CloudFront field-level encryption profile.
            D. Configure CloudFront and set the Origin Protocol...

    Returns True if block has 4 or more options indented with 4 spaces.
    """
    _INDENTED_OPTION_RE = re.compile(r'^\s{4}([A-E])\.\s+.+$')

    indented_count = 0
    for line in block_lines:
        if _INDENTED_OPTION_RE.match(line):
            indented_count += 1

    return indented_count >= 4


def extract_explanation_after_options(block_lines: List[str]) -> str:
    """
    Extract explanation text that appears after all indented options.

    Used for Format 4 heuristic analysis.
    """
    _INDENTED_OPTION_RE = re.compile(r'^\s{4}([A-E])\.\s+.+$')

    # Find index of last indented option
    last_option_idx = -1
    for i, line in enumerate(block_lines):
        if _INDENTED_OPTION_RE.match(line):
            last_option_idx = i

    if last_option_idx == -1:
        return ""

    # Get all lines after last option
    explanation_lines = block_lines[last_option_idx + 1:]
    explanation = '\n'.join(explanation_lines).strip()

    return explanation


def validate_answer_letters(letters: Set[str]) -> bool:
    """
    Validate that detected answer letters are reasonable.

    Checks:
    1. All letters are A-E
    2. Count is reasonable (1-3 letters)

    Returns True if valid, False otherwise.
    """
    if not letters:
        return False

    # Check all letters are A-E
    if not all(l in 'ABCDE' for l in letters):
        return False

    # Check count is reasonable (1-3 for most questions)
    if len(letters) > 3:
        return False

    return True


def print_diagnostic_report(stats: dict, total_blocks: int, parsed_solutions: Dict[int, dict]):
    """
    Print diagnostic report showing parser statistics.

    Called after parsing solutions.txt, before starting GUI.
    """
    print("\n" + "="*70)
    print("SOLUTIONS PARSER DIAGNOSTIC REPORT")
    print("="*70)

    print(f"\nTotal solution blocks found: {total_blocks}")
    print(f"Successfully parsed solutions: {len(parsed_solutions)}")
    if total_blocks > 0:
        print(f"Parse success rate: {len(parsed_solutions)/total_blocks*100:.1f}%")

    print("\n--- Format Detection Breakdown ---")
    print(f"  Format 1 (Explicit marker 'ans-'):     {stats.get('format1', 0):4d}")
    print(f"  Format 2 (Single letter at line start): {stats.get('format2', 0):4d}")
    print(f"  Format 3 (Multi-answer):                {stats.get('format3', 0):4d}")
    print(f"  Format 4 (Test format - heuristic):     {stats.get('format4_success', 0):4d}")
    print(f"  Format 4 (Test format - failed):        {stats.get('format4_failed', 0):4d}")
    print(f"  Unparsed (no format detected):          {stats.get('unparsed', 0):4d}")

    print("\n--- Missing Solutions ---")
    missing_count = total_blocks - len(parsed_solutions)
    if missing_count > 0:
        print(f"  {missing_count} questions could not be parsed")
        print(f"  These questions will not appear in the quiz")
    else:
        print(f"  All solutions successfully parsed!")

    print("\n" + "="*70)


def detect_format1_explicit_marker(block_text: str) -> Optional[dict]:
    """
    Format 1: Explicit marker (ans-, answer:, correct answer:)

    Example:
        1] [Question text]
        ans- Turn on S3 Transfer Acceleration...

    This is the original format detection (already working).
    """
    for line in block_text.splitlines():
        am = _ANS_MARK_ANY_RE.search(line)
        if am:
            payload = (am.group(2) or "").strip()
            letters = _letters_from_tail_if_compact(payload)
            if letters:
                return {"letters": letters, "text": None}
            else:
                return {"letters": None, "text": payload}
    return None


def detect_format2_3_letters(block_lines: List[str]) -> Optional[dict]:
    """
    Format 2/3: Answer letters at start of line (not indented).

    Format 2 example (single answer):
        4] [Question text]

        A. Create a gateway VPC endpoint to the S3 bucket.

        Keywords:
        - EC2 in VPC

    Format 3 example (multi-answer):
        18] [Question text]
        Which combination...? (Choose two.)

        A. Create an Amazon Simple Queue Service...

        B. Configure the Lambda function to use...

    Stops scanning when encountering delimiters like:
    - Keywords:
    - --- or ===
    - Explanation sections

    Returns:
        {"letters": Set[str], "text": None} or None if no letters found
    """
    _LETTER_LINE_RE = re.compile(r'^([A-E])\.\s+(.+)$')
    _DELIMITER_RE = re.compile(r'^(Keywords?:|---+|===+|explanation|option\s+[A-E]:|because\b)', re.IGNORECASE)

    found_letters: Set[str] = set()
    in_answer_section = True

    for line in block_lines[1:]:  # Skip first line (question number)
        stripped = line.strip()

        # Stop at delimiter/explanation section
        if _DELIMITER_RE.match(stripped):
            in_answer_section = False
            break

        # Look for answer letters at line start (not indented)
        if in_answer_section and line:
            m = _LETTER_LINE_RE.match(line)
            if m:
                letter = m.group(1)
                found_letters.add(letter)

    # Validate found letters
    if found_letters and validate_answer_letters(found_letters):
        return {"letters": found_letters, "text": None}

    return None


def analyze_service_keywords(explanation: str, options: Dict[str, str]) -> Dict[str, float]:
    """
    Extract AWS service names from options and count mentions in explanation.

    Returns: Dict[letter, score] based on keyword mentions
    """
    # AWS service patterns
    service_patterns = [
        r'\bAWS\s+\w+(?:\s+\w+)?\b',
        r'\bAmazon\s+\w+(?:\s+\w+)?\b',
        r'\b(?:S3|EC2|RDS|Lambda|CloudFront|DynamoDB|VPC|IAM|SNS|SQS|EBS|EFS)\b',
    ]

    scores: Dict[str, float] = {}
    explanation_lower = explanation.lower()

    for letter, option_text in options.items():
        option_lower = option_text.lower()

        # Extract services from option
        services = []
        for pattern in service_patterns:
            services.extend(re.findall(pattern, option_lower, re.IGNORECASE))

        # Count mentions in explanation
        mention_count = 0
        for service in services:
            mention_count += explanation_lower.count(service.lower())

        # Normalize by number of services
        if services:
            scores[letter] = mention_count / len(services)
        else:
            scores[letter] = 0.0

    return scores


def apply_heuristic_analysis(explanation: str, options: Dict[str, str]) -> Optional[Set[str]]:
    """
    Analyze explanation text to detect correct answer (Format 4 heuristic).

    Strategies (in order):
    1. Look for explicit "Option X" or "Answer is X"
    2. Look for answer letter at start of explanation
    3. Analyze which option text appears most in explanation (similarity scoring)
    4. Look for AWS service keywords

    Returns: Set of letters or None if uncertain (conservative approach)
    """
    if not explanation or len(explanation) < 20:
        return None

    explanation_lower = explanation.lower()

    # Strategy 1: Look for explicit "Option X" or "Answer is X"
    explicit_patterns = [
        r'\b(?:option|answer|correct\s+answer)\s+([A-E])\b',
        r'\b([A-E])\s+is\s+(?:correct|the\s+answer)',
        r'\bchoose\s+([A-E])\b',
    ]

    for pattern in explicit_patterns:
        m = re.search(pattern, explanation, re.IGNORECASE)
        if m:
            return {m.group(1).upper()}

    # Strategy 2: Look for option letter at start of explanation
    # Sometimes explanation starts with "C. Configure..."
    m = re.match(r'^([A-E])\.\s+', explanation)
    if m:
        return {m.group(1)}

    # Strategy 3: Analyze which option text appears most in explanation
    # Use similarity scoring
    scores: Dict[str, float] = {}
    for letter, option_text in options.items():
        # Normalize texts
        option_norm = _norm(option_text)
        explanation_norm = _norm(explanation)

        # Calculate similarity
        similarity = difflib.SequenceMatcher(None, option_norm, explanation_norm).ratio()

        # Also check for substring match
        if option_norm in explanation_norm or explanation_norm.startswith(option_norm[:30]):
            similarity = max(similarity, 0.70)

        scores[letter] = similarity

    # Find best match
    if scores:
        best_letter = max(scores, key=scores.get)
        best_score = scores[best_letter]

        # Conservative threshold: only accept if confidence > 65%
        if best_score > 0.65:
            return {best_letter}

    # Strategy 4: Look for AWS service keywords
    service_scores = analyze_service_keywords(explanation, options)
    if service_scores:
        best_letter = max(service_scores, key=service_scores.get)
        if service_scores[best_letter] > 0.60:
            return {best_letter}

    return None  # Low confidence


def detect_format4_test_heuristic(block_lines: List[str]) -> Optional[dict]:
    """
    Format 4: Test format with heuristic analysis.

    Example:
        172] [Question text]
        Which action should the solutions architect take?

            A. Configure a CloudFront signed URL.
            B. Configure a CloudFront signed cookie.
            C. Configure a CloudFront field-level encryption profile.
            D. Configure CloudFront and set the Origin Protocol...

    Extract indented options, then analyze explanation to determine answer.

    Returns:
        {"letters": Set[str], "text": None} or None if heuristic fails
    """
    _INDENTED_OPTION_RE = re.compile(r'^\s{4}([A-E])\.\s+(.+)$')

    # Step 1: Extract all indented options
    options: Dict[str, str] = {}
    for line in block_lines:
        m = _INDENTED_OPTION_RE.match(line)
        if m:
            letter = m.group(1)
            text = m.group(2).strip()
            options[letter] = text

    if len(options) < 4:
        return None  # Not enough options for test format

    # Step 2: Extract explanation section (after options)
    explanation = extract_explanation_after_options(block_lines)

    if not explanation or len(explanation) < 20:
        return None  # No explanation to analyze

    # Step 3: Apply heuristic
    detected_letters = apply_heuristic_analysis(explanation, options)

    if detected_letters and validate_answer_letters(detected_letters):
        return {"letters": detected_letters, "text": None}

    return None  # Heuristic failed


def parse_solutions_raw(path: str) -> Dict[int, dict]:
    """
    Parse solutions.txt into raw format, detecting 4 different answer formats.

    Returns:
        Dict[qnum, {"letters": Set[str] or None, "text": str or None}]
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"No existe solutions file: {path}")

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [ln.rstrip("\n") for ln in f]

    # Phase 1: Split into blocks by question number
    blocks = split_into_blocks(lines)

    out: Dict[int, dict] = {}
    stats = {
        'format1': 0,          # Explicit marker (ans-)
        'format2': 0,          # Single letter at line start
        'format3': 0,          # Multi-answer
        'format4_success': 0,  # Test format with heuristic success
        'format4_failed': 0,   # Test format with heuristic failure
        'unparsed': 0          # No format detected
    }

    # Phase 2: Process each block
    for qnum, block_lines in blocks.items():
        block_text = '\n'.join(block_lines)

        # Try Format 1: Explicit marker (ans-, answer:, correct answer:)
        result = detect_format1_explicit_marker(block_text)
        if result:
            out[qnum] = result
            stats['format1'] += 1
            continue

        # Try Format 4: Test format (check BEFORE Format 2/3)
        # Format 4 has indented options which might confuse Format 2/3 detection
        if is_test_format(block_lines):
            result = detect_format4_test_heuristic(block_lines)
            if result:
                out[qnum] = result
                stats['format4_success'] += 1
            else:
                stats['format4_failed'] += 1
            continue

        # Try Format 2/3: Letters at line start
        result = detect_format2_3_letters(block_lines)
        if result:
            letter_count = len(result['letters'])
            if letter_count == 1:
                stats['format2'] += 1
            else:
                stats['format3'] += 1
            out[qnum] = result
            continue

        # No format detected
        stats['unparsed'] += 1

    # Phase 3: Print diagnostic report
    print_diagnostic_report(stats, len(blocks), out)

    return out


def answer_text_to_letters(q: Question, answer_text: str) -> Set[str]:
    at = _norm(answer_text)
    if not at:
        return set()

    # A veces aparece la letra sola en el texto
    direct = set(re.findall(r"\b([a-e])\b", at))
    if 1 <= len(direct) <= 3:
        return {x.upper() for x in direct}

    scores: List[Tuple[float, str]] = []
    for k, opt in q.options.items():
        o = _norm(opt)
        r = difflib.SequenceMatcher(None, at, o).ratio()
        if at in o or o in at:
            r = max(r, 0.92)
        scores.append((r, k))
    scores.sort(reverse=True, key=lambda x: x[0])

    picked: Set[str] = set()
    for r, k in scores:
        if r >= 0.80:
            picked.add(k)

    if not picked and scores and scores[0][0] >= 0.55:
        picked.add(scores[0][1])

    # safety: evita capturar todo
    if len(picked) > 3:
        return set()
    return picked


def build_solutions_letters(questions: Dict[int, Question], solutions_raw: Dict[int, dict]) -> Dict[int, Set[str]]:
    solutions: Dict[int, Set[str]] = {}
    for qnum, q in questions.items():
        if qnum not in solutions_raw:
            continue
        item = solutions_raw[qnum]
        if item.get("letters"):
            letters = set(item["letters"])
        else:
            letters = answer_text_to_letters(q, item.get("text") or "")
        if 1 <= len(letters) <= 3:
            solutions[qnum] = letters
    return solutions


# ==========
# Stats management (persistent spaced repetition)
# ==========
def load_stats() -> Dict[int, dict]:
    """
    Load question statistics from JSON file.

    Returns:
        Dict[qnum, {"correct": int, "wrong": int, "last_seen": float, "weight": float}]
    """
    if not os.path.exists(STATS_PATH):
        return {}

    try:
        with open(STATS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Convert string keys back to int
            return {int(k): v for k, v in data.items()}
    except Exception as e:
        print(f"Warning: Could not load stats from {STATS_PATH}: {e}")
        return {}


def save_stats(stats: Dict[int, dict]):
    """
    Save question statistics to JSON file.
    """
    try:
        # Convert int keys to strings for JSON
        data = {str(k): v for k, v in stats.items()}
        with open(STATS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Could not save stats to {STATS_PATH}: {e}")


def calculate_weight(stats: dict) -> float:
    """
    Calculate selection weight based on question statistics.

    Higher weight = more likely to appear.

    Strategy:
    - Base weight: 1.0
    - Multiply by (1 + error_rate * 3) to prioritize failed questions
    - Questions never seen get base weight
    - Questions with 100% correct get 40% of base weight (still appear)

    Returns:
        Weight multiplier (0.4 to 4.0)
    """
    correct = stats.get("correct", 0)
    wrong = stats.get("wrong", 0)
    total = correct + wrong

    if total == 0:
        # Never seen - use base weight
        return 1.0

    error_rate = wrong / total

    # Weight increases with error rate
    # 0% errors -> 0.4x weight (still appears, but less)
    # 50% errors -> 2.5x weight
    # 100% errors -> 4.0x weight
    weight = 0.4 + (error_rate * 3.6)

    return max(0.4, min(weight, 4.0))


def init_question_stats(qnums: List[int], stats: Dict[int, dict], domain_mapping: Dict[int, int]) -> Dict[int, dict]:
    """
    Initialize stats for questions that don't have them yet.

    Args:
        qnums: List of question numbers
        stats: Existing stats dict
        domain_mapping: Dict mapping qnum to domain (1-4)

    Returns:
        Updated stats dict
    """
    for qnum in qnums:
        if qnum not in stats:
            stats[qnum] = {
                "correct": 0,
                "wrong": 0,
                "last_seen": 0.0,
                "weight": 1.0,
                "domain": domain_mapping.get(qnum, 0)  # 0 = unclassified
            }
        else:
            # Update domain if not present or changed
            if "domain" not in stats[qnum]:
                stats[qnum]["domain"] = domain_mapping.get(qnum, 0)
    return stats


def update_question_stats(stats: Dict[int, dict], qnum: int, is_correct: bool) -> Dict[int, dict]:
    """
    Update statistics for a question after answering.

    Returns:
        Updated stats dict
    """
    import time

    if qnum not in stats:
        stats[qnum] = {
            "correct": 0,
            "wrong": 0,
            "last_seen": 0.0,
            "weight": 1.0
        }

    if is_correct:
        stats[qnum]["correct"] += 1
    else:
        stats[qnum]["wrong"] += 1

    stats[qnum]["last_seen"] = time.time()
    stats[qnum]["weight"] = calculate_weight(stats[qnum])

    return stats


# ==========
# Adaptive selection (in-session only)
# ==========
def complexity_bucket(q: Question) -> Tuple[int, int]:
    ln = len(q.text)
    if ln < 400:
        b = 0
    elif ln < 900:
        b = 1
    else:
        b = 2
    return (q.choose_n, b)


def weighted_pick(items: List[int], weights: List[float], rng: random.Random) -> int:
    total = sum(weights)
    r = rng.random() * total
    acc = 0.0
    for it, w in zip(items, weights):
        acc += w
        if acc >= r:
            return it
    return items[-1]


def scaled_score_sim(pct_scored: float) -> int:
    pct = max(0.0, min(1.0, pct_scored))
    return int(round(100 + pct * 900))


# ==========
# UI: OptionCard
# ==========
class OptionCard(tk.Frame):
    def __init__(
        self,
        master: tk.Widget,
        key: str,
        text: str,
        on_toggle,
        colors: Dict[str, str],
        wrap: int = 860,
    ):
        super().__init__(master, bg=colors["card_bg"], highlightthickness=1, highlightbackground=colors["border"])
        self.key = key
        self.on_toggle = on_toggle
        self.colors = colors
        self.selected = False
        self.pressed = False
        self.locked = False

        self.configure(cursor="hand2")

        self.lbl = tk.Label(
            self,
            text=f"{key}) {text}",
            bg=self.colors["card_bg"],
            fg=self.colors["fg"],
            justify="left",
            anchor="w",
            wraplength=wrap,
            font=("TkDefaultFont", 11, "normal"),
            padx=12,
            pady=10,
        )
        self.lbl.pack(fill="both", expand=True)

        for w in (self, self.lbl):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<ButtonPress-1>", self._on_press)
            w.bind("<ButtonRelease-1>", self._on_release)

    def set_locked(self, locked: bool):
        self.locked = locked
        self.configure(cursor=("arrow" if locked else "hand2"))

    def _apply_style(self):
        if self.selected:
            bg = self.colors["sel_bg"]
            bd = self.colors["sel_border"]
        elif self.pressed:
            bg = self.colors["press_bg"]
            bd = self.colors["border"]
        else:
            bg = self.colors["card_bg"]
            bd = self.colors["border"]

        self.configure(bg=bg, highlightbackground=bd)
        self.lbl.configure(bg=bg)

    def set_selected(self, value: bool):
        self.selected = value
        self._apply_style()

    def set_border(self, color: str):
        self.configure(highlightbackground=color)

    def _on_enter(self, _e):
        if self.locked:
            return
        if not self.selected:
            self.configure(highlightbackground=self.colors["hover_border"])

    def _on_leave(self, _e):
        self._apply_style()

    def _on_press(self, _e):
        if self.locked:
            return
        self.pressed = True
        self._apply_style()

    def _on_release(self, _e):
        if self.locked:
            return
        self.pressed = False
        self._apply_style()
        self.on_toggle(self.key)


# ==========
# GUI
# ==========
class QuizApp(tk.Tk):
    def __init__(
        self,
        questions: Dict[int, Question],
        solutions: Dict[int, Set[str]],
        exam_total: int = EXAM_TOTAL_DEFAULT,
        scored_count: int = SCORED_DEFAULT,
        pass_pct_scored: float = PASS_PERCENT_SCORED,
    ):
        super().__init__()

        self.title("AWS SAA-C03 Quiz")
        self.minsize(920, 640)

        self.theme = {
            "bg": "#0f1115",
            "fg": "#e8e8e8",
            "muted": "#a7a7a7",
            "accent": "#4da3ff",
            "good": "#57d18a",
            "bad": "#ff5c5c",

            "panel": "#151924",
            "panel_border": "#23283a",

            "card_bg": "#141a28",
            "border": "#2a3248",
            "hover_border": "#3d4a70",
            "sel_bg": "#1a2740",
            "sel_border": "#4da3ff",
            "press_bg": "#101626",
        }
        self.configure(bg=self.theme["bg"])

        self.questions_all = questions
        self.solutions_all = solutions
        self.rng = random.Random()

        self.usable = sorted(set(questions.keys()) & set(solutions.keys()))
        if not self.usable:
            raise RuntimeError("No hay preguntas emparejadas pregunta+respuesta.")

        # Classify questions by domain
        print("Clasificando preguntas por dominio...")
        self.domain_mapping = classify_all_questions(questions)
        classified_count = len([q for q in self.usable if q in self.domain_mapping])
        print(f"Clasificadas: {classified_count}/{len(self.usable)} preguntas")

        # Load persistent stats
        self.stats = load_stats()
        self.stats = init_question_stats(self.usable, self.stats, self.domain_mapping)

        self.exam_total = min(exam_total, len(self.usable))
        self.scored_count = min(scored_count, self.exam_total)
        self.unscored_count = self.exam_total - self.scored_count
        self.pass_pct_scored = pass_pct_scored

        self.remaining: List[int] = self.usable[:]
        self.selected_order: List[int] = []

        scored_set = set(self.rng.sample(self.usable, self.scored_count))
        self.is_scored: Dict[int, bool] = {q: (q in scored_set) for q in self.usable}

        # adaptativo
        self.global_hardness = 0.0
        self.bucket_heat: Dict[Tuple[int, int], float] = {}

        # estado
        self.idx = 0
        self.current_qnum: Optional[int] = None
        self.current_choose_n = 1

        self.correct_total = 0
        self.wrong_total = 0
        self.correct_scored = 0
        self.wrong_scored = 0

        self.answer_locked = False

        # FIX: inicializar antes del primer _next_question()
        self.cards: Dict[str, OptionCard] = {}
        self.selected_keys: Set[str] = set()

        # Timer
        self.exam_time_seconds = EXAM_TIME_SECONDS
        self.time_remaining = self.exam_time_seconds
        self.timer_running = False
        self.timer_id: Optional[str] = None

        self._build_ui()
        self._next_question()

    def _build_ui(self):
        top = tk.Frame(self, bg=self.theme["bg"])
        top.pack(fill="x", padx=18, pady=(16, 10))

        tk.Label(top, text="AWS SAA-C03", fg=self.theme["fg"], bg=self.theme["bg"], font=("TkDefaultFont", 16, "bold")).pack(side="left")

        # Timer label
        self.lbl_timer = tk.Label(top, text="", fg=self.theme["accent"], bg=self.theme["bg"], font=("TkDefaultFont", 14, "bold"))
        self.lbl_timer.pack(side="right", padx=(0, 20))

        self.lbl_progress = tk.Label(top, text="", fg=self.theme["muted"], bg=self.theme["bg"], font=("TkDefaultFont", 11, "normal"))
        self.lbl_progress.pack(side="right")

        self.panel = tk.Frame(self, bg=self.theme["panel"], highlightthickness=1, highlightbackground=self.theme["panel_border"])
        self.panel.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        hdr = tk.Frame(self.panel, bg=self.theme["panel"])
        hdr.pack(fill="x", padx=16, pady=(14, 6))

        self.lbl_qmeta = tk.Label(hdr, text="", fg=self.theme["muted"], bg=self.theme["panel"], font=("TkDefaultFont", 10, "normal"))
        self.lbl_qmeta.pack(side="left")

        self.lbl_score = tk.Label(hdr, text="", fg=self.theme["muted"], bg=self.theme["panel"], font=("TkDefaultFont", 10, "normal"))
        self.lbl_score.pack(side="right")

        self.txt_question = tk.Text(
            self.panel,
            height=10,
            wrap="word",
            bg=self.theme["panel"],
            fg=self.theme["fg"],
            insertbackground=self.theme["fg"],
            relief="flat",
            font=("TkDefaultFont", 12, "normal"),
            padx=16,
            pady=6,
        )
        self.txt_question.pack(fill="x", padx=0, pady=(0, 8))
        self.txt_question.configure(state="disabled")

        self.opt_frame = tk.Frame(self.panel, bg=self.theme["panel"])
        self.opt_frame.pack(fill="both", expand=True, padx=16, pady=(0, 6))

        self.lbl_feedback = tk.Label(self.panel, text="", fg=self.theme["muted"], bg=self.theme["panel"], font=("TkDefaultFont", 11, "bold"))
        self.lbl_feedback.pack(fill="x", padx=16, pady=(6, 10))

        bottom = tk.Frame(self, bg=self.theme["bg"])
        bottom.pack(fill="x", padx=18, pady=(0, 16))

        self.btn_primary = tk.Button(
            bottom,
            text="Responder",
            command=self._on_primary,
            bg=self.theme["accent"],
            fg="#0b0c10",
            activebackground=self.theme["accent"],
            relief="flat",
            font=("TkDefaultFont", 11, "bold"),
            padx=16,
            pady=10,
        )
        self.btn_primary.pack(side="right")

        tk.Button(
            bottom,
            text="Salir",
            command=self.destroy,
            bg="#1c2231",
            fg=self.theme["fg"],
            activebackground="#1c2231",
            relief="flat",
            font=("TkDefaultFont", 11, "normal"),
            padx=14,
            pady=10,
        ).pack(side="right", padx=(0, 10))

        self.bind("<Return>", lambda e: self._on_primary())

    def _set_question_text(self, s: str):
        self.txt_question.configure(state="normal")
        self.txt_question.delete("1.0", "end")
        self.txt_question.insert("1.0", s.strip())
        self.txt_question.configure(state="disabled")

    def _clear_options(self):
        for w in self.opt_frame.winfo_children():
            w.destroy()
        self.cards = {}
        self.selected_keys = set()

    def _render_options(self, q: Question):
        self._clear_options()
        self.current_choose_n = q.choose_n

        keys = sorted(q.options.keys())
        for k in keys:
            card = OptionCard(
                self.opt_frame,
                key=k,
                text=q.options[k],
                on_toggle=self._toggle_option,
                colors={
                    "card_bg": self.theme["card_bg"],
                    "border": self.theme["border"],
                    "hover_border": self.theme["hover_border"],
                    "sel_bg": self.theme["sel_bg"],
                    "sel_border": self.theme["sel_border"],
                    "press_bg": self.theme["press_bg"],
                    "fg": self.theme["fg"],
                },
                wrap=860,
            )
            card.pack(fill="x", pady=6)
            self.cards[k] = card

        hint = f"elige {q.choose_n} (ej. AC)" if q.choose_n > 1 else "elige 1"
        self.lbl_qmeta.config(text=f"Q{q.qnum}  •  {hint}")

    def _toggle_option(self, key: str):
        if self.answer_locked:
            return
        if key not in self.cards:
            return

        if self.current_choose_n == 1:
            for k, c in self.cards.items():
                c.set_selected(k == key)
            self.selected_keys = {key}
        else:
            if key in self.selected_keys:
                self.selected_keys.remove(key)
                self.cards[key].set_selected(False)
            else:
                self.selected_keys.add(key)
                self.cards[key].set_selected(True)

    def _pick_next_qnum(self) -> int:
        weights: List[float] = []
        for qnum in self.remaining:
            q = self.questions_all[qnum]
            b = complexity_bucket(q)

            # Base weight from persistent stats (spaced repetition)
            stats_weight = self.stats.get(qnum, {}).get("weight", 1.0)
            w = stats_weight

            # In-session adaptive boost (for current session difficulty)
            choose_boost = 0.18 * max(0, q.choose_n - 1)
            len_boost = 0.12 * (1 if b[1] == 1 else 2 if b[1] == 2 else 0)
            w *= (1.0 + self.global_hardness * (choose_boost + len_boost))
            w *= (1.0 + self.bucket_heat.get(b, 0.0))

            weights.append(max(0.05, min(w, 30.0)))

        return weighted_pick(self.remaining, weights, self.rng)

    def _update_labels(self):
        self.lbl_progress.config(text=f"{self.idx}/{self.exam_total}")
        self.lbl_score.config(text=f"✅ {self.correct_total}  ❌ {self.wrong_total}    |    Scored: ✅ {self.correct_scored}/{self.scored_count}")

    def _format_time(self, seconds: int) -> str:
        """Format seconds as MM:SS"""
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins:02d}:{secs:02d}"

    def _update_timer(self):
        """Update timer display and handle time expiration"""
        if not self.timer_running:
            return

        self.time_remaining -= 1

        # Update display
        time_str = self._format_time(self.time_remaining)

        # Change color when time is running low
        if self.time_remaining <= 300:  # 5 minutes
            self.lbl_timer.config(text=f"⏱️ {time_str}", fg=self.theme["bad"])
        elif self.time_remaining <= 900:  # 15 minutes
            self.lbl_timer.config(text=f"⏱️ {time_str}", fg="#ff9f40")
        else:
            self.lbl_timer.config(text=f"⏱️ {time_str}", fg=self.theme["accent"])

        # Check if time expired
        if self.time_remaining <= 0:
            self._stop_timer()
            messagebox.showinfo("Tiempo Agotado", "Se acabó el tiempo del examen. El examen finalizará ahora.")
            self._finish()
            return

        # Schedule next update
        self.timer_id = self.after(1000, self._update_timer)

    def _start_timer(self):
        """Start the exam timer"""
        if not self.timer_running:
            self.timer_running = True
            self._update_timer()

    def _stop_timer(self):
        """Stop the exam timer"""
        self.timer_running = False
        if self.timer_id:
            self.after_cancel(self.timer_id)
            self.timer_id = None

    def _flash_panel(self, color: str, times: int = 6):
        def step(i: int):
            if i >= times:
                self.panel.configure(highlightbackground=self.theme["panel_border"])
                return
            self.panel.configure(highlightbackground=(color if i % 2 == 0 else self.theme["panel_border"]))
            self.after(60, lambda: step(i + 1))
        step(0)

    def _pulse_button(self, color: str, times: int = 6):
        base = self.theme["accent"]

        def step(i: int):
            if i >= times:
                self.btn_primary.configure(bg=base)
                return
            self.btn_primary.configure(bg=(color if i % 2 == 0 else base))
            self.after(60, lambda: step(i + 1))
        step(0)

    def _shake_window(self, intensity: int = 8, steps: int = 10):
        try:
            x = self.winfo_x()
            y = self.winfo_y()
        except Exception:
            return

        def step(i: int):
            if i >= steps:
                self.geometry(f"+{x}+{y}")
                return
            dx = intensity if i % 2 == 0 else -intensity
            self.geometry(f"+{x + dx}+{y}")
            self.after(35, lambda: step(i + 1))
        step(0)

    def _lock_cards(self, locked: bool):
        if not hasattr(self, "cards") or not self.cards:
            return
        for c in self.cards.values():
            c.set_locked(locked)

    def _next_question(self):
        if self.idx >= self.exam_total:
            self._finish()
            return

        self.answer_locked = False
        self._lock_cards(False)

        qnum = self._pick_next_qnum()
        self.remaining.remove(qnum)
        self.selected_order.append(qnum)
        self.current_qnum = qnum
        self.idx += 1

        # Start timer on first question
        if self.idx == 1:
            self._start_timer()

        q = self.questions_all[qnum]
        self._update_labels()
        self._set_question_text(q.text)
        self._render_options(q)

        self.lbl_feedback.config(text="", fg=self.theme["muted"])
        self.btn_primary.config(text="Responder")

    def _paint_after_answer(self, correct: Set[str], user: Set[str]):
        if not hasattr(self, "cards") or not self.cards:
            return
        for k, card in self.cards.items():
            if k in correct:
                card.set_selected(True)
                card.set_border(self.theme["good"])
            elif k in user and k not in correct:
                card.set_selected(True)
                card.set_border(self.theme["bad"])

    def _on_primary(self):
        if self.current_qnum is None:
            return

        if self.btn_primary.cget("text") == "Siguiente":
            self._next_question()
            return

        q = self.questions_all[self.current_qnum]
        correct = set(sorted(self.solutions_all[self.current_qnum]))
        user = set(sorted(self.selected_keys))

        if not user:
            messagebox.showinfo("Respuesta", "Selecciona una opción (en AWS en blanco cuenta como incorrecta).")
            return
        if q.choose_n > 1 and len(user) != q.choose_n:
            messagebox.showinfo("Respuesta", f"Selecciona exactamente {q.choose_n} opciones.")
            return
        if q.choose_n == 1 and len(user) != 1:
            messagebox.showinfo("Respuesta", "Selecciona una opción.")
            return

        self.answer_locked = True
        self._lock_cards(True)

        is_correct = (user == correct)
        scored = self.is_scored.get(self.current_qnum, True)

        self._paint_after_answer(correct, user)

        if is_correct:
            self.correct_total += 1
            if scored:
                self.correct_scored += 1
            self.lbl_feedback.config(text="Correcto", fg=self.theme["good"])
            self._flash_panel(self.theme["good"])
            self._pulse_button(self.theme["good"])
        else:
            self.wrong_total += 1
            if scored:
                self.wrong_scored += 1
            self.lbl_feedback.config(text=f"Incorrecto  •  Correcta: {''.join(sorted(correct))}", fg=self.theme["bad"])
            self._flash_panel(self.theme["bad"])
            self._pulse_button(self.theme["bad"])
            self._shake_window()

            self.global_hardness = min(1.25, self.global_hardness + 0.10)
            b = complexity_bucket(q)
            self.bucket_heat[b] = min(1.8, self.bucket_heat.get(b, 0.0) + 0.22)

        # Update persistent stats and save to JSON
        self.stats = update_question_stats(self.stats, self.current_qnum, is_correct)
        save_stats(self.stats)

        self._update_labels()
        self.btn_primary.config(text="Siguiente")

    def _calculate_domain_stats(self) -> Dict[int, dict]:
        """
        Calculate statistics by domain.

        Returns:
            Dict[domain_num, {"correct": int, "wrong": int, "total": int, "error_rate": float}]
        """
        domain_stats = {}

        for domain_num in DOMAINS.keys():
            domain_stats[domain_num] = {
                "correct": 0,
                "wrong": 0,
                "total": 0,
                "error_rate": 0.0
            }

        # Aggregate stats by domain
        for qnum, stat in self.stats.items():
            domain = stat.get("domain", 0)
            if domain == 0:  # Skip unclassified
                continue

            correct = stat.get("correct", 0)
            wrong = stat.get("wrong", 0)
            total = correct + wrong

            if total > 0:
                domain_stats[domain]["correct"] += correct
                domain_stats[domain]["wrong"] += wrong
                domain_stats[domain]["total"] += total

        # Calculate error rates
        for domain_num in domain_stats:
            total = domain_stats[domain_num]["total"]
            if total > 0:
                wrong = domain_stats[domain_num]["wrong"]
                domain_stats[domain_num]["error_rate"] = wrong / total

        return domain_stats

    def _show_domain_stats(self, parent: tk.Frame):
        """
        Show statistics by domain in the final screen.
        """
        domain_stats = self._calculate_domain_stats()

        # Check if we have any data
        has_data = any(s["total"] > 0 for s in domain_stats.values())
        if not has_data:
            return

        tk.Label(
            parent,
            text="📊 Rendimiento por Dominio de Contenido:",
            fg=self.theme["fg"],
            bg=self.theme["bg"],
            font=("TkDefaultFont", 12, "bold"),
            justify="left",
        ).pack(anchor="w", pady=(20, 8))

        # Sort domains by error rate (worst first)
        sorted_domains = sorted(
            domain_stats.items(),
            key=lambda x: (x[1]["error_rate"], -x[1]["total"]),
            reverse=True
        )

        for domain_num, stats in sorted_domains:
            if stats["total"] == 0:
                continue

            info = get_domain_info(domain_num)
            correct = stats["correct"]
            wrong = stats["wrong"]
            total = stats["total"]
            error_rate = stats["error_rate"]
            accuracy = (correct / total) * 100 if total > 0 else 0

            # Color based on performance
            if error_rate < 0.30:
                color = self.theme["good"]
                icon = "✅"
            elif error_rate < 0.50:
                color = "#ff9f40"  # Orange
                icon = "⚠️"
            else:
                color = self.theme["bad"]
                icon = "❌"

            text = f"{icon} Domain {domain_num}: {info['name']}"
            tk.Label(
                parent,
                text=text,
                fg=self.theme["fg"],
                bg=self.theme["bg"],
                font=("TkDefaultFont", 10, "bold"),
                justify="left",
            ).pack(anchor="w", pady=(6, 2))

            detail = f"     {correct}/{total} correctas ({accuracy:.0f}%)  •  {info['weight']*100:.0f}% del examen"
            tk.Label(
                parent,
                text=detail,
                fg=color,
                bg=self.theme["bg"],
                font=("TkDefaultFont", 9, "normal"),
                justify="left",
            ).pack(anchor="w", pady=(0, 2))

    def _show_weak_areas(self, parent: tk.Frame):
        """
        Show top 5 most failed questions in the final screen.
        """
        # Calculate error rate for each question
        question_errors: List[Tuple[int, float, int, int, int]] = []
        for qnum, stat in self.stats.items():
            total = stat["correct"] + stat["wrong"]
            if total > 0:
                error_rate = stat["wrong"] / total
                domain = stat.get("domain", 0)
                question_errors.append((qnum, error_rate, stat["wrong"], total, domain))

        # Sort by error rate, then by number of wrongs
        question_errors.sort(key=lambda x: (x[1], x[2]), reverse=True)

        # Take top 5
        top_errors = question_errors[:5]

        if not top_errors:
            return

        tk.Label(
            parent,
            text="📝 Preguntas Más Falladas:",
            fg=self.theme["fg"],
            bg=self.theme["bg"],
            font=("TkDefaultFont", 12, "bold"),
            justify="left",
        ).pack(anchor="w", pady=(20, 8))

        for qnum, error_rate, wrongs, total, domain in top_errors:
            domain_name = get_domain_info(domain)["name"] if domain > 0 else "Sin clasificar"
            text = f"  • Q{qnum} ({domain_name[:30]}...): {wrongs}/{total} errores ({error_rate*100:.0f}%)"
            tk.Label(
                parent,
                text=text,
                fg=self.theme["bad"],
                bg=self.theme["bg"],
                font=("TkDefaultFont", 10, "normal"),
                justify="left",
            ).pack(anchor="w", pady=2)

    def _finish(self):
        # Stop the timer
        self._stop_timer()

        for w in self.winfo_children():
            w.destroy()

        root = tk.Frame(self, bg=self.theme["bg"])
        root.pack(fill="both", expand=True, padx=22, pady=22)

        pct_scored = (self.correct_scored / self.scored_count) if self.scored_count else 0.0
        scaled = scaled_score_sim(pct_scored)
        passed = pct_scored >= self.pass_pct_scored

        status = "PASS" if passed else "FAIL"
        status_color = self.theme["good"] if passed else self.theme["bad"]

        tk.Label(root, text="Resultado", fg=self.theme["fg"], bg=self.theme["bg"], font=("TkDefaultFont", 18, "bold")).pack(anchor="w")
        tk.Label(root, text=status, fg=status_color, bg=self.theme["bg"], font=("TkDefaultFont", 34, "bold")).pack(anchor="w", pady=(8, 6))

        tk.Label(
            root,
            text=f"Scored: {self.correct_scored}/{self.scored_count}  ({pct_scored*100:.1f}%)  •  criterio PASS: ≥ {int(self.pass_pct_scored*100)}%",
            fg=self.theme["muted"],
            bg=self.theme["bg"],
            font=("TkDefaultFont", 12, "normal"),
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

        tk.Label(
            root,
            text=f"Total: ✅ {self.correct_total}  ❌ {self.wrong_total}   (incluye {self.unscored_count} unscored)",
            fg=self.theme["muted"],
            bg=self.theme["bg"],
            font=("TkDefaultFont", 12, "normal"),
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        tk.Label(
            root,
            text=f"Scaled score (simulado): {scaled}  •  Passing real AWS: {AWS_PASS_SCALED} (modelado aproximado)",
            fg=self.theme["muted"],
            bg=self.theme["bg"],
            font=("TkDefaultFont", 11, "normal"),
            justify="left",
        ).pack(anchor="w", pady=(10, 12))

        # Show domain statistics
        self._show_domain_stats(root)

        # Show top 5 most failed questions
        self._show_weak_areas(root)

        tk.Button(
            root,
            text="Reintentar (nuevo examen)",
            command=self._restart,
            bg=self.theme["accent"],
            fg="#0b0c10",
            activebackground=self.theme["accent"],
            relief="flat",
            font=("TkDefaultFont", 11, "bold"),
            padx=16,
            pady=12,
        ).pack(anchor="w", pady=(6, 0))

        tk.Button(
            root,
            text="Salir",
            command=self.destroy,
            bg="#1c2231",
            fg=self.theme["fg"],
            activebackground="#1c2231",
            relief="flat",
            font=("TkDefaultFont", 11, "normal"),
            padx=16,
            pady=12,
        ).pack(anchor="w", pady=(10, 0))

    def _restart(self):
        # Stop current timer
        self._stop_timer()

        self.remaining = self.usable[:]
        self.selected_order = []
        self.bucket_heat = {}
        self.global_hardness = 0.0

        self.idx = 0
        self.current_qnum = None

        self.correct_total = 0
        self.wrong_total = 0
        self.correct_scored = 0
        self.wrong_scored = 0

        # Reset timer
        self.time_remaining = self.exam_time_seconds
        self.timer_running = False
        self.timer_id = None

        scored_set = set(self.rng.sample(self.usable, self.scored_count))
        self.is_scored = {q: (q in scored_set) for q in self.usable}

        for w in self.winfo_children():
            w.destroy()
        self._build_ui()
        self._next_question()


def main():
    print("="*70)
    print("AWS SAA-C03 Quiz - Inicializando")
    print("="*70)

    print("\n🧠 Sistema de Repetición Espaciada Activado")
    print("   • Las preguntas que falles aparecerán con más frecuencia")
    print("   • Tus estadísticas se guardan en quiz_stats.json")
    print("   • Todas las preguntas siguen disponibles en cada quiz")

    print("\nParsing questions...")
    questions = parse_questions(QUESTIONS_PATH)
    print(f"Found {len(questions)} questions")

    print("\nParsing solutions...")
    solutions_raw = parse_solutions_raw(SOLUTIONS_PATH)
    # Diagnostic report printed inside parse_solutions_raw()

    print("\nBuilding final solutions map...")
    solutions = build_solutions_letters(questions, solutions_raw)

    usable = sorted(set(questions.keys()) & set(solutions.keys()))
    print(f"\nUsable questions (with both question and solution): {len(usable)}")

    if not usable:
        print("\nERROR: No hay preguntas emparejadas entre questions.txt y solutions.txt!")
        print("Cannot start quiz without questions and solutions.")
        sys.exit(2)

    print(f"\nStarting quiz with {len(usable)} questions...")
    print("="*70 + "\n")

    app = QuizApp(
        questions,
        solutions,
        exam_total=EXAM_TOTAL_DEFAULT,
        scored_count=SCORED_DEFAULT,
        pass_pct_scored=PASS_PERCENT_SCORED,
    )
    app.mainloop()


if __name__ == "__main__":
    main()
