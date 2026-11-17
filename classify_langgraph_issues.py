    return False, 0


def classify_issue(issue):
    """Attach draft classification fields while preserving the source record."""
    why_category, why_note, comment_signals, comment_conflict, confidence = classify_why(issue)
    contains_multiple, additional_count = count_additional_problems(issue)
    problem_area = (
        "Multiple areas (multi-problem issue)"
        if contains_multiple
        else classify_area(issue)
    )

    needs_review = (
        why_category == "unclear"
        or problem_area == "Other / needs review"
        or contains_multiple
        or comment_conflict
        or matches(r"\[bug/feature\]|\[feature/bug\]", issue.get("title", ""))
    )

    classified = dict(issue)
    classified["classification"] = {
        "why_category": why_category,
        "problem_area": problem_area,
        "subcategory": identify_subcategory(issue),
        "why_note": why_note,
        "confidence": confidence,
        "evidence": {
            "issue_title": issue.get("title", ""),
            "issue_body_excerpt": clean_text(issue.get("body", ""))[:500],
            "comment_signals": comment_signals[:5],
        },
        "contains_multiple_problems": contains_multiple,
        "additional_problem_count": additional_count,
        "excluded_from_human_count": issue.get("number") in EXCLUDED_ISSUE_NUMBERS,
        "needs_review": needs_review,
        "method": "rule_based_issue_and_comment_parser",
    }
    return classified


def main():
    """Read the raw export, classify issues, and save a separate processed file."""
    input_file = find_input_file()
    source = json.loads(input_file.read_text(encoding="utf-8"))
    classified_issues = [classify_issue(issue) for issue in source.get("issues", [])]

    human_issues = [
        issue for issue in classified_issues
        if not issue["classification"]["excluded_from_human_count"]
    ]
    why_counts = Counter(issue["classification"]["why_category"] for issue in human_issues)
    area_counts = Counter(issue["classification"]["problem_area"] for issue in human_issues)

    output = dict(source)
    output["classification_method"] = "rule_based_issue_and_comment_parser"
    output["classification_note"] = (
        "Draft categories use issue titles, cleaned descriptions, and explicit comment wording. "
        "Comment authors are not weighted. GitHub labels and generic bug-report checkboxes do not decide categories. "
        "Questions and guesses in comments are recorded as context, not treated as confirmed causes. "
        "Review the output before treating category totals as final."
    )
    output["classification_summary"] = {
        "issue_records": len(classified_issues),
        "human_issue_records": len(human_issues),
        "excluded_issue_records": len(classified_issues) - len(human_issues),
        "needs_review": sum(issue["classification"]["needs_review"] for issue in human_issues),
        "multi_problem_issues": sum(issue["classification"]["contains_multiple_problems"] for issue in human_issues),
        "additional_problems": sum(issue["classification"]["additional_problem_count"] for issue in human_issues),
        "why_category_counts": dict(why_counts),
        "problem_area_counts": dict(area_counts),
    }
    output["issues"] = classified_issues

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # Save convenient category-specific files. Bot/test records are kept in the
    # master file and a separate exclusion file, not mixed into human buckets.
    BUCKET_DIR.mkdir(parents=True, exist_ok=True)
    for category in (
        "product_defect",
        "setup_configuration",
        "dependency_platform",
        "documentation_gap",
        "feature_request",
        "unclear",
    ):
        bucket = [
            issue for issue in human_issues
            if issue["classification"]["why_category"] == category
        ]
        (BUCKET_DIR / f"{category}.json").write_text(
            json.dumps(bucket, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    review_issues = [
        issue for issue in human_issues if issue["classification"]["needs_review"]
    ]
    REVIEW_FILE.write_text(
        json.dumps(review_issues, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    excluded_issues = [
        issue for issue in classified_issues
        if issue["classification"]["excluded_from_human_count"]
    ]
    EXCLUDED_FILE.write_text(
        json.dumps(excluded_issues, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Classified {len(classified_issues)} GitHub issues.")
    print(f"Human issues: {len(human_issues)}; excluded bot/test records: {len(excluded_issues)}.")
    print("Category counts:")
    for category, count in sorted(why_counts.items()):
        print(f"  {category}: {count}")
    print(f"Needs review: {len(review_issues)} human issues.")
    print(f"Saved the classified copy to: {OUTPUT_FILE}")
    print(f"Saved separate category files to: {BUCKET_DIR}")


if __name__ == "__main__":
