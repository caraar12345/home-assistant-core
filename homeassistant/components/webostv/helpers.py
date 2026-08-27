"""Helper functions for LG webOS TV."""

from collections.abc import Iterable
from typing import TYPE_CHECKING

from aiowebostv import WebOsTvState

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_SOURCES, DOMAIN, LIVE_TV_APP_ID, LOGGER

if TYPE_CHECKING:
    from .coordinator import WebOsTvConfigEntry


@callback
def async_get_device_entry_by_device_id(
    hass: HomeAssistant, device_id: str
) -> DeviceEntry:
    """Get Device Entry from Device Registry by device ID.

    Raises ValueError if device ID is invalid.
    """
    device_reg = dr.async_get(hass)
    if (device := device_reg.async_get(device_id, include_child_devices=False)) is None:
        raise ValueError(f"Device {device_id} is not a valid {DOMAIN} device.")

    return device


@callback
def async_get_device_id_from_entity_id(hass: HomeAssistant, entity_id: str) -> str:
    """Get device ID from an entity ID.

    Raises HomeAssistantError if entity or device ID is invalid.
    """
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id)

    if (
        entity_entry is None
        or entity_entry.device_id is None
        or entity_entry.platform != DOMAIN
    ):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_entity_id",
            translation_placeholders={"entity_id": entity_id},
        )

    return entity_entry.device_id


def get_sources(tv_state: WebOsTvState) -> dict[str, str]:
    """Construct mapping of stable source id to its current display label."""
    sources: dict[str, str] = {}
    found_live_tv = False
    for app in tv_state.apps.values():
        sources[app["id"]] = app["title"]
        if app["id"] == LIVE_TV_APP_ID:
            found_live_tv = True

    for source in tv_state.inputs.values():
        sources[source["appId"]] = source["label"]
        if source["appId"] == LIVE_TV_APP_ID:
            found_live_tv = True

    if not found_live_tv:
        sources[LIVE_TV_APP_ID] = "Live TV"

    return sources


def sources_to_ids(
    available_sources: dict[str, str], sources: Iterable[str]
) -> list[str]:
    """Translate configured sources (ids or legacy labels) to their current id.

    A source already matching a current id is kept as-is. A source matching a
    current label is translated to that id. Anything that matches neither (the
    source may have been renamed away, or the TV state may be incomplete, for
    example if the TV was off) is left untouched.
    """
    label_to_id = {label: source_id for source_id, label in available_sources.items()}
    return list(
        dict.fromkeys(
            source if source in available_sources else label_to_id.get(source, source)
            for source in sources
        )
    )


@callback
def async_migrate_sources_option(
    hass: HomeAssistant, entry: WebOsTvConfigEntry, tv_state: WebOsTvState
) -> None:
    """Rewrite configured sources that still match a current label to their id.

    Older versions matched a configured source by its display label, which stops
    working once that source is renamed on the TV.
    """
    configured_sources = entry.options.get(CONF_SOURCES)
    if not configured_sources:
        return

    migrated_sources = sources_to_ids(get_sources(tv_state), configured_sources)

    if migrated_sources != configured_sources:
        LOGGER.debug(
            "Migrating sources option for %s from %s to %s",
            entry.title,
            configured_sources,
            migrated_sources,
        )
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_SOURCES: migrated_sources}
        )
