# Docker Deployment

This project can run as a Docker Compose stack with the API, Langfuse, and PostgreSQL.

## Prerequisites

- Docker Desktop or Docker Engine
- Docker Compose
- `.env` created from `.env.example`

Minimum useful environment variables:

```text
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GOOGLE_API_KEY=...
GROQ_API_KEY=...
EMAIL_SCHEDULER_ENABLED=false
```

Set only the providers you plan to use. Keep `EMAIL_SCHEDULER_ENABLED=false` unless you intentionally want the API process to run the legacy in-process email timer.

## Start

```bash
docker-compose up -d
```

Or use the helper scripts:

```bash
bash docker-deploy.sh setup
```

Windows:

```cmd
docker-deploy.bat setup
```

## Verify

```bash
docker-compose ps
curl http://localhost:8000/health
```

Open:

```text
API docs:  http://localhost:8000/docs
Langfuse:  http://localhost:3000
```

## Logs

```bash
docker-compose logs -f be-invest
docker-compose logs -f langfuse-server
```

## Data

Generated broker data is stored under `data/output/` in the project workspace. Langfuse uses the PostgreSQL service configured in `docker-compose.yml`.

Important files:

```text
data/output/broker_cost_analyses.json
data/output/fee_rules.json
data/output/cost_comparison_tables.json
data/output/news.jsonl
```

## Common Operations

Restart the API after changing `.env`:

```bash
docker-compose restart be-invest
```

Rebuild after dependency or Dockerfile changes:

```bash
docker-compose build be-invest
docker-compose up -d
```

Stop the stack:

```bash
docker-compose down
```

## Troubleshooting

If the API does not start:

```bash
docker-compose logs be-invest
```

If Langfuse does not load:

```bash
docker-compose logs langfuse-server
docker-compose logs langfuse-db
```

If ports conflict, check which process owns the port and update `docker-compose.yml` if needed:

```bash
docker-compose ps
```
