"""
Report Generation Workflow.
Phase 3: Orchestrates the multi-agent pipeline:
Dispatcher → Context Retriever → LLM Analyzer → Validator
Phase 4: Extended with multiple output formats (markdown, json, text).
"""
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class ReportWorkflow:
    """
    Orchestrates the report generation pipeline.
    Each step is decoupled for potential future distributed execution.
    """

    def __init__(self, openrouter_api_key: Optional[str] = None, model: str = "anthropic/claude-3.5-sonnet"):
        self.api_key = openrouter_api_key
        self.model = model

    def generate(self, project_id: str) -> str:
        """
        Run the full report generation pipeline synchronously.

        Args:
            project_id: Project UUID

        Returns:
            Final validated Markdown report

        Raises:
            ValueError if project not found
            Exception on unrecoverable failure
        """
        logger.info(f"Starting report generation for project {project_id}")

        # Step 1: Context Retrieval
        logger.info("Step 1: Retrieving project context...")
        from src.services.report_generator.context_retriever import ContextRetriever

        retriever = ContextRetriever()
        context = retriever.retrieve(project_id)

        # Step 2: LLM Analysis (with fallback)
        logger.info("Step 2: Generating report with LLM...")
        report = self._generate_report(context)

        # Step 3: Validation
        logger.info("Step 3: Validating report citations...")
        from src.services.report_generator.report_validator import Validator

        validator = Validator()
        validated_report, confidence, warnings = validator.validate(report, context)

        logger.info(
            f"Report generation complete: {len(validated_report)} chars, "
            f"confidence={confidence}%, warnings={len(warnings)}"
        )

        return validated_report

    def _generate_report(self, context: dict) -> str:
        """
        Generate report using LLM, with fallback on failure.
        """
        if not self.api_key:
            logger.warning("No OpenRouter API key — using fallback report")
            return self._fallback_report(context)

        try:
            from src.services.report_generator.llm_analyzer import LLMAnalyzer

            analyzer = LLMAnalyzer(
                api_key=self.api_key,
                model=self.model,
            )
            return analyzer.generate_report(context)

        except Exception as e:
            logger.warning(f"LLM generation failed, using fallback: {e}")
            return self._fallback_report(context)

    def _fallback_report(self, context: dict) -> str:
        """
        Generate a basic report from raw data when LLM is unavailable.
        """
        from src.services.report_generator.llm_analyzer import LLMAnalyzer

        analyzer = LLMAnalyzer(api_key="")
        return analyzer.generate_fallback_report(context)

    def format_report(self, validated_report: str, context: dict, fmt: str = "markdown") -> str:
        """
        Format a report in the specified format.

        Args:
            validated_report: The validated Markdown report string
            context: Original context dict
            fmt: Output format ('markdown', 'json', 'text')

        Returns:
            Formatted report string
        """
        if fmt == "json":
            return self._format_json(context, validated_report)
        elif fmt == "markdown":
            return validated_report
        else:  # text (plain text)
            return validated_report  # Markdown is already readable as text

    def _format_json(self, context: dict, report: str) -> str:
        """
        Convert report context and report text to structured JSON.
        """
        project = context.get("project", {})
        snapshot = context.get("latest_snapshot")

        # Extract sections from report (simple heuristic: split by ## headers)
        sections = {}
        current_section = "header"
        current_lines = []

        for line in report.split("\n"):
            if line.startswith("## "):
                # Save previous section
                section_key = current_section.lower().replace(" ", "_").replace("#", "").strip("_")
                sections[section_key] = "\n".join(current_lines).strip()
                current_section = line.replace("## ", "")
                current_lines = []
            else:
                current_lines.append(line)

        # Save last section
        section_key = current_section.lower().replace(" ", "_").replace("#", "").strip("_")
        sections[section_key] = "\n".join(current_lines).strip()

        # Calculate metadata
        days_idle = 0
        if project.get("last_synced"):
            try:
                last_sync = datetime.fromisoformat(project["last_synced"])
                days_idle = (datetime.utcnow() - last_sync).days
            except (ValueError, TypeError):
                pass

        # Extract confidence from report
        confidence = 0
        if "Confidence:" in report:
            import re
            match = re.search(r'Confidence:\s*(\d+)%', report)
            if match:
                confidence = int(match.group(1))

        output = {
            "project": project.get("name", "Unknown"),
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "sections": sections,
            "metadata": {
                "days_idle": days_idle,
                "completion_percentage": float(snapshot.get("completion_simple", 0)) if snapshot else 0,
                "confidence_score": confidence,
                "total_tasks": len(context.get("tasks", [])),
                "total_commits": len(context.get("commits", [])),
            },
        }

        return json.dumps(output, indent=2, default=str)
