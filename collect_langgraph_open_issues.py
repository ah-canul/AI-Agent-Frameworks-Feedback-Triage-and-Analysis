"""Download open issues from langchain-ai/langgraph into a JSON file.

Uses only Python's standard library. It does not need a GitHub token for this
public repository and does not make any changes to GitHub.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


OWNER = "langchain-ai"
REPOSITORY = "langgraph"
API_URL = f"https://api.github.com/repos/{OWNER}/{REPOSITORY}/issues"
ITEMS_PER_PAGE = 100
OUTPUT_FILE = Path(__file__).resolve().parent / "data" / "raw" / "langgraph_open_issues.json"


def download_page(page_number):
    """Ask GitHub for one page of open issues (and possibly pull requests)."""
    query = urlencode(
        {
            "state": "open",
            "per_page": ITEMS_PER_PAGE,
            "page": page_number,
        }
    )
    request = Request(
        f"{API_URL}?{query}",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "langgraph-issue-learning-project",
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code in (403, 429):
            raise RuntimeError(
                "GitHub temporarily limited this request. Wait a while and run "
                "the script again. The script only reads data and makes no "
                "changes to GitHub."
            ) from error
        raise RuntimeError(
            f"GitHub returned HTTP {error.code}. Check the repository name "
            "and your internet connection."
        ) from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError(
            "Could not reach GitHub. Check your internet connection and try again."
        ) from error


def keep_issue_fields(record):
    """Keep the issue information useful for analysis in a readable format."""
    author = record.get("user") or {}
    return {
        "number": record["number"],
        "title": record["title"],
        "url": record["html_url"],
        "state": record["state"],
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "closed_at": record.get("closed_at"),
        "author": author.get("login"),
        "labels": [label["name"] for label in record.get("labels", [])],
        "body": record.get("body") or "",
        "comment_count": record.get("comments", 0),
        "comments_url": record.get("comments_url"),
    }


def main():
    """Download every page, remove pull requests, and save the issue records."""
    api_records = []
    page_number = 1

    while True:
        page = download_page(page_number)
        if not page:
            break

        api_records.extend(page)
        print(f"Received page {page_number}: {len(page)} GitHub records")

        # A short pause keeps requests gentle. The script may request one extra
        # empty page when the final page contains exactly 100 records.
        if len(page) < ITEMS_PER_PAGE:
            break
        page_number += 1
        time.sleep(0.2)

    # GitHub's issues endpoint can include pull requests, so omit records that
    # contain the special "pull_request" field.
    issue_records = [record for record in api_records if "pull_request" not in record]
    issues = [keep_issue_fields(record) for record in issue_records]

    output = {
        "source_repository": f"{OWNER}/{REPOSITORY}",
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "filters": {
            "state": "open",
            "pull_requests_included": False,
        },
        "issue_count": len(issues),
        "issues": issues,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Saved {len(issues)} open issues to: {OUTPUT_FILE}")
    print("Issue descriptions and metadata are included. Comment text is not yet included.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        raise SystemExit(f"Error: {error}") from error
