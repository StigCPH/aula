"""Regression checks for the installed integration's token persistence lifecycle."""
import ast
import asyncio
import base64
import json
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "aula"
KEYS = {"CONF_ACCESS_TOKEN": "access_token", "CONF_REFRESH_TOKEN": "refresh_token",
        "CONF_TOKEN_EXPIRES_AT": "token_expires_at"}

def load_functions(filename):
    tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
             and n.name in {"async_update_tokens", "options_update_listener"}]
    ns = {**KEYS, "DOMAIN": "aula", "base64": base64, "json": json,
          "_LOGGER": logging.getLogger("test"),
          "core": SimpleNamespace(HomeAssistant=object),
          "config_entries": SimpleNamespace(ConfigEntry=object)}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, "exec"), ns)
    return ns

def jwt(exp):
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return "header." + payload + ".signature"

class Entries:
    def __init__(self):
        self.saved = None
        self.reloads = []
        self.fail = False
    def async_update_entry(self, entry, *, data):
        if self.fail:
            raise OSError("simulated storage failure")
        entry.data = dict(data)
        self.saved = dict(data)
    async def async_reload(self, entry_id):
        self.reloads.append(entry_id)

class Lifecycle(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fn = load_functions("__init__.py")
        self.old = {"access_token": jwt(100), "refresh_token": "old", "token_expires_at": 100,
                    "ugeplan": True, "custom_preference": "keep"}
        self.entry = SimpleNamespace(entry_id="entry", data=dict(self.old), options={})
        self.runtime = {"_applied_entry_data": dict(self.old), "_applied_entry_options": {}}
        self.hass = SimpleNamespace(data={"aula": {"entry": self.runtime}}, config_entries=Entries())
        self.new = {"access_token": jwt(10000), "refresh_token": "rotated", "expires_at": 100}
    async def persist(self):
        await self.fn["async_update_tokens"](self.hass, self.entry, self.new)
    async def listen(self):
        await self.fn["options_update_listener"](self.hass, self.entry)
    async def test_rotated_tokens_survive_restart_with_real_jwt_expiry(self):
        await self.persist()
        restarted_entry = dict(self.hass.config_entries.saved)
        self.assertEqual(restarted_entry["refresh_token"], "rotated")
        self.assertEqual(restarted_entry["token_expires_at"], 10000)
        self.assertEqual(restarted_entry["custom_preference"], "keep")
    async def test_own_token_save_does_not_reload(self):
        await self.persist()
        await self.listen()
        await self.listen()
        self.assertEqual(self.hass.config_entries.reloads, [])
    async def test_concurrent_feature_edit_is_preserved_and_reloaded(self):
        self.entry.data["ugeplan"] = False
        await self.persist()
        await self.listen()
        self.assertFalse(self.hass.config_entries.saved["ugeplan"])
        self.assertEqual(self.hass.config_entries.reloads, ["entry"])
    async def test_option_edit_still_reloads(self):
        await self.persist()
        self.entry.options["interval"] = 30
        await self.listen()
        self.assertEqual(self.hass.config_entries.reloads, ["entry"])
    async def test_human_reauthentication_still_reloads(self):
        await self.persist()
        self.entry.data = {**self.entry.data, "refresh_token": "human-reauth"}
        await self.listen()
        self.assertEqual(self.hass.config_entries.reloads, ["entry"])
    async def test_persistence_failure_restores_reload_baseline(self):
        self.hass.config_entries.fail = True
        with self.assertRaises(OSError):
            await self.persist()
        self.assertEqual(self.runtime["_applied_entry_data"], self.old)
        self.assertNotIn("tokens", self.runtime)
    async def test_missing_refresh_token_cannot_overwrite_saved_credentials(self):
        self.new.pop("refresh_token")
        with self.assertRaises(ValueError):
            await self.persist()
        self.assertIsNone(self.hass.config_entries.saved)
    async def test_input_mutation_does_not_modify_runtime_token_snapshot(self):
        await self.persist()
        self.new["refresh_token"] = "later"
        self.assertEqual(self.runtime["tokens"]["refresh_token"], "rotated")

if __name__ == "__main__":
    unittest.main(verbosity=2)
