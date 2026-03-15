#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AWS SAA-C03 Domain Classifier

Classifies questions into the 4 content domains using keyword matching.
"""

import re
from typing import Dict, Set, Optional

# AWS SAA-C03 Content Domains
DOMAINS = {
    1: {"name": "Design Secure Architectures", "weight": 0.30},
    2: {"name": "Design Resilient Architectures", "weight": 0.26},
    3: {"name": "Design High-Performing Architectures", "weight": 0.24},
    4: {"name": "Design Cost-Optimized Architectures", "weight": 0.20},
}

# Keywords for each domain (case-insensitive)
DOMAIN_KEYWORDS = {
    1: {
        # Security-related keywords
        "security", "secure", "encrypt", "encryption", "kms", "iam", "policy", "policies",
        "authentication", "authorization", "credentials", "secret", "secrets manager",
        "certificate", "ssl", "tls", "https", "waf", "shield", "firewall", "nacl",
        "security group", "vpc", "private", "public", "vpn", "direct connect",
        "compliance", "audit", "cloudtrail", "guardduty", "inspector", "macie",
        "cognito", "mfa", "multi-factor", "principle of least privilege", "roles",
        "access control", "ddos", "penetration", "vulnerability", "threat",
        "data protection", "network security", "identity", "federation",
        "signing", "signed url", "signed cookie", "presigned", "sts",
    },
    2: {
        # Resilience and availability keywords
        "availability", "resilient", "fault tolerant", "disaster recovery", "backup",
        "multi-az", "multi-region", "cross-region", "failover", "high availability",
        "redundant", "redundancy", "recovery", "rto", "rpo", "durability",
        "replica", "replication", "standby", "active-active", "active-passive",
        "load balancer", "elb", "alb", "nlb", "auto scaling", "elastic load",
        "health check", "route 53", "dns", "failover routing", "latency routing",
        "cloudformation", "elastic beanstalk", "elastic disaster recovery",
        "s3 replication", "rds replica", "aurora replica", "global database",
        "outage", "downtime", "uptime", "sla", "service level",
    },
    3: {
        # Performance keywords
        "performance", "latency", "throughput", "bandwidth", "optimize",
        "cache", "caching", "cloudfront", "cdn", "edge", "accelerate",
        "elasticache", "redis", "memcached", "dax", "dynamodb accelerator",
        "ebs", "iops", "provisioned iops", "gp3", "io2", "throughput optimized",
        "instance type", "compute", "cpu", "memory", "network performance",
        "placement group", "cluster placement", "partition placement",
        "enhanced networking", "ena", "sr-iov", "jumbo frames",
        "lambda", "serverless", "step functions", "sqs", "sns", "kinesis",
        "data transfer", "direct connect", "snowball", "transfer acceleration",
        "read replica", "query performance", "database performance",
        "connection pooling", "parallel", "concurrent", "scalability",
    },
    4: {
        # Cost optimization keywords
        "cost", "pricing", "budget", "savings", "reserved", "spot",
        "cost-effective", "cost-optimized", "cheaper", "reduce cost", "minimize cost",
        "savings plan", "reserved instance", "spot instance", "spot fleet",
        "rightsizing", "instance family", "burstable", "t3", "t4g",
        "s3 lifecycle", "glacier", "deep archive", "intelligent-tiering",
        "storage class", "infrequent access", "one zone", "standard-ia",
        "free tier", "data transfer cost", "egress", "cross-region cost",
        "cloudwatch", "cost explorer", "billing", "aws organizations",
        "consolidated billing", "volume discount", "commitment",
        "serverless", "pay per use", "on-demand", "waste", "unused",
        "idle", "underutilized", "license", "byol", "bring your own license",
    },
}


def classify_question_by_keywords(text: str) -> Dict[int, float]:
    """
    Classify a question into domains based on keyword matching.

    Returns:
        Dict[domain_num, confidence_score] for each domain
    """
    text_lower = text.lower()

    # Count keyword matches for each domain
    domain_scores = {}

    for domain_num, keywords in DOMAIN_KEYWORDS.items():
        score = 0.0
        matched_keywords = set()

        for keyword in keywords:
            # Use word boundaries for better matching
            pattern = r'\b' + re.escape(keyword) + r'\b'
            matches = len(re.findall(pattern, text_lower, re.IGNORECASE))

            if matches > 0:
                matched_keywords.add(keyword)
                # Weight multiple occurrences
                score += 1.0 + (matches - 1) * 0.3

        domain_scores[domain_num] = score

    # Normalize scores
    total_score = sum(domain_scores.values())
    if total_score > 0:
        domain_scores = {k: v / total_score for k, v in domain_scores.items()}

    return domain_scores


def get_primary_domain(text: str, threshold: float = 0.35) -> Optional[int]:
    """
    Get the primary domain for a question.

    Args:
        text: Question text
        threshold: Minimum confidence required (default 0.35)

    Returns:
        Domain number (1-4) or None if no clear domain
    """
    scores = classify_question_by_keywords(text)

    if not scores:
        return None

    # Get domain with highest score
    best_domain = max(scores, key=scores.get)
    best_score = scores[best_domain]

    # Only return if confidence is above threshold
    if best_score >= threshold:
        return best_domain

    return None


def classify_all_questions(questions: Dict[int, any]) -> Dict[int, int]:
    """
    Classify all questions and return mapping.

    Args:
        questions: Dict[qnum, Question]

    Returns:
        Dict[qnum, domain_num] - only includes questions with clear domain
    """
    mapping = {}

    for qnum, question in questions.items():
        domain = get_primary_domain(question.text)
        if domain:
            mapping[qnum] = domain

    return mapping


def get_domain_info(domain_num: int) -> dict:
    """Get name and weight for a domain."""
    return DOMAINS.get(domain_num, {"name": "Unknown", "weight": 0.0})


def print_classification_report(questions: Dict[int, any], mapping: Dict[int, int]):
    """Print a classification report."""
    print("\n" + "=" * 70)
    print("DOMAIN CLASSIFICATION REPORT")
    print("=" * 70)

    # Count by domain
    domain_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for domain_num in mapping.values():
        domain_counts[domain_num] += 1

    total_classified = len(mapping)
    total_questions = len(questions)
    unclassified = total_questions - total_classified

    print(f"\nTotal questions: {total_questions}")
    print(f"Classified: {total_classified} ({total_classified/total_questions*100:.1f}%)")
    print(f"Unclassified: {unclassified} ({unclassified/total_questions*100:.1f}%)")

    print("\n--- Questions by Domain ---")
    for domain_num in sorted(DOMAINS.keys()):
        info = DOMAINS[domain_num]
        count = domain_counts[domain_num]
        expected = info["weight"]
        actual = count / total_classified if total_classified > 0 else 0

        print(f"\nDomain {domain_num}: {info['name']}")
        print(f"  Expected: {expected*100:.0f}%  |  Actual: {count} questions ({actual*100:.1f}%)")

    if unclassified > 0:
        print(f"\n⚠️  {unclassified} questions could not be classified with confidence")
        print("    These will appear in quiz but not in domain statistics")

    print("\n" + "=" * 70)
