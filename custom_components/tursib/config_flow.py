import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_NAME

from .const import DOMAIN

CONF_STATIONS = "stations"


class TursibConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tursib."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Validate that at least one station is provided
            stations = user_input.get(CONF_STATIONS, {})
            if not stations:
                errors["base"] = "no_stations"
            else:
                return self.async_create_entry(title="Tursib", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_STATIONS): vol.Schema(
                    {
                        vol.Required("123"): str,
                        vol.Optional("456"): str,
                    }
                )
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    @callback
    def async_get_options_flow(config_entry):
        return TursibOptionsFlowHandler(config_entry)


class TursibOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Tursib."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        stations = self.config_entry.data.get(CONF_STATIONS, {})

        schema = vol.Schema(
            {
                vol.Required(CONF_STATIONS, default=stations): dict,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
