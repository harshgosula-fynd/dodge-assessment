.PHONY: setup seed backend frontend dev clean

# One-command setup
setup:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

# Ingest data + build semantic layer
seed:
	cd backend && PYTHONPATH=. python seed.py

# Start backend only
backend:
	cd backend && PYTHONPATH=. python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Start frontend only
frontend:
	cd frontend && npm run dev

# Start both (run in two terminals)
dev:
	@echo "Run in two terminals:"
	@echo "  make backend"
	@echo "  make frontend"

# Remove generated files
clean:
	rm -f backend/o2c.duckdb backend/o2c.duckdb.wal
