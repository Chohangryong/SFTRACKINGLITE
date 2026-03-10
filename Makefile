.PHONY: help setup backend-install frontend-install install build-frontend build test test-backend test-frontend run-backend run-frontend run

help:
	@echo "Available targets:"
	@echo "  make install        - install backend and frontend dependencies"
	@echo "  make build          - build frontend assets"
	@echo "  make test           - run backend and frontend tests"
	@echo "  make run-backend    - run FastAPI backend"
	@echo "  make run-frontend   - run Vite frontend"
	@echo "  make run            - run backend"

backend-install:
	cd backend && python3 -m pip install -e ".[dev]"

frontend-install:
	cd frontend && npm install

install: backend-install frontend-install

build-frontend:
	cd frontend && npm run build

build: build-frontend

test-backend:
	cd backend && pytest

test-frontend:
	cd frontend && npm run test -- --run

test: test-backend test-frontend

run-backend:
	cd backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

run-frontend:
	cd frontend && npm run dev

run: run-backend
