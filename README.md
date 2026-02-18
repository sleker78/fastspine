# FastStack

## Development Setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and Python environment handling.

### Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   uv sync --extra dev
   ```

### Authentication for Private PyPI Index

This project uses a private PyPI index. You'll need to configure authentication:

```bash
# Set up authentication for the private index
uv index add mdpiai https://gitlab.mdpi.com:8081/api/v4/groups/485/-/packages/pypi/simple --username <your-username>
```

### Development Commands

Use the provided Makefile targets:

- `make install` - Install dependencies
- `make test` - Run tests
- `make ruff` - Run linter
- `make mypy` - Run type checker
- `make check` - Run all checks (tests, linting, etc.)
- `make install_pre_commit` - Setup pre-commit hooks

Or use uv directly:

- `uv run pytest` - Run tests
- `uv run ruff check .` - Run linter
- `uv run mypy faststack` - Run type checker
- `uv add <package>` - Add new dependency
- `uv remove <package>` - Remove dependency
