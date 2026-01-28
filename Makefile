.PHONY: test lint format clean eval docker-build docker-up docker-down docker-logs help

test:
	pytest -v

lint:
	pylint src/ tests/ 2>/dev/null || echo "⚠️  pylint not installed. Run: pip install pylint"

format:
	black src/ tests/ --line-length=100 2>/dev/null || echo "⚠️  black not installed. Run: pip install black"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

eval:
	python -m evals.run_eval

# Docker targets
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-restart:
	docker-compose restart

help:
	@echo "LLMOps Lab - Available commands:"
	@echo "  make test            Run pytest"
	@echo "  make lint            Run pylint code checks"
	@echo "  make format          Format code with black"
	@echo "  make clean           Remove cache files"
	@echo "  make eval            Run evaluation (writes evals/report.json)"
	@echo ""
	@echo "Docker commands:"
	@echo "  make docker-build    Build Docker images"
	@echo "  make docker-up       Start containers in background"
	@echo "  make docker-down     Stop and remove containers"
	@echo "  make docker-logs     View container logs"
	@echo "  make docker-restart  Restart containers"
	@echo ""
	@echo "  make help            Show this message"
