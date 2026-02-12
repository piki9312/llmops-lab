"""
Evaluation metrics for Agent Regression with llmops integration.

This module provides evaluation and scoring functions for test results,
including operational metrics from llmops (cost, latency, cache hit rate).
"""

from typing import List, Dict, Any
from .models import TestResult, RegressionReport
from .aggregate import severity_pass_rate, format_rate


class Evaluator:
    """Evaluates test results using both functional and operational metrics."""
    
    @staticmethod
    def calculate_accuracy(results: List[TestResult]) -> float:
        """
        Calculate accuracy (pass rate) of test results.
        
        Args:
            results: List of test results
            
        Returns:
            Accuracy as a float between 0 and 1
        """
        if not results:
            return 0.0
        
        passed = sum(1 for r in results if r.passed)
        return passed / len(results)
    
    @staticmethod
    def calculate_average_score(results: List[TestResult]) -> float:
        """
        Calculate average score across all results.
        
        Args:
            results: List of test results
            
        Returns:
            Average score as a float
        """
        if not results:
            return 0.0
        
        return sum(r.score for r in results) / len(results)
    
    @staticmethod
    def calculate_average_execution_time(results: List[TestResult]) -> float:
        """
        Calculate average execution time across all results.
        
        Args:
            results: List of test results
            
        Returns:
            Average execution time in seconds
        """
        if not results:
            return 0.0
        
        return sum(r.execution_time for r in results) / len(results)
    
    @staticmethod
    def calculate_average_latency_ms(results: List[TestResult]) -> float:
        """
        Calculate average LLM latency from llmops metrics.
        
        Args:
            results: List of test results
            
        Returns:
            Average latency in milliseconds
        """
        if not results:
            return 0.0
        
        latencies = [r.latency_ms for r in results if r.latency_ms > 0]
        if not latencies:
            return 0.0
        
        return sum(latencies) / len(latencies)
    
    @staticmethod
    def calculate_total_cost(results: List[TestResult]) -> float:
        """
        Calculate total cost from llmops metrics.
        
        Args:
            results: List of test results
            
        Returns:
            Total cost in USD
        """
        return sum(r.cost_usd for r in results)
    
    @staticmethod
    def calculate_average_cost_per_test(results: List[TestResult]) -> float:
        """
        Calculate average cost per test case.
        
        Args:
            results: List of test results
            
        Returns:
            Average cost in USD per test
        """
        if not results:
            return 0.0
        
        return sum(r.cost_usd for r in results) / len(results)
    
    @staticmethod
    def calculate_cache_hit_rate(results: List[TestResult]) -> float:
        """
        Calculate cache hit rate from llmops metrics.
        
        Args:
            results: List of test results
            
        Returns:
            Cache hit rate as percentage (0-100)
        """
        if not results:
            return 0.0
        
        hits = sum(1 for r in results if r.cache_hit)
        return (hits / len(results)) * 100
    
    @staticmethod
    def calculate_cost_efficiency(results: List[TestResult]) -> Dict[str, float]:
        """
        Calculate cost efficiency metrics.
        
        Args:
            results: List of test results
            
        Returns:
            Dict with cost per token and cost per passed test
        """
        total_tokens = sum(r.total_tokens for r in results)
        total_cost = sum(r.cost_usd for r in results)
        passed_count = sum(1 for r in results if r.passed)
        
        return {
            "cost_per_token": (total_cost / total_tokens * 1000) if total_tokens > 0 else 0.0,
            "cost_per_passed_test": (total_cost / passed_count) if passed_count > 0 else 0.0,
            "tokens_per_test": (total_tokens / len(results)) if results else 0,
        }
    
    @staticmethod
    def generate_summary(report: RegressionReport) -> Dict[str, Any]:
        """
        Generate a comprehensive summary from a regression report.
        
        Args:
            report: The regression report to summarize
            
        Returns:
            Dictionary containing functional and operational metrics
        """
        evaluator = Evaluator()
        cost_efficiency = evaluator.calculate_cost_efficiency(report.results)
        
        # S1 / S2 pass-rate breakdown
        s1_stats = severity_pass_rate(report.results, "S1")
        s2_stats = severity_pass_rate(report.results, "S2")

        return {
            # Test execution metrics
            "run_id": report.run_id,
            "timestamp": report.timestamp.isoformat(),
            "total_cases": report.total_cases,
            "passed_cases": report.passed_cases,
            "failed_cases": report.failed_cases,
            "pass_rate_percent": report.pass_rate,
            "average_score": report.average_score,
            "accuracy": evaluator.calculate_accuracy(report.results),
            "avg_execution_time_seconds": evaluator.calculate_average_execution_time(report.results),
            
            # S1 / S2 breakdown
            "s1_rate_percent": s1_stats[0],
            "s1_passed": s1_stats[1],
            "s1_total": s1_stats[2],
            "pass_rate_s1": format_rate(s1_stats),
            "s2_rate_percent": s2_stats[0],
            "s2_passed": s2_stats[1],
            "s2_total": s2_stats[2],
            "pass_rate_s2": format_rate(s2_stats),

            # llmops operational metrics
            "total_cost_usd": evaluator.calculate_total_cost(report.results),
            "avg_cost_per_test_usd": evaluator.calculate_average_cost_per_test(report.results),
            "avg_latency_ms": evaluator.calculate_average_latency_ms(report.results),
            "cache_hit_rate_percent": evaluator.calculate_cache_hit_rate(report.results),
            "total_tokens": sum(r.total_tokens for r in report.results),
            "cost_efficiency": cost_efficiency,
        }
