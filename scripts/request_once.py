"""Send a single non-streaming request to a vLLM OpenAI-compatible server.

Usage on the server, after vLLM is running on the default port:

    uv run python scripts/request_once.py \
        --base-url http://127.0.0.1:8000 \
        --model meta-llama/Llama-3.1-8B-Instruct \
        --prompt "Say hi in one short sentence."

Prints the assistant text, request id, and token usage. No measurement here —
this is the smoke test before running ``scripts/measure_ttft_once.py``.
"""

from __future__ import annotations

import argparse
import json
import sys

from scripts._client import CompletionRequest, chat_completion, extract_assistant_text


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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    request = CompletionRequest(
        base_url=args.base_url,
        model=args.model,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )

    response = chat_completion(request, timeout=args.timeout)

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
