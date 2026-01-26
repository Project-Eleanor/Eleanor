# Contributing to Eleanor

First off, thank you for considering contributing to Eleanor! It's people like you that make Eleanor such a great tool for the DFIR community.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Style Guidelines](#style-guidelines)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Community](#community)

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to security@project-eleanor.dev.

## Getting Started

### Finding Something to Work On

- Check out our [Good First Issues](https://github.com/Project-Eleanor/Eleanor/labels/good%20first%20issue) for beginner-friendly tasks
- Look at [Help Wanted](https://github.com/Project-Eleanor/Eleanor/labels/help%20wanted) issues for more challenging contributions
- Browse the [Roadmap](https://github.com/Project-Eleanor/Eleanor/projects/1) to see planned features

### Before You Start

1. **Search existing issues** to avoid duplicating work
2. **Open an issue first** for significant changes to discuss the approach
3. **Fork the repository** and create your branch from `main`

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues. When you create a bug report, include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples** (config snippets, log outputs)
- **Describe the behavior you observed and what you expected**
- **Include screenshots or recordings** if applicable
- **Include your environment details** (OS, Docker version, browser)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

- **Use a clear and descriptive title**
- **Provide a detailed description** of the proposed functionality
- **Explain why this enhancement would be useful** to Eleanor users
- **List any similar features** in other DFIR tools for reference

### Code Contributions

#### Types of Contributions We Welcome

- **Bug fixes** — Fix issues and improve stability
- **Features** — Implement new functionality from the roadmap
- **Evidence parsers** — Add support for new artifact types
- **Detection rules** — Contribute correlation rules and signatures
- **Documentation** — Improve docs, add examples, fix typos
- **Tests** — Increase test coverage
- **Workbooks & Dashboards** — Share useful investigation templates

#### What We're NOT Looking For

- Major architectural changes without prior discussion
- Features that significantly increase complexity without clear benefit
- Changes that break backward compatibility without strong justification

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- Git

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
pytest

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install

# Run tests
npm test

# Start development server
ng serve --host 0.0.0.0
```

### Running with Docker

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Run backend tests in container
docker compose exec backend pytest
```

## Style Guidelines

### Python (Backend)

We follow [PEP 8](https://pep8.org/) with these additions:

- **Line length**: 100 characters maximum
- **Imports**: Use `isort` for sorting, grouped by standard/third-party/local
- **Type hints**: Required for all public functions
- **Docstrings**: Google style for modules, classes, and functions

```python
def process_evidence(
    evidence_id: str,
    parser_type: str,
    options: dict[str, Any] | None = None
) -> ParseResult:
    """Process evidence file with the specified parser.

    Args:
        evidence_id: Unique identifier for the evidence file.
        parser_type: Type of parser to use (e.g., 'evtx', 'registry').
        options: Optional parser-specific configuration.

    Returns:
        ParseResult containing parsed artifacts and metadata.

    Raises:
        ParserNotFoundError: If the specified parser type doesn't exist.
        EvidenceNotFoundError: If the evidence file cannot be located.
    """
```

**Tools**: `black`, `isort`, `flake8`, `mypy`

### TypeScript (Frontend)

We follow the [Angular Style Guide](https://angular.io/guide/styleguide):

- **Component selector prefix**: `app-`
- **File naming**: `feature-name.component.ts`, `feature-name.service.ts`
- **Standalone components**: Preferred for new components
- **Signals**: Use for reactive state management

```typescript
@Component({
  selector: 'app-evidence-viewer',
  standalone: true,
  imports: [CommonModule, MatButtonModule],
  template: `...`
})
export class EvidenceViewerComponent {
  // Signals for reactive state
  evidence = signal<Evidence | null>(null);
  loading = signal(false);

  // Computed values
  hasEvidence = computed(() => this.evidence() !== null);
}
```

**Tools**: `eslint`, `prettier`

### SQL & Database

- Use lowercase for SQL keywords (consistency with SQLAlchemy)
- Include meaningful index names
- Add comments for complex queries

### Git Workflow

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make your changes with clear, atomic commits
3. Push to your fork: `git push origin feature/my-feature`
4. Open a Pull Request

## Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, semicolons, etc.)
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `test`: Adding or correcting tests
- `chore`: Maintenance tasks (deps, CI, etc.)

### Examples

```
feat(parsers): add Windows Prefetch parser

Implements parser for Windows Prefetch files (.pf) to extract:
- Executable name and path
- Run count and timestamps
- Referenced files and directories

Closes #123
```

```
fix(api): handle null timestamps in evidence upload

Previously, evidence files without modification timestamps caused
a 500 error. Now defaults to upload time if not available.

Fixes #456
```

## Pull Request Process

### Before Submitting

- [ ] Code follows the style guidelines
- [ ] Self-review of your code
- [ ] Comments added for complex logic
- [ ] Documentation updated if needed
- [ ] Tests added/updated for changes
- [ ] All tests pass locally
- [ ] Commit messages follow conventions

### PR Description

Use the PR template and include:

- **Summary** of changes
- **Related issue(s)** being addressed
- **Type of change** (bug fix, feature, breaking change)
- **Testing performed**
- **Screenshots** for UI changes

### Review Process

1. A maintainer will review your PR
2. Address any requested changes
3. Once approved, a maintainer will merge
4. Your contribution will be included in the next release!

### After Merge

- Delete your feature branch
- Celebrate your contribution!

## Community

### Getting Help

- **GitHub Discussions**: Ask questions, share ideas
- **Discord**: Real-time chat with the community (coming soon)
- **Documentation**: Check the [docs](docs/) folder

### Recognition

Contributors are recognized in:
- The [Contributors](https://github.com/Project-Eleanor/Eleanor/graphs/contributors) page
- Release notes for significant contributions
- The project README for major features

---

Thank you for contributing to Eleanor! Your efforts help make DFIR more accessible to everyone.
