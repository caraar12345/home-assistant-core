"""Test the Mailgun notify platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components import mailgun
from homeassistant.const import CONF_API_KEY, CONF_DOMAIN, CONF_RECIPIENT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_mailgunner_client():
    """Mock the pymailgunner Client."""
    with patch("homeassistant.components.mailgun.notify.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.domain = "example.com"
        mock_client.return_value = mock_instance
        yield mock_client


async def test_notify_with_eu_domain_true(
    hass: HomeAssistant, mock_mailgunner_client
) -> None:
    """Test that eu_domain=True is passed to the Client."""
    config = {
        mailgun.DOMAIN: {
            CONF_API_KEY: "test_api_key",
            CONF_DOMAIN: "example.com",
            mailgun.CONF_EU_DOMAIN: True,
        },
        "notify": {
            "platform": "mailgun",
            CONF_RECIPIENT: "test@example.com",
        },
    }

    assert await async_setup_component(hass, "notify", config)
    await hass.async_block_till_done()

    # Verify Client was called with eu_domain=True
    mock_mailgunner_client.assert_called_once_with(
        "test_api_key", "example.com", False, True
    )


async def test_notify_with_eu_domain_false(
    hass: HomeAssistant, mock_mailgunner_client
) -> None:
    """Test that eu_domain=False is passed to the Client."""
    config = {
        mailgun.DOMAIN: {
            CONF_API_KEY: "test_api_key",
            CONF_DOMAIN: "example.com",
            mailgun.CONF_EU_DOMAIN: False,
        },
        "notify": {
            "platform": "mailgun",
            CONF_RECIPIENT: "test@example.com",
        },
    }

    assert await async_setup_component(hass, "notify", config)
    await hass.async_block_till_done()

    # Verify Client was called with eu_domain=False
    mock_mailgunner_client.assert_called_once_with(
        "test_api_key", "example.com", False, False
    )


async def test_notify_without_eu_domain(
    hass: HomeAssistant, mock_mailgunner_client
) -> None:
    """Test backward compatibility when eu_domain is not specified."""
    config = {
        mailgun.DOMAIN: {
            CONF_API_KEY: "test_api_key",
            CONF_DOMAIN: "example.com",
        },
        "notify": {
            "platform": "mailgun",
            CONF_RECIPIENT: "test@example.com",
        },
    }

    assert await async_setup_component(hass, "notify", config)
    await hass.async_block_till_done()

    # Verify Client was called with eu_domain=False (default)
    mock_mailgunner_client.assert_called_once_with(
        "test_api_key", "example.com", False, False
    )


async def test_notify_with_sandbox_and_eu_domain(
    hass: HomeAssistant, mock_mailgunner_client
) -> None:
    """Test that both sandbox and eu_domain parameters work together."""
    config = {
        mailgun.DOMAIN: {
            CONF_API_KEY: "test_api_key",
            CONF_DOMAIN: "example.com",
            mailgun.CONF_SANDBOX: True,
            mailgun.CONF_EU_DOMAIN: True,
        },
        "notify": {
            "platform": "mailgun",
            CONF_RECIPIENT: "test@example.com",
        },
    }

    assert await async_setup_component(hass, "notify", config)
    await hass.async_block_till_done()

    # Verify Client was called with sandbox=True and eu_domain=True
    mock_mailgunner_client.assert_called_once_with(
        "test_api_key", "example.com", True, True
    )
