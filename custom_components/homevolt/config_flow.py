"""Config flow for Homevolt integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HomevoltApiClient, HomevoltAuthError, HomevoltConnectionError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            int, vol.Range(min=10, max=300)
        ),
    }
)


class HomevoltConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homevolt."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None
        self._port: int = DEFAULT_PORT

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step (manual entry)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            password = user_input.get(CONF_PASSWORD)

            session = async_get_clientsession(self.hass)
            client = HomevoltApiClient(
                session=session, host=host, port=port, password=password
            )

            try:
                ems_data = await client.async_validate_connection()
            except HomevoltAuthError:
                errors["base"] = "invalid_auth"
            except HomevoltConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"
            else:
                # Use ecu_id from first EMS device as unique ID
                ecu_id = str(ems_data.ems[0].ecu_id) if ems_data.ems else host
                await self.async_set_unique_id(ecu_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Homevolt ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_PASSWORD: password,
                    },
                    options={
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: Any
    ) -> ConfigFlowResult:
        """Handle Zeroconf discovery."""
        host = str(discovery_info.host)
        port = discovery_info.port or DEFAULT_PORT
        self._host = host
        self._port = port

        # Try to connect and get unique ID
        session = async_get_clientsession(self.hass)
        client = HomevoltApiClient(session=session, host=host, port=port)

        try:
            ems_data = await client.async_validate_connection()
        except (HomevoltConnectionError, HomevoltAuthError):
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.debug("Unexpected error during Zeroconf validation", exc_info=True)
            return self.async_abort(reason="cannot_connect")

        ecu_id = str(ems_data.ems[0].ecu_id) if ems_data.ems else host
        await self.async_set_unique_id(ecu_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self.context["title_placeholders"] = {"name": f"Homevolt ({host})"}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Zeroconf discovery."""
        if user_input is not None:
            password = user_input.get(CONF_PASSWORD)
            return self.async_create_entry(
                title=f"Homevolt ({self._host})",
                data={
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    CONF_PASSWORD: password,
                },
                options={
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                },
            )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={"host": self._host},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of host/port/password."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            password = user_input.get(CONF_PASSWORD)

            session = async_get_clientsession(self.hass)
            client = HomevoltApiClient(
                session=session, host=host, port=port, password=password
            )

            try:
                await client.async_validate_connection()
            except HomevoltAuthError:
                errors["base"] = "invalid_auth"
            except HomevoltConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during reconfigure")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    title=f"Homevolt ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_PASSWORD: password,
                    },
                )

        current_data = self._get_reconfigure_entry().data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=current_data.get(CONF_HOST, "")
                    ): str,
                    vol.Optional(CONF_PASSWORD): str,
                    vol.Optional(
                        CONF_PORT,
                        default=current_data.get(CONF_PORT, DEFAULT_PORT),
                    ): int,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return HomevoltOptionsFlow()


class HomevoltOptionsFlow(OptionsFlow):
    """Handle options for Homevolt."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options step."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_SCAN_INTERVAL, default=current): vol.All(
                        int, vol.Range(min=10, max=300)
                    ),
                }
            ),
        )
