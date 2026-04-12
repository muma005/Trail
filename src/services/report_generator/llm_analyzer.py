"""
LLM Analyzer Agent.
Phase 3: Calls OpenRouter API to generate resumption reports from project context.
"""
import json
import logging
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Structured prompt template enforcing 6 sections and citation rules
REPORT_PROMPT_TEMPLATE = """You are a project management analyst. Generate a resumption report for the project described below.

The report must have exactly these 6 sections:
1. **Header**: Project name, days since last activity, status emoji (🟢 active / 🟡 stale / 🔴 abandoned)
2. **Progress Summary**: overall completion percentage (simple and weighted), task breakdown (Done/In Progress/Blocked/Not Started), commit activity (last 4 weeks)
3. **What Was Done**: last 10 commits with SHAs and messages, completed tasks, merged PRs
4. **What Needs To Be Done**: priority-ordered pending tasks, immediate next action (file/function if available), blocked tasks with reason
5. **Context & Where to Pick Up**: last commit details (branch, SHA, message), last task status, suggested starting command (e.g., `git checkout branch && code file`)
6. **AI Confidence Score**: how confident you are (0-100%) and any missing data warnings.

CRITICAL RULES:
- For every commit you mention, you MUST include its full SHA (or at least 8 characters).
- For every task, include its title.
- If you are unsure about something, state "Unknown" and do NOT invent data.
- Use actual data from the context below. Do not hallucinate.

Here is the project context:
{context_json}
"""


class LLMAnalyzer:
    """
    Generates reports using OpenRouter API.
    Retries with exponential backoff on failure.
    """

    def __init__(self, api_key: str, model: str = "anthropic/claude-3.5-sonnet", timeout: int = 60):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    def generate_report(self, context: dict) -> str:
        """
        Generate a resumption report from project context.

        Args:
            context: Structured context dict from ContextRetriever

        Returns:
            Markdown report string

        Raises:
            Exception on API failure after retries
        """
        context_json = json.dumps(context, indent=2, default=str)
        prompt = REPORT_PROMPT_TEMPLATE.format(context_json=context_json)

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/muma005/Trail",
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 4000,
            },
            timeout=self.timeout,
        )

        if response.status_code != 200:
            raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")

        data = response.json()
        report = data["choices"][0]["message"]["content"]

        logger.info(f"Report generated: {len(report)} characters")
        return report

    def generate_fallback_report(self, context: dict) -> str:
        """
        Generate a basic report from raw data when LLM is unavailable.

        Args:
            context: Structured context dict

        Returns:
            Plain text report with raw data
        """
        project = context.get("project", {})
        tasks = context.get("tasks", [])
        commits = context.get("commits", [])
        snapshot = context.get("latest_snapshot")

        lines = []
        lines.append(f"# Resumption Report: {project.get('name', 'Unknown')}")
        lines.append(f"**Key:** {project.get('key', 'N/A')}")
        lines.append(f"**Last Sync:** {project.get('last_synced', 'Never')}")
        lines.append("")

        lines.append("## Progress Summary")
        if snapshot:
            lines.append(f"- Completion (simple): {snapshot.get('completion_simple', 0)}%")
            lines.append(f"- Completion (weighted): {snapshot.get('completion_weighted', 0)}%")
            lines.append(f"- Tasks: {snapshot.get('completed_tasks', 0)}/{snapshot.get('total_tasks', 0)} completed")
        else:
            completed = sum(1 for t in tasks if t.get("status") in ("Done", "Completed"))
            lines.append(f"- Tasks completed: {completed}/{len(tasks)}")
        lines.append("")

        lines.append("## What Was Done (Recent Commits)")
        for c in commits[:10]:
            lines.append(f"- `{c['sha'][:8]}` {c['message'][:60]} ({c.get('date', 'N/A')})")
        lines.append("")

        lines.append("## What Needs To Be Done")
        pending = [t for t in tasks if t.get("status") not in ("Done", "Completed")]
        for t in pending[:10]:
            priority = t.get("priority", "Medium")
            lines.append(f"- [{priority}] {t['title']}")
        lines.append("")

        lines.append("## AI Confidence Score")
        lines.append("- ⚠️ LLM unavailable — this is a raw data summary only.")
        return "\n".join(lines)
