import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Daily token limits — adjust these as needed
DAILY_LIMITS = {
    'haiku_input_tokens':  200_000,
    'haiku_output_tokens':  50_000,
    'sonnet_input_tokens':  20_000,
    'sonnet_output_tokens': 10_000,
}

# Approximate costs per 1000 tokens in USD (as of mid-2025)
COSTS_PER_1K = {
    'haiku_input':   0.00025,
    'haiku_output':  0.00125,
    'sonnet_input':  0.003,
    'sonnet_output': 0.015,
}

# In-memory usage tracker for current run
_usage = {
    'haiku_input_tokens':  0,
    'haiku_output_tokens': 0,
    'sonnet_input_tokens': 0,
    'sonnet_output_tokens': 0,
}


def reset_usage():
    """Reset usage counters at start of each cron run."""
    for key in _usage:
        _usage[key] = 0


def record_usage(model: str, input_tokens: int, output_tokens: int):
    """
    Record token usage after each LLM call.
    model: 'haiku' or 'sonnet'
    """
    if model == 'haiku':
        _usage['haiku_input_tokens'] += input_tokens
        _usage['haiku_output_tokens'] += output_tokens
    elif model == 'sonnet':
        _usage['sonnet_input_tokens'] += input_tokens
        _usage['sonnet_output_tokens'] += output_tokens


def is_within_budget(model: str) -> bool:
    """
    Check if we are still within daily token limits
    before making another LLM call.
    Returns False if limit exceeded — caller should stop.
    """
    if model == 'haiku':
        if _usage['haiku_input_tokens'] >= DAILY_LIMITS['haiku_input_tokens']:
            print(f"BUDGET GUARD: Haiku input token limit reached "
                  f"({_usage['haiku_input_tokens']:,} tokens)")
            return False
        if _usage['haiku_output_tokens'] >= DAILY_LIMITS['haiku_output_tokens']:
            print(f"BUDGET GUARD: Haiku output token limit reached "
                  f"({_usage['haiku_output_tokens']:,} tokens)")
            return False
    elif model == 'sonnet':
        if _usage['sonnet_input_tokens'] >= DAILY_LIMITS['sonnet_input_tokens']:
            print(f"BUDGET GUARD: Sonnet input token limit reached "
                  f"({_usage['sonnet_input_tokens']:,} tokens)")
            return False
        if _usage['sonnet_output_tokens'] >= DAILY_LIMITS['sonnet_output_tokens']:
            print(f"BUDGET GUARD: Sonnet output token limit reached "
                  f"({_usage['sonnet_output_tokens']:,} tokens)")
            return False
    return True


def get_usage_summary() -> dict:
    """
    Return current usage and estimated cost for this run.
    """
    haiku_cost = (
        (_usage['haiku_input_tokens'] / 1000) * COSTS_PER_1K['haiku_input'] +
        (_usage['haiku_output_tokens'] / 1000) * COSTS_PER_1K['haiku_output']
    )
    sonnet_cost = (
        (_usage['sonnet_input_tokens'] / 1000) * COSTS_PER_1K['sonnet_input'] +
        (_usage['sonnet_output_tokens'] / 1000) * COSTS_PER_1K['sonnet_output']
    )
    total_cost = haiku_cost + sonnet_cost

    return {
        'haiku_input_tokens':  _usage['haiku_input_tokens'],
        'haiku_output_tokens': _usage['haiku_output_tokens'],
        'sonnet_input_tokens': _usage['sonnet_input_tokens'],
        'sonnet_output_tokens': _usage['sonnet_output_tokens'],
        'haiku_cost_usd':  round(haiku_cost, 6),
        'sonnet_cost_usd': round(sonnet_cost, 6),
        'total_cost_usd':  round(total_cost, 6),
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


def print_usage_summary():
    """Print a readable usage summary to console."""
    summary = get_usage_summary()
    print("\n--- Token Usage Summary ---")
    print(f"Haiku  — input: {summary['haiku_input_tokens']:,} | "
          f"output: {summary['haiku_output_tokens']:,} | "
          f"cost: ${summary['haiku_cost_usd']:.6f}")
    print(f"Sonnet — input: {summary['sonnet_input_tokens']:,} | "
          f"output: {summary['sonnet_output_tokens']:,} | "
          f"cost: ${summary['sonnet_cost_usd']:.6f}")
    print(f"Total cost this run: ${summary['total_cost_usd']:.6f}")
    print("---------------------------\n")