TEMP_FILE := *.egg-info build dist .pytest_cache .mypy_cache
MYPY_FLAG := --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

SRC_DIR := src
PY_FILES := $(shell find $(SRC_DIR) -name "*.py")

UV := uv
MAKEFLAGS += -s


all: run

run:
	$(UV) run python -m src

install:
	$(UV) sync

clean:
	$(RM) -rf $(TEMP_FILE)
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[co]" -delete

debug:
	$(UV) run python -m pdb -m $(SRC_DIR)

lint:
	$(UV) run flake8 $(PY_FILES)
	$(UV) run mypy $(PY_FILES) $(MYPY_FLAG)

lint-strict:
	$(UV) run flake8 $(PY_FILES)
	$(UV) run mypy $(PY_FILES) --strict
