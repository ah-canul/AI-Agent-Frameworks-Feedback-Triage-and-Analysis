# Issue Categorization Framework

## Purpose

This framework groups each GitHub issue by **why the problem happened** and records **where in LangGraph or its surrounding tools the problem occurs**. Issue descriptions and comments are evidence for classification. GitHub labels such as `external` and `internal` remain source metadata and do not determine the category.

The current analysis covers 342 open issue records. Issue #9649 is a bot permission test and is excluded from the human issue count, while remaining in the raw export. The current human issue count is therefore 341.

## Classification fields

Each GitHub issue should have:

- **Why category:** one of the six categories below.
- **Problem area:** the relevant component or workflow, such as graph execution, checkpoint recovery, SQLite storage, or SDK streaming.
- **Subcategory:** the specific behavior involved, such as retry handling, serialization, cache keys, timeout cancellation, installation, or test configuration.
- **Evidence note:** a short explanation tied to the issue description, reproduction steps, or comments.
- **Multiple-problem marker:** whether the GitHub issue describes more than one distinct underlying problem.
- **Additional problem count:** the number of distinct underlying problems beyond the first, when the evidence supports a count.

The GitHub issue remains the main counting unit. Comments, pull requests, and repeated mentions of the same underlying problem are not counted as additional GitHub issues.

## Why categories

### Product defect

Use when LangGraph or one of its components behaves incorrectly during supported use. The issue should provide evidence that actual behavior conflicts with the documented or expected behavior.

Examples include incorrect query results, a stream that stops delivering events, lost state, or a cache returning incorrect results.

### Setup/configuration

Use when the failure is caused by a missing or incorrect setup step, command, setting, environment value, installation, or input. This category can also include a typo or mistake in a build or test configuration file.

Use a subcategory to identify the specific setup issue, such as installation, environment configuration, command usage, or test configuration.

### Dependency/platform

Use when the reported behavior is specifically tied to an operating system, Python or Node version, database driver, or another dependency's compatibility or behavior.

Record the affected platform or dependency in the problem area or subcategory. A platform-specific report still needs evidence connecting the problem to that environment.

### Documentation gap

Use when official instructions, examples, error guidance, or links are missing, incorrect, outdated, or unclear, and that gap contributes to the reported problem.

If documentation omits a required setup step, classify the overall cause as a documentation gap and record the setup step as the problem area or subcategory.

### Feature request

Use when the reporter asks for new behavior or an additional option, and the issue does not show that existing documented behavior is malfunctioning.

### Unclear

Use temporarily when the issue description, reproduction steps, and comments do not provide enough evidence to choose another category. Revisit this label if later comments or investigation clarify the cause.

## Problem areas

Problem areas describe **where** the issue occurs. They can be refined into more specific subcategories as recurring patterns appear.

- **Graph execution and control flow:** routing, parallel work, interrupts, retries, cancellation, and node scheduling.
- **State, checkpoints, and recovery:** saving and restoring state, serialization, resuming, time travel, and durability.
- **Stores, search, and caching:** SQLite, Postgres, Redis, in-memory stores, filters, indexes, vector search, cache keys, and TTL behavior.
- **SDK, API, server, and streaming:** client/server requests, authentication, HTTP, SSE, WebSockets, run/thread endpoints, and event delivery.
- **Tools, messages, and integrations:** ToolNode, MCP, tool results, message formats, schemas, and connected libraries or services.
- **Developer tooling and compatibility:** CLI, deployment configuration, builds, tests, CI, packaging, type hints, dependencies, and platform-specific tooling.
- **Performance and resource handling:** latency, CPU use, memory growth, blocking, and cleanup of tasks, streams, or connections.
- **Documentation and examples:** guides, quickstarts, API references, examples, error explanations, and links.

## Choosing between similar categories

Classify from the evidence, rather than from the issue title or a GitHub label alone.

- A broken SDK stream during valid use is a **Product defect** in the **SDK/streaming** area.
- A missing server URL in the user's configuration is **Setup/configuration** in the **SDK connection** area.
- A quickstart that fails to mention the required server URL is a **Documentation gap** in the **SDK documentation** area.
- A failure limited to a specific OS, runtime version, or driver may be **Dependency/platform** if the issue evidence supports that connection.
- A request for a new option, without evidence of broken existing behavior, is a **Feature request**.

## Multiple-problem issues and exclusions

An issue that summarizes several distinct bugs is counted as **one GitHub issue**. Mark it as containing multiple problems and record the supported additional problem count. If the underlying problems have different causes or problem areas, preserve those details rather than forcing them into one narrow subcategory.

For example, issue #9655 describes 14 distinct bug reports. It is counted as one GitHub issue with `contains_multiple_problems = true` and `additional_problem_count = 13`.

Issue #9649 is authored by a bot and is a permission test. Keep it in the raw data, mark it excluded from the human issue analysis, and do not include it in the human issue denominator.

## Illustrative classifications

These examples show how the fields work. They are starting classifications and can be revised during issue-by-issue review.

| Issue | Why category | Problem area / subcategory |
|---|---|---|
| #9607 | Product defect | Stores and search / SQLite numeric filter results |
| #9660 | Setup/configuration | Developer tooling / test selection configuration |
| #7814 | Dependency/platform | Developer tooling / Windows compatibility during dependency installation |
| #9577 | Documentation gap | SDK documentation / quickstart setup instructions |
| #6798 | Feature request | Streaming / configurable state keys |

