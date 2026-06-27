"""Regression tests for install.sh environment sanitization and tool detection.

When install.sh is launched from another Python-driven tool session, inherited
PYTHONPATH/PYTHONHOME can shadow the freshly installed checkout. The installer
must sanitize those vars both during installation and at runtime launch.
"""

import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"


def _extract_function(name: str) -> str:
    text = INSTALL_SH.read_text(encoding="utf-8")
    match = re.search(
        rf"(?P<body>^{name}\(\) \{{\n.*?^\}})",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, f"Could not locate {name}() in scripts/install.sh"
    return match["body"]


def test_install_script_unsets_pythonpath_and_pythonhome_early() -> None:
    text = INSTALL_SH.read_text()

    # During install, inherited Python env must be sanitized before pip/venv use.
    assert 'unset PYTHONPATH' in text
    assert 'unset PYTHONHOME' in text


def test_hermes_launcher_wrapper_clears_python_env_before_exec() -> None:
    text = INSTALL_SH.read_text()

    # Wrapper should clear env and forward args untouched to the venv entrypoint.
    assert 'cat > "$command_link_dir/hermes" <<EOF' in text
    assert 'unset PYTHONPATH' in text
    assert 'unset PYTHONHOME' in text
    assert 'exec "$HERMES_BIN" "\\$@"' in text


def test_check_node_uses_user_shell_path_before_installing_managed_node() -> None:
    check_node = _extract_function("check_node")

    shell_probe_idx = check_node.find("find_node_on_user_shell_path")
    managed_idx = check_node.find('"$HERMES_HOME/node/bin/node"')
    install_idx = check_node.find("install_node")

    assert shell_probe_idx != -1, "check_node() must probe the user's shell PATH"
    assert managed_idx != -1, "expected Hermes-managed Node fallback to remain"
    assert install_idx != -1, "expected install_node fallback to remain"
    assert shell_probe_idx < managed_idx < install_idx, (
        "user shell PATH must be checked before Hermes-managed Node fallback "
        "and before installing a new managed Node"
    )


def test_install_node_does_not_link_node_tools_into_command_dir() -> None:
    install_node = _extract_function("install_node")

    forbidden = (
        'ln -sf "$HERMES_HOME/node/bin/node"',
        'ln -sf "$HERMES_HOME/node/bin/npm"',
        'ln -sf "$HERMES_HOME/node/bin/npx"',
        "node_link_dir=",
    )
    for snippet in forbidden:
        assert snippet not in install_node

    assert '"$HERMES_HOME/node/bin/npm" config set prefix "$HERMES_HOME/node"' in install_node
    assert 'export PATH="$HERMES_HOME/node/bin:$PATH"' in install_node


def test_find_node_on_user_shell_path_accepts_shell_managed_node(tmp_path: Path) -> None:
    node_bin = tmp_path / "volta" / "bin"
    node_bin.mkdir(parents=True)
    node = node_bin / "node"
    node.write_text("#!/bin/sh\necho v24.15.0\n")
    node.chmod(0o755)

    fake_shell = tmp_path / "fake-zsh"
    fake_shell.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "-ic" ]; then\n'
        f"  printf '%s\\n' {node}\n"
        "fi\n"
    )
    fake_shell.chmod(0o755)

    script = "\n".join(
        [
            "set -e",
            _extract_function("find_node_on_user_shell_path"),
            f"SHELL={fake_shell}",
            "find_node_on_user_shell_path",
        ]
    )
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(node)


def test_find_node_on_user_shell_path_ignores_noisy_shell_output(tmp_path: Path) -> None:
    node_bin = tmp_path / "fnm" / "bin"
    node_bin.mkdir(parents=True)
    node = node_bin / "node"
    node.write_text("#!/bin/sh\necho v22.22.3\n")
    node.chmod(0o755)

    fake_shell = tmp_path / "fake-zsh"
    fake_shell.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "-ic" ]; then\n'
        "  printf '%s\\n' 'welcome from shell rc'\n"
        f"  printf '%s\\n' {node}\n"
        "fi\n"
    )
    fake_shell.chmod(0o755)

    script = "\n".join(
        [
            "set -e",
            _extract_function("find_node_on_user_shell_path"),
            f"SHELL={fake_shell}",
            "find_node_on_user_shell_path",
        ]
    )
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(node)
