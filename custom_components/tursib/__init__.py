import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .sensor import TursibCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Tursib integration from YAML (deprecated)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tursib from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Creează coordinatorul aici
    coordinator = TursibCoordinator(
        hass,
        entry.data["station_id"],
        entry.data["station_name"],
    )

    # Prima actualizare — dacă eșuează, ridică ConfigEntryNotReady
    await coordinator.async_config_entry_first_refresh()

    # Salvează coordinatorul pentru platforma sensor
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward către platforma sensor
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    _LOGGER.info(
        "Tursib integration set up with station: %s (%s)",
        entry.data.get("station_name"),
        entry.data.get("station_id"),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Tursib config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
