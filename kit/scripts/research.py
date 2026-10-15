"""Parse and date-check Research findings from a piece spec."""
from __future__ import annotations

import re
from datetime import date
from typing import Optional
from urllib.parse import urlsplit


_FINDING = re.compile(
    r"^\s*[-*]\s*(R\d+)\s*:\s*(.+?)\s+\(source:\s*(https?://\S+),\s*"
    r"read:\s*(\d{4}-\d{2}-\d{2})\)\s*$",
    re.IGNORECASE,
)


def parse_research(lines: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    """Return findings and validation gaps for the optional Research section."""
    findings: list[dict[str, str]] = []
    gaps: list[str] = []
    seen: set[str] = set()
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        match = _FINDING.match(line)
        if not match:
            gaps.append(f"Research line {number} must include an R ID, source URL and read date")
            continue
        finding_id, finding, source, read_date = match.groups()
        finding_id = finding_id.upper()
        if finding_id in seen:
            gaps.append(f"Research ID {finding_id} is used twice")
        seen.add(finding_id)
        parsed_url = urlsplit(source)
        if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
            gaps.append(f"Research {finding_id} source must be an HTTP or HTTPS URL")
        try:
            read = date.fromisoformat(read_date)
            if read.isoformat() != read_date:
                raise ValueError
        except ValueError:
            gaps.append(f"Research {finding_id} read date must be a real YYYY-MM-DD date")
            continue
        if read > date.today():
            gaps.append(f"Research {finding_id} read date cannot be in the future")
        findings.append({"id": finding_id, "finding": finding, "source": source,
                         "read": read_date})
    return findings, gaps


def stale_findings(findings: list[dict[str, str]], today: Optional[date] = None) -> list[str]:
    """Return finding IDs that are more than 30 days old on the claim date."""
    today = today or date.today()
    stale = []
    for finding in findings:
        read = date.fromisoformat(finding["read"])
        if (today - read).days > 30:
            stale.append(finding["id"])
    return stale
