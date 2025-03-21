"""HongHui Climate 气候实体."""
from __future__ import annotations

import logging
import asyncio
from typing import Any, Final, List, cast

import voluptuous as vol

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_AC_ENTITY_ID,
    CONF_TEMP_ENTITY_ID,
    DEFAULT_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# 重试间隔和最大尝试次数
RETRY_INTERVAL = 10  # 秒
MAX_RETRIES = 12  # 最多重试12次，总共2分钟


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """设置HongHui Climate气候实体."""
    ac_entity_id = entry.data[CONF_AC_ENTITY_ID]
    temp_entity_id = entry.data[CONF_TEMP_ENTITY_ID]
    
    # 确保配置项存在
    if not ac_entity_id or not temp_entity_id:
        _LOGGER.error("缺少必要的配置项：空调实体或温度传感器实体")
        return
    
    # 创建延迟加载任务，等待依赖实体加载完成
    hass.async_create_task(
        async_setup_climate_with_retry(
            hass, entry, async_add_entities, ac_entity_id, temp_entity_id
        )
    )


async def async_setup_climate_with_retry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    ac_entity_id: str,
    temp_entity_id: str,
    attempt: int = 0,
) -> None:
    """尝试设置气候实体，如果失败则重试."""
    # 检查实体是否都已加载
    ac_entity_available = hass.states.get(ac_entity_id) is not None
    temp_entity_available = hass.states.get(temp_entity_id) is not None
    
    if not ac_entity_available or not temp_entity_available:
        if attempt >= MAX_RETRIES:
            _LOGGER.error(
                "在多次尝试后仍无法找到必要的实体。空调实体: %s (%s), 温度传感器实体: %s (%s)",
                ac_entity_id,
                "可用" if ac_entity_available else "不可用",
                temp_entity_id,
                "可用" if temp_entity_available else "不可用",
            )
            return
            
        attempt += 1
        _LOGGER.debug(
            "等待实体加载，尝试 %s/%s。空调实体: %s (%s), 温度传感器实体: %s (%s)",
            attempt,
            MAX_RETRIES,
            ac_entity_id,
            "可用" if ac_entity_available else "不可用",
            temp_entity_id,
            "可用" if temp_entity_available else "不可用",
        )
        
        # 延迟后重试
        await asyncio.sleep(RETRY_INTERVAL)
        await async_setup_climate_with_retry(
            hass, entry, async_add_entities, ac_entity_id, temp_entity_id, attempt
        )
        return
    
    # 到这里，说明两个实体都已加载
    _LOGGER.info("创建洪绘空调实体，使用空调：%s，温度传感器：%s", ac_entity_id, temp_entity_id)
    
    entity = HonghuiAirClimate(
        hass=hass,
        entry_id=entry.entry_id,
        ac_entity_id=ac_entity_id,
        temp_entity_id=temp_entity_id
    )
    
    async_add_entities([entity], True)


class HonghuiAirClimate(ClimateEntity):
    """表示虚拟空调实体."""

    # 不设置has_entity_name，使用自定义名称
    _attr_name = DEFAULT_NAME
    _attr_precision = PRECISION_TENTHS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = "climate"
    
    # 预设一些基本属性，防止初始化时出错
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.AUTO]
    _attr_hvac_mode = HVACMode.OFF
    _attr_hvac_action = HVACAction.OFF
    _attr_fan_modes = []
    _attr_swing_modes = []

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        ac_entity_id: str,
        temp_entity_id: str,
    ) -> None:
        """初始化虚拟空调."""
        self.hass = hass
        self._entry_id = entry_id
        self._ac_entity_id = ac_entity_id
        self._temp_entity_id = temp_entity_id
        
        # 生成唯一ID
        self._attr_unique_id = f"{DOMAIN}_{entry_id}"
        
        # 设备信息
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=DEFAULT_NAME,
            manufacturer="Honghui",
            model="Virtual AC",
        )
        
        # 跟踪源实体的变化
        self._unsubscribe_ac = None
        self._unsubscribe_temp = None
        
    async def async_added_to_hass(self) -> None:
        """实体添加到Home Assistant时的处理."""
        await super().async_added_to_hass()
        
        self._unsubscribe_ac = async_track_state_change_event(
            self.hass, [self._ac_entity_id], self._async_ac_changed
        )
        
        self._unsubscribe_temp = async_track_state_change_event(
            self.hass, [self._temp_entity_id], self._async_temp_changed
        )
        
        # 初始状态更新
        self._update_state()
        
    async def async_will_remove_from_hass(self) -> None:
        """实体从Home Assistant移除时的处理."""
        if self._unsubscribe_ac:
            self._unsubscribe_ac()
        if self._unsubscribe_temp:
            self._unsubscribe_temp()
            
    @callback
    def _async_ac_changed(self, event) -> None:
        """空调实体状态变化时的处理."""
        self._update_state()
        self.async_write_ha_state()
        
    @callback
    def _async_temp_changed(self, event) -> None:
        """温度传感器状态变化时的处理."""
        self._update_state()
        self.async_write_ha_state()
        
    def _update_state(self) -> None:
        """更新实体状态."""
        # 获取源空调实体状态
        ac_state = self.hass.states.get(self._ac_entity_id)
        if ac_state is None or ac_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            # 源空调不可用时，我们的虚拟空调也不可用
            self._attr_available = False
            return
        
        self._attr_available = True
        
        # 从源空调复制模式和功能
        try:
            self._attr_hvac_mode = HVACMode(ac_state.state) if ac_state.state in [mode.value for mode in HVACMode] else HVACMode.OFF
        except ValueError:
            self._attr_hvac_mode = HVACMode.OFF
            
        # 重置HVAC模式列表
        self._attr_hvac_modes = [HVACMode.OFF]
        
        # 获取支持的模式
        for mode in HVACMode:
            if mode.value in ac_state.attributes.get("hvac_modes", []):
                if mode not in self._attr_hvac_modes:
                    self._attr_hvac_modes.append(mode)
                
        # 复制风扇模式
        if "fan_modes" in ac_state.attributes and "fan_mode" in ac_state.attributes:
            self._attr_fan_modes = ac_state.attributes.get("fan_modes", [])
            self._attr_fan_mode = ac_state.attributes.get("fan_mode")
            
        # 复制摆动模式
        if "swing_modes" in ac_state.attributes and "swing_mode" in ac_state.attributes:
            self._attr_swing_modes = ac_state.attributes.get("swing_modes", [])
            self._attr_swing_mode = ac_state.attributes.get("swing_mode")
            
        # 从源空调获取目标温度
        if ATTR_TEMPERATURE in ac_state.attributes:
            self._attr_target_temperature = ac_state.attributes.get(ATTR_TEMPERATURE)
            self._attr_target_temperature_high = ac_state.attributes.get("target_temp_high")
            self._attr_target_temperature_low = ac_state.attributes.get("target_temp_low")
            self._attr_max_temp = ac_state.attributes.get("max_temp")
            self._attr_min_temp = ac_state.attributes.get("min_temp")
            self._attr_target_temperature_step = ac_state.attributes.get("target_temp_step", 1)
            
        # 从温度传感器获取当前温度
        temp_state = self.hass.states.get(self._temp_entity_id)
        if temp_state is not None and temp_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                self._attr_current_temperature = float(temp_state.state)
            except (ValueError, TypeError):
                _LOGGER.warning("无法从温度传感器获取有效温度: %s", temp_state.state)
                
        # 设置空调动作
        if self.hvac_mode == HVACMode.OFF:
            self._attr_hvac_action = HVACAction.OFF
        elif ac_state.attributes.get("hvac_action"):
            try:
                self._attr_hvac_action = HVACAction(ac_state.attributes.get("hvac_action"))
            except ValueError:
                self._attr_hvac_action = HVACAction.IDLE
        else:
            # 根据目标温度和当前温度推断动作
            if hasattr(self, "current_temperature") and hasattr(self, "target_temperature"):
                if self.hvac_mode == HVACMode.COOL and self.current_temperature > self.target_temperature:
                    self._attr_hvac_action = HVACAction.COOLING
                elif self.hvac_mode == HVACMode.HEAT and self.current_temperature < self.target_temperature:
                    self._attr_hvac_action = HVACAction.HEATING
                else:
                    self._attr_hvac_action = HVACAction.IDLE
            else:
                self._attr_hvac_action = HVACAction.IDLE
                
    async def async_set_temperature(self, **kwargs) -> None:
        """设置温度."""
        # 将温度设置传递给源空调
        await self.hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": self._ac_entity_id, **kwargs},
            blocking=True,
        )
        
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """设置HVAC模式."""
        # 将模式设置传递给源空调
        await self.hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": self._ac_entity_id, "hvac_mode": hvac_mode},
            blocking=True,
        )
        
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """设置风扇模式."""
        # 将风扇模式设置传递给源空调
        await self.hass.services.async_call(
            "climate",
            "set_fan_mode",
            {"entity_id": self._ac_entity_id, "fan_mode": fan_mode},
            blocking=True,
        )
        
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """设置摆动模式."""
        # 将摆动模式设置传递给源空调
        await self.hass.services.async_call(
            "climate",
            "set_swing_mode",
            {"entity_id": self._ac_entity_id, "swing_mode": swing_mode},
            blocking=True,
        ) 