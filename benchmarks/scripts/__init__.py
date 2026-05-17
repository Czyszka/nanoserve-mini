"""nanoserve-mini measurement scripts.

Each script in this package is intended to be run as a module, not as a path:

    uv run python -m scripts.check_server_env
    uv run python -m scripts.request_once --model ...
    uv run python -m scripts.measure_ttft_once --model ...
    uv run python -m scripts.run_sequential_benchmark --model ...

Module execution makes the relative imports between ``scripts._client``,
``scripts._metrics`` and the entry-point scripts work without needing
``sys.path`` tricks.
"""
