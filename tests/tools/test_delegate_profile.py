#!/usr/bin/env python3
"""Tests for profile-backed delegation in delegate_task (issue #41889).

Profile delegation runs the subagent as an in-process child AIAgent built with
the target profile's SOUL.md + model/provider/credentials + toolsets. These
tests mock the profile-resolution and child-execution layers so no real
AIAgent, CLI, or API calls happen.

Run with:  scripts/run_tests.sh tests/tools/test_delegate_profile.py -q
"""

import json
import threading
import unittest
from unittest.mock import MagicMock, patch

from tools.delegate_tool import (
    DELEGATE_TASK_SCHEMA,
    _build_child_system_prompt,
    _build_top_level_description,
    _resolve_profile_bundle,
    delegate_task,
)


def _make_mock_parent(depth=0):
    parent = MagicMock()
    parent.base_url = "https://api.example/v1"
    parent.api_key = "parent-key"
    parent.provider = "openrouter"
    parent.api_mode = "chat_completions"
    parent.model = "anthropic/claude-sonnet-4"
    parent.platform = "cli"
    parent.providers_allowed = None
    parent.providers_ignored = None
    parent.providers_order = None
    parent.provider_sort = None
    parent._session_db = None
    parent._delegate_depth = depth
    parent._active_children = []
    parent._active_children_lock = threading.Lock()
    parent._print_fn = None
    parent.tool_progress_callback = None
    parent.thinking_callback = None
    parent._delegate_spinner = None
    parent._memory_manager = None
    parent.session_id = "parent-sess"
    parent._current_turn_id = ""
    parent.session_estimated_cost_usd = 0.0
    return parent


class TestProfileSchema(unittest.TestCase):
    def test_top_level_profile_property(self):
        props = DELEGATE_TASK_SCHEMA["parameters"]["properties"]
        self.assertIn("profile", props)
        self.assertEqual(props["profile"]["type"], "string")

    def test_per_task_profile_property(self):
        task_props = DELEGATE_TASK_SCHEMA["parameters"]["properties"]["tasks"][
            "items"
        ]["properties"]
        self.assertIn("profile", task_props)

    def test_description_mentions_profile(self):
        self.assertIn("profile", _build_top_level_description().lower())


class TestSoulInjection(unittest.TestCase):
    def test_profile_soul_prepended(self):
        prompt = _build_child_system_prompt(
            "do the thing", profile_soul="I am the Reader. Terse."
        )
        self.assertTrue(prompt.startswith("I am the Reader. Terse."))
        self.assertIn("YOUR TASK:", prompt)

    def test_no_soul_unchanged(self):
        prompt = _build_child_system_prompt("do the thing")
        self.assertTrue(prompt.startswith("You are a focused subagent"))


class TestResolveProfileBundle(unittest.TestCase):
    @patch("hermes_cli.profiles.profile_exists", return_value=False)
    def test_missing_profile_raises(self, _exists):
        with self.assertRaises(ValueError) as ctx:
            _resolve_profile_bundle("ghost")
        self.assertIn("does not exist", str(ctx.exception))

    def test_bundle_fields(self):
        # Patch the dependencies _resolve_profile_bundle imports at call time.
        with patch("hermes_cli.profiles.profile_exists", return_value=True), patch(
            "hermes_cli.profiles.get_profile_dir"
        ) as gpd, patch("hermes_cli.config.load_config") as lc, patch(
            "hermes_cli.runtime_provider.resolve_runtime_provider"
        ) as rrp, patch(
            "hermes_cli.tools_config._get_platform_tools",
            return_value={"web", "file"},
        ):
            fake_dir = MagicMock()
            # SOUL.md path → not a file (skip reading)
            fake_dir.__truediv__.return_value.is_file.return_value = False
            gpd.return_value = fake_dir
            lc.return_value = {"model": {"default": "m/x", "provider": "prov"}}
            rrp.return_value = {
                "provider": "prov",
                "base_url": "https://prov/v1",
                "api_key": "prof-key",
                "api_mode": "chat_completions",
            }
            bundle = _resolve_profile_bundle("reader")
        self.assertEqual(bundle["name"], "reader")
        self.assertEqual(bundle["model"], "m/x")
        self.assertEqual(bundle["api_key"], "prof-key")
        self.assertEqual(bundle["base_url"], "https://prov/v1")
        self.assertEqual(sorted(bundle["toolsets"]), ["file", "web"])

    def test_env_scoped_without_mutating_os_environ(self):
        # Regression guard for the in-process concurrency concern: the
        # profile's .env must reach credential resolution via the secret scope
        # (a contextvar), NOT by mutating os.environ. We assert that during
        # resolve_runtime_provider the profile key is visible through
        # get_secret while os.environ stays untouched.
        import os
        import tempfile
        from pathlib import Path
        from agent.secret_scope import get_secret

        seen = {}
        before = dict(os.environ)

        def _capture(*_a, **_k):
            seen["scope_value"] = get_secret("PROFILE_ONLY_KEY")
            seen["os_environ_value"] = os.environ.get("PROFILE_ONLY_KEY")
            return {
                "provider": "prov",
                "base_url": "u",
                "api_key": "k",
                "api_mode": "chat_completions",
            }

        with tempfile.TemporaryDirectory() as td:
            prof_dir = Path(td)
            (prof_dir / ".env").write_text(
                "PROFILE_ONLY_KEY=secret-from-profile\n", encoding="utf-8"
            )
            with patch(
                "hermes_cli.profiles.profile_exists", return_value=True
            ), patch(
                "hermes_cli.profiles.get_profile_dir", return_value=prof_dir
            ), patch(
                "hermes_cli.config.load_config",
                return_value={"model": {"default": "m", "provider": "prov"}},
            ), patch(
                "hermes_cli.runtime_provider.resolve_runtime_provider",
                side_effect=_capture,
            ), patch(
                "hermes_cli.tools_config._get_platform_tools", return_value=set()
            ):
                _resolve_profile_bundle("reader")

        # The credential was visible through the scope during resolution …
        self.assertEqual(seen["scope_value"], "secret-from-profile")
        # … but never leaked into os.environ, and os.environ is unchanged after.
        self.assertIsNone(seen["os_environ_value"])
        self.assertEqual(dict(os.environ), before)


class TestDelegateTaskProfileRouting(unittest.TestCase):
    def setUp(self):
        self.parent = _make_mock_parent()

    @patch("tools.delegate_tool._run_single_child")
    @patch("tools.delegate_tool._build_child_agent")
    @patch("tools.delegate_tool._resolve_profile_bundle")
    def test_single_profile_overrides_passed(self, mbundle, mbuild, mrun):
        mbundle.return_value = {
            "name": "reader",
            "soul": "Reader persona",
            "model": "prof/model",
            "provider": "prov",
            "base_url": "https://prov/v1",
            "api_key": "prof-key",
            "api_mode": "chat_completions",
            "toolsets": ["web"],
        }
        fake_child = MagicMock()
        fake_child.model = "prof/model"
        mbuild.return_value = fake_child
        mrun.return_value = {
            "task_index": 0,
            "profile": "reader",
            "status": "completed",
            "summary": "ok",
        }
        out = delegate_task(
            goal="extract key points", profile="reader", parent_agent=self.parent
        )
        data = json.loads(out)
        self.assertEqual(data["results"][0]["profile"], "reader")
        # _build_child_agent received the profile's overrides + soul + name.
        kwargs = mbuild.call_args.kwargs
        self.assertEqual(kwargs["model"], "prof/model")
        self.assertEqual(kwargs["override_provider"], "prov")
        self.assertEqual(kwargs["override_api_key"], "prof-key")
        self.assertEqual(kwargs["override_base_url"], "https://prov/v1")
        self.assertEqual(kwargs["profile_soul"], "Reader persona")
        self.assertEqual(kwargs["profile_name"], "reader")

    @patch("tools.delegate_tool._run_single_child")
    @patch("tools.delegate_tool._build_child_agent")
    @patch("tools.delegate_tool._resolve_profile_bundle")
    def test_top_level_profile_inherited_by_batch_tasks(self, mbundle, mbuild, mrun):
        # delegate_task(profile="reader", tasks=[{...}, {...}]) must apply
        # "reader" to EACH batch item that doesn't override it. Regression
        # guard for the top-level-profile + batch inheritance mismatch.
        mbundle.return_value = {
            "name": "reader",
            "soul": "Reader persona",
            "model": "prof/model",
            "provider": "prov",
            "base_url": "u",
            "api_key": "k",
            "api_mode": "chat_completions",
            "toolsets": None,
        }
        fake_child = MagicMock()
        fake_child.model = "prof/model"
        mbuild.return_value = fake_child
        mrun.return_value = {"task_index": 0, "status": "completed", "summary": "ok"}
        delegate_task(
            profile="reader",
            tasks=[{"goal": "a"}, {"goal": "b"}],
            parent_agent=self.parent,
        )
        # The profile was resolved once per batch task (inherited by both).
        resolved = [c.args[0] for c in mbundle.call_args_list]
        self.assertEqual(resolved, ["reader", "reader"])
        # Every child was built with the profile's soul + name.
        for call in mbuild.call_args_list:
            self.assertEqual(call.kwargs["profile_name"], "reader")
            self.assertEqual(call.kwargs["profile_soul"], "Reader persona")

    @patch("tools.delegate_tool._run_single_child")
    @patch("tools.delegate_tool._build_child_agent")
    @patch("tools.delegate_tool._resolve_profile_bundle")
    def test_per_task_profile_overrides_top_level(self, mbundle, mbuild, mrun):
        # A task's own 'profile' wins over the inherited top-level one.
        mbundle.side_effect = lambda name: {
            "name": name,
            "soul": f"{name} persona",
            "model": "m",
            "provider": "p",
            "base_url": "u",
            "api_key": "k",
            "api_mode": "chat_completions",
            "toolsets": None,
        }
        fake_child = MagicMock()
        fake_child.model = "m"
        mbuild.return_value = fake_child
        mrun.return_value = {"task_index": 0, "status": "completed", "summary": "ok"}
        delegate_task(
            profile="reader",
            tasks=[{"goal": "a"}, {"goal": "b", "profile": "writer"}],
            parent_agent=self.parent,
        )
        resolved = [c.args[0] for c in mbundle.call_args_list]
        self.assertEqual(resolved, ["reader", "writer"])

    @patch(
        "tools.delegate_tool._resolve_profile_bundle",
        side_effect=ValueError("Profile 'ghost' does not exist."),
    )
    def test_invalid_profile_returns_tool_error(self, _mb):
        out = delegate_task(goal="g", profile="ghost", parent_agent=self.parent)
        data = json.loads(out)
        self.assertIn("error", data)
        self.assertIn("does not exist", data["error"])

    @patch("tools.delegate_tool._build_child_agent")
    @patch("tools.delegate_tool._resolve_profile_bundle")
    def test_background_plus_profile_allowed(self, mbundle, mbuild):
        # background+profile must NOT be rejected; it should reach async dispatch.
        mbundle.return_value = {
            "name": "reader",
            "soul": "",
            "model": "prof/model",
            "provider": "prov",
            "base_url": "u",
            "api_key": "k",
            "api_mode": "chat_completions",
            "toolsets": None,
        }
        fake_child = MagicMock()
        fake_child.model = "prof/model"
        mbuild.return_value = fake_child
        with patch(
            "tools.async_delegation.dispatch_async_delegation",
            return_value={"status": "dispatched", "delegation_id": "d1"},
        ), patch("tools.approval.get_current_session_key", return_value=""):
            out = delegate_task(
                goal="g", profile="reader", background=True, parent_agent=self.parent
            )
        data = json.loads(out)
        # Crucially NOT a rejection that background can't be combined with profile.
        self.assertNotIn("cannot be combined", json.dumps(data))
        self.assertEqual(data.get("status"), "dispatched")


class TestProfileToolsetBounding(unittest.TestCase):
    """A profile's toolset preferences are bounded by the parent's tools
    (least privilege), but the narrowing must not be silent: tools the parent
    can't grant are recorded on the child and surfaced in the result.
    """

    def _parent(self, enabled):
        from types import SimpleNamespace

        return SimpleNamespace(
            enabled_toolsets=list(enabled),
            api_key="k", base_url="u", provider="p", api_mode="chat_completions",
            model="m", platform="cli", providers_allowed=None,
            providers_ignored=None, providers_order=None, provider_sort=None,
            _session_db=None, _delegate_depth=0, _active_children=[],
            _active_children_lock=threading.Lock(), _print_fn=None,
            tool_progress_callback=None, thinking_callback=None,
            _delegate_spinner=None, _memory_manager=None, session_id="s",
            _current_turn_id="", session_estimated_cost_usd=0.0,
            valid_tool_names=[],
        )

    def test_dropped_profile_toolsets_recorded(self):
        from tools.delegate_tool import _build_child_agent

        with patch("run_agent.AIAgent", return_value=MagicMock()):
            # Parent lacks 'web'; profile wants web+file → web is dropped.
            child = _build_child_agent(
                task_index=0, goal="g", context=None,
                toolsets=["web", "file"], model="m", max_iterations=3,
                task_count=1, parent_agent=self._parent(["file", "terminal"]),
                profile_soul="persona", profile_name="reader",
            )
        self.assertEqual(
            getattr(child, "_delegate_profile_dropped_toolsets"), ["web"]
        )

    def test_no_drop_when_parent_has_all_profile_tools(self):
        from tools.delegate_tool import _build_child_agent

        with patch("run_agent.AIAgent", return_value=MagicMock()):
            child = _build_child_agent(
                task_index=0, goal="g", context=None,
                toolsets=["web", "file"], model="m", max_iterations=3,
                task_count=1,
                parent_agent=self._parent(["file", "web", "terminal"]),
                profile_soul="persona", profile_name="reader",
            )
        self.assertEqual(
            getattr(child, "_delegate_profile_dropped_toolsets"), []
        )

    def test_no_drop_field_for_non_profile_child(self):
        # Ordinary (non-profile) subagents never get a dropped-toolset list.
        from tools.delegate_tool import _build_child_agent

        with patch("run_agent.AIAgent", return_value=MagicMock()):
            child = _build_child_agent(
                task_index=0, goal="g", context=None,
                toolsets=["web"], model="m", max_iterations=3, task_count=1,
                parent_agent=self._parent(["file"]),
            )
        self.assertEqual(
            getattr(child, "_delegate_profile_dropped_toolsets"), []
        )


class TestProfileMemoryWiring(unittest.TestCase):
    """A profile-backed child loads the target profile's memory: it is built
    with skip_memory=False and profile_home pointing at the profile dir.
    Ordinary subagents stay memory-less (skip_memory=True, profile_home=None).
    """

    def _parent(self):
        from types import SimpleNamespace

        return SimpleNamespace(
            enabled_toolsets=["file", "web"],
            api_key="k", base_url="u", provider="p", api_mode="chat_completions",
            model="m", platform="cli", providers_allowed=None,
            providers_ignored=None, providers_order=None, provider_sort=None,
            _session_db=None, _delegate_depth=0, _active_children=[],
            _active_children_lock=threading.Lock(), _print_fn=None,
            tool_progress_callback=None, thinking_callback=None,
            _delegate_spinner=None, _memory_manager=None, session_id="s",
            _current_turn_id="", session_estimated_cost_usd=0.0,
            valid_tool_names=[],
        )

    def test_profile_child_loads_profile_memory(self):
        from tools.delegate_tool import _build_child_agent

        with patch("run_agent.AIAgent", return_value=MagicMock()) as MA:
            _build_child_agent(
                task_index=0, goal="g", context=None, toolsets=["file"],
                model="m", max_iterations=3, task_count=1,
                parent_agent=self._parent(), profile_soul="persona",
                profile_name="reader", profile_home="/home/x/.hermes/profiles/reader",
            )
        kw = MA.call_args.kwargs
        self.assertFalse(kw["skip_memory"])
        self.assertEqual(kw["profile_home"], "/home/x/.hermes/profiles/reader")

    def test_ordinary_child_stays_memoryless(self):
        from tools.delegate_tool import _build_child_agent

        with patch("run_agent.AIAgent", return_value=MagicMock()) as MA:
            _build_child_agent(
                task_index=0, goal="g", context=None, toolsets=["file"],
                model="m", max_iterations=3, task_count=1,
                parent_agent=self._parent(),
            )
        kw = MA.call_args.kwargs
        self.assertTrue(kw["skip_memory"])
        self.assertIsNone(kw["profile_home"])

    def test_bundle_carries_profile_home(self):
        # _resolve_profile_bundle must expose the profile dir as profile_home.
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            prof = Path(td)
            with patch(
                "hermes_cli.profiles.profile_exists", return_value=True
            ), patch(
                "hermes_cli.profiles.get_profile_dir", return_value=prof
            ), patch(
                "hermes_cli.config.load_config",
                return_value={"model": {"default": "m", "provider": "p"}},
            ), patch(
                "hermes_cli.runtime_provider.resolve_runtime_provider",
                return_value={"provider": "p", "base_url": "u", "api_key": "k",
                              "api_mode": "chat_completions"},
            ), patch(
                "hermes_cli.tools_config._get_platform_tools", return_value=set()
            ):
                bundle = _resolve_profile_bundle("reader")
        self.assertEqual(bundle["profile_home"], str(prof))


class TestAgentDispatchForwardsProfile(unittest.TestCase):
    """Guard the second invocation path: the agent loop dispatches delegate_task
    via AIAgent._dispatch_delegate_task (run_agent.py), NOT the registry handler.
    That method enumerates every forwarded arg, so a new schema field silently
    breaks unless it's added there too. This regression test fails if `profile`
    (or parent_agent) stops being forwarded. See issue #41889 follow-up.
    """

    def test_dispatch_delegate_task_forwards_profile(self):
        import run_agent

        captured = {}

        def fake_delegate_task(**kwargs):
            captured.update(kwargs)
            return "{}"

        with patch("tools.delegate_tool.delegate_task", fake_delegate_task):
            # Call unbound with a throwaway `self`; the method only uses self as
            # parent_agent and imports delegate_task lazily inside.
            run_agent.AIAgent._dispatch_delegate_task(
                object(), {"profile": "reader", "goal": "g"}
            )

        self.assertEqual(captured.get("profile"), "reader")
        self.assertIn("parent_agent", captured)


if __name__ == "__main__":
    unittest.main()
