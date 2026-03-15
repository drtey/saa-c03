#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utility script to view and manage quiz statistics.

Usage:
    python view_stats.py           # View statistics
    python view_stats.py --reset   # Reset all statistics
"""

import json
import os
import sys
from typing import Dict
from domain_classifier import DOMAINS, get_domain_info

BASE_DIR = "/home/drtey/develop/roadmap26/saa-c03/quiz"
STATS_PATH = os.path.join(BASE_DIR, "quiz_stats.json")


def load_stats() -> Dict[int, dict]:
    """Load statistics from JSON file."""
    if not os.path.exists(STATS_PATH):
        print(f"No statistics file found at: {STATS_PATH}")
        return {}

    with open(STATS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        return {int(k): v for k, v in data.items()}


def save_stats(stats: Dict[int, dict]):
    """Save statistics to JSON file."""
    data = {str(k): v for k, v in stats.items()}
    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def calculate_domain_stats(stats: Dict[int, dict]) -> Dict[int, dict]:
    """
    Calculate statistics by domain.

    Returns:
        Dict[domain_num, {"correct": int, "wrong": int, "total": int, "error_rate": float, "questions": int}]
    """
    domain_stats = {}

    for domain_num in DOMAINS.keys():
        domain_stats[domain_num] = {
            "correct": 0,
            "wrong": 0,
            "total": 0,
            "error_rate": 0.0,
            "questions": 0
        }

    # Aggregate stats by domain
    for qnum, stat in stats.items():
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
            domain_stats[domain]["questions"] += 1

    # Calculate error rates
    for domain_num in domain_stats:
        total = domain_stats[domain_num]["total"]
        if total > 0:
            wrong = domain_stats[domain_num]["wrong"]
            domain_stats[domain_num]["error_rate"] = wrong / total

    return domain_stats


def view_stats():
    """Display statistics in a formatted table."""
    stats = load_stats()

    if not stats:
        print("No statistics available yet. Start the quiz to generate statistics!")
        return

    print("=" * 80)
    print("AWS SAA-C03 Quiz Statistics")
    print("=" * 80)

    # Calculate totals
    total_correct = sum(s["correct"] for s in stats.values())
    total_wrong = sum(s["wrong"] for s in stats.values())
    total_attempts = total_correct + total_wrong

    print(f"\n📊 Overall Statistics:")
    print(f"   Total attempts: {total_attempts}")
    print(f"   Correct: {total_correct} ({total_correct/total_attempts*100:.1f}%)" if total_attempts > 0 else "   No attempts yet")
    print(f"   Wrong: {total_wrong} ({total_wrong/total_attempts*100:.1f}%)" if total_attempts > 0 else "")
    print(f"   Questions with data: {len(stats)}")

    # Show domain statistics
    domain_stats = calculate_domain_stats(stats)
    has_domain_data = any(s["total"] > 0 for s in domain_stats.values())

    if has_domain_data:
        print("\n" + "=" * 80)
        print("📚 PERFORMANCE BY CONTENT DOMAIN")
        print("=" * 80)

        # Sort by error rate (worst first)
        sorted_domains = sorted(
            domain_stats.items(),
            key=lambda x: (x[1]["error_rate"], -x[1]["total"]),
            reverse=True
        )

        for domain_num, dstats in sorted_domains:
            if dstats["total"] == 0:
                continue

            info = get_domain_info(domain_num)
            correct = dstats["correct"]
            wrong = dstats["wrong"]
            total = dstats["total"]
            questions = dstats["questions"]
            error_rate = dstats["error_rate"]
            accuracy = (correct / total) * 100 if total > 0 else 0

            # Status icon
            if error_rate < 0.30:
                icon = "✅"
            elif error_rate < 0.50:
                icon = "⚠️"
            else:
                icon = "❌"

            print(f"\n{icon} Domain {domain_num}: {info['name']}")
            print(f"   Exam weight: {info['weight']*100:.0f}%")
            print(f"   Questions answered: {questions}")
            print(f"   Accuracy: {accuracy:.1f}% ({correct}/{total} correct)")
            print(f"   Error rate: {error_rate*100:.1f}%")

    # Sort by error rate
    question_stats = []
    for qnum, stat in stats.items():
        total = stat["correct"] + stat["wrong"]
        if total > 0:
            error_rate = stat["wrong"] / total
            domain = stat.get("domain", 0)
            question_stats.append((qnum, stat["correct"], stat["wrong"], total, error_rate, stat["weight"], domain))

    question_stats.sort(key=lambda x: (x[4], x[2]), reverse=True)

    # Show most failed questions
    print("\n" + "=" * 80)
    print("❌ TOP 15 MOST FAILED QUESTIONS")
    print("=" * 80)
    print(f"{'Q#':<6} {'Domain':<8} {'Correct':<8} {'Wrong':<8} {'Total':<8} {'Error%':<10} {'Weight':<8}")
    print("-" * 80)

    for qnum, correct, wrong, total, error_rate, weight, domain in question_stats[:15]:
        domain_str = f"D{domain}" if domain > 0 else "---"
        print(f"{qnum:<6} {domain_str:<8} {correct:<8} {wrong:<8} {total:<8} {error_rate*100:>6.1f}%    {weight:>6.2f}x")

    # Show best questions
    print("\n" + "=" * 80)
    print("✅ TOP 15 BEST ANSWERED QUESTIONS")
    print("=" * 80)
    print(f"{'Q#':<6} {'Domain':<8} {'Correct':<8} {'Wrong':<8} {'Total':<8} {'Error%':<10} {'Weight':<8}")
    print("-" * 80)

    best_questions = sorted(question_stats, key=lambda x: (x[4], -x[1]))[:15]
    for qnum, correct, wrong, total, error_rate, weight, domain in best_questions:
        domain_str = f"D{domain}" if domain > 0 else "---"
        print(f"{qnum:<6} {domain_str:<8} {correct:<8} {wrong:<8} {total:<8} {error_rate*100:>6.1f}%    {weight:>6.2f}x")

    print("\n" + "=" * 80)
    print(f"Statistics saved at: {STATS_PATH}")
    print("=" * 80)


def reset_stats():
    """Reset all statistics."""
    if not os.path.exists(STATS_PATH):
        print("No statistics file to reset.")
        return

    response = input("Are you sure you want to reset all statistics? (yes/no): ")
    if response.lower() in ("yes", "y"):
        os.remove(STATS_PATH)
        print("✅ Statistics reset successfully!")
    else:
        print("❌ Reset cancelled.")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        reset_stats()
    else:
        view_stats()


if __name__ == "__main__":
    main()
