"""The tests for the LG webOS TV platform."""

from aiowebostv import WebOsTvPairError

from homeassistant.components.media_player import ATTR_INPUT_SOURCE_LIST
from homeassistant.components.webostv.const import CONF_SOURCES, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_CLIENT_SECRET, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from . import setup_webostv
from .const import ENTITY_ID


async def test_reauth_setup_entry(hass: HomeAssistant, client) -> None:
    """Test reauth flow triggered by setup entry."""
    client.is_connected.return_value = False
    client.connect.side_effect = WebOsTvPairError
    entry = await setup_webostv(hass)

    assert entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_key_update_setup_entry(hass: HomeAssistant, client) -> None:
    """Test key update from setup entry."""
    client.is_connected.return_value = False
    client.client_key = "new_key"
    entry = await setup_webostv(hass)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_CLIENT_SECRET] == "new_key"


async def test_update_options(hass: HomeAssistant, client) -> None:
    """Test update options triggers reload."""
    config_entry = await setup_webostv(hass)

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.update_listeners is not None
    sources = hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]
    assert sources == ["Input01", "Input02", "Live TV"]

    # remove Input01 and reload
    new_options = config_entry.options.copy()
    new_options[CONF_SOURCES] = ["Input02", "Live TV"]
    hass.config_entries.async_update_entry(config_entry, options=new_options)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    sources = hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]
    assert sources == ["Input02", "Live TV"]


async def test_source_filtered_by_id_survives_rename(
    hass: HomeAssistant, client
) -> None:
    """Test a source selected by its stable id is kept after being renamed on the TV."""
    config_entry = await setup_webostv(hass)

    new_options = config_entry.options.copy()
    new_options[CONF_SOURCES] = ["app0"]
    hass.config_entries.async_update_entry(config_entry, options=new_options)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    sources = hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]
    assert sources == ["Input01", "Live TV"]

    # rename the input on the TV
    client.tv_state.inputs = {
        **client.tv_state.inputs,
        "in1": {**client.tv_state.inputs["in1"], "label": "AVR"},
    }
    await client.mock_state_update()
    await hass.async_block_till_done()

    sources = hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]
    assert sources == ["AVR", "Live TV"]


async def test_source_options_migrated_to_id(hass: HomeAssistant, client) -> None:
    """Test a source configured by its label is silently migrated to its id."""
    config_entry = await setup_webostv(hass)

    new_options = {**config_entry.options, CONF_SOURCES: ["Input01"]}
    hass.config_entries.async_update_entry(config_entry, options=new_options)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.options[CONF_SOURCES] == ["app0"]
    sources = hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]
    assert sources == ["Input01", "Live TV"]

    # migrating an already-migrated option is a no-op
    hass.config_entries.async_update_entry(config_entry, options=config_entry.options)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.options[CONF_SOURCES] == ["app0"]


async def test_unmatched_source_option_preserved(hass: HomeAssistant, client) -> None:
    """Test a source that matches nothing right now is left untouched, not dropped."""
    config_entry = await setup_webostv(hass)

    # "AVR" doesn't match any known source or label
    new_options = {**config_entry.options, CONF_SOURCES: ["Input02", "AVR"]}
    hass.config_entries.async_update_entry(config_entry, options=new_options)
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.options[CONF_SOURCES] == ["app1", "AVR"]

    sources = hass.states.get(ENTITY_ID).attributes[ATTR_INPUT_SOURCE_LIST]
    assert sources == ["Input02", "Live TV"]


async def test_source_options_untouched_when_tv_state_empty(
    hass: HomeAssistant, client
) -> None:
    """Test sources aren't dropped if the TV reports no apps or inputs on setup."""
    config_entry = await setup_webostv(hass)

    new_options = {**config_entry.options, CONF_SOURCES: ["app0", "app1"]}
    hass.config_entries.async_update_entry(config_entry, options=new_options)

    # simulate the TV being off/unreachable, e.g. right after a HA restart
    client.tv_state.apps = {}
    client.tv_state.inputs = {}
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.options[CONF_SOURCES] == ["app0", "app1"]


async def test_source_option_untouched_when_unset(hass: HomeAssistant, client) -> None:
    """Test setup doesn't add a sources option when none is configured."""
    config_entry = await setup_webostv(hass)

    assert CONF_SOURCES not in config_entry.options


async def test_disconnect_on_stop(hass: HomeAssistant, client) -> None:
    """Test we disconnect the client and clear callbacks when Home Assistants stops."""
    config_entry = await setup_webostv(hass)

    assert client.disconnect.call_count == 0
    assert client.clear_state_update_callbacks.call_count == 0
    assert config_entry.state is ConfigEntryState.LOADED

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert client.disconnect.call_count == 1
    assert client.clear_state_update_callbacks.call_count == 1
    assert config_entry.state is ConfigEntryState.LOADED
