from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.config import GatewayConfig, HomeChannel, Platform, PlatformConfig
from gateway.session import SessionSource


def _runner_with_config(config: GatewayConfig):
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = config
    runner.adapters = {}
    runner.adapters_by_id = {}
    runner._platform_adapter_ids = {}
    return runner


def _adapter(config: PlatformConfig):
    return SimpleNamespace(
        config=config,
        platform=Platform.FEISHU,
        adapter_id=None,
        send=AsyncMock(return_value=SimpleNamespace(success=True)),
    )


def test_gateway_config_round_trips_multi_feishu_configs():
    data = {
        "platforms": {
            "feishu": [
                {"enabled": True, "app_id": "cli_app1", "app_secret": "secret1"},
                {"enabled": True, "app_id": "cli_app2", "app_secret": "secret2"},
            ]
        }
    }

    config = GatewayConfig.from_dict(data)

    assert isinstance(config.platforms[Platform.FEISHU], list)
    assert config.platforms[Platform.FEISHU][0].extra["app_id"] == "cli_app1"
    assert config.platforms[Platform.FEISHU][1].extra["app_id"] == "cli_app2"
    assert config.to_dict()["platforms"]["feishu"][1]["extra"]["app_id"] == "cli_app2"


def test_adapter_registration_routes_source_to_matching_feishu_app():
    app1_cfg = PlatformConfig(enabled=True, extra={"app_id": "cli_app1"})
    app2_cfg = PlatformConfig(enabled=True, extra={"app_id": "cli_app2"})
    runner = _runner_with_config(
        GatewayConfig(platforms={Platform.FEISHU: [app1_cfg, app2_cfg]})
    )
    app1 = _adapter(app1_cfg)
    app2 = _adapter(app2_cfg)

    runner._register_connected_adapter(Platform.FEISHU, app1)
    runner._register_connected_adapter(Platform.FEISHU, app2)

    source = SessionSource(
        platform=Platform.FEISHU,
        chat_id="chat-from-app2",
        adapter_id="feishu:cli_app2",
    )

    assert runner.adapters[Platform.FEISHU] is app1
    assert runner._adapter_for_source(source) is app2


@pytest.mark.asyncio
async def test_startup_notifications_use_each_feishu_app_home_channel():
    app1_cfg = PlatformConfig(
        enabled=True,
        extra={"app_id": "cli_app1"},
        home_channel=HomeChannel(platform=Platform.FEISHU, chat_id="chat-app1", name="App 1"),
    )
    app2_cfg = PlatformConfig(
        enabled=True,
        extra={"app_id": "cli_app2"},
        home_channel=HomeChannel(platform=Platform.FEISHU, chat_id="chat-app2", name="App 2"),
    )
    runner = _runner_with_config(
        GatewayConfig(platforms={Platform.FEISHU: [app1_cfg, app2_cfg]})
    )
    app1 = _adapter(app1_cfg)
    app2 = _adapter(app2_cfg)
    runner._register_connected_adapter(Platform.FEISHU, app1)
    runner._register_connected_adapter(Platform.FEISHU, app2)

    delivered = await runner._send_home_channel_startup_notifications()

    assert ("feishu", "chat-app1", None) in delivered
    assert ("feishu", "chat-app2", None) in delivered
    app1.send.assert_awaited_once()
    app2.send.assert_awaited_once()
