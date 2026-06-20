PY := ./venv/bin/python

.PHONY: install demo inspect-demo test package

install:
	$(PY) -m pip install -e .

demo:
	$(PY) -m claim_orchestrator demo

inspect-demo:
	$(PY) -m claim_orchestrator inspect --contract examples/demo_challenge/contract.toml --query "I was charged twice for my plan"

test:
	$(PY) -m unittest discover -s tests -p 'test_*.py'

package:
	sh scripts/package_submission.sh
