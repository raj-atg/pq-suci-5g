# pq-suci-5g: common tasks. Run `make help` for a list.
SHELL := /bin/bash
VENV := .venv
PY := $(VENV)/bin/python
export OQS_INSTALL_PATH := $(CURDIR)/third_party/install/liboqs

.PHONY: help setup build venv keys core-up core-down subscribers test lint bench \
	experiments figures export-figures all clean-runtime

help:  ## Show this help
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

setup:  ## Install system packages (needs sudo) and create the Python venv
	scripts/setup_deps.sh
	$(MAKE) venv

venv:  ## Create the Python venv and install pqsuci with dev tools
	command -v uv >/dev/null || export PATH="$$HOME/.local/bin:$$PATH"; \
	  uv venv -q $(VENV) && uv pip install -q --python $(PY) -e ".[dev]"

build:  ## Build liboqs, Open5GS, UERANSIM, then the patched (post-quantum) versions
	scripts/build_all.sh
	scripts/apply_patches.sh

keys:  ## Generate TEST key pairs and UERANSIM UE configs
	scripts/gen_test_keys.sh
	scripts/make_ue_configs.sh

core-up:  ## Start MongoDB and the Open5GS 5G core (patched build if O5GS_PREFIX points to it)
	scripts/start_core.sh

core-down:  ## Stop the 5G core and MongoDB
	scripts/stop_core.sh

subscribers:  ## Add 120 test subscribers
	scripts/add_subscribers.sh 120

test:  ## Run unit tests
	$(PY) -m pytest -q

lint:  ## ruff, shellcheck and the em dash check
	$(VENV)/bin/ruff check src tests bench experiments
	$(VENV)/bin/ruff format --check src tests bench experiments
	shellcheck -x scripts/*.sh scripts/hooks/* experiments/*.sh bench/*.sh
	scripts/check_no_emdash.sh

bench:  ## E1 microbenchmarks (Python and native liboqs)
	bench/e1_repeat.sh 3
	bench/e1_native.sh

experiments:  ## Run all experiments (E1 to E6); needs the core and builds
	scripts/run_all.sh

figures:  ## Make all figures from results/processed
	$(PY) experiments/make_figures.py

export-figures:  ## Copy the repository (incl. figures) to the Windows folder (WSL only)
	scripts/sync_to_windows.sh

all: keys test bench experiments figures  ## Reproduce all results and figures

clean-runtime:  ## Remove runtime data (logs, MongoDB data) created by the core scripts
	rm -rf runtime
