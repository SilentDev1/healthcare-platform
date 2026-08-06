# Local development

Install Docker, Python 3.12, uv, Node.js 22, and npm. Then:

```bash
cp .env.example .env
make setup
make db-up
make migrate
uv run python -m collectors.cms_hospitals --source-file data/fixtures/cms_hospitals.csv
make api
```

PostgreSQL listens on `localhost:5432`, the API on `localhost:8000`, the public app on 3000,
and admin on 3001. The default password is deliberately local-only. Override values in the
ignored `.env` file.

Use `make test`, `make lint`, `make typecheck`, and `make build` before submitting changes.
`make db-down` stops containers without deleting the persistent database volume. To inspect
generated API documentation, open <http://localhost:8000/docs> while the API is running.
