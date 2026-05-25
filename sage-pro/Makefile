.PHONY: install ci test lint type sec bench demo docker-build clean

install:
	pip install -r requirements.txt -r requirements-dev.txt

test:
	pytest sage/tests

lint:
	ruff check sage/

type:
	mypy sage/

sec:
	bandit -r sage/
	semgrep --config auto sage/

ci: lint type sec test

bench:
	python -m sage.benchmarks.compare_single_vs_sage

demo:
	python demos/demo_sage_pro.py

docker-build:
	docker build -t sage-pro:latest -f Dockerfile.rocm .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .venv .mypy_cache .ruff_cache .pytest_cache .coverage htmlcov
