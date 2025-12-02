import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN

CONF_STATION_ID = "station_id"
CONF_STATION_NAME = "station_name"


class TursibConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tursib."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Creează intrarea cu cheile corecte
            return self.async_create_entry(
                title=user_input[CONF_STATION_NAME],
                data={
                    CONF_STATION_ID: user_input[CONF_STATION_ID],
                    CONF_STATION_NAME: user_input[CONF_STATION_NAME],
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_STATION_ID): str,
                vol.Required(CONF_STATION_NAME): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class TursibOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Tursib."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_STATION_ID: user_input[CONF_STATION_ID],
                    CONF_STATION_NAME: user_input[CONF_STATION_NAME],
                },
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_STATION_ID,
                    default=self.config_entry.data.get(CONF_STATION_ID, ""),
                ): str,
                vol.Required(
                    CONF_STATION_NAME,
                    default=self.config_entry.data.get(CONF_STATION_NAME, ""),
                ): str,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
