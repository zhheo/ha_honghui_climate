"""HongHui Climate 集成的配置流程."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
)
from homeassistant.const import Platform

from .const import (
    CONF_AC_ENTITY_ID,
    CONF_TEMP_ENTITY_ID,
    DEFAULT_NAME,
    DOMAIN,
)


class HonghuiAirConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """HongHui Climate 配置流程处理."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """处理用户配置步骤."""
        errors = {}

        if user_input is not None:
            # 验证选择的实体是否存在
            if not self.hass.states.get(user_input[CONF_AC_ENTITY_ID]):
                errors[CONF_AC_ENTITY_ID] = "entity_not_found"
            if not self.hass.states.get(user_input[CONF_TEMP_ENTITY_ID]):
                errors[CONF_TEMP_ENTITY_ID] = "entity_not_found"
                
            # 验证空调实体不是虚拟空调实体，避免递归
            if user_input[CONF_AC_ENTITY_ID].startswith(f"{DOMAIN}."):
                errors[CONF_AC_ENTITY_ID] = "cannot_use_virtual_climate"

            if not errors:
                # 检查这种配置是否已存在
                await self.async_set_unique_id(
                    f"{user_input[CONF_AC_ENTITY_ID]}_{user_input[CONF_TEMP_ENTITY_ID]}"
                )
                self._abort_if_unique_id_configured()
                
                # 创建条目
                return self.async_create_entry(
                    title=f"{DEFAULT_NAME}: {user_input[CONF_AC_ENTITY_ID].split('.')[-1]}",
                    data=user_input,
                )

        # 创建配置表单
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AC_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(domain=Platform.CLIMATE)
                    ),
                    vol.Required(CONF_TEMP_ENTITY_ID): EntitySelector(
                        EntitySelectorConfig(domain=Platform.SENSOR)
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """创建选项流."""
        return HonghuiAirOptionsFlow(config_entry)


class HonghuiAirOptionsFlow(config_entries.OptionsFlow):
    """HongHui Climate 选项流程类."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """初始化选项流程."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """管理选项."""
        errors = {}

        if user_input is not None:
            # 验证选择的实体是否存在
            if not self.hass.states.get(user_input[CONF_AC_ENTITY_ID]):
                errors[CONF_AC_ENTITY_ID] = "entity_not_found"
            if not self.hass.states.get(user_input[CONF_TEMP_ENTITY_ID]):
                errors[CONF_TEMP_ENTITY_ID] = "entity_not_found"
                
            # 验证空调实体不是虚拟空调实体，避免递归
            if user_input[CONF_AC_ENTITY_ID].startswith(f"{DOMAIN}."):
                errors[CONF_AC_ENTITY_ID] = "cannot_use_virtual_climate"

            if not errors:
                # 更新条目数据
                data = {**self.config_entry.data}
                data.update(user_input)
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=data
                )
                return self.async_create_entry(title="", data={})

        # 获取现有配置
        data = {**self.config_entry.data}

        # 创建选项表单
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AC_ENTITY_ID, default=data.get(CONF_AC_ENTITY_ID)
                    ): EntitySelector(EntitySelectorConfig(domain=Platform.CLIMATE)),
                    vol.Required(
                        CONF_TEMP_ENTITY_ID, default=data.get(CONF_TEMP_ENTITY_ID)
                    ): EntitySelector(EntitySelectorConfig(domain=Platform.SENSOR)),
                }
            ),
            errors=errors,
        ) 