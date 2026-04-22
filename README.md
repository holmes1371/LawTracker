# LawTracker

A Python program to track when specific laws are updated.

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows (bash): .venv/Scripts/activate | PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Run

```bash
python -m lawtracker
```

## Test

```bash
pytest
```

## Project layout

```
src/lawtracker/   # package source
tests/            # pytest tests
pyproject.toml    # project metadata & dependencies
```
