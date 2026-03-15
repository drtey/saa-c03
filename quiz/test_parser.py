#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to validate the solutions parser without starting GUI
"""

import os
import sys

# Import from aws_quiz.py
from aws_quiz import (
    parse_questions,
    parse_solutions_raw,
    build_solutions_letters,
    QUESTIONS_PATH,
    SOLUTIONS_PATH,
)

def main():
    print("="*70)
    print("PARSER TEST - NO GUI")
    print("="*70)

    print("\n1. Parsing questions...")
    try:
        questions = parse_questions(QUESTIONS_PATH)
        print(f"   ✓ Successfully parsed {len(questions)} questions")
    except Exception as e:
        print(f"   ✗ Error parsing questions: {e}")
        sys.exit(1)

    print("\n2. Parsing solutions...")
    try:
        solutions_raw = parse_solutions_raw(SOLUTIONS_PATH)
        # Diagnostic report printed inside parse_solutions_raw()
        print(f"   ✓ Successfully parsed {len(solutions_raw)} raw solutions")
    except Exception as e:
        print(f"   ✗ Error parsing solutions: {e}")
        sys.exit(1)

    print("\n3. Building final solutions map...")
    try:
        solutions = build_solutions_letters(questions, solutions_raw)
        print(f"   ✓ Successfully built {len(solutions)} final solutions")
    except Exception as e:
        print(f"   ✗ Error building solutions: {e}")
        sys.exit(1)

    print("\n4. Checking usable questions...")
    usable = sorted(set(questions.keys()) & set(solutions.keys()))
    print(f"   ✓ Usable questions (with both question and solution): {len(usable)}")

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)

    # Show some sample questions
    if usable:
        print("\nSample questions with solutions:")
        for qnum in sorted(usable)[:5]:
            q = questions[qnum]
            sol = solutions[qnum]
            print(f"  Q{qnum}: {q.choose_n}-choice question → Answer: {sorted(sol)}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
