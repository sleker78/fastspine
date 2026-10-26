PHONY: install_pre_commit
install_pre_commit:  ## configure and install pre commit tool
	uv run pre-commit install

.PHONY: uninstall_pre_commit
uninstall_pre_commit:  ## configure and install pre commit tool
	uv run pre-commit uninstall

.PHONY: install
install:  ## Install the project, its development dependencies, and every optional extra
	uv sync --group dev --all-extras

.PHONY: ruff
ruff:  ## Run ruff linter
	uv run ruff check .
.PHONY: ruff-formatter
ruff-formatter:  ## Run ruff linter
	uv run ruff format  .

.PHONY: deptry
deptry:  ## Run deptry dependency checker
	uv run deptry .

.PHONY: test
test:  ## Run unittests with pytest
	uv run pytest

.PHONY: check
check: test ruff-formatter ruff deptry mypy ## Run all checks

.PHONY: mypy
mypy:  ## Run mypy type checker
	uv run mypy fastspine
	
