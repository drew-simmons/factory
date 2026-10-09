#!/usr/bin/env sh
# Seeds a tiny python repo with a green change on a feature branch.
# Run the case with:
#   claude plugin eval . --case verify-runs-on-fixture --scaffold \
#     --allow-tools Write "Bash(sh *)" "Bash(uv *)" "Bash(uvx *)" "Bash(poly-crap *)" "Bash(jq *)" "Bash(git *)"
set -eu
git init -q -b main
git config commit.gpgsign false
git config user.name eval
git config user.email eval@example.com
mkdir -p src tests
cat >pyproject.toml <<'EOF'
[project]
name = "fixture"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[dependency-groups]
dev = ["pytest>=8", "pytest-cov>=5"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.coverage.run]
source = ["src"]
EOF
printf 'def add(a: int, b: int) -> int:\n    return a + b\n' >src/fixture.py
printf 'from fixture import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n' >tests/test_fixture.py
printf '.venv/\n.verify/\n.pytest_cache/\n__pycache__/\n.coverage\nuv.lock\n' >.gitignore
printf "[factory]\nbase = 'main'\n" >factory.toml
git add -A
git commit -q -m base
git switch -q -c feature
printf '\n\ndef sub(a: int, b: int) -> int:\n    return a - b\n' >>src/fixture.py
printf '\n\ndef test_sub():\n    assert sub(3, 1) == 2\n' >>tests/test_fixture.py
sed -i.bak 's/from fixture import add$/from fixture import add, sub/' tests/test_fixture.py
rm -f tests/test_fixture.py.bak
