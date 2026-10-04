PY := .venv/bin/python
FE := frontend

.PHONY: check test types typecheck lint api demo web e2e smoke

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
	cd backend && HEDGECAST_FAKES=1 HEDGECAST_V2_DB=/tmp/hedgecast-demo.db ../$(PY) -m uvicorn hedgecast.main:app --port 8000

web:
	cd $(FE) && npm run dev

e2e:
	cd $(FE) && npx playwright test

smoke:
	$(PY) backend/scripts/smoke.py
