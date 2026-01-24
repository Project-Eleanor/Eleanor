# Contributing to Eleanor

Thank you for your interest in contributing to Eleanor! This document provides guidelines and information for contributors.

## Code of Conduct

Be respectful, inclusive, and considerate. We're building a tool to help defenders protect organizations - let's maintain that positive spirit in our community.

## Getting Started

### Development Environment

1. **Fork and clone** the repository
2. **Install prerequisites**:
   - Docker and Docker Compose
   - Python 3.12+
   - Node.js 20+
   - Angular CLI (`npm install -g @angular/cli`)

3. **Start infrastructure**:
   ```bash
   docker compose up -d postgres elasticsearch redis
   ```

4. **Backend setup**:
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -e ".[dev]"
   alembic upgrade head
   uvicorn app.main:app --reload
   ```

5. **Frontend setup**:
   ```bash
   cd frontend
   npm install
   ng serve
   ```

### Project Structure

```
eleanor/
├── backend/          # FastAPI backend
│   ├── app/
│   │   ├── api/      # API endpoints
│   │   ├── core/     # Business logic
│   │   ├── auth/     # Authentication providers
│   │   ├── adapters/ # External integrations
│   │   └── models/   # Database models
│   └── tests/
├── frontend/         # Angular frontend
│   └── src/app/
│       ├── core/     # Services, guards, interceptors
│       ├── shared/   # Shared components
│       ├── layout/   # App shell, navigation
│       └── features/ # Feature modules
└── docs/             # Documentation
```

## Development Guidelines

### Backend (Python)

- **Style**: Follow PEP 8, use Black for formatting
- **Type hints**: Use type annotations for all functions
- **Tests**: Write tests for new features using pytest
- **Docstrings**: Use Google-style docstrings

```python
def process_evidence(file_path: str, case_id: UUID) -> Evidence:
    """Process and hash evidence file.

    Args:
        file_path: Path to the evidence file
        case_id: UUID of the associated case

    Returns:
        Evidence object with computed hashes

    Raises:
        FileNotFoundError: If file doesn't exist
        PermissionError: If file isn't readable
    """
```

### Frontend (Angular/TypeScript)

- **Style**: Follow Angular style guide
- **Components**: Use standalone components where possible
- **State**: Use signals for reactive state
- **Tests**: Write unit tests with Jasmine/Karma

### Commit Messages

Use conventional commits:

```
feat: add timeline filtering by entity type
fix: correct ES|QL query escaping
docs: update API reference for evidence endpoints
refactor: simplify case lifecycle state machine
test: add integration tests for LDAP auth
```

### Pull Requests

1. **Create a feature branch** from `main`
2. **Make your changes** with appropriate tests
3. **Run tests locally**: `pytest` (backend), `ng test` (frontend)
4. **Submit PR** with clear description
5. **Address review feedback**

### PR Checklist

- [ ] Tests pass locally
- [ ] New features have tests
- [ ] Documentation updated if needed
- [ ] No sensitive data in commits
- [ ] Follows coding standards

## Areas for Contribution

### Good First Issues

- Documentation improvements
- UI/UX enhancements
- Test coverage
- Bug fixes

### Feature Development

- New adapters (EDR, SIEM integrations)
- Visualization components
- Automation/playbook features
- Performance optimizations

### Security Research

- Security review and hardening
- Penetration testing
- Vulnerability disclosure (see SECURITY.md)

## Questions?

- **GitHub Issues**: For bugs and feature requests
- **Discussions**: For questions and ideas

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
