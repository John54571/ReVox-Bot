# Contributing Guide (CONTRIBUTING.md)

Thank you for your interest in contributing to **ReVox**! All contributions (bug reports, UI enhancements, documentation improvements, or new features) are welcome.

---

## 🛠️ Getting Started

1. **Fork** the repository on GitHub.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ReVox-Bot.git
   cd ReVox-Bot
   ```
3. Create a descriptive branch for your changes:
   ```bash
   git checkout -b feature/new-improvement
   ```
4. Set up the virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   copy .env.example .env
   ```

---

## 🧪 Local Testing

Before submitting a Pull Request, verify that all modules import cleanly:
```powershell
.\.venv\Scripts\python -c "import bot, panel; print('ReVox OK')"
```

If you made changes to the web dashboard (`web/index.html`), test it in your browser by running:
```powershell
.\.venv\Scripts\python panel.py
```

---

## 📝 Code Style & Best Practices

- **Python:** Clean, asynchronous (`asyncio`), typed where appropriate, following PEP 8.
- **Frontend:** Maintain the minimalist, dark aesthetic without adding heavy external dependencies (Tailwind CDN, React, or Node.js) to keep the dashboard lightweight in a single HTML/Vanilla JS file.
- **Commits:** Clear commit messages following Conventional Commits (`feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`).

---

## 🚀 Submitting Your Pull Request

1. Make sure no `.env` file or personal credentials are included in your commits.
2. Push your changes to your fork:
   ```bash
   git push origin feature/new-improvement
   ```
3. Open a Pull Request against the main repository explaining the problem your changes solve and how to test them.
