# 🤝 Contributing to Tagr

First off, thank you for considering contributing to Tagr! Every contribution matters — whether it's a bug fix, a new feature, improved documentation, or even a question.

---

## 📋 Table of Contents

- [Code of Conduct](#-code-of-conduct)
- [Getting Started](#-getting-started)
- [How to Contribute](#-how-to-contribute)
- [Development Setup](#-development-setup)
- [Coding Standards](#-coding-standards)
- [Commit Guidelines](#-commit-guidelines)
- [Pull Request Process](#-pull-request-process)
- [Reporting Bugs](#-reporting-bugs)
- [Requesting Features](#-requesting-features)

---

## 📜 Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment. Please:

- Be welcoming and considerate in your language
- Respect differing viewpoints and experiences
- Accept constructive criticism gracefully
- Focus on what is best for the community and the project

---

## 🚀 Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/your-username/tagr.git
   cd tagr
   ```
3. **Create a branch** for your work:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Set up** the development environment (see below)

---

## 💡 How to Contribute

### Types of Contributions We Welcome

| Type                  | Examples                                                  |
|-----------------------|-----------------------------------------------------------|
| 🐛 **Bug Fixes**      | Fix broken endpoints, UI glitches, query errors           |
| ✨ **Features**        | New API endpoints, UI components, ML improvements         |
| 📖 **Documentation**  | README updates, API docs, inline code comments            |
| 🧪 **Tests**          | Unit tests, integration tests, end-to-end tests           |
| 🎨 **UI/UX**          | Frontend improvements, design refinements                 |
| ⚡ **Performance**     | Query optimization, caching, batch processing improvements|

---

## 🛠️ Development Setup

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
- Python 3.11+
- Git

### Start the Full Stack

```bash
# Copy environment config
cp .env.example .env

# Build and start all services
docker-compose up -d --build

# Verify everything is running
docker-compose ps
```

### Running Locally (Without Docker)

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Start the web server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> **Note:** You'll need PostgreSQL (with pgvector) and MinIO running locally.

---

## 📏 Coding Standards

### Python (Backend)

- Follow **PEP 8** style guidelines
- Use **type hints** for function parameters and return types
- Write **docstrings** for all public functions and classes
- Keep functions focused — one function, one responsibility
- Use meaningful variable and function names

```python
# ✅ Good
async def get_photo_tags(photo_id: uuid.UUID, db: Session) -> dict:
    """Retrieve all tags associated with a photo."""
    ...

# ❌ Bad
async def get_tags(id, db):
    ...
```

### Frontend (HTML/CSS/JS & React Native)

We support two frontends, but only the FastAPI static frontend is actively integrated into our development environment:

#### 1. FastAPI Static Frontend (Active/Primary)
Located at [app/static/](file:///c:/Workspace/face-rec-sm/app/static/). This is the primary web UI served directly by FastAPI.
- Use semantic HTML5 elements and Vanilla CSS.
- Keep JavaScript modular, cleanly structured, and well-commented.
- Follow the design parameters in [Tagr_Design_System.md](file:///c:/Workspace/face-rec-sm/docs/Tagr_Design_System.md).

#### 2. React Native / Expo Frontend (Optional Mobile Client)
Located at [frontend/](file:///c:/Workspace/face-rec-sm/frontend/).
- This mobile app is **not** included in the Docker orchestration.
- If you want to work on it, navigate to `frontend/`, run `npm install`, and use `npm start` to run the Expo developer server.
- Follow standard React Native best practices.

### General
- No hardcoded secrets or credentials in code
- Use environment variables for all configuration
- Keep imports organized (stdlib → third-party → local)

---

## 📝 Commit Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

### Types

| Type       | Description                                          |
|------------|------------------------------------------------------|
| `feat`     | A new feature                                        |
| `fix`      | A bug fix                                            |
| `docs`     | Documentation only changes                           |
| `style`    | Code style changes (formatting, no logic change)     |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test`     | Adding or updating tests                             |
| `chore`    | Build process, tooling, or dependency changes        |

### Examples

```bash
feat(auth): add face enrollment endpoint
fix(batcher): resolve race condition in flush queue
docs(readme): update API reference table
refactor(storage): extract MinIO client into helper class
```

---

## 🔀 Pull Request Process

1. **Update your branch** with the latest `main`:
   ```bash
   git fetch origin
   git rebase origin/main
   ```

2. **Ensure everything works**:
   ```bash
   docker-compose up -d --build
   # Test your changes manually or with automated tests
   ```

3. **Push your branch**:
   ```bash
   git push origin feature/your-feature-name
   ```

4. **Open a Pull Request** on GitHub with:
   - A clear title following commit conventions
   - A description of **what** changed and **why**
   - Screenshots for any UI changes
   - Reference to any related issues (e.g., `Closes #42`)

5. **Address review feedback** — push additional commits to your branch as needed

### PR Checklist

- [ ] Code follows the project's coding standards
- [ ] No hardcoded secrets or credentials
- [ ] New endpoints are documented in the API reference
- [ ] Docker build succeeds (`docker-compose up --build`)
- [ ] Existing functionality is not broken

---

## 🐛 Reporting Bugs

Found a bug? [Open an issue](https://github.com/your-username/tagr/issues/new) with:

- **Title**: A short, descriptive summary
- **Environment**: OS, Docker version, browser (if frontend)
- **Steps to Reproduce**: Numbered steps to trigger the bug
- **Expected Behavior**: What should have happened
- **Actual Behavior**: What actually happened
- **Screenshots/Logs**: Docker logs, browser console, or screenshots

```bash
# Grab logs for bug reports
docker-compose logs web > web_logs.txt
docker-compose logs inference > inference_logs.txt
```

---

## 💡 Requesting Features

Have an idea? [Open a feature request](https://github.com/your-username/tagr/issues/new) with:

- **Problem**: What problem does this solve?
- **Proposed Solution**: How should it work?
- **Alternatives Considered**: Other approaches you thought of
- **Additional Context**: Mockups, references, or examples

---

## 🙏 Thank You!

Every contribution, no matter how small, helps make Tagr better. We appreciate your time and effort!
