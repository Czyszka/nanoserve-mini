$ErrorActionPreference = "Stop"

Write-Host "==> Python"
python --version

Write-Host "==> uv"
uv --version

Write-Host "==> rg (ripgrep)"
rg --version

Write-Host "==> Sync dependencies"
uv sync --extra dev

Write-Host "==> Ruff"
uv run ruff check .

Write-Host "==> Pytest"
uv run pytest

Write-Host "==> Done"
