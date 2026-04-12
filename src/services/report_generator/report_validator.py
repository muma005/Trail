"""
Validator Agent.
Phase 3: Verifies that report citations (commit SHAs, task IDs) match actual database records.
Flags hallucinations and adjusts confidence score.
"""
import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# Regex patterns for extracting citations from reports
SHA_PATTERN = re.compile(r'\b([a-f0-9]{8,40})\b')
TASK_TITLE_PATTERN = re.compile(r'["\*\*]([^"\*\*]+)["\*\*]')


class Validator:
    """
    Validates report citations against the database.
    Penalizes confidence for invalid citations.
    """

    def validate(self, report: str, context: Dict[str, Any]) -> Tuple[str, float, List[str]]:
        """
        Validate a report's citations.

        Args:
            report: Generated report text (Markdown)
            context: Original context used to generate the report

        Returns:
            Tuple of (validated_report, confidence_score, warnings)
        """
        warnings = []
        confidence = 100.0

        # Extract SHAs from report
        cited_shas = self._extract_shas(report)
        valid_shas = set(c.get("sha", "") for c in context.get("commits", []))

        # Verify each cited SHA
        invalid_shas = []
        for sha in cited_shas:
            # Check if any stored SHA starts with this prefix (user may cite short SHA)
            matched = any(valid_sha.startswith(sha[:8]) for valid_sha in valid_shas)
            if not matched:
                invalid_shas.append(sha)

        if invalid_shas:
            penalty = len(invalid_shas) * 20
            confidence = max(0, confidence - penalty)
            warnings.append(
                f"⚠️ Unverified commit SHAs: {', '.join(invalid_shas[:5])}"
            )

        # Check for task titles mentioned
        cited_tasks = self._extract_task_titles(report, context)
        if cited_tasks["invalid"]:
            penalty = len(cited_tasks["invalid"]) * 10
            confidence = max(0, confidence - penalty)
            warnings.append(
                f"⚠️ Unverified task references: {', '.join(cited_tasks['invalid'][:5])}"
            )

        # Add validation section to report
        validated_report = report + "\n\n---\n## Validation\n"
        if not warnings:
            validated_report += "✅ All citations verified against source data.\n"
        else:
            for w in warnings:
                validated_report += f"- {w}\n"

        validated_report += f"\n**Confidence: {confidence}%**\n"

        logger.info(
            f"Validation complete: confidence={confidence}%, "
            f"warnings={len(warnings)}, invalid_shas={len(invalid_shas)}"
        )

        return validated_report, confidence, warnings

    def _extract_shas(self, report: str) -> List[str]:
        """
        Extract potential commit SHAs from report text.
        Filters out common false positives.
        """
        candidates = SHA_PATTERN.findall(report)
        # Filter: SHAs should be hex-only, not common words
        filtered = []
        seen = set()
        for sha in candidates:
            sha_lower = sha.lower()
            if sha_lower in seen:
                continue
            seen.add(sha_lower)
            # Must be at least 8 hex chars
            if len(sha_lower) >= 8 and all(c in "0123456789abcdef" for c in sha_lower):
                filtered.append(sha_lower)
        return filtered

    def _extract_task_titles(self, report: str, context: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Check if task titles mentioned in the report exist in the context.
        Returns dict with 'valid' and 'invalid' lists.
        """
        valid_titles = set()
        for task in context.get("tasks", []):
            title = task.get("title", "")
            if title:
                valid_titles.add(title.lower())

        # Extract quoted/bold text from report
        cited = TASK_TITLE_PATTERN.findall(report)
        valid = []
        invalid = []

        for title in cited:
            if title.lower() in valid_titles:
                valid.append(title)
            # Skip very short or generic text
            elif len(title) > 3 and title.lower() not in (
                "what was done", "progress summary", "header",
                "what needs", "context", "confidence", "unknown",
            ):
                invalid.append(title)

        return {"valid": valid, "invalid": invalid}
