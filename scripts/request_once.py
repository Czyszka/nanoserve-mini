"""Send a single non-streaming request to a vLLM OpenAI-compatible server.

Usage on the server, after vLLM is running on the default port:

    uv run python -m scripts.request_once \
        --base-url http://127.0.0.1:8000 \
        --model meta-llama/Llama-3.1-8B-Instruct \
        --prompt "Say hi in one short sentence."

Prints the assistant text, request id, and token usage. No measurement here —
this is the smoke test before running ``scripts/measure_ttft_once.py``.

With --run-id or --output, also writes a JSON result record.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from scripts._client import CompletionRequest, chat_completion, extract_assistant_text
from scripts._metrics import RunControls, get_git_commit, now_iso, resolve_output_path

_BENCHMARK_MODE = "singlestream_lite_correctness"
_METHODOLOGY = "mlperf_inspired_lite"
_SCRIPT_NAME = "request_once.py"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Single non-streaming chat completion against a vLLM server.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL of the vLLM server (default: %(default)s).",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Model name as registered by the vLLM server (e.g. the HF repo id).",
    )
    parser.add_argument(
        "--prompt",
        default="Say hi in one short sentence.",
        help="User prompt to send (default: %(default)r).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=64,
        help="max_tokens for the request (default: %(default)s).",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature (default: %(default)s).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="HTTP timeout in seconds (default: %(default)s).",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print the full raw JSON response instead of the formatted summary.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write result JSON to this path. Overrides --run-id path.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run identifier. Sets output to results/runs/<run_id>/"
             f"{_BENCHMARK_MODE}/result.json unless --output is also given.",
    )
    parser.add_argument("--dtype", default=None, help="Model dtype, e.g. bfloat16.")
    parser.add_argument("--quantization", default=None)
    parser.add_argument("--gpu-model", default=None, help="e.g. 'H200 NVL'.")
    parser.add_argument("--vllm-version", default=None)
    parser.add_argument("--max-model-len", type=int, default=None)
    parser.add_argument("--max-num-seqs", type=int, default=None)
    parser.add_argument("--max-num-batched-tokens", type=int, default=None)
    parser.add_argument("--workload", default="single-prompt-smoke")
    parser.add_argument("--notes", default=None)
    return parser.parse_args(argv)


def build_record(
    *,
    request: CompletionRequest,
    controls: RunControls,
    response: dict[str, Any] | None,
    e2e_seconds: float | None,
    error: str | None,
) -> dict[str, Any]:
    if response is not None:
        text = extract_assistant_text(response)
        usage = response.get("usage") or {}
        record: dict[str, Any] = {
            "schema": "nanoserve-mini.request-once.v1",
            "methodology": _METHODOLOGY,
            "benchmark_mode": _BENCHMARK_MODE,
            "timestamp": now_iso(),
            "controls": controls.as_dict(),
            "request": {
                "prompt": request.prompt,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
            },
            "metrics": {
                "e2e_seconds": e2e_seconds,
                "output_chars": len(text),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "completed": True,
            },
            "response": {
                "id": response.get("id", ""),
                "model": response.get("model", request.model),
            },
            "output_text": text,
            "error": None,
        }
    else:
        record = {
            "schema": "nanoserve-mini.request-once.v1",
            "methodology": _METHODOLOGY,
            "benchmark_mode": _BENCHMARK_MODE,
            "timestamp": now_iso(),
            "controls": controls.as_dict(),
            "request": {
                "prompt": request.prompt,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
            },
            "metrics": {
                "e2e_seconds": e2e_seconds,
                "output_chars": 0,
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "completed": False,
            },
            "response": None,
            "output_text": None,
            "error": error,
        }
    return record


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    output_path_str = resolve_output_path(
        run_id=args.run_id,
        explicit_path=args.output,
        benchmark_mode=_BENCHMARK_MODE,
        filename="result.json",
        fallback=None,
    )

    request = CompletionRequest(
        base_url=args.base_url,
        model=args.model,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )
    controls = RunControls(
        model=args.model,
        base_url=args.base_url,
        dtype=args.dtype,
        quantization=args.quantization,
        gpu_model=args.gpu_model,
        vllm_version=args.vllm_version,
        max_model_len=args.max_model_len,
        max_num_seqs=args.max_num_seqs,
        max_num_batched_tokens=args.max_num_batched_tokens,
        decoding={"temperature": args.temperature, "max_tokens": args.max_tokens},
        warmup_runs=0,
        measured_runs=1,
        workload=args.workload,
        notes=args.notes,
        run_id=args.run_id,
        script_name=_SCRIPT_NAME,
        git_commit=get_git_commit(),
    )

    response: dict[str, Any] | None = None
    error: str | None = None
    e2e_seconds: float | None = None

    t0 = time.perf_counter()
    try:
        response = chat_completion(request, timeout=args.timeout)
        e2e_seconds = time.perf_counter() - t0
    except Exception as exc:  # noqa: BLE001
        e2e_seconds = time.perf_counter() - t0
        error = f"{type(exc).__name__}: {exc}"

    if error is not None:
        if output_path_str is not None:
            record = build_record(
                request=request,
                controls=controls,
                response=None,
                e2e_seconds=e2e_seconds,
                error=error,
            )
            out = Path(output_path_str)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False),
                encoding="utf-8",
            )
            print(f"ERROR: {error}", file=sys.stderr)
            print(f"saved: {out}", file=sys.stderr)
        else:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    assert response is not None

    if output_path_str is not None:
        record = build_record(
            request=request,
            controls=controls,
            response=response,
            e2e_seconds=e2e_seconds,
            error=None,
        )
        out = Path(output_path_str)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )
        print(f"saved: {out}")

    if args.raw:
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 0

    text = extract_assistant_text(response)
    usage = response.get("usage") or {}
    request_id = response.get("id", "")
    model = response.get("model", args.model)

    print(f"id:    {request_id}")
    print(f"model: {model}")
    print(f"usage: prompt={usage.get('prompt_tokens')} "
          f"completion={usage.get('completion_tokens')} "
          f"total={usage.get('total_tokens')}")
    print("---")
    print(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
