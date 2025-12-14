# Contributing to OpenAPI-MCP

Thank you for your interest in contributing! We welcome all contributions, whether it's reporting a bug, suggesting a feature, or submitting a pull request.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git

### Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/gujord/OpenAPI-MCP.git
   cd OpenAPI-MCP
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install development dependencies**
   ```bash
   make install-dev
   ```
   This installs the package in editable mode with dev dependencies, sets up pre-commit hooks, and installs linting/testing tools.

4. **Verify the setup**
   ```bash
   make check
   ```
   This runs all checks (lint, type-check, security, tests).

### Available Make Commands

| Command | Description |
|---------|-------------|
| `make install` | Install package in production mode |
| `make install-dev` | Install package with dev dependencies |
| `make test` | Run all tests |
| `make test-cov` | Run tests with coverage report |
| `make lint` | Run linting checks (flake8, isort) |
| `make format` | Format code with black and isort |
| `make type-check` | Run mypy type checking |
| `make security` | Run security checks with bandit |
| `make check` | Run all checks (lint, type-check, security, test) |
| `make build` | Build package for distribution |
| `make clean` | Remove build artifacts |
| `make run` | Run the MCP server (requires OPENAPI_URL env var) |
| `make run-example` | Run with example Petstore API |

### Running the Server Locally

```bash
# With a custom OpenAPI spec
OPENAPI_URL=https://api.example.com/openapi.json make run

# With the Petstore example
make run-example
```

## How to Contribute

### 1. Reporting Issues

If you encounter a bug, have a question, or want to suggest an improvement, please open an [issue](https://github.com/gujord/OpenAPI-MCP/issues) and provide the following details:

- A clear title and description of the issue
- Steps to reproduce (if applicable)
- Expected vs. actual behavior
- Any relevant logs, screenshots, or error messages

### 2. Submitting a Pull Request

If you want to contribute code, follow these steps:

1. **Fork the repository** and create your branch from `main`.
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**, ensuring your code follows the project's coding style.

3. **Format and lint your code** before committing:
   ```bash
   make format
   make lint
   ```

4. **Run the tests** to verify they pass:
   ```bash
   make test
   ```

5. **Commit and push your changes** with a meaningful commit message.
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   git push origin feature/your-feature-name
   ```

6. **Open a pull request (PR)** and include:
   - A description of the changes
   - Any relevant issue numbers (e.g., "Closes #12")
   - Steps to test your changes

### 3. Code Style & Best Practices

- **Formatting**: We use [Black](https://github.com/psf/black) with a line length of 120 characters
- **Import sorting**: We use [isort](https://github.com/pycqa/isort) with the black profile
- **Linting**: We use [flake8](https://flake8.pycqa.org/) for linting
- **Type hints**: Add type hints to new functions and methods
- **Security**: We use [bandit](https://bandit.readthedocs.io/) for security checks
- **Pre-commit hooks**: All checks run automatically on commit via pre-commit

### 4. Commit Message Convention

We follow conventional commits:

- `feat:` - A new feature
- `fix:` - A bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

### 5. Project Structure

```
OpenAPI-MCP/
├── src/openapi_mcp/       # Main source code
│   ├── __init__.py
│   ├── fastmcp_server.py  # FastMCP server implementation
│   ├── config.py          # Configuration management
│   ├── auth.py            # Authentication handling
│   ├── openapi_loader.py  # OpenAPI spec loading
│   ├── request_handler.py # HTTP request handling
│   └── ...
├── test/                  # Test files
├── .github/workflows/     # CI/CD workflows
├── Makefile               # Development commands
├── pyproject.toml         # Project configuration
└── README.md
```

### 6. Reviewing & Merging

- PRs will be reviewed as soon as possible.
- Constructive feedback is encouraged; be open to suggestions.
- Once approved, a maintainer will merge your changes.

### 7. Communication

- Be respectful and professional in discussions.
- If you need help, feel free to ask in an issue or discussion thread.

## License

By contributing, you agree that your contributions will be licensed under the MIT license.

Happy coding!
