"""Tests for credential exclusion during profile export.

Profile exports should NEVER include auth.json or .env — these contain
API keys, OAuth tokens, and credential pool data. Users share exported
profiles; leaking credentials in the archive is a security issue.
"""

import tarfile

from hermes_cli.profiles import export_profile, _DEFAULT_EXPORT_EXCLUDE_ROOT


class TestCredentialExclusion:

    def test_auth_json_in_default_exclude_set(self):
        """auth.json must be in the default export exclusion set."""
        assert "auth.json" in _DEFAULT_EXPORT_EXCLUDE_ROOT

    def test_dotenv_in_default_exclude_set(self):
        """.env must be in the default export exclusion set."""
        assert ".env" in _DEFAULT_EXPORT_EXCLUDE_ROOT

    def test_named_profile_export_excludes_auth(self, tmp_path, monkeypatch):
        """Named profile export must not contain auth.json or .env."""
        profiles_root = tmp_path / "profiles"
        profile_dir = profiles_root / "testprofile"
        profile_dir.mkdir(parents=True)

        # Create a profile with credentials
        (profile_dir / "config.yaml").write_text("model: gpt-4\n")
        (profile_dir / "auth.json").write_text('{"tokens": {"access": "sk-secret"}}')
        (profile_dir / ".env").write_text("OPENROUTER_API_KEY=sk-secret-key\n")
        (profile_dir / "SOUL.md").write_text("I am helpful.\n")
        (profile_dir / "memories").mkdir()
        (profile_dir / "memories" / "MEMORY.md").write_text("# Memories\n")

        monkeypatch.setattr("hermes_cli.profiles._get_profiles_root", lambda: profiles_root)
        monkeypatch.setattr("hermes_cli.profiles.get_profile_dir", lambda n: profile_dir)
        monkeypatch.setattr("hermes_cli.profiles.validate_profile_name", lambda n: None)

        output = tmp_path / "export.tar.gz"
        result = export_profile("testprofile", str(output))

        # Check archive contents
        with tarfile.open(result, "r:gz") as tf:
            names = tf.getnames()

        assert any("config.yaml" in n for n in names), "config.yaml should be in export"
        assert any("SOUL.md" in n for n in names), "SOUL.md should be in export"
        assert not any("auth.json" in n for n in names), "auth.json must NOT be in export"
        assert not any(".env" in n for n in names), ".env must NOT be in export"

    def test_named_profile_export_state_db_omits_session_model_api_key(
        self, tmp_path, monkeypatch
    ):
        """Persisted /model overrides in state.db must not leak API keys."""
        from hermes_state import SessionDB

        profiles_root = tmp_path / "profiles"
        profile_dir = profiles_root / "testprofile"
        profile_dir.mkdir(parents=True)
        (profile_dir / "config.yaml").write_text("model: gpt-5.4\n")

        secret = "sk-live-session-secret"
        db = SessionDB(db_path=profile_dir / "state.db")
        try:
            db.set_gateway_session_model_override(
                "agent:main:telegram:dm:273403055:351260",
                {
                    "model": "gpt-5.5",
                    "provider": "openai-codex",
                    "api_key": secret,
                    "base_url": "https://chatgpt.com/backend-api/codex",
                    "api_mode": "codex_responses",
                },
            )
        finally:
            db.close()

        monkeypatch.setattr("hermes_cli.profiles._get_profiles_root", lambda: profiles_root)
        monkeypatch.setattr("hermes_cli.profiles.get_profile_dir", lambda n: profile_dir)
        monkeypatch.setattr("hermes_cli.profiles.validate_profile_name", lambda n: None)

        output = tmp_path / "export.tar.gz"
        result = export_profile("testprofile", str(output))

        with tarfile.open(result, "r:gz") as tf:
            state_member = next(m for m in tf.getmembers() if m.name.endswith("/state.db"))
            extracted = tf.extractfile(state_member)
            assert extracted is not None
            state_bytes = extracted.read()

        assert secret.encode() not in state_bytes
        assert b"api_key" not in state_bytes
