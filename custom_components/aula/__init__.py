from homeassistant.loader import async_get_integration
import asyncio
import base64
import json
from homeassistant import config_entries, core
from homeassistant.helpers import entity_registry as er
from .const import (
    DOMAIN,
    STARTUP,
    CONF_MITID_USERNAME,
    CONF_MITID_PASSWORD,
    CONF_MITID_TOKEN,
    CONF_AUTH_METHOD,
    CONF_MITID_IDENTITY,
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_EXPIRES_AT,
    AUTH_METHOD_APP,
    CONF_SCHOOLSCHEDULE,
    CONF_UGEPLAN,
    CONF_MU_OPGAVER,
)
import logging
from .client import Client

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    integration = await async_get_integration(hass, DOMAIN)
    _LOGGER.info(STARTUP, integration.version)
    hass.data.setdefault(DOMAIN, {})

    # Extract configuration
    mitid_username = entry.data.get(CONF_MITID_USERNAME)
    auth_method = entry.data.get(CONF_AUTH_METHOD, AUTH_METHOD_APP)
    mitid_password = entry.data.get(CONF_MITID_PASSWORD)
    mitid_token = entry.data.get(CONF_MITID_TOKEN)
    mitid_identity = entry.data.get(CONF_MITID_IDENTITY, 1)

    _LOGGER.info(
        f"Setting up Aula entry for {mitid_username} using method {auth_method}"
    )
    _LOGGER.info(f"Entry data keys: {list(entry.data.keys())}")

    # Extract stored tokens
    stored_tokens = None
    if CONF_ACCESS_TOKEN in entry.data:
        stored_tokens = {
            "access_token": entry.data[CONF_ACCESS_TOKEN],
            "refresh_token": entry.data[CONF_REFRESH_TOKEN],
            "expires_at": entry.data.get(CONF_TOKEN_EXPIRES_AT, 0),
            "token_type": "Bearer",
        }
        _LOGGER.info("Stored tokens found in config entry")
    else:
        _LOGGER.warning(
            f"No stored tokens found in config entry! Keys present: {list(entry.data.keys())}"
        )

    hass_data = dict(entry.data)
    # Track the configuration actually applied, separately from token-only saves.
    hass_data["_applied_entry_data"] = dict(entry.data)
    hass_data["_applied_entry_options"] = dict(entry.options)
    hass_data[CONF_MITID_USERNAME] = mitid_username
    hass_data[CONF_AUTH_METHOD] = auth_method
    hass_data[CONF_MITID_PASSWORD] = mitid_password
    hass_data[CONF_MITID_IDENTITY] = mitid_identity
    hass_data["stored_tokens"] = stored_tokens

    # Store tokens in runtime storage (not entry.data) to avoid triggering reload cycles
    # Tokens in entry.data are only for HA restart recovery and reauth flows
    if stored_tokens:
        hass_data["tokens"] = stored_tokens.copy()
        _LOGGER.debug("Tokens stored in runtime storage for active use")

    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener
    hass.data[DOMAIN][entry.entry_id] = hass_data

    # Create client with MitID authentication
    client = await hass.async_add_executor_job(
        Client,
        mitid_username,
        auth_method,
        mitid_password,
        mitid_token,
        entry.data.get(CONF_SCHOOLSCHEDULE, True),
        entry.data.get(CONF_UGEPLAN, True),
        entry.data.get(CONF_MU_OPGAVER, True),
        stored_tokens,
        0,  # unread_messages
        mitid_identity,
        hass,  # Pass hass reference for token persistence
        entry,  # Pass config entry for token persistence
    )
    hass.data[DOMAIN]["client"] = client

    # Perform login/validation
    if not stored_tokens:
        _LOGGER.warning("No stored tokens found, performing authentication")
        await hass.async_add_executor_job(client.login)
    else:
        _LOGGER.info(f"Using stored tokens from config entry")
        # Ensure session is initialized with tokens by calling login which now handles validation
        await hass.async_add_executor_job(client.login)

    # Fetch initial data before setting up platforms
    await hass.async_add_executor_job(client.update_data)

    # Unloading a platform that was never forwarded raises and leaves the entry
    # stuck in the non-recoverable FAILED_UNLOAD state, so async_unload_entry
    # must unload exactly what was forwarded here - not what entry.data says
    # *now*, since options updates change entry.data before the reload that
    # calls async_unload_entry. Remember the actual list in runtime storage.
    platforms = ["sensor", "binary_sensor"]
    if entry.data.get(CONF_SCHOOLSCHEDULE, True):
        platforms.append("calendar")
    else:
        # Unloading only makes calendar entities unavailable, it doesn't remove
        # them from the registry - so when schoolschedule is off, drop any
        # calendar entities left over from when it was previously on.
        entity_registry = er.async_get(hass)
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if entity_entry.domain == "calendar":
                entity_registry.async_remove(entity_entry.entity_id)
    hass_data["platforms"] = platforms
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_update_tokens(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry, tokens: dict
):
    """Persist rotated tokens through HA's config-entry API without reloading."""
    runtime = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if runtime is None:
        _LOGGER.warning("Cannot persist refreshed tokens for an unloaded Aula entry")
        return

    # Snapshot before awaiting anything: the login client mutates this mapping.
    snapshot = tokens.copy()
    if not snapshot.get("access_token") or not snapshot.get("refresh_token"):
        raise ValueError("Refreshed Aula token state is incomplete")

    expires_at = snapshot.get("expires_at", 0)
    try:
        payload = snapshot["access_token"].split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        expires_at = claims.get("exp", expires_at)
    except (IndexError, ValueError, TypeError, UnicodeError):
        pass
    snapshot["expires_at"] = expires_at
    updates = {
        CONF_ACCESS_TOKEN: snapshot["access_token"],
        CONF_REFRESH_TOKEN: snapshot["refresh_token"],
        CONF_TOKEN_EXPIRES_AT: expires_at,
    }

    # Only advance token fields in the applied baseline. A simultaneous feature
    # or options change must still trigger its normal reload.
    baseline = dict(runtime.get("_applied_entry_data", entry.data))
    baseline.update(updates)
    previous_baseline = runtime.get("_applied_entry_data")
    runtime["_applied_entry_data"] = baseline
    try:
        hass.config_entries.async_update_entry(entry, data={**entry.data, **updates})
    except Exception:
        runtime["_applied_entry_data"] = previous_baseline
        raise
    runtime["tokens"] = snapshot
    runtime["stored_tokens"] = snapshot.copy()
    _LOGGER.debug("Refreshed Aula tokens persisted without reloading")


async def options_update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Reload configuration/reauth changes, but not our own token-only saves."""
    runtime = hass.data.get(DOMAIN, {}).get(config_entry.entry_id)
    if runtime is not None and (
        config_entry.data == runtime.get("_applied_entry_data")
        and config_entry.options == runtime.get("_applied_entry_options")
    ):
        return
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    # Unload exactly the platforms that async_setup_entry actually forwarded,
    # not what entry.data currently says - see the comment there for why.
    stored = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    platforms_to_unload = stored.get("platforms")
    if platforms_to_unload is None:
        platforms_to_unload = ["sensor", "binary_sensor"]
        if entry.data.get(CONF_SCHOOLSCHEDULE, True):
            platforms_to_unload.append("calendar")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms_to_unload)

    # Remove options_update_listener.
    if entry.entry_id in hass.data.get(DOMAIN, {}):
        hass.data[DOMAIN][entry.entry_id]["unsub_options_update_listener"]()
        # Remove config entry from domain.
        if unload_ok:
            hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
