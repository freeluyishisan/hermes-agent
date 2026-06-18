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
