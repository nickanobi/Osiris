#!/usr/bin/env python3
"""
Osiris — llama3.1:70b Baseline Benchmark
Run on Mac Studio via SSH: python3 ~/agent/benchmark_70b.py
Tests speed and quality across five prompt categories.
"""

import json
import time
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.1:70b"

TESTS = [
    {
        "category": "Factual Recall",
        "prompt": "What is the capital of Australia and what is its population?",
    },
    {
        "category": "Multi-step Reasoning",
        "prompt": (
            "A train leaves Chicago at 8am travelling at 80mph toward New York (790 miles away). "
            "Another train leaves New York at 9am travelling at 100mph toward Chicago. "
            "At what time do they meet, and how far from Chicago?"
        ),
    },
    {
        "category": "Code Generation",
        "prompt": (
            "Write a Python function that takes a list of integers and returns a new list "
            "containing only the prime numbers, with a brief explanation of the approach."
        ),
    },
    {
        "category": "Long-form Writing",
        "prompt": (
            "Write a concise but thorough explanation of how large language models work, "
            "suitable for a technically literate but non-AI-expert audience. "
            "Cover training, inference, and tokenisation."
        ),
    },
    {
        "category": "Instruction Following",
        "prompt": (
            "List exactly 5 practical ways to reduce household energy consumption. "
            "Format each as: [Number]. [Title]: [One sentence explanation]. "
            "Do not include any introduction or conclusion."
        ),
    },
]


def run_test(category, prompt):
    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {
            "num_predict": 500,
            "temperature": 0.7,
        }
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            elapsed = time.time() - start
            data = json.loads(resp.read())
    except Exception as e:
        return {"error": str(e), "elapsed": time.time() - start}

    content = data.get("message", {}).get("content", "")
    eval_count = data.get("eval_count", 0)
    eval_duration_ns = data.get("eval_duration", 1)
    prompt_eval_count = data.get("prompt_eval_count", 0)
    prompt_eval_duration_ns = data.get("prompt_eval_duration", 1)

    tokens_per_sec = eval_count / (eval_duration_ns / 1e9) if eval_duration_ns else 0
    prompt_ms = prompt_eval_duration_ns / 1e6

    return {
        "category": category,
        "elapsed_s": round(elapsed, 2),
        "output_tokens": eval_count,
        "tokens_per_sec": round(tokens_per_sec, 1),
        "prompt_tokens": prompt_eval_count,
        "prompt_eval_ms": round(prompt_ms, 0),
        "response": content,
    }


def main():
    print(f"\n{'='*60}")
    print(f"  Osiris Benchmark — {MODEL}")
    print(f"  Mac Studio M3 96GB")
    print(f"{'='*60}\n")

    results = []
    for i, test in enumerate(TESTS, 1):
        print(f"[{i}/{len(TESTS)}] {test['category']} ...", end="", flush=True)
        result = run_test(test["category"], test["prompt"])
        results.append(result)

        if "error" in result:
            print(f" ERROR: {result['error']}")
        else:
            print(f" {result['tokens_per_sec']} tok/s  ({result['output_tokens']} tokens in {result['elapsed_s']}s)")

    print(f"\n{'='*60}")
    print("  RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"{'Category':<25} {'tok/s':>7} {'Out tokens':>11} {'Total time':>11} {'Prompt eval':>12}")
    print(f"{'-'*25} {'-'*7} {'-'*11} {'-'*11} {'-'*12}")
    total_tps = []
    for r in results:
        if "error" not in r:
            total_tps.append(r["tokens_per_sec"])
            print(f"{r['category']:<25} {r['tokens_per_sec']:>7} {r['output_tokens']:>11} {r['elapsed_s']:>10}s {r['prompt_eval_ms']:>10}ms")
        else:
            print(f"{r['category']:<25} {'ERROR':>7}")

    if total_tps:
        avg = sum(total_tps) / len(total_tps)
        print(f"\n  Average speed: {avg:.1f} tok/s")
        print(f"  Peak speed:    {max(total_tps):.1f} tok/s")
        print(f"  Min speed:     {min(total_tps):.1f} tok/s")

    print(f"\n{'='*60}")
    print("  RESPONSES")
    print(f"{'='*60}")
    for r in results:
        if "error" not in r:
            print(f"\n--- {r['category']} ---")
            print(r["response"])
            print()


if __name__ == "__main__":
    main()
