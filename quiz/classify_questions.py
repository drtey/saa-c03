#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classify all questions and generate a report.

Usage:
    python classify_questions.py                    # Show classification report
    python classify_questions.py --export           # Export to domain_mapping.json
    python classify_questions.py --show-unclassified # Show unclassified questions
"""

import sys
import json
import os
from typing import Dict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from aws_quiz import parse_questions, QUESTIONS_PATH
from domain_classifier import (
    classify_all_questions,
    classify_question_by_keywords,
    get_domain_info,
    DOMAINS,
    print_classification_report,
)

BASE_DIR = "/home/drtey/develop/roadmap26/saa-c03/quiz"
MAPPING_PATH = os.path.join(BASE_DIR, "domain_mapping.json")


def export_mapping(questions: Dict[int, any], mapping: Dict[int, int]):
    """Export domain mapping to JSON file."""
    # Add domain name for readability
    export_data = {}
    for qnum, domain_num in mapping.items():
        info = get_domain_info(domain_num)
        export_data[str(qnum)] = {
            "domain": domain_num,
            "domain_name": info["name"],
            "question_preview": questions[qnum].text[:100] + "..."
        }

    with open(MAPPING_PATH, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Mapping exported to: {MAPPING_PATH}")
    print(f"   {len(export_data)} questions classified")


def show_unclassified(questions: Dict[int, any], mapping: Dict[int, int]):
    """Show questions that could not be classified."""
    unclassified = []

    for qnum in sorted(questions.keys()):
        if qnum not in mapping:
            q = questions[qnum]
            # Try to get scores
            scores = classify_question_by_keywords(q.text)
            unclassified.append((qnum, q.text[:150], scores))

    if not unclassified:
        print("\n✅ All questions were successfully classified!")
        return

    print("\n" + "=" * 80)
    print(f"⚠️  UNCLASSIFIED QUESTIONS ({len(unclassified)})")
    print("=" * 80)

    for qnum, preview, scores in unclassified:
        print(f"\nQ{qnum}: {preview}...")
        print("   Confidence scores:")
        for domain_num in sorted(scores.keys()):
            info = get_domain_info(domain_num)
            score = scores[domain_num]
            print(f"      Domain {domain_num} ({info['name'][:30]}): {score:.2f}")


def show_detailed_classification(questions: Dict[int, any], mapping: Dict[int, int]):
    """Show detailed classification for each domain."""
    print("\n" + "=" * 80)
    print("DETAILED CLASSIFICATION BY DOMAIN")
    print("=" * 80)

    # Group by domain
    by_domain = {1: [], 2: [], 3: [], 4: []}
    for qnum, domain_num in mapping.items():
        by_domain[domain_num].append(qnum)

    # Show each domain
    for domain_num in sorted(DOMAINS.keys()):
        info = get_domain_info(domain_num)
        qnums = sorted(by_domain[domain_num])

        print(f"\n{'='*80}")
        print(f"Domain {domain_num}: {info['name']}")
        print(f"Exam weight: {info['weight']*100:.0f}%  |  Questions classified: {len(qnums)}")
        print('='*80)

        # Show first 5 questions as examples
        for qnum in qnums[:5]:
            q = questions[qnum]
            preview = q.text[:120].replace('\n', ' ')
            print(f"  Q{qnum}: {preview}...")

        if len(qnums) > 5:
            print(f"  ... and {len(qnums) - 5} more questions")


def main():
    print("=" * 80)
    print("AWS SAA-C03 Question Classifier")
    print("=" * 80)

    # Parse questions
    print("\nLoading questions...")
    questions = parse_questions(QUESTIONS_PATH)
    print(f"Loaded {len(questions)} questions")

    # Classify questions
    print("\nClassifying questions by domain...")
    mapping = classify_all_questions(questions)

    # Print classification report
    print_classification_report(questions, mapping)

    # Handle command line arguments
    if len(sys.argv) > 1:
        if "--export" in sys.argv:
            export_mapping(questions, mapping)

        if "--show-unclassified" in sys.argv:
            show_unclassified(questions, mapping)

        if "--detailed" in sys.argv:
            show_detailed_classification(questions, mapping)
    else:
        # Default: show basic report
        print("\n💡 Available options:")
        print("   --export            Export mapping to domain_mapping.json")
        print("   --show-unclassified Show questions that couldn't be classified")
        print("   --detailed          Show detailed classification by domain")


if __name__ == "__main__":
    main()
