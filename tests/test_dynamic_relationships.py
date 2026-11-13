"""Manual locks, per-turn snapshots, provider errors and identity injection."""

import asyncio
import copy
import importlib.util
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dynamic_identity_test", ROOT / "plugin.py")
identity = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = identity
SPEC.loader.exec_module(identity)


class Logger:
    def __init__(self):
        self.warnings = []
    def info(self, *args):
        pass
    def debug(self, *args):
        pass
    def warning(self, *args):
        self.warnings.append(args)


class Provider:
    def __init__(self):
        self.label = "朋友"
        self.found = True
        self.calls = []
        self.error = None
        self.wrapped = True
    async def call(self, api_name, **kwargs):
        self.calls.append((api_name, kwargs))
        if self.error:
            raise self.error
        value = {"schema_version": 1, "ready": True, "enabled": True, "found": self.found,
                 "protected": False, "label": self.label}
        return {"success": True, "result": value} if self.wrapped else value


def plugin():
    result = identity.IdentityPlugin()
    cfg = identity.IdentityPluginConfig().model_dump()
    cfg["identity"].update(
        roster="100000001 = 主人\n100000003 = 朋友\n100000004 = 群友",
        inject_for_others=True,
    )
    cfg["dynamic_relationship"]["enabled"] = True
    result.set_plugin_config(cfg)
    result._ctx = SimpleNamespace(api=Provider(), logger=Logger())
    result._rebuild_roster()
    return result


def turn(result, uid, message_id, *, platform="qq", session="test-session"):
    speaker = {"user_id": uid, "name": "测试人物", "platform": platform,
               "session": session, "ts": time.time(), "is_notify": False}
    result._recent[message_id] = speaker
    result._latest_by_session[session] = speaker
    return {"session_id": session, "items": [
        {"item_type": "SystemMessageItem", "parts": [{"type": "text", "text": "原本人设"}]},
        {"item_type": "UserMessageItem", "parts": [{"type": "text", "text": f"[msg_id:{message_id}] 测试消息"}]},
    ]}


def injected_text(value):
    return "\n".join(part.get("text", "") for item in value["modified_kwargs"]["items"]
                     for part in item.get("parts", []))


def test_dynamic_demotion_applies_next_turn_and_both_stages_agree():
    async def exercise():
        inst = plugin()
        first = turn(inst, "100000002", "m1")
        planner = await inst.inject_to_planner(**copy.deepcopy(first))
        assert "你的朋友" in injected_text(planner)
        inst._ctx.api.label = "群友"
        replyer = await inst.inject_to_replyer(**copy.deepcopy(first))
        assert "你的朋友" in injected_text(replyer)
        assert len(inst._ctx.api.calls) == 1
        second = turn(inst, "100000002", "m2")
        planner = await inst.inject_to_planner(**second)
        assert "你的群友" in injected_text(planner)
        assert "100000002" not in injected_text(planner)
    asyncio.run(exercise())


@pytest.mark.parametrize("uid,expected", [("100000001", "主人"), ("100000003", "朋友"), ("100000004", "群友")])
def test_every_manual_entry_is_locked_and_never_queries_provider(uid, expected):
    async def exercise():
        inst = plugin()
        original_roster = inst.config.identity.roster
        inst._ctx.api.label = "群友" if expected != "群友" else "朋友"
        result = await inst.inject_to_planner(**turn(inst, uid, "m1"))
        assert f"你的{expected}" in injected_text(result)
        assert not inst._ctx.api.calls
        assert inst.config.identity.roster == original_roster
        assert inst._labels[uid] == expected
    asyncio.run(exercise())


def test_provider_failure_keeps_known_identity_and_is_logged():
    async def exercise():
        inst = plugin()
        await inst.inject_to_planner(**turn(inst, "100000002", "m1"))
        inst._ctx.api.error = TimeoutError("provider unavailable")
        result = await inst.inject_to_planner(**turn(inst, "100000002", "m2"))
        assert "你的朋友" in injected_text(result)
        assert inst._ctx.logger.warnings
        inst._ctx.api.error = None
        inst._ctx.api.label = "群友"
        same_turn = {"session_id": "test-session", "items": [
            {"item_type": "SystemMessageItem", "parts": []},
            {"item_type": "UserMessageItem", "parts": [{"type": "text", "text": "[msg_id:m2] 测试"}]},
        ]}
        assert "你的朋友" in injected_text(await inst.inject_to_replyer(**same_turn))
        assert "你的群友" in injected_text(await inst.inject_to_planner(**turn(inst, "100000002", "m3")))
    asyncio.run(exercise())


def test_provider_cannot_return_owner_and_notifications_do_not_query_it():
    async def exercise():
        inst = plugin()
        inst._ctx.api.label = "主人"
        result = await inst.inject_to_planner(**turn(inst, "100000002", "m1"))
        assert "你的主人" not in injected_text(result)
        assert "你的群友" in injected_text(result)
        inst._ctx.api.calls.clear()
        args = turn(inst, "100000002", "m2")
        inst._latest_by_session["test-session"]["is_notify"] = True
        await inst.inject_to_planner(**args)
        assert not inst._ctx.api.calls
    asyncio.run(exercise())


def test_manual_lock_removal_and_platform_names_do_not_reuse_old_scores():
    async def exercise():
        inst = plugin()
        await inst.inject_to_planner(**turn(inst, "100000002", "m1"))
        inst._ctx.api.found = False
        result = await inst.inject_to_planner(**turn(inst, "100000002", "m2", platform="other"))
        assert "你的群友" in injected_text(result)
        assert inst._label_for("100000002", "qq")[0] == "朋友"
        inst.config.identity.roster += "\n100000002 = 群友"
        await inst.on_config_update("self", {}, "1.1.0")
        result = await inst.inject_to_planner(**turn(inst, "100000002", "m3"))
        assert "你的群友" in injected_text(result)
    asyncio.run(exercise())
