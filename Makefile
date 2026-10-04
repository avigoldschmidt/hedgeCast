PY := .venv/bin/python
FE := frontend
DB := backend/hedgecast.db
DEMO_DB := /tmp/hedgecast-demo.db

.PHONY: check test types typecheck lint api demo web start start-fake live fake reset-db e2e smoke

test:
	$(PY) -m pytest -q

types:
	$(PY) backend/scripts/export_openapi.py
	cd $(FE) && npx openapi-typescript src/api/openapi.json -o src/api/schema.d.ts

typecheck:
	cd $(FE) && npx tsc -b

lint:
	cd $(FE) && npm run lint

check: test typecheck lint

api:
	cd backend && ../$(PY) -m uvicorn hedgecast.main:app --reload --port 8000

demo:
	cd backend && HEDGECAST_FAKES=1 HEDGECAST_V2_DB=$(DEMO_DB) ../$(PY) -m uvicorn hedgecast.main:app --port 8000

web:
	cd $(FE) && npm run dev

# Wipe local SQLite (businesses/policies). Does not reset Nessie sandbox balances.
reset-db:
	rm -f $(DB) $(DB)-wal $(DB)-shm $(DEMO_DB) $(DEMO_DB)-wal $(DEMO_DB)-shm

# Run API + Vite together without touching the DB. Use after an interrupt.
start:
	@trap 'kill 0' EXIT INT TERM; \
	$(MAKE) api & \
	$(MAKE) web & \
	wait

# Fresh live demo: reset DB, then start both. Ctrl+C stops both.
live: reset-db start

# Resume offline Plan B without wiping the DB.
start-fake:
	@trap 'kill 0' EXIT INT TERM; \
	$(MAKE) demo & \
	$(MAKE) web & \
	wait

# Fresh offline Plan B: reset DB, then start fakes + Vite.
fake: reset-db start-fake

e2e:
	cd $(FE) && npx playwright test

smoke:
	$(PY) backend/scripts/smoke.py
