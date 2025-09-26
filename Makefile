.PHONY: install dev-install lint format type test pre-commit-install run-dashboard setup migrate

install:
	pip install -r requirements.txt

dev-install: install
	pip install -r requirements-dev.txt
	pre-commit install

lint:
	ruff check .

format:
	black .
	isort .

type:
	mypy src

test:
	pytest -q

pre-commit-install:
	pre-commit install

run-dashboard:
	streamlit run src/dashboard/app.py

setup:
	python src/setup_initial.py

migrate:
	alembic upgrade head
