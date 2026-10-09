import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent / "skills" / "verify" / "scripts" / "factory-config.py"
)
spec = importlib.util.spec_from_file_location("factory_config", SCRIPT)
config = importlib.util.module_from_spec(spec)
sys.modules["factory_config"] = config
spec.loader.exec_module(config)


def parse(output: str) -> dict[str, str]:
    pairs = (line.split("=", 1) for line in output.splitlines() if line)
    return {key: value for key, value in pairs}


def test_missing_file_prints_defaults(tmp_path: Path, capsys):
    assert config.main(["factory-config.py", str(tmp_path / "factory.toml")]) == 0
    values = parse(capsys.readouterr().out)
    assert values["FACTORY_BASE"] == "origin/main"
    assert values["VERIFY_THRESHOLD"] == "5"
    assert values["VERIFY_CMD_TEST"] == "''"
    assert values["VERIFY_LLM"] == "0"


def test_values_override_defaults_and_are_quoted(tmp_path: Path, capsys):
    toml = tmp_path / "factory.toml"
    toml.write_text(
        "[factory]\nbase = 'main'\n"
        "[tracker]\nkind = 'jira'\njira_project = 'ENG'\n"
        "[verify]\ncrap_threshold = 12\nllm = true\nexclude = ['upstream/*', 'vendor/*']\n"
        "[verify.commands]\ntest = \"pnpm test -- --coverage 'a b'\"\n"
    )
    config.main(["factory-config.py", str(toml)])
    values = parse(capsys.readouterr().out)
    assert values["FACTORY_BASE"] == "main"
    assert values["FACTORY_TRACKER"] == "jira"
    assert values["FACTORY_JIRA_PROJECT"] == "ENG"
    assert values["FACTORY_JIRA_TYPE"] == "Task"
    assert values["VERIFY_THRESHOLD"] == "12"
    assert values["VERIFY_LLM"] == "1"
    assert values["VERIFY_EXCLUDE"] == "'upstream/* vendor/*'"
    assert values["VERIFY_CMD_TEST"] == "'pnpm test -- --coverage '\"'\"'a b'\"'\"''"


def test_empty_string_keeps_default(tmp_path: Path, capsys):
    toml = tmp_path / "factory.toml"
    toml.write_text("[verify]\ncoverage = ''\n[verify.commands]\nlint = ''\n")
    config.main(["factory-config.py", str(toml)])
    values = parse(capsys.readouterr().out)
    assert values["VERIFY_COVERAGE"] == "''"
    assert values["VERIFY_CMD_LINT"] == "''"


def test_output_is_valid_shell(tmp_path: Path):
    toml = tmp_path / "factory.toml"
    toml.write_text("[verify.commands]\ntest = \"echo 'it works'\"\n")
    result = subprocess.run(
        ["sh", "-c", f'eval "$(python3 -I {SCRIPT} {toml})"; sh -c "$VERIFY_CMD_TEST"'],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "it works"
