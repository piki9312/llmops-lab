"""LLM Gateway - Log Visualization Dashboard

Streamlit app for visualizing gateway logs and metrics.

Usage:
    streamlit run src/llmops/dashboard.py
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
import streamlit as st


def load_logs(log_path: Path) -> List[Dict[str, Any]]:
    """Load JSONL logs from file.
    
    Args:
        log_path: Path to gateway.jsonl
        
    Returns:
        List of log entries
    """
    logs = []
    if log_path.exists():
        with open(log_path) as f:
            for line in f:
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return logs


def compute_metrics(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregate metrics from logs.
    
    Args:
        logs: List of log entries
        
    Returns:
        Dict with metrics
    """
    if not logs:
        return {
            "total_requests": 0,
            "success_rate": 0.0,
            "avg_latency_ms": 0.0,
            "total_tokens": 0,
            "json_generation_rate": 0.0,
            "total_cost_usd": 0.0,
            "avg_cost_usd": 0.0,
            "cache_hit_rate": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
            "rate_limited_count": 0,
        }
    
    total = len(logs)
    success = sum(1 for log in logs if log.get("error_type") is None)
    latencies = [log.get("latency_ms", 0) for log in logs]
    tokens = [log.get("token_usage", {}).get("total", 0) for log in logs]
    json_generated = sum(1 for log in logs if log.get("json_generated", False))
    schema_requests = sum(1 for log in logs if log.get("has_schema", False))
    costs = [log.get("cost_usd", 0.0) for log in logs]
    cache_hits = sum(1 for log in logs if log.get("cache_hit") is True)
    cache_misses = total - cache_hits
    rate_limited_count = sum(1 for log in logs if log.get("rate_limited") is True)
    
    return {
        "total_requests": total,
        "success_rate": (success / total * 100) if total > 0 else 0,
        "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
        "total_tokens": sum(tokens),
        "json_generation_rate": (json_generated / schema_requests * 100) 
                                if schema_requests > 0 else 0,
        "total_cost_usd": sum(costs),
        "avg_cost_usd": sum(costs) / len(costs) if costs else 0.0,
        "cache_hit_rate": (cache_hits / total * 100) if total > 0 else 0.0,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "rate_limited_count": rate_limited_count,
    }


def main():
    """Main dashboard app."""
    st.set_page_config(
        page_title="LLM Gateway Dashboard",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 LLM Gateway - Observability Dashboard")
    
    # Load logs
    log_path = Path("runs/logs/gateway.jsonl")
    logs = load_logs(log_path)
    
    if not logs:
        st.warning("⚠️ No logs found. Run some API requests first.")
        st.code("""
# Generate logs by calling the API:
python test_api.py

# Or start the server and make requests:
python -m uvicorn src.llmops.gateway:app --host 127.0.0.1 --port 8000
        """)
        return
    
    # Compute metrics
    metrics = compute_metrics(logs)
    
    # Display metrics
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
    with col1:
        st.metric("Total Requests", metrics["total_requests"])
    
    with col2:
        st.metric("Success Rate", f"{metrics['success_rate']:.1f}%")
    
    with col3:
        st.metric("Avg Latency", f"{metrics['avg_latency_ms']:.1f}ms")
    
    with col4:
        st.metric("Total Tokens", f"{metrics['total_tokens']:,}")
    
    with col5:
        st.metric("JSON Success", f"{metrics['json_generation_rate']:.1f}%")
    
    with col6:
        st.metric("Total Cost", f"${metrics['total_cost_usd']:.6f}")

    with col7:
        st.metric("Cache Hit Rate", f"{metrics['cache_hit_rate']:.1f}%")
    
    st.divider()
    
    # Convert logs to DataFrame
    df = pd.DataFrame(logs)
    
    # Add timestamp parsing
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601", utc=True)
        df = df.sort_values("timestamp")
    
    # Latency chart
    st.subheader("📈 Latency Over Time")
    if "latency_ms" in df.columns and "timestamp" in df.columns:
        latency_df = df[["timestamp", "latency_ms"]].copy()
        st.line_chart(latency_df.set_index("timestamp"))
    else:
        st.info("No latency data available")
    
    st.divider()
    
    # Token usage chart
    st.subheader("🔢 Token Usage")
    if "token_usage" in df.columns:
        token_data = []
        for idx, row in df.iterrows():
            usage = row.get("token_usage", {})
            token_data.append({
                "timestamp": row.get("timestamp"),
                "prompt": usage.get("prompt", 0),
                "completion": usage.get("completion", 0),
            })
        token_df = pd.DataFrame(token_data)
        if not token_df.empty and "timestamp" in token_df.columns:
            token_df["timestamp"] = pd.to_datetime(token_df["timestamp"], format="ISO8601", utc=True)
            token_chart_df = token_df.set_index("timestamp")[["prompt", "completion"]]
            st.area_chart(token_chart_df)
    else:
        st.info("No token usage data available")
    
    st.divider()
    
    # Cost analysis
    st.subheader("💰 Cost Analysis")
    if "cost_usd" in df.columns:
        cost_data = df[["timestamp", "cost_usd"]].copy()
        cost_data["timestamp"] = pd.to_datetime(cost_data["timestamp"], format="ISO8601", utc=True)
        cost_chart_df = cost_data.set_index("timestamp")
        st.line_chart(cost_chart_df)
        st.write(f"**Average Cost per Request:** ${metrics['avg_cost_usd']:.8f}")
    else:
        st.info("No cost data available")
    
    st.divider()
    
    # Error breakdown
    st.subheader("⚠️ Error Breakdown")
    error_counts = df["error_type"].value_counts()
    if not error_counts.empty:
        st.bar_chart(error_counts)
    else:
        st.success("✅ No errors!")
    
    st.divider()

    # Cache analysis
    st.subheader("🗄️ Cache Performance")
    if "cache_hit" in df.columns:
        cache_counts = df["cache_hit"].value_counts()
        hits = cache_counts.get(True, 0)
        misses = cache_counts.get(False, 0)
        st.write(f"Hits: {hits}, Misses: {misses}")
        st.bar_chart(cache_counts.rename(index={True: "hit", False: "miss"}))
    else:
        st.info("No cache data available")

    st.divider()

    # Rate limiting analysis
    st.subheader("⚡ Rate Limiting")
    if "rate_limited" in df.columns:
        rate_limited_total = metrics["rate_limited_count"]
        rate_limit_pct = (rate_limited_total / metrics["total_requests"] * 100) if metrics["total_requests"] > 0 else 0
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Rate Limited Requests", rate_limited_total, 
                     delta=f"{rate_limit_pct:.1f}% of total",
                     delta_color="inverse")
        
        with col2:
            # Breakdown by reason
            rate_limited_logs = [log for log in logs if log.get("rate_limited") is True]
            if rate_limited_logs:
                reasons = {}
                for log in rate_limited_logs:
                    reason = log.get("rate_limit_reason", "unknown")
                    reasons[reason] = reasons.get(reason, 0) + 1
                st.write("**Rate Limit Reasons:**")
                for reason, count in reasons.items():
                    st.write(f"- {reason}: {count}")
            else:
                st.success("✅ No rate limiting occurred")
    else:
        st.info("No rate limiting data available")

    st.divider()
    
    # Prompt version analysis
    st.subheader("📝 Prompt Version Usage")
    if "prompt_version_used" in df.columns:
        version_counts = df["prompt_version_used"].value_counts()
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Version Distribution:**")
            st.bar_chart(version_counts)
        with col2:
            st.write("**Version Details:**")
            for version, count in version_counts.items():
                pct = (count / len(df)) * 100
                st.write(f"- v{version}: {count} requests ({pct:.1f}%)")
    else:
        st.info("No prompt version data available")
    
    st.divider()
    
    # Recent requests table
    st.subheader("📋 Recent Requests")
    display_cols = ["timestamp", "request_id", "provider", "model", 
                    "prompt_version_used", "latency_ms", "cost_usd", "cache_hit", 
                    "rate_limited", "error_type"]
    available_cols = [col for col in display_cols if col in df.columns]
    
    if available_cols:
        recent_df = df[available_cols].tail(20).sort_values("timestamp", ascending=False)
        st.dataframe(recent_df, use_container_width=True)
    
    # Refresh button
    st.divider()
    if st.button("🔄 Refresh Data"):
        st.rerun()


if __name__ == "__main__":
    main()
