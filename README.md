<<<<<<< HEAD
# 🏛️ Central Think Tank

An autonomous multi-agent system with 5 AI-powered departments that work, communicate, and produce strategic documents — all running locally on your machine.

## Departments

| Code | Name | Schedule |
|------|------|----------|
| HF | Health & Welfare | Daily 08:00 |
| FIN | Finance & Resources | Monday 09:00 |
| RES | Research & Intelligence | Daily 10:00 |
| ING | Engineering & Science | Tuesday 11:00 |
| STR | Strategy & Planning | Monday 07:00 |

## Architecture

- **AI Backend**: Claude API (heavy tasks) + Ollama (routine), with automatic fallback
- **Internal Mail**: SQLite-backed inter-department messaging with threads and priorities
- **Draft Vault**: All AI outputs stored as drafts for your approval/rejection
- **Scheduler**: APScheduler cron triggers per department
- **Web Dashboard**: Full browser UI at `http://localhost:8000`
- **Email Digest**: Daily SMTP notification of pending drafts

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure
#    Edit config.yaml — add your Claude API key, email credentials, Ollama URL

# 3. Run
python run.py
```

Then open `http://localhost:8000` in your browser.

## Config

Edit `config.yaml`:

```yaml
ai:
  claude:
    api_key: "sk-ant-..."     # Your Anthropic API key
  ollama:
    base_url: "http://localhost:11434"
    model: "llama3"           # Or mistral, phi3, etc.

email:
  username: "you@gmail.com"
  password: "your-app-password"
  recipient: "you@gmail.com"
```

## Dashboard

| Section | Description |
|---------|-------------|
| Dashboard | Live dept overview, run cycles manually |
| Drafts | Review, approve, or reject AI-generated documents |
| Mail Room | Browse all inter-department communications |
| Department pages | Per-dept projects, drafts, mail |
| Audit Log | Full activity history |
| Projects | All active projects across departments |

## Running a Cycle

- **Manual**: Click "Run Cycle" on any department card or use "Run All Departments"
- **Automatic**: Each department runs on its configured cron schedule when the server is on
- After each cycle, pending drafts appear in the Vault and trigger an email digest
=======
# ThinkTank
Personal think-tank
>>>>>>> origin/main
