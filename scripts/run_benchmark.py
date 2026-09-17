"""Run benchmark episodes from the command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.metrics import group_summary
from evaluation.runner import DEFAULT_AGENT_TYPES, DEFAULT_TASK_IDS, run_benchmark


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SurvivalAgent benchmark episodes.")
    parser.add_argument(
        "--agents",
        nargs="+",
        default=list(DEFAULT_AGENT_TYPES),
        help="Agent types to evaluate.",
    )
    parser.add_argument(
        "--tasks",
        nargs="+",
        default=list(DEFAULT_TASK_IDS),
        help="Task IDs to evaluate.",
    )
    parser.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        default=[1, 2, 3],
        help="Random seeds to evaluate.",
    )
    parser.add_argument(
        "--log-dir",
        default="logs/benchmark",
        help="Directory for episode trace logs.",
    )
    parser.add_argument(
        "--summary",
        default="evaluation/reports/latest_summary.json",
        help="Path for the benchmark summary JSON.",
    )
    parser.add_argument(
        "--memory-path",
        default=None,
        help="Optional JSON memory store shared by benchmark episodes.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Optional per-episode step limit override.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    episodes = run_benchmark(
        agent_types=tuple(args.agents),
        task_ids=tuple(args.tasks),
        seeds=tuple(args.seeds),
        log_dir=args.log_dir,
        memory_path=args.memory_path,
        max_steps=args.max_steps,
    )
    summary = group_summary(episodes)
    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
