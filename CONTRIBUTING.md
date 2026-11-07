# Contributing to ILA Manager

Thank you for your interest in contributing to ILA Manager!

> **English** | [ภาษาไทย](CONTRIBUTING.th.md)

## Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/<your-username>/ILA-Manager.git
   cd ILA-Manager
   ```

2. Create a virtual environment and install in editable mode with dev dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. Launch the development server:
   ```bash
   ila-manager --port 8765
   ```

## Workflow & Coding Standards

- **Branching**: Create a branch off `main` for your feature or bug fix:
  ```bash
  git checkout -b feat/your-feature-name
  ```
- **Commit Messages**: Follow [Conventional Commits](https://www.conventionalcommits.org/):
  - `feat: add support for SystemVerilog interfaces`
  - `fix: resolve generic arithmetic in architecture declarative region`
  - `docs: update Thai README guide`
  - `test: add fixture for 2D VHDL array`
- **Linting & Code Quality**: Run `ruff` before committing:
  ```bash
  ruff check .
  ```
- **Testing**: Add unit tests in `tests/` and make sure all tests pass:
  ```bash
  pytest -v
  ```
- **Zero Frontend Build Step**: The web UI in `src/ila_manager/web/` is written in standard ES modules and CSS. Do not introduce npm / webpack / vite build steps for the main runtime.

## Submitting Pull Requests

1. Push your branch to GitHub.
2. Open a Pull Request against `main`.
3. Provide a clear description of changes and attach test results or screenshots for UI modifications.
