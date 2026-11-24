"""Sort the collected LangGraph issues into a first-pass category set.

This version uses visible text rules, so it needs no extra package or API key.
Treat its output as a draft: issues marked for review need a human check.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
INPUT_CANDIDATES = [
    PROJECT_DIR / "data" / "raw" / "langgraph_open_issues_with_comments.json",
    PROJECT_DIR / "upload" / "langgraph_open_issues_with_comments.json",
]
OUTPUT_FILE = (
    PROJECT_DIR / "data" / "processed" / "langgraph_open_issues_classified.json"
)
BUCKET_DIR = OUTPUT_FILE.parent / "by_category"
REVIEW_FILE = OUTPUT_FILE.parent / "needs_review.json"
EXCLUDED_FILE = OUTPUT_FILE.parent / "excluded_from_human_analysis.json"

# This bot permission check stays in the output but is left out of human totals.
EXCLUSIONS = {("langchain-ai/langgraph", 9649): "Bot permission probe, not human feedback."}


def find_input_file():
    """Find the downloaded comment export in the usual project locations."""
    for candidate in INPUT_CANDIDATES:
        if candidate.exists():
            return candidate
    expected = INPUT_CANDIDATES[0]
    raise SystemExit(
        "Could not find the comment export. Make sure it is saved at: "
        f"{expected}"
    )


def matches(pattern, text):
    """Return True when a regular-expression pattern is present in the text."""
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def clean_text(value):
    """Remove template checkboxes and code blocks before matching category words."""
    text = value or ""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    kept_lines = []
    for line in text.splitlines():
        if re.match(r"^\s*(?:[-*]\s*)?\[[ xX]\]\s*", line):
            continue
        if matches(r"this is a bug, not a usage question|i am sure that this is a bug", line):
            continue
        kept_lines.append(line)
    return " ".join(" ".join(kept_lines).split())


QUESTION_OR_GUESS = (
    r"\b(?:could this|could it|could be|might this|might it|might be|maybe|perhaps|possibly|"
    r"i wonder if|is it possible|anyone know|any ideas|how do i|what should i|"
    r"does anyone know|i think|i suspect|seems like|probably)\b"
)
# Each rule needs a specific statement, not a GitHub label or a template checkbox.
WHY_RULES = [
    ('documentation_gap', 'documentation_incorrect_or_incomplete',
     r'\b(?:docs?|documentation|readme|quickstart|guide|docstring|api reference|import path)\b.{0,100}\b(?:omit(?:s|ted)?|missing|incorrect|wrong|outdated|broken|dead|unclear|incomplete|does not (?:mention|work)|doesn.t (?:mention|work))\b|\b(?:missing|incorrect|wrong|outdated|broken|dead|incomplete)\b.{0,70}\b(?:docs?|documentation|readme|quickstart|guide|docstring|api reference|import path)\b|\b(?:broken|dead)\s+(?:documentation\s+)?link\b'),
    ('documentation_gap', 'explicit_documentation_error',
     r'\b(?:dead|broken|stale|outdated)\b.{0,70}\b(?:redirect|docstring|documentation|docs?|guide|quickstart)\b|\b(?:documentation|docs?|api.contract)\s+clarification\b|\b(?:readme|quickstart|documentation)\b.{0,50}\bexample\b.{0,45}\b(?:returns?|produces?|restores?)\b.{0,30}\b(?:empty|wrong|incorrect)\b|\bdocstring\b.{0,60}\b(?:no longer|does not match|outdated|incorrect)\b'),
    ('documentation_gap', 'documented_guidance_omission',
     r'\b(?:docstrings?|documentation|docs?|quickstart|readme)\b.{0,60}\b(?:describes? only|omit(?:s|ted)?|does not mention|do not mention)\b'),
    ('setup_configuration', 'user_setup_cause',
     r'\b(?:my|our|user.s?|the user.s?)\b.{0,55}\b(?:wrong|incorrect|invalid|missing|misconfigured|misspelled)\b.{0,55}\b(?:setting|config\w*|value|command|input|environment|variable|installation|store|router)\b|\b(?:wrong|incorrect|invalid|misconfigured|misspelled|typo in)\b.{0,40}\b(?:setting|config\w*|value|command|input|environment variable)\b|\bmissing\s+(?:a\s+|the\s+)?(?:setting|configuration|config|environment variable)\b|\b(?:store (?:was|is) not provided|router returned an unmapped value|forgot to install|i (?:had|used) (?:the )?wrong|i misspelled|i misconfigured)\b'),
    ('setup_configuration', 'malformed_configuration',
     r'\b(?:malformed|invalid|non-string)\b.{0,90}\b(?:config\w*|(?:python|node)_version|auth|checkpointer)\b|\b(?:config\w*|langgraph\.json)\b.{0,90}\b(?:malformed|invalid|non-string)\b'),
    ('setup_configuration', 'input_violates_declared_schema',
     r"\b(?:router|routing function)\b.{0,100}\breturns?\b.{0,80}\b(?:isn.t|is not)\s+(?:a\s+)?key of\b|\bkey\b.{0,30}\b(?:wasn.t|was not|isn.t|is not)\s+declared\b.{0,50}\bschema\b|\binvalid\s+(?:state|input)\b.{0,60}\bviolat\w*\b.{0,30}\bschema\b"),
    ('setup_configuration', 'test_configuration_cause',
     r'\b(?:makefile|make test|test configuration|test selection|no_docker)\b.{0,120}\b(?:instead of|misconfigur\w*|typo|wrong|incorrect|skips?|selects? the (?:wrong|no-docker))\b|\b(?:wrong|incorrect|typo|misconfigur\w*)\b.{0,70}\b(?:makefile|test configuration|test selection)\b'),
    ('dependency_platform', 'specific_compatibility_link',
     r'\b(?:fail\w*|break\w*|crash\w*|not work\w*)\b.{0,60}\bonly (?:on|with)\s+(?:windows|macos|linux|python\s*3\.\d+|node\s*\d+|psycopg\s*\d+|pydantic\s*v?\d+)\b|\b(?:windows|macos|linux|python\s*3\.\d+|node\s*\d+|psycopg\s*\d+|pydantic\s*v?\d+)\b.{0,80}\b(?:incompatib\w*|unsupported|not support\w*|does not support|doesn.t support|fails? only|removed in|deprecated)\b|\b(?:deprecated|removed)\b.{0,50}\b(?:in|on|as of)\s+python\s*3\.\d+\b|\bdeclared\s+(?:minimum|floor|pydantic floor)\b.{0,70}\b(?:fail\w*|does not work|doesn.t work)\b|\bfails?\b.{0,70}\bdeclared\s+(?:minimum|pydantic floor)\b'),
    ('dependency_platform', 'platform_or_driver_specific_behavior',
     r'\b(?:windows|linux|macos)\b.{0,50}\b(?:refuses? (?:that |the )?deletion|unicodeencodeerror|unicodedecodeerror|cp1252|line endings|locale encoding)\b|\b(?:unicodeencodeerror|unicodedecodeerror)\b.{0,40}\bon\s+(?:windows|linux|macos)\b|\bbreaks?\s+(?:non.stdlib|third.party)\s+drivers?\b|\bdoes not work with an? (?:asynchronous|async) \w+ client\b|\bdoes not declare .{0,50}\b(?:dependency|dependencies)\b'),
    ('dependency_platform', 'locale_dependent_decoding',
     r'\b(?:decoding|encoding)\b.{0,40}\bdepends on\b.{0,35}\blocale\b.{0,70}\b(?:corrupt\w*|reject\w*|fail\w*|error)\b'),
    ('dependency_platform', 'locale_specific_read_failure',
     r'\b(?:windows|linux|macos)\b.{0,70}\blocale\b.{0,100}\b(?:read|decod\w*)\b.{0,35}\bfails?\b'),
    ('dependency_platform', 'explicit_version_compatibility',
     r'\b(?:guard|support|compatibil\w*)\b.{0,60}\bon\s+python\s*[<>]=?\s*\d+\.\d+\b|'
     r'\bbreaks? with older versions of\b'),
    ('dependency_platform', 'released_dependency_version_too_old',
     r'\blatest\b.{0,30}\brelease\b.{0,100}\bnot new enough\b.{0,50}\bfails?\b'),
    ('feature_request', 'new_capability_request',
     r'\b(?:feature request|suggest\s*:\s*\w+|please add|add support for|provide a way to|(?:there is )?no way to|does not provide a documented way to|there is no configuration\b.{0,60}\bto change|it would be (?:nice|useful) to|it.d be great to|would (?:like|love) to|allow (?:configur\w*|specif\w*|setting|using|select\w*|binding|\w+ to)|allow .{0,55}\b(?:to be|to update)\b|expose .{0,60}\b(?:option|parameter|api|way)\b|support (?:custom|additional|new)|improve .{0,70}\bby (?:adding|including|providing)\b|refactor\s*:\s*replace|add (?:a )?(?:tests.only )?regression|add .{0,35}build to ci|enforce .{0,40} across the repo)\b'),
    ('product_defect', 'observable_unexpected_behavior',
     r'\b(?:returns? .{1,65} instead of|returns? (?:the )?(?:wrong|incorrect|unexpected|empty|duplicate|adjacent)\b|returns? (?:an? )?adjacent\b|wrong (?:result|output|value)|incorrect (?:result|output|behavior)|data loss|loses? (?:data|state)|drops? (?:events?|messages?|data|state)|does not (?:persist|save|preserve|deliver)|doesn.t (?:persist|save|preserve|deliver)|hangs?|deadlocks?|applies? twice|requests? \d+ \w+ when .{1,45}(?:is|equals?) 0|limit\s*=\s*0.{0,40}requests?\s+\d+|(?:parallel|concurrent)\b.{0,100}\bfail\w*\b.{0,30}\b(?:runtimeerror|exception)\b|(?:remains?|stay(?:s)?) retained after close|(?:re-?runs?|re-?scans?) .{0,60}(?:again|every|duplicate)|(?:skips?|ignores?) .{0,70}(?:test|event|message|setting)|(?:actual|observed) behavior\s*: .{3,}|(?:expected|actual) (?:result|output)\s*: .{3,})\b'),
    ('product_defect', 'result_exceeds_requested_limit',
     r'\breturn\w*\b.{0,60}\bwhen\b.{0,50}\b(?:asked|requested) for none\b'),
    ('product_defect', 'duplicate_application',
     r'\b(?:appl(?:y|ies|ied)|execut(?:e|es|ed)|run(?:s)?|deliver(?:s|ed)?)\b.{0,55}\btwice\b|'
     r'\b(?:applied|executed|delivered)\s+twice\b'),
    ('product_defect', 'reported_data_loss',
     r'\b(?:data|values?|state|events?|messages?|checkpoints?|writes?)\b.{0,55}\b(?:is|are|was|were)\s+(?:silently\s+)?(?:lost|dropped|corrupted)\b|'
     r'\b(?:silently\s+)?(?:loses?|drops?|corrupts?)\s+(?:the\s+)?(?:data|values?|state|events?|messages?|checkpoints?|writes?)\b'),
    ('product_defect', 'reported_incorrect_attribute',
     r'\b(?:asserted|returned|reported|stored|emitted)\s+(?:values?|attributes?|annotations?)\s+(?:are|is)\s+(?:wrong|incorrect)\b'),
    ('product_defect', 'reported_operation_exception',
     r'\b(?:causes?|raises?|throws?)\s+(?:an?\s+)?[A-Za-z]+(?:Error|Exception)\b'),
    ('product_defect', 'missing_parent_event_metadata',
     r'\bevents?\b.{0,80}\b(?:do not|don.t) include metadata\b.{0,60}\bparent\b'),
]

AREA_RULES = [
    ('Tools, messages, and integrations', 'tool handling and integrations', r'toolnode|tool ?call|toolmessage|\bmcp\b'),
    ('SDK, API, server, and streaming', 'streaming and event delivery', r'\bstream\w*|\bsse\b|websocket|astream_events'),
    ('State, checkpoints, and recovery', 'checkpoint and recovery behavior', r'checkpoint\w*|durability|resum\w*|serializ\w*|time travel'),
    ('Stores, search, and caching', 'cache behavior', r'\bcach\w*|\bttl\b'),
    ('Stores, search, and caching', 'database or store behavior', r'\bsqlite\b|\bpostgres\w*|\bredis\b|\bvector search\b|\bstore\b'),
    ('Graph execution and control flow', 'retry behavior', r'\bretr\w*|retrypolicy'),
    ('Graph execution and control flow', 'interrupt handling', r'\binterrupt\w*'),
    ('Graph execution and control flow', 'routing and execution', r'\bpregel\b|routing|conditional edge|\bsubgraph\w*'),
    ('Performance and resource handling', 'memory and resource cleanup', r'memory leak|retained after close|resource cleanup'),
    ('Developer tooling and compatibility', 'test/build configuration', r'makefile|make test|no_docker|test (?:target|matrix|fixture|selection)|\bci\b'),
    ('Developer tooling and compatibility', 'Python type information', r'py\.typed|\btyping\b|type checker'),
    ('Developer tooling and compatibility', 'platform or dependency compatibility', r'\bwindows\b|\bmacos\b|\blinux\b|python\s*3\.\d+|\bpsycopg\b|\bpydantic\b'),
    ('Documentation and examples', 'documentation and examples', r'\bdocs?\b|documentation|readme|quickstart|docstring|dead link'),
    ('SDK, API, server, and streaming', 'API or server behavior', r'\bsdk\b|\bapi\b|\bclient\b|\bserver\b|\bhttp\b|endpoint'),
]
# Question wording matters even when the author omitted a question mark.
UNCERTAIN = re.compile(QUESTION_OR_GUESS + r'|\b(?:is this|is it|is the issue|is the problem|was it|was this|was the issue|could|would|might|may be|wonder|do you think|what if|not sure|unsure)\b|\?', re.I)
CAUSE = re.compile(r'\b(?:the (?:root )?cause (?:was|is)|(?:this|it|the issue|the problem) (?:was|is) (?:caused by|due to|because of)|(?:i|we) (?:had|used|configured) (?:the )?(?:wrong|incorrect|missing)|(?:i|we) (?:misspelled|misconfigured)|(?:fixed|resolved) by)\b', re.I)


def sentences(value):
    """Yield readable report text, skipping generic template and environment metadata."""
    section = ''
    in_fence = False
    fence_language = ''
    for line in (value or '').splitlines():
        stripped = line.strip()
        heading = re.match(r'^#{1,6}\s+(.+)', stripped)
        if heading:
            section = heading.group(1).strip().lower()
            continue
        if stripped.startswith('```'):
            if not in_fence:
                fence_language = stripped[3:].strip().lower()
            in_fence = not in_fence
            continue
        if in_fence and fence_language not in ('text', 'output', 'console'):
            continue
        if re.search(r'\b(system info(?:rmation)?|environment info(?:rmation)?|package info(?:rmation)?|checked other resources|related issues|privileged issue)\b', section):
            continue
        if re.match(r'^\s*(?:[-*]\s*)?\[[ xX]\]', line):
            continue
        if re.search(r'optional packages not installed|this is (?:a reproducible )?bug, not a usage question|i am sure that this is a bug', line, re.I):
            continue
        for part in re.split(r'(?<=[.!?])\s+', line):
            if part.strip():
                yield part.strip()


def rule_matches(text, source, url=None):
    found = []
    lines = list(sentences(text))
    proposal_lines = set()
    in_proposal = False
    if source == 'body':
        for raw_line in (text or '').splitlines():
            header = re.match(r'^\s*#{1,6}\s+(.+)', raw_line)
            if header:
                in_proposal = bool(re.search(r'^(?:ask|propos\w*|suggested (?:fix|solution)|workaround)', header.group(1), re.I))
                continue
            if in_proposal:
                proposal_lines.update(sentences(raw_line))
    # Reports sometimes wrap a single sentence across lines. Rejoin only a
    # fragment ending in a connective; do not join complete sentences.
    usable_lines = set(lines)
    wrapped = []
    previous = None
    in_fence = False
    for raw_line in (text or '').splitlines():
        line = raw_line.strip()
        if line.startswith('```'):
            in_fence = not in_fence
            previous = None
            continue
        if in_fence or not line or line not in usable_lines or line.startswith('#'):
            previous = None
            continue
        if (previous and len(previous) + len(line) <= 500 and
                re.search(r'\b(?:that|when|whose|which|with|the|a|an|of|and|or|to|by|on|in|from|is|as)\s*$', previous, re.I)):
            wrapped.append(previous + ' ' + line)
        previous = line
    for sentence in lines + wrapped:
        if (UNCERTAIN.search(sentence) and not
                (source != 'comment' and re.search(r'\bwould (?:like|love) to\b', sentence, re.I)
                 and not re.search(r'\?|\b(?:could|maybe|might)\b|\bperhaps\b.{0,100}\bwould (?:like|love) to\b', sentence, re.I))):
            continue
        for category, rule, pattern in WHY_RULES:
            if category == 'product_defect' and source == 'body' and any(part in sentence for part in proposal_lines):
                continue
            if category == 'documentation_gap' and re.search(r'\b(?:missing-issue-link|re-link|issue-link)\b', sentence, re.I):
                continue
            if (category == 'setup_configuration' and re.search(
                    r'\b(?:validator|validation)\b.{0,50}\b(?:rejects?|detects?)\b', sentence, re.I)):
                # A validator rejecting bad input describes its behavior,
                # not necessarily the cause of the reported issue.
                continue
            if category == 'setup_configuration' and re.search(
                    r'\b(?:result|output|returned)\b.{0,50}\bwrong value\b|\binvalid value\b.{0,50}\bshould\b.{0,30}\breject', sentence, re.I):
                continue
            if (category == 'feature_request' and source != 'title' and
                    re.search(r'\b(?:contribut\w*|assigned|assignment|submit (?:the |a )?\w* ?fix|open (?:a |the )?(?:pr|pull request)|regression tests?)\b', sentence, re.I)):
                continue
            match = re.search(pattern, sentence, re.I)
            if not match:
                continue
            prefix = sentence[max(0, match.start()-35):match.start()]
            if re.search(r'\b(?:not|no|never|without|if|whether)\s+(?:\w+\s+){0,2}$', prefix, re.I):
                continue
            excerpt = sentence[max(0, match.start() - 150):match.end() + 150]
            found.append({'category': category, 'rule': rule, 'source': source,
                          'excerpt': excerpt, 'matched_text': match.group(), 'url': url})
    return found


def reproduction_evidence(body):
    """Capture explicit result comparisons and compatibility errors in output."""
    found = []
    compatibility = re.compile(
        r'\b[\w.-]+\s+does not support\s+(?:windows|macos|linux|python\s*3\.\d+)\b', re.I
    )
    in_system_info = False
    for line in (body or '').splitlines():
        heading = re.match(r'^\s*#{1,6}\s+(.+)', line)
        if heading:
            in_system_info = bool(re.search(r'system info|environment info|package info', heading.group(1), re.I))
        match = compatibility.search(line)
        if not in_system_info and match and not UNCERTAIN.search(line):
            found.append({'category': 'dependency_platform', 'rule': 'explicit_compatibility_error',
                          'source': 'body', 'excerpt': line.strip()[:500],
                          'matched_text': match.group(), 'url': None})
    # Use both sections together; neither section alone proves a mismatch.
    sections = {}
    section = None
    for line in (body or '').splitlines():
        header = re.match(r'^\s*#{1,6}\s*(?:(expected|actual|observed)\s+(?:behavior|result|output)|(what happens))\s*:?.*$', line, re.I)
        if header:
            section = 'expected' if (header.group(1) or '').lower() == 'expected' else 'actual'
            sections.setdefault(section, [])
            continue
        if re.match(r'^\s*#{1,6}\s+', line):
            section = None
        elif section and line.strip() and not line.strip().startswith('```'):
            sections[section].append(line.strip())
    if sections.get('expected') and sections.get('actual'):
        expected, actual = ' '.join(sections['expected'])[:300], ' '.join(sections['actual'])[:300]
        if not UNCERTAIN.search(expected + ' ' + actual):
            found.append({'category': 'product_defect', 'rule': 'reported_expected_actual_comparison',
                          'source': 'body', 'excerpt': f'Expected: {expected} | Actual: {actual}',
                          'matched_text': None, 'url': None})
    lines = list(sentences(body))
    exception = next((line for line in lines if re.search(r'\braises?\s+`?[A-Za-z]+(?:Error|Exception)\b', line, re.I)), None)
    expected = next((line for line in lines if re.search(r'\b(?:i|we) expected\b', line, re.I) and not UNCERTAIN.search(line)), None)
    if exception and expected:
        found.append({'category': 'product_defect', 'rule': 'reported_exception_and_expected_behavior',
                      'source': 'body', 'excerpt': exception[:250] + ' | ' + expected[:250],
                      'matched_text': None, 'url': None})
    expected_line = next((line for line in lines if not UNCERTAIN.search(line) and re.search(
        r'\b(?:i expect(?:ed)?|we expect(?:ed)?|expected(?: behavior| result)?|'
        r'expected behavior|expected result|documented (?:as|to)|'
        r'(?:docstring|documentation)\b.{0,100}\bwithout (?:type|value) restrictions|'
        r'should (?:return|produce|save|preserve|send|work|run|be|pause|accept|reject|catch|stop|create|emit|unblock|validate|match|prevent|appear|remain|retain|distinguish|include|proceed|continue))\b', line, re.I)), None)
    if expected_line and re.fullmatch(r'\s*\**expected(?: behavior| result| output)?\**\s*:?\s*', expected_line, re.I):
        position = lines.index(expected_line)
        expected_line = lines[position + 1] if position + 1 < len(lines) else None
    actual_line = next((line for line in lines if not UNCERTAIN.search(line) and re.search(
        r'\b(?:instead|actual(?:ly)?|but .{0,60}(?:fails?|raises?|returns?|does not|doesn.t|never)|'
        r'however\b.{0,100}\b(?:fails?|crashes?|does not|doesn.t)\b|'
        r'but\b.{0,90}\b(?:only one|only the|silently lost|no longer|does not|doesn.t)\b|'
        r'(?:restores?|decodes?|loads?)\b.{0,65}\b(?:wrong|incorrect) (?:shape|type|value)|'
        r'rather than\s+(?:being|returning|producing|showing|preserving)\b|'
        r'raises?\s+`?[\w.]+(?:Error|Exception)|returns?\s+no\s+results?|does not (?:return|save|preserve|work)|'
        r'doesn.t (?:return|save|preserve|work)|(?:wrong|incorrect) (?:result|output|value))\b', line, re.I)), None)
    if expected_line and actual_line:
        found.append({'category': 'product_defect', 'rule': 'reported_expected_and_observed',
                      'source': 'body', 'excerpt': expected_line[:220] + ' | ' + actual_line[:220],
                      'matched_text': None, 'url': None})
    # An explicit Expected: statement can be paired with a concrete observed
    # result even when the reporter did not add a separate Actual: section.
    expected_label = next((line for line in lines if re.match(r'^\s*\**expected\**\s*:\s*\S.{8,}', line, re.I)), None)
    observed_result = next((line for line in lines if not UNCERTAIN.search(line)
                            and not re.search(r'\b(?:expected|should|propos\w*|suggest\w*)\b', line, re.I)
                            and re.search(r'\b(?:returns|prints|reports|produces)\b.{2,100}', line, re.I)
                            and re.search(r'\b(?:wrong|incorrect|unexpected|empty|only|also|silently|vacuously|duplicate\w*|stale|missing)\b', line, re.I)), None)
    if expected_label and observed_result:
        found.append({'category': 'product_defect', 'rule': 'explicit_expected_and_reported_result',
                      'source': 'body', 'excerpt': expected_label[:220] + ' | ' + observed_result[:220],
                      'matched_text': None, 'url': None})
    expected_output = re.search(
        r'^\s*(?:\*\*)?expected(?:\*\*)?\s*:\s*\r?\n\s*```(?:text|output|console)?\s*\r?\n([^\r\n`]{1,200})',
        body or '', re.I | re.M)
    incorrect_result = next((line for line in lines if not UNCERTAIN.search(line) and re.search(
        r'\b(?:result|output|ranking|order)\s+(?:is|was)\s+(?:incorrect|wrong|unexpected)\b', line, re.I)), None)
    if expected_output and incorrect_result:
        found.append({'category': 'product_defect', 'rule': 'incorrect_result_with_expected_output',
                      'source': 'body', 'excerpt': incorrect_result[:220] + ' | Expected: ' + expected_output.group(1),
                      'matched_text': None, 'url': None})
    return found


def corroborated_symptom(title, body):
    """Require a concrete symptom plus supporting report text, not a bug label."""
    symptom = re.search(
        r'\b(?:raises?\s+`?[\w.]+(?:Error|Exception)\b|'
        r'[A-Za-z]+(?:Error|Exception)\b|'
        r'serialization\s+(?:failure|error)\b|'
        r'returns?\b.{1,80}\binstead of\b|'
        r'(?:reports?|returns?)\b.{0,70}\b(?:never written|not requested|unrelated)\b|'
        r'returns?\b.{0,60}\b(?:each other.s|another user.s|another graph.s)\s+results?\b|'
        r'(?:type signature|type hints?|annotations?|invoke type)\b.{0,65}\b(?:incompatib\w*|unknown|reject\w*|error)\b|'
        r'returns?\b.{0,50}\b(?:farthest|nan|duplicate\w*|incorrect|wrong)\b|'
        r'replays?\s+(?:a\s+)?stale\b|'
        r'expires?\b.{1,55}\b(?:at once|immediately|too early)\b|'
        r'(?:is|are|gets?) ignored|ignores?\b.{1,80}|'
        r'(?:never|does not|doesn.t|do not|don.t|fails? to|cannot|can.t)\s+(?:apply|refresh|persist|save|return|deliver|stop|work|run|update|load|restore|unblock|catch|accept|emit|match|read|resolve|create|validate|terminate|recognize|backfill|reuse|disable|use)\w*|'
        r'\bnot\s+(?:work\w*|resum\w*|handled)\b|'
        r'\bstops?\s+(?:receiving|sending|returning|saving|streaming)\b|'
        r'\bcan\s+keep\s+(?:commands?|process(?:es)?)\b.{0,40}\balive\b|'
        r'\bworks?\s+unexpected(?:ly)?\b|'
        r'\b(?:missed|missing|misplaced)\s+(?:events?|interrupts?|messages?|values?|states?|outputs?|traces?)\b|'
        r'\b(?:events?|interrupts?|messages?|values?|state|outputs?|traces?)\s+(?:are\s+|is\s+)?(?:missing|misplaced|lost|duplicated)\b|'
        r'(?:cancels?|duplicates?|corrupts?|leaks?|drops?|deadlocks?|re-?runs?|re-?scans?|'
        r'crash(?:es|ed)?|fails?|raises?|throws?|overwrites?|rewrites?|corrupting|discards?|blocks?|skips?|misses?|rejects?|empties?|loses?|'
        r'resets?|clears?|renames?|expires?|re-deliver(?:s|ed)?|omits?|downcasts?|collides?|replaces?)\b.{0,70}|'
        r'los(?:e|es)\s+(?:their|its|the)\s+(?:type|value|data|state)\b|'
        r'(?:defined|declared)\s+twice\b.{0,80}\b(?:never|ignored|overwritten)\b|'
        r'chang\w*\s+(?:already[ -])?(?:saved|persisted|stored)\s+(?:data|state|values?|checkpoints?)\b|'
        r'(?:silently\s+)?re.execut(?:ed|es?)\b|'
        r'(?:wrong|stale|missing|duplicated|unhandled)\s+(?:results?|values?|state|events?|messages?|errors?|exceptions?|data|vectors?)\b|'
        r'reports?\s+(?:the\s+)?wrong\b.{1,50}|'
        r'(?:partial(?:ly)? persist\w*|restored as (?:a )?(?:list|dict|tuple)|comes back .{0,25} as a dict))',
        title, re.I)
    if not symptom or UNCERTAIN.search(title):
        return []
    report_lines = list(sentences(body))
    exception_name = re.fullmatch(r'[A-Za-z]+(?:Error|Exception)', symptom.group(), re.I)
    if exception_name:
        # Prefer a line that names the same exception. A preceding "raises"
        # or "fails" line can also introduce an exception shown in output.
        corroboration = next((line for line in report_lines if not UNCERTAIN.search(line)
                              and re.search(r'\b' + re.escape(symptom.group()) + r'\b', line, re.I)), None)
        if not corroboration and re.search(r'\b' + re.escape(symptom.group()) + r'\b', body, re.I):
            corroboration = next((line for line in report_lines if not UNCERTAIN.search(line)
                                  and re.search(r'\b(?:raises?|fails?|crashes?|traceback)\b', line, re.I)), None)
    else:
        corroboration = next((line for line in report_lines
                              if not UNCERTAIN.search(line) and re.search(
                                  r'\b(?:expected|instead|actual|reproduc\w*|should|documented|'
                                  r'wrong|incorrect|exception|error|ignored|duplicate|fails?|'
                                  r're-run\w*|cancel\w*|raises?|returns?|missing|lost|overwritten|'
                                  r'preserv\w*|incompatible|no longer|expires?|expiry|farthest|stale|'
                                  r'cannot disable|not applied|does not work|doesn.t run|type checkers?|type system|invariant|excludes?|'
                                  r'receiv\w*.{0,60}\bresults?)\b', line, re.I)), None)
        if not corroboration:
            # An explicit observation can be separated from a surrounding
            # speculative clause; the speculation itself is not evidence.
            observed = next((re.search(r'\b(?:did in fact hit|observed this) in production\b', line, re.I)
                             for line in report_lines
                             if re.search(r'\b(?:did in fact hit|observed this) in production\b', line, re.I)), None)
            corroboration = observed.group() if observed else None
    if not corroboration:
        return []
    return [{'category': 'product_defect', 'rule': 'corroborated_concrete_symptom',
             'source': 'title_and_body', 'excerpt': f'{title[:200]} | {corroboration[:250]}',
             'matched_text': symptom.group(), 'url': None}]


def test_tooling_evidence(title, body):
    """Recognize a defect in a test command or test setup, not tests of product code."""
    match = re.search(
        r'\b(?:make test|makefile|test matrix|test fixture|test target|'
        r'test\w*.{0,65}\bassertion|test\s*:\s*unskip|tests?\s+(?:flush|delete)\b.{0,45}\bunrelated|'
        r'test\s*:.{0,120}\bfails? only in the full suite)\b', title, re.I)
    if not match or UNCERTAIN.search(title):
        return []
    support = next((line for line in sentences(body) if re.search(
        r'\b(?:makefile|pytest|test fixture|test target|test suite|test matrix|'
        r'test command|assertion|test.*(?:skipped|failed|fails))\b', line, re.I)), None)
    if not support:
        return []
    return [{'category': 'setup_configuration', 'rule': 'test_tooling_configuration',
             'source': 'title_and_body', 'excerpt': title[:200] + ' | ' + support[:250],
             'matched_text': match.group(), 'url': None}]


def proposed_design_evidence(title, body):
    """Recognize a proposed design change, with both title and body support."""
    if not re.search(r'\b(?:make|refactor|redesign)\b', title, re.I):
        return []
    line = next((line for line in sentences(body)
                 if re.search(r'\b(?:changes?|redesign|refactor)\b.{0,70}\bwould\s+(?:remove|avoid|simplify|improve)\b', line, re.I)
                 and not re.search(r'\?|\b(?:maybe|perhaps|might|could)\b', line, re.I)), None)
    if not line:
        return []
    return [{'category': 'feature_request', 'rule': 'proposed_design_change',
             'source': 'title_and_body', 'excerpt': title[:200] + ' | ' + line[:250],
             'matched_text': None, 'url': None}]


def platform_output_evidence(title, body):
    """Link platform-specific file output to a described compatibility mechanism."""
    if not re.search(r'\bwindows\b', title, re.I):
        return []
    lines = list(sentences(body))
    patterns = []
    if re.search(r'\bline endings?\b', title, re.I):
        patterns.append(r'\btext mode\b.{0,100}\b(?:turns?|converts?)\b.{0,80}\bagain\b')
    if re.search(r'\bpaths?\b', title, re.I):
        patterns.append(r'\b(?:dockerfile|container)\b.{0,90}\bmix\b.{0,80}\b(?:posix|windows)\b')
    for pattern in patterns:
        line = next((line for line in lines if not UNCERTAIN.search(line) and re.search(pattern, line, re.I)), None)
        if line:
            return [{'category': 'dependency_platform', 'rule': 'platform_output_compatibility',
                     'source': 'title_and_body', 'excerpt': title[:200] + ' | ' + line[:250],
                     'matched_text': None, 'url': None}]
    return []


def repeated_unused_work_evidence(title, body):
    """Identify repeated unused work when the report describes its cost."""
    if not re.search(r'\bunused\b.{0,70}\bevery\b', title, re.I):
        return []
    line = next((line for line in sentences(body)
                 if not UNCERTAIN.search(line) and
                 re.search(r'\b(?:gets? slower|increases? latency|performance degrades?)\b', line, re.I)), None)
    if not line:
        return []
    return [{'category': 'product_defect', 'rule': 'repeated_unused_work',
             'source': 'title_and_body', 'excerpt': title[:200] + ' | ' + line[:250],
             'matched_text': None, 'url': None}]


def type_checker_discrepancy(title, body):
    """Compare a reported type-check failure with working runtime behavior."""
    if not re.search(r'\b(?:type checkers?|type checking|type hints?)\b', title, re.I):
        return []
    lines = [line for line in sentences(body) if not UNCERTAIN.search(line)]
    failure = next((line for line in lines if re.search(r'\b(?:fails?|incompatible|type error)\b', line, re.I)), None)
    runtime = next((line for line in lines if re.search(r'\b(?:run|runs|works?)\s+(?:fine|correctly)\b', line, re.I)), None)
    if not failure or not runtime:
        return []
    return [{'category': 'product_defect', 'rule': 'type_checker_runtime_discrepancy',
             'source': 'title_and_body', 'excerpt': title[:150] + ' | ' + failure[:150] + ' | ' + runtime[:150],
             'matched_text': None, 'url': None}]


def repeated_log_without_event(title, body):
    """Identify reported repeated log output when the event did not occur."""
    if not re.search(r'\blog spam\b', title, re.I):
        return []
    line = next((line for line in sentences(body) if not UNCERTAIN.search(line) and
                 re.search(r'\b(?:logs?|output)\b.{0,100}\b(?:repeatedly|continuously|every\s+\d+)\b', line, re.I)
                 and re.search(r'\bno\s+(?:actual\s+)?reload\b', line, re.I)), None)
    if not line:
        return []
    return [{'category': 'product_defect', 'rule': 'repeated_log_without_event',
             'source': 'title_and_body', 'excerpt': title[:180] + ' | ' + line[:300],
             'matched_text': None, 'url': None}]


def missing_authentication_binding(title, body):
    """Identify a described cross-context replay and its stated mechanism."""
    if not re.search(r'\bencrypted\b.{0,60}\bcan be replayed\b.{0,60}\bdifferent\b', title, re.I):
        return []
    line = next((line for line in sentences(body) if not UNCERTAIN.search(line) and
                 re.search(r'\bauthentication tag\b.{0,100}\b(?:only covers|does not bind)\b', line, re.I)), None)
    if not line:
        return []
    return [{'category': 'product_defect', 'rule': 'missing_authentication_binding',
             'source': 'title_and_body', 'excerpt': title[:180] + ' | ' + line[:300],
             'matched_text': None, 'url': None}]


def optional_input_exception(title, body):
    """A question about a cause may still report an observed exception."""
    exception = re.search(r'\b[A-Za-z]+(?:Error|Exception)\b', title)
    if not exception:
        return []
    lines = list(sentences(body))
    supported = next((line for line in lines if re.search(r'\bparameters?\b.{0,45}\boptional\b', line, re.I)), None)
    observed = next((line for line in lines if re.search(r'\bwhy am i getting\b.{0,80}\berror\b.{0,50}\bcrash\w*\b', line, re.I)), None)
    if not supported or not observed or not re.search(r'\b' + re.escape(exception.group()) + r'\b', body):
        return []
    return [{'category': 'product_defect', 'rule': 'optional_input_observed_exception',
             'source': 'title_and_body', 'excerpt': title[:150] + ' | ' + supported[:150] + ' | ' + observed[:150],
             'matched_text': exception.group(), 'url': None}]


def deleted_content_remains(title, body):
    """Record a reported retention result after a deletion operation."""
    if not re.search(r'\bleaves?\b.{0,60}\bdeleted\b.{0,80}\b(?:database|files?)\b', title, re.I):
        return []
    line = next((line for line in sentences(body) if not UNCERTAIN.search(line) and
                 re.search(r'\bfile\b.{0,50}\bstill held\b', line, re.I)), None)
    if not line:
        return []
    return [{'category': 'product_defect', 'rule': 'deleted_content_remains',
             'source': 'title_and_body', 'excerpt': title[:200] + ' | ' + line[:250],
             'matched_text': None, 'url': None}]


def assess_comments(issue):
    signals, evidence = [], []
    comments = sorted(issue.get('comments', []), key=lambda item: item.get('created_at') or '')
    for comment in comments:
        previous_evidence_count = len(evidence)
        previous_signal_count = len(signals)
        for sentence in sentences(comment.get('body', '')):
            reproduced = re.search(r'\b(?:i|we) (?:reproduced|verified|confirmed)\b', sentence, re.I)
            if not (CAUSE.search(sentence) or UNCERTAIN.search(sentence) or reproduced):
                continue
            signal = {'source': 'comment', 'created_at': comment.get('created_at'),
                      'url': comment.get('url'), 'excerpt': sentence[:500], 'used_for_category': False}
            if UNCERTAIN.search(sentence):
                signal['signal'] = 'question_or_hypothesis'
            elif CAUSE.search(sentence) or reproduced:
                hits = rule_matches(sentence, 'comment', comment.get('url'))
                # A specifically stated cause can describe a malfunction
                # without using the word "bug". Questions were filtered above.
                if matches(r'\b(?:bug|defect)\b', sentence) and not matches(r'\bnot\s+(?:a\s+)?(?:bug|defect)\b', sentence):
                    hits.append({'category':'product_defect', 'rule':'explicit_defect_cause', 'source':'comment',
                                 'excerpt':sentence[:500], 'matched_text':(CAUSE.search(sentence) or reproduced).group(), 'url':comment.get('url')})
                if hits:
                    signal['signal'] = 'explicit_cause'
                elif reproduced and not CAUSE.search(sentence):
                    # A reproduced symptom can be useful context, but it does
                    # not claim a diagnosis that needs conflict review.
                    signal['signal'] = 'reproduction_without_diagnosis'
                else:
                    signal['signal'] = 'clarification_needs_review'
                signal['used_for_category'] = bool(hits)
                evidence.extend(hits)
            signals.append(signal)
        # A later comment must explicitly retract the earlier diagnosis and
        # give a specific new cause; recency alone never resolves disagreement.
        correction = re.search(
            r'\b(?:i was wrong earlier|we were wrong earlier|'
            r'(?:earlier|previous) (?:diagnosis|explanation|conclusion) (?:was|is) (?:wrong|incorrect))\b',
            comment.get('body') or '', re.I)
        new_evidence = evidence[previous_evidence_count:]
        if correction and previous_evidence_count and len({hit['category'] for hit in new_evidence}) == 1:
            for signal in signals[:previous_signal_count]:
                if signal['used_for_category']:
                    signal['used_for_category'] = False
                    signal['signal'] = 'superseded_by_explicit_correction'
            evidence = new_evidence
            signals.append({'source': 'comment', 'created_at': comment.get('created_at'),
                            'url': comment.get('url'), 'excerpt': correction.group(),
                            'signal': 'explicit_correction', 'used_for_category': False})
    return evidence, signals


def area_for_text(text):
    for area, subcategory, pattern in AREA_RULES:
        match = re.search(pattern, text or '', re.I)
        if match:
            return area, subcategory, match.group()
    return 'Other / needs review', 'Needs a more specific review', None


def problem_details(issue):
    """Extract described problems from issue tables, retaining each description."""
    details = []
    for line in (issue.get('body') or '').splitlines():
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if len(cells) < 2 or not re.search(r'#\d+', cells[0]):
            continue
        description = cells[1]
        if not description or re.fullmatch(r'[-: ]+', description):
            continue
        area, subcategory, matched = area_for_text(description)
        details.append({'reference': re.search(r'#\d+', cells[0]).group(), 'description': description,
                        'problem_area': area, 'subcategory': subcategory, 'area_match': matched})
    # Reports may describe individual problems as numbered bold paragraphs.
    if not details:
        for line in (issue.get('body') or '').splitlines():
            match = re.match(r'^\s*\*\*(\d+)\.\s+(.+?)\*\*', line)
            if match:
                description = match.group(2).strip()
                area, subcategory, matched = area_for_text(description)
                details.append({'reference': None, 'description': description, 'problem_area': area,
                                'subcategory': subcategory, 'area_match': matched})
    return details


def multiple_problems(issue, details):
    text = (issue.get('title') or '') + '\n' + clean_text(issue.get('body', ''))
    # A number and explicit distinct problem noun are required; issue links alone do not count.
    match = re.search(r'\b(?:\d+\s+(?:open\s+)?(?:distinct\s+)?(?:bugs|issues|problems)|(?:two|three|four|five)\s+(?:distinct|separate)\s+(?:bugs|problems|defects))\b', text, re.I)
    number_words = {'two': 2, 'three': 3, 'four': 4, 'five': 5}
    number = match.group().split()[0].lower() if match else None
    total = int(number) if number and number.isdigit() else number_words.get(number)
    if total is not None and total > 1:
        return True, total - 1, match.group()
    if len(details) > 1 and all(d['reference'] for d in details) and len({d['reference'] for d in details}) == len(details):
        return True, len(details) - 1, 'distinct issue table entries'
    if re.search(r'\b(?:multiple|several|various)\s+(?:distinct\s+)?(?:bugs|problems)\b', text, re.I):
        return True, None, 'multiple problems stated; count not specified'
    return False, None, None


def describe_evidence_strength(item):
    """Describe the evidence itself; these levels are not measured accuracy."""
    source = item['source']
    excerpt = item.get('excerpt') or ''
    if source == 'title':
        return 'weak', 'Title wording is a clue that needs support from the report.'
    if source == 'comment' and CAUSE.search(excerpt):
        return 'strong', 'The comment explicitly states a cause; verify it concerns this issue.'
    if item['rule'] == 'reported_expected_actual_comparison':
        return 'moderate', 'The report supplies expected and observed sections; verify they describe the same behavior.'
    if source == 'title_and_body':
        return 'moderate', 'The title symptom has supporting text in the report.'
    return 'moderate', 'The report contains a specific rule match; context can change its meaning.'


def corroborated_title_causes(title_evidence, body):
    """Link a title clue to related cause details in the report."""
    lines = list(sentences(body))
    findings = []
    for item in title_evidence:
        category = item['category']
        title_text = item['excerpt']
        checks = []
        if category == 'documentation_gap' and re.search(r'\b(?:redirect|url|link|docs?)\b', title_text, re.I):
            checks = [r'\b(?:redirect|url|link|docs?)\b.{0,100}\b(?:404|no longer exists|does not exist|broken|dead)\b',
                      r'\b(?:redirect|url|link)\b', r'\b(?:404|no longer exists|does not exist)\b']
        elif category == 'setup_configuration' and re.search(r'\bnon.string\b', title_text, re.I):
            checks = [r'\b(?:schema|config)\b.{0,120}\b(?:type|string|unquoted)\b']
        elif category == 'dependency_platform' and re.search(r'\bdrivers?\b', title_text, re.I):
            checks = [r'\b(?:driver|sqlcipher|psycopg)\b.{0,100}\b(?:error|exception|fail\w*|not subclass)\b']
        elif category == 'dependency_platform' and re.search(r'\bpython\s*[<>]=?\s*\d+\.\d+', title_text, re.I):
            checks = [r'\bpython\s*\d+\.\d+\+?\b.{0,50}\b(?:required|unsupported|incompatible)\b']
        elif category == 'dependency_platform' and re.search(r'\b(?:deprecated|deprecationwarning)\b.{0,80}\bpython\s*\d+\.\d+', title_text, re.I):
            checks = [r'\bdeprecationwarning\b.{0,60}\bpython\s*\d+\.\d+\b']
        elif category == 'dependency_platform' and re.search(r'\bbreaks? with older versions\b', title_text, re.I):
            checks = [r'\bunpin\b.{0,60}\bupdate\b.{0,40}\blatest\b.{0,40}\bworks\b']
        if not checks:
            continue
        selected = []
        for pattern in checks:
            line = next((line for line in lines if not UNCERTAIN.search(line) and re.search(pattern, line, re.I)), None)
            if line:
                selected.append(line)
                if len(checks) == 1 or pattern == checks[0]:
                    break
        if len(selected) < (2 if len(checks) > 1 and not re.search(checks[0], selected[0] if selected else '', re.I) else 1):
            continue
        findings.append({'category': category, 'rule': 'title_cause_corroborated_by_report',
                         'source': 'title_and_body', 'excerpt': title_text[:160] + ' | ' + ' | '.join(selected)[:300],
                         'matched_text': item['matched_text'], 'url': None})
    return findings


def has_consistent_reported_failure(title, evidence):
    """Identify a narrow, corroborated expected/observed report for review routing.

    This is a rule-of-thumb, not a probability or proof of a product defect.
    Other conflict and data-quality flags still require review.
    """
    rules = {item['rule']: item for item in evidence if item['category'] == 'product_defect'}
    if not {'reported_expected_and_observed', 'corroborated_concrete_symptom'} <= rules.keys():
        return False
    # These clues may change the cause; keep a human check even if the
    # text also describes an observable failure.
    if re.search(r'\b(?:python\s*<?\s*3\.|psycopg|windows|dependency|compatibil\w*)\b', title, re.I):
        return False
    parts = rules['reported_expected_and_observed']['excerpt'].split(' | ', 1)
    if len(parts) != 2 or min(map(len, parts)) < 40:
        return False
    common_words = {
        'that', 'this', 'when', 'with', 'from', 'which', 'expected', 'actual',
        'should', 'does', 'return', 'returns', 'instead', 'would', 'have',
        'after', 'before', 'result', 'results', 'using', 'value', 'values',
        'state', 'same', 'into', 'where', 'their', 'there', 'will', 'they',
        'only', 'been', 'were', 'each', 'these', 'then', 'them', 'those',
        'than', 'also', 'more', 'work', 'some',
    }
    def meaningful_words(text):
        return set(re.findall(r'\b[a-z_][a-z_0-9]{3,}\b', text.lower())) - common_words

    return len(meaningful_words(parts[0]) & meaningful_words(parts[1])) >= 2


def classify_issue(issue, repository):
    title = issue.get('title') or ''
    body = issue.get('body') or ''
    report_evidence = (rule_matches(title, 'title') + rule_matches(body, 'body') +
                       reproduction_evidence(body) + corroborated_symptom(title, body) +
                       test_tooling_evidence(title, body) + proposed_design_evidence(title, body) +
                       platform_output_evidence(title, body) + repeated_unused_work_evidence(title, body) +
                       type_checker_discrepancy(title, body) + repeated_log_without_event(title, body) +
                       missing_authentication_binding(title, body) + optional_input_exception(title, body) +
                       deleted_content_remains(title, body))
    report_evidence.extend(corroborated_title_causes([item for item in report_evidence if item['source'] == 'title'], body))
    comment_evidence, comment_signals = assess_comments(issue)
    evidence = report_evidence + comment_evidence
    for item in evidence:
        item['strength'], item['strength_reason'] = describe_evidence_strength(item)

    # A title clue should not outweigh issue text, and an explicit causal
    # clarification can resolve a symptom. Matching the same clue repeatedly
    # does not make it stronger.
    non_title = [item for item in evidence if item['strength'] != 'weak']
    active_evidence = non_title if non_title else evidence
    explicit_causes = [item for item in active_evidence if item['strength'] == 'strong']
    if explicit_causes and len({item['category'] for item in explicit_causes}) == 1:
        active_evidence = explicit_causes
    categories = {item['category'] for item in active_evidence}
    # A proposed capability can also describe an existing limitation. Keep
    # that conflict open unless the report provides paired behavior sections.
    feature_title = any(item['category'] == 'feature_request' and item['strength'] == 'weak' for item in evidence)
    paired_behavior = any(item['rule'] == 'reported_expected_actual_comparison' for item in active_evidence)
    only_proposed_capability = (feature_title and categories == {'product_defect'} and
                                all(item['rule'] == 'reported_expected_and_observed' for item in active_evidence) and
                                any(re.search(r'\b(?:does not|doesn.t) currently support\b', item['excerpt'], re.I)
                                    for item in active_evidence))
    if only_proposed_capability:
        # A desired capability and an explicitly stated current limitation do
        # not by themselves establish that an existing promise is broken.
        active_evidence = [item for item in evidence if item['category'] == 'feature_request']
        categories = {'feature_request'}
    if feature_title and categories == {'product_defect'} and not paired_behavior and not explicit_causes:
        categories.add('feature_request')
    # A symptom is compatible with a stated cause; it is not a competing diagnosis.
    specific = categories & {'setup_configuration', 'dependency_platform', 'documentation_gap'}
    had_specific_and_defect = bool(specific and 'product_defect' in categories)
    if had_specific_and_defect:
        categories.remove('product_defect')
    review_reasons = []
    weak_conflicts = {item['category'] for item in evidence if item['strength'] == 'weak'} - categories
    if weak_conflicts:
        review_reasons.append('weaker_title_clue_differs')
    proposed_alternatives = (any(item['rule'] == 'reported_expected_actual_comparison' and
                                 re.search(r'\bfor example,? one or more of\b', item['excerpt'], re.I)
                                 for item in report_evidence) and
                             any(re.search(r'\bdoes not provide a documented way to\b', item['excerpt'], re.I)
                                 for item in report_evidence if item['category'] == 'feature_request'))
    if 'product_defect' in categories and 'feature_request' in categories and proposed_alternatives:
        categories.remove('product_defect')
        review_reasons.append('verify_proposed_capability')
    if ('product_defect' in categories and 'feature_request' in categories and
            any(item['rule'] in {'reported_expected_actual_comparison', 'reported_incorrect_attribute'}
                for item in report_evidence)):
        categories.remove('feature_request')
        review_reasons.append('verify_existing_behavior_and_feature_request')
    if len(categories) == 1:
        why = next(iter(categories))
    else:
        why = 'unclear'
        review_reasons.append('conflicting_category_signals' if categories else 'no_clear_category_evidence')
    if re.search(r'\b(?:semantics question|not a clear.cut bug|intended behavior is (?:unclear|unknown))\b', body, re.I):
        why = 'unclear'
        review_reasons.append('intended_behavior_uncertain')
    if len({item['category'] for item in comment_evidence}) > 1:
        why = 'unclear'
        review_reasons.append('conflicting_comment_causes')
    if had_specific_and_defect:
        review_reasons.append('verify_cause_and_reported_behavior')
    consistent_failure = (why == 'product_defect' and
                          has_consistent_reported_failure(title, active_evidence))
    if why == 'product_defect' and not consistent_failure and not any(e['rule'] == 'explicit_defect_cause' for e in evidence):
        review_reasons.append('reported_symptom_needs_confirmation')
    supporting = [item for item in evidence if item['category'] == why]
    if supporting and all(item['source'] == 'title' for item in supporting):
        review_reasons.append('classification_based_on_title_only')
        if why in {'product_defect', 'dependency_platform'}:
            why = 'unclear'
    if (why == 'feature_request' and supporting and
            all(re.fullmatch(r'would (?:like|love) to', item.get('matched_text') or '', re.I)
                for item in supporting)):
        review_reasons.append('feature_intent_needs_confirmation')
    # Preserve uncertainty where a report's symptom and a later cause disagree.
    if comment_evidence and report_evidence and {e['category'] for e in comment_evidence} != {e['category'] for e in report_evidence}:
        review_reasons.append('comment_report_difference')
    if comment_evidence:
        review_reasons.append('verify_comment_refers_to_this_issue')
    if any(s['signal'] == 'clarification_needs_review' for s in comment_signals):
        review_reasons.append('comment_cause_needs_review')
    if why == 'documentation_gap' and any(e['rule'] == 'documented_guidance_omission' for e in evidence):
        review_reasons.append('verify_documentation_gap_caused_problem')
    area, subcategory, area_match = area_for_text(title)
    area_source = 'title'
    if not area_match:
        area, subcategory, area_match = area_for_text(' '.join(sentences(body)))
        area_source = 'body' if area_match else None
    if not area_match:
        review_reasons.append('area_not_identified')
    details = problem_details(issue)
    multiple, additional, count_evidence = multiple_problems(issue, details)
    if multiple:
        review_reasons.append('multiple_problems')
        if details and additional is not None and len(details) != additional + 1:
            review_reasons.append('problem_detail_count_mismatch')
    if issue.get('comment_count') is not None and issue.get('comment_count') != len(issue.get('comments', [])):
        review_reasons.append('comment_count_mismatch')
    for item in evidence:
        item['used_for_decision'] = item in active_evidence and item['category'] == why
    reason = EXCLUSIONS.get(((repository or '').lower(), issue.get('number')))
    result = dict(issue)
    result['classification'] = {
        'why_category': why, 'problem_area': area, 'subcategory': subcategory,
        'why_note': 'Rule-based draft; inspect matched evidence and review flags.',
        'confidence': 'low' if review_reasons or why == 'unclear' else 'medium',
        'evidence': {'matches': evidence, 'comment_signals': comment_signals,
                     'area_source': area_source, 'area_match': area_match, 'multiple_problem_count': count_evidence},
        'evidence_strength': max((item['strength'] for item in evidence if item['used_for_decision']),
                                 key={'weak': 0, 'moderate': 1, 'strong': 2}.get, default=None),
        'review_policy_note': ('Expected and observed text overlap and the report corroborates the title symptom.'
                               if consistent_failure else None),
        'contains_multiple_problems': multiple, 'additional_problem_count': additional,
        'problem_details': details, 'excluded_from_human_count': bool(reason), 'exclusion_reason': reason,
        'needs_review': bool(review_reasons), 'review_reasons': review_reasons,
        'method': 'rule_based_issue_and_comment_parser',
    }
    return result


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Classify a raw GitHub issue snapshot with visible rules.')
    parser.add_argument('--input', type=Path, help='Raw JSON snapshot; default is the original LangGraph file')
    parser.add_argument('--output-dir', type=Path, default=OUTPUT_FILE.parent, help='Folder for processed results')
    args = parser.parse_args()
    input_file = args.input if args.input else find_input_file()
    source = json.loads(input_file.read_text(encoding='utf-8'))
    repository = source.get('source_repository') or ''
    issues = [classify_issue(issue, repository) for issue in source.get('issues', [])]
    human = [issue for issue in issues if not issue['classification']['excluded_from_human_count']]
    excluded = [issue for issue in issues if issue['classification']['excluded_from_human_count']]
    review = [issue for issue in human if issue['classification']['needs_review']]
    counts = Counter(issue['classification']['why_category'] for issue in human)
    output = dict(source)
    output['classification_method'] = 'rule_based_issue_and_comment_parser'
    output['classification_note'] = 'Draft rule matches, not measured accuracy. Review uncertain and conflicting cases.'
    output['classification_summary'] = {
        'issue_records': len(issues), 'human_issue_records': len(human), 'excluded_issue_records': len(excluded),
        'needs_review': len(review), 'multi_problem_issues': sum(i['classification']['contains_multiple_problems'] for i in human),
        'additional_problems': sum(i['classification']['additional_problem_count'] or 0 for i in human),
        'why_category_counts': dict(counts),
        'problem_area_counts': dict(Counter(i['classification']['problem_area'] for i in human)),
    }
    output['issues'] = issues
    write_json(args.output_dir / 'langgraph_open_issues_classified.json', output)
    for category in ('product_defect', 'setup_configuration', 'dependency_platform', 'documentation_gap', 'feature_request', 'unclear'):
        write_json(args.output_dir / 'by_category' / (category + '.json'),
                   [i for i in human if i['classification']['why_category'] == category])
    write_json(args.output_dir / 'needs_review.json', review)
    write_json(args.output_dir / 'excluded_from_human_analysis.json', excluded)
    print(f'Classified {len(issues)} issues; human: {len(human)}; excluded: {len(excluded)}; review: {len(review)}.')
    print(f'Saved processed files to: {args.output_dir}')


if __name__ == '__main__':
    main()
