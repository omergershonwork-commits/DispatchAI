from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import time

from app.evaluations.qwen_incident_eval import (
    check_accuracy,
    evaluate_extraction,
    failed_evaluation,
    load_evaluation_cases,
    passes_success_rate,
    success_rate,
)
from app.services.incident_extraction import IncidentExtractionService
from app.services.qwen_client import QwenClient, QwenClientError


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.90)
    parser.add_argument("--cases", default="app/evaluations/live_qwen_cases.json")
    parser.add_argument("--report", default="qwen-live-evaluation.json")
    args = parser.parse_args()

    model = required("QWEN_MODEL_NAME")
    cases = load_evaluation_cases(args.cases)
    if len(cases) < 10:
        raise RuntimeError("Live Qwen evaluation requires at least 10 cases.")

    client = QwenClient(
        base_url=required("QWEN_BASE_URL"),
        model_name=model,
        timeout_seconds=float(os.getenv("QWEN_TIMEOUT_SECONDS", "120")),
        headers_mode=os.getenv("QWEN_REQUEST_HEADERS_MODE", "none"),
        extra_headers_json=os.getenv("QWEN_EXTRA_HEADERS_JSON", ""),
    )
    service = IncidentExtractionService(client)
    retries = max(0, int(os.getenv("QWEN_EVAL_RETRIES", "2")))
    delay = max(0.0, float(os.getenv("QWEN_EVAL_DELAY_SECONDS", "0.5")))
    outcomes = []

    for index, case in enumerate(cases, 1):
        started = time.perf_counter()
        outcome = None
        for attempt in range(retries + 1):
            try:
                result = service.extract_from_text(case["message"])
                outcome = evaluate_extraction(
                    case,
                    result,
                    duration_seconds=time.perf_counter() - started,
                )
                break
            except QwenClientError as exc:
                if attempt == retries:
                    outcome = failed_evaluation(
                        case,
                        exc,
                        duration_seconds=time.perf_counter() - started,
                    )
                else:
                    time.sleep(min(8.0, 2.0 ** attempt))
            except Exception as exc:
                outcome = failed_evaluation(
                    case,
                    exc,
                    duration_seconds=time.perf_counter() - started,
                )
                break

        outcomes.append(outcome or failed_evaluation(case, "No result"))
        current = outcomes[-1]
        status = "PASS" if current.passed else "FAIL"
        failed = ",".join(current.failed_checks) or "none"
        print(f"[{index:02d}/{len(cases):02d}] {status} {current.name} failed={failed}")
        if delay and index < len(cases):
            time.sleep(delay)

    rate = success_rate(outcomes)
    accuracy = check_accuracy(outcomes)
    gate_passed = passes_success_rate(outcomes, args.threshold)
    passed = sum(item.passed for item in outcomes)
    report = {
        "model": model,
        "threshold": args.threshold,
        "comparison": "strictly_greater_than",
        "total_cases": len(outcomes),
        "passed_cases": passed,
        "failed_cases": len(outcomes) - passed,
        "success_rate": rate,
        "check_accuracy": accuracy,
        "gate_passed": gate_passed,
        "outcomes": [asdict(item) for item in outcomes],
    }
    Path(args.report).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"Qwen SR={rate:.2%}; checks={accuracy:.2%}; required SR > {args.threshold:.2%}")
    return 0 if gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
