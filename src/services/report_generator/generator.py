"""
Report Generation Workflow.
Phase 3: Orchestrates the multi-agent pipeline:
Dispatcher → Context Retriever → LLM Analyzer → Validator
"""
import json
import logging
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
