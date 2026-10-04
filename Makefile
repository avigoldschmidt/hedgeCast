PY := .venv/bin/python
FE := frontend
DB := backend/hedgecast.db
DEMO_DB := /tmp/hedgecast-demo.db
API_PORT := 8000
WEB_PORT := 5173

.PHONY: check test types typecheck lint api demo web start start-fake live fake reset-db stop e2e smoke

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
	cd backend && ../$(PY) -m uvicorn hedgecast.main:app --reload --port $(API_PORT)

demo:
	cd backend && HEDGECAST_FAKES=1 HEDGECAST_V2_DB=$(DEMO_DB) ../$(PY) -m uvicorn hedgecast.main:app --port $(API_PORT)

web:
	cd $(FE) && npm run dev

# Free API/Vite ports so a leftover process cannot keep serving a wiped DB.
stop:
	@pids=$$(lsof -tiTCP:$(API_PORT) -sTCP:LISTEN 2>/dev/null); \
	if [ -n "$$pids" ]; then kill $$pids 2>/dev/null || true; fi
	@pids=$$(lsof -tiTCP:$(WEB_PORT) -sTCP:LISTEN 2>/dev/null); \
	if [ -n "$$pids" ]; then kill $$pids 2>/dev/null || true; fi
	@for i in 1 2 3 4 5; do \
		lsof -tiTCP:$(API_PORT) -sTCP:LISTEN >/dev/null 2>&1 || lsof -tiTCP:$(WEB_PORT) -sTCP:LISTEN >/dev/null 2>&1 || break; \
		sleep 0.2; \
	done

# Wipe local SQLite (businesses/policies). Stops servers first so they cannot keep an unlinked DB open.
# Does not reset Nessie sandbox balances.
reset-db: stop
	rm -f $(DB) $(DB)-wal $(DB)-shm $(DEMO_DB) $(DEMO_DB)-wal $(DEMO_DB)-shm

# Run API + Vite together without touching the DB. Use after an interrupt.
start: stop
	@trap 'kill 0' EXIT INT TERM; \
	$(MAKE) api & \
	$(MAKE) web & \
	wait

# Fresh live demo: reset DB, then start both. Ctrl+C stops both.
live: reset-db start

# Resume offline Plan B without wiping the DB.
start-fake: stop
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
