.PHONY: test lint format clean eval help

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

help:
	@echo "LLMOps Lab - Available commands:"
	@echo "  make test       Run pytest"
	@echo "  make lint       Run pylint code checks"
	@echo "  make format     Format code with black"
	@echo "  make clean      Remove cache files"
	@echo "  make eval       Run evaluation (writes evals/report.json)"
	@echo "  make help       Show this message"
