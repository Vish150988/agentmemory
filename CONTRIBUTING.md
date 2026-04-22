# Contributing to CrossAgentMemory

Thanks for your interest in contributing! 🎉

## Getting Started

1. Fork the repo: https://github.com/Vish150988/crossagentmemory
2. Clone your fork:
   ```bash
   git clone https://github.com/<your-username>/crossagentmemory.git
   cd crossagentmemory
   ```
3. Install in editable mode with dev dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
4. Run the tests to make sure everything is green:
   ```bash
   python -m pytest tests/ -v
   ```

## Development Workflow

- Create a branch: `git checkout -b feature/your-feature-name`
- Make your changes
- Run tests and linting:
  ```bash
  python -m ruff check crossagentmemory/ tests/
  python -m pytest tests/ -v
  ```
- Commit and push
- Open a Pull Request

## Adding a New Storage Backend

Backends live in `crossagentmemory/backends/`. To add one:

1. Subclass `MemoryBackend` from `crossagentmemory.backends.base`
2. Implement all abstract methods
3. Add it to the factory in `crossagentmemory/backends/__init__.py`
4. Add tests in `tests/test_storage_backends.py`
5. Update README with install instructions (e.g. `pip install crossagentmemory[chroma]`)

## Adding an Importer

Importers live in `crossagentmemory/importers.py`. Add a new function and wire it into the CLI in `crossagentmemory/cli.py`.

## Code Style

- We use **Ruff** for linting and import sorting (`python -m ruff check .`)
- Line length: 100 characters
- Target Python: 3.10+

## Questions?

Open a [Discussion](https://github.com/Vish150988/crossagentmemory/discussions) or ping us on the issue tracker.
