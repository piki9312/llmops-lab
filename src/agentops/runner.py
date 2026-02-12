"""
Test runner for Agent Regression - llmops integrated.

This module executes test cases via llmops gateway to collect both
functional results and operational metrics (cost, latency, cache hit, etc).
"""

import asyncio
import json
import os
import time
import uuid
from datetime import datetime
from typing import List, Optional

from .json_validator import JSONContractValidator
from .models import RegressionReport, TestCase, TestResult


def _default_llmops_config() -> dict:
    """Build default llmops config from environment variables."""
    provider = os.getenv("LLM_PROVIDER", "mock")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini" if provider == "openai" else "gpt-4-mock")
    return {
        "provider": provider,
        "model": model,
        "timeout_seconds": int(os.getenv("LLM_TIMEOUT", "30")),
        "max_retries": int(os.getenv("LLM_MAX_RETRIES", "2")),
    }


def _soft_match(actual: str, expected: str) -> bool:
    """Lightweight semantic match for S2 cases.

    Returns True when the actual output *reasonably* addresses the
    expected answer.  Heuristic: extract meaningful keywords from
    ``expected`` and check that at least 50 % appear in ``actual``
    (case-insensitive).  Single-word expected values require an exact
    substring match.
    """
    if not expected or not actual:
        return bool(actual)

    actual_lower = actual.lower()
    expected_lower = expected.lower()

    # Strip common noise phrases
    for noise in ("a ", "an ", "the ", "or equivalent"):
        expected_lower = expected_lower.replace(noise, " ")

    # Tokenise into keywords (len >= 2)
    keywords = [w for w in expected_lower.split() if len(w) >= 2]
    if not keywords:
        return True  # nothing to check

    hits = sum(1 for kw in keywords if kw in actual_lower)
    ratio = hits / len(keywords)
    return ratio >= 0.5


class RegressionRunner:
    """Executes regression test cases via llmops gateway."""

    def __init__(self, use_llmops: bool = True, llmops_config: Optional[dict] = None):
        """
        Initialize the regression runner with optional llmops integration.

        Args:
            use_llmops: If True, use llmops gateway for execution
            llmops_config: Configuration for llmops (provider, model, etc)
        """
        self.use_llmops = use_llmops
        self.llmops_config = llmops_config or _default_llmops_config()
        self.results: List[TestResult] = []
        self.llm_client = None

        if self.use_llmops:
            self._init_llmops_client()

    def _init_llmops_client(self):
        """Initialize llmops LLMClient for test execution."""
        from llmops.llm_client import LLMClient, MockLLMProvider, OpenAIProvider

        provider_name = self.llmops_config.get("provider", "mock")
        if provider_name == "openai":
            provider = OpenAIProvider(model_name=self.llmops_config.get("model", "gpt-4o-mini"))
        else:
            provider = MockLLMProvider(self.llmops_config.get("model", "gpt-4-mock"))

        self.llm_client = LLMClient(
            provider=provider,
            timeout_seconds=self.llmops_config.get("timeout_seconds", 30),
            max_retries=self.llmops_config.get("max_retries", 2),
        )

    def _run_async(self, coro):
        """
        Run async code in a sync context.
        Handles nested event loops gracefully.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in an async context (e.g., pytest with asyncio)
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    return executor.submit(asyncio.run, coro).result()
            else:
                # Not in an async context
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop in current thread
            return asyncio.run(coro)

    def run_case(self, case: TestCase) -> TestResult:
        """
        Execute a single test case via llmops (or fallback to agent function).

        Args:
            case: The test case to execute

        Returns:
            TestResult with llmops metrics
        """
        start_time = time.time()
        error = None
        failure_type = None
        actual_output = ""
        request_id = str(uuid.uuid4())[:8]
        severity = (case.metadata or {}).get("severity", "S2")

        # llmops metrics (populated when use_llmops=True)
        latency_ms = 0.0
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        cost_usd = 0.0
        cache_hit = False
        provider = self.llmops_config.get("provider", "mock")
        model = self.llmops_config.get("model", "gpt-4-mock")

        try:
            if self.use_llmops and self.llm_client:
                # Execute via llmops synchronously
                llmops_result = self._run_async(
                    self._call_llmops(
                        case.input_prompt, severity, expected_output=case.expected_output
                    )
                )
                actual_output = llmops_result.get("text", "")
                error = llmops_result.get("error")

                # --- S1: JSON contract validation ---
                if severity == "S1" and not error:
                    try:
                        json.loads(actual_output)
                    except (json.JSONDecodeError, ValueError):
                        error = "Output is not valid JSON"
                        failure_type = "bad_json"
                    if not error and case.expected_output:
                        is_valid, fail_type, error_msg = JSONContractValidator.validate_contract(
                            case.expected_output, actual_output
                        )
                        if not is_valid:
                            error = error_msg
                            failure_type = fail_type

                # --- S2: lightweight semantic check ---
                if severity != "S1" and not error and case.expected_output:
                    if not _soft_match(actual_output, case.expected_output):
                        error = f"Output does not match expected: {case.expected_output[:80]}"
                        failure_type = "quality_fail"

                # Extract llmops metrics
                latency_ms = llmops_result.get("latency_ms", 0.0)
                prompt_tokens = llmops_result.get("prompt_tokens", 0)
                completion_tokens = llmops_result.get("completion_tokens", 0)
                total_tokens = llmops_result.get("total_tokens", 0)
                cost_usd = llmops_result.get("cost_usd", 0.0)
                cache_hit = llmops_result.get("cache_hit", False)
            else:
                # Fallback: direct agent function (placeholder)
                actual_output = f"Processed: {case.input_prompt[:50]}"

        except Exception as e:
            error = str(e)
            if "timeout" in str(e).lower():
                failure_type = "timeout"
            else:
                failure_type = "tool_error"

        execution_time = time.time() - start_time

        # Score: 1.0 if no error, 0.0 otherwise
        passed = error is None and len(actual_output) > 0
        score = 1.0 if passed else 0.0

        result = TestResult(
            case_id=case.case_id,
            actual_output=actual_output,
            passed=passed,
            score=score,
            execution_time=execution_time,
            timestamp=datetime.now(),
            error=error,
            failure_type=failure_type,
            metrics=dict(case.metadata) if case.metadata else {},
            request_id=request_id,
            provider=provider,
            model=model,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            cache_hit=cache_hit,
        )

        return result

    async def _call_llmops(
        self, prompt: str, severity: str = "S2", expected_output: Optional[str] = None
    ) -> dict:
        """Call llmops gateway to execute prompt.

        For S1 cases the LLM is asked to reply in JSON that conforms to the
        expected contract schema.  Latency is measured around the actual API
        call so the metric reflects real-world performance.
        """
        from llmops.pricing import calculate_cost_usd

        # --- Build request --------------------------------------------------
        messages: list[dict] = []
        schema = None

        if severity == "S1" and expected_output:
            # Ask the model to respond with JSON matching the expected schema
            try:
                expected_json = json.loads(expected_output)
                schema = {
                    "type": "object",
                    "properties": {k: {"type": type(v).__name__} for k, v in expected_json.items()},
                }
                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "You are an API backend. Respond ONLY with a valid JSON "
                            "object. Do not include any explanation or markdown.\n"
                            f"Required keys and example values: {expected_output}"
                        ),
                    }
                )
            except (json.JSONDecodeError, ValueError):
                pass  # fall through to plain-text mode

        messages.append({"role": "user", "content": prompt})

        # --- Execute with latency measurement --------------------------------
        t0 = time.perf_counter()
        result = await self.llm_client.generate(
            messages=messages,
            schema=schema,
            max_tokens=512 if severity == "S1" else 256,
        )
        latency_ms = (time.perf_counter() - t0) * 1000

        # --- Extract metrics -------------------------------------------------
        tokens = result.get("tokens", {"prompt": 0, "completion": 0, "total": 0})
        model = self.llmops_config.get("model", "gpt-4-mock")
        provider = self.llmops_config.get("provider", "mock")

        cost_usd = calculate_cost_usd(
            model=model,
            prompt_tokens=tokens.get("prompt", 0),
            completion_tokens=tokens.get("completion", 0),
            provider=provider,
        )

        output_text = result.get("text", "")

        return {
            "text": output_text,
            "error": result.get("error_type"),
            "prompt_tokens": tokens.get("prompt", 0),
            "completion_tokens": tokens.get("completion", 0),
            "total_tokens": tokens.get("total", 0),
            "cost_usd": cost_usd,
            "cache_hit": False,
            "latency_ms": latency_ms,
        }

    def run_all(self, cases: List[TestCase], run_id: Optional[str] = None) -> RegressionReport:
        """
        Execute all test cases and generate a report with llmops metrics.

        Args:
            cases: List of test cases to execute
            run_id: Optional unique identifier for this run

        Returns:
            RegressionReport with aggregated results and llmops stats
        """
        if run_id is None:
            run_id = str(uuid.uuid4())

        self.results = []

        for case in cases:
            result = self.run_case(case)
            self.results.append(result)

        # Calculate aggregates
        passed_cases = sum(1 for r in self.results if r.passed)
        failed_cases = len(self.results) - passed_cases
        average_score = (
            sum(r.score for r in self.results) / len(self.results) if self.results else 0.0
        )

        report = RegressionReport(
            run_id=run_id,
            timestamp=datetime.now(),
            total_cases=len(cases),
            passed_cases=passed_cases,
            failed_cases=failed_cases,
            average_score=average_score,
            results=self.results,
        )

        return report
