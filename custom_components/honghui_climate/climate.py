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
import functools

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

# 添加递归保护计数器
_RECURSION_COUNTERS = {}
_MAX_RECURSION_DEPTH = 3  # 设置最大递归深度

def prevent_recursion(method):
    """防止方法被递归调用超过特定次数的装饰器。"""
    @functools.wraps(method)
    async def wrapper(self, *args, **kwargs):
        # 为每个实体和方法创建唯一键
        key = f"{self.entity_id}_{method.__name__}"
        
        # 初始化或增加计数器
        if key not in _RECURSION_COUNTERS:
            _RECURSION_COUNTERS[key] = 0
        _RECURSION_COUNTERS[key] += 1
        
        try:
            # 检查是否超过最大递归深度
            if _RECURSION_COUNTERS[key] > _MAX_RECURSION_DEPTH:
                _LOGGER.error(
                    "检测到过度递归调用(%s次)：%s - 操作已取消",
                    _RECURSION_COUNTERS[key],
                    key
                )
                return
            
            # 执行原始方法
            return await method(self, *args, **kwargs)
        finally:
            # 减少计数器
            _RECURSION_COUNTERS[key] -= 1
            # 如果计数器归零，移除它以避免内存泄漏
            if _RECURSION_COUNTERS[key] == 0:
                del _RECURSION_COUNTERS[key]
    
    return wrapper


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
    
    # 验证空调实体不是虚拟空调实体，避免递归
    if ac_entity_id.startswith(f"{DOMAIN}."):
        _LOGGER.error(
            "不能使用虚拟空调实体作为源空调实体，这会导致递归调用。请选择真实的空调实体。实体ID: %s",
            ac_entity_id
        )
        return
    
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

    # 启用实体注册表命名，以便正确使用翻译
    _attr_has_entity_name = True
    _attr_name = None  # 不设置名称，让翻译系统处理
    _attr_precision = PRECISION_TENTHS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = "honghui_climate"
    
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
        # 为了防止过多的状态更新，我们使用key来跟踪最近的更新时间
        key = f"{self.entity_id}_ac_changed"
        current_time = self.hass.loop.time()
        
        # 检查是否在短时间内多次更新
        if key in _RECURSION_COUNTERS:
            if isinstance(_RECURSION_COUNTERS[key], dict) and 'time' in _RECURSION_COUNTERS[key]:
                # 如果最近一次更新在1秒内，则增加计数
                if current_time - _RECURSION_COUNTERS[key]['time'] < 1.0:
                    _RECURSION_COUNTERS[key]['count'] += 1
                    # 如果短时间内更新次数太多，则跳过此次更新
                    if _RECURSION_COUNTERS[key]['count'] > _MAX_RECURSION_DEPTH:
                        _LOGGER.debug("跳过短时间内过多的状态更新: %s", key)
                        return
                else:
                    # 重置计数器
                    _RECURSION_COUNTERS[key]['count'] = 1
            else:
                # 如果结构不正确，重新初始化
                _RECURSION_COUNTERS[key] = {'count': 1, 'time': current_time}
        else:
            # 初始化计数器
            _RECURSION_COUNTERS[key] = {'count': 1, 'time': current_time}
        
        # 更新时间戳
        _RECURSION_COUNTERS[key]['time'] = current_time
        
        # 记录事件详情，帮助调试
        _LOGGER.debug("接收到空调状态变化事件: %s", event.data)
        
        self._update_state()
        self.async_write_ha_state()
        
    @callback
    def _async_temp_changed(self, event) -> None:
        """温度传感器状态变化时的处理."""
        # 温度传感器的变化通常不会导致递归，所以简单处理
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
        
        # 防止无限递归的简单检查 - 标记正在更新过程中
        key = f"{self.entity_id}_updating"
        if key in _RECURSION_COUNTERS and _RECURSION_COUNTERS[key] > 0:
            _RECURSION_COUNTERS[key] += 1
            if _RECURSION_COUNTERS[key] > _MAX_RECURSION_DEPTH:
                _LOGGER.debug("跳过递归状态更新: %s", key)
                return
        else:
            _RECURSION_COUNTERS[key] = 1
            
        try:
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
                _LOGGER.debug(
                    "从源空调更新温度 - 目标温度: %s, 最小: %s, 最大: %s, 步长: %s",
                    self._attr_target_temperature,
                    self._attr_min_temp,
                    self._attr_max_temp,
                    self._attr_target_temperature_step
                )
            else:
                _LOGGER.debug("源空调 %s 状态中没有温度属性", self._ac_entity_id)
                
            # 从温度传感器获取当前温度
            temp_state = self.hass.states.get(self._temp_entity_id)
            if temp_state is not None and temp_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    self._attr_current_temperature = float(temp_state.state)
                except ValueError:
                    _LOGGER.error("无法将温度传感器值转换为数字: %s", temp_state.state)
                    
            # 更新HVAC操作状态
            if self.hvac_mode == HVACMode.OFF:
                self._attr_hvac_action = HVACAction.OFF
            elif hasattr(self, "current_temperature") and hasattr(self, "target_temperature"):
                if self.hvac_mode == HVACMode.COOL and self.current_temperature > self.target_temperature:
                    self._attr_hvac_action = HVACAction.COOLING
                elif self.hvac_mode == HVACMode.HEAT and self.current_temperature < self.target_temperature:
                    self._attr_hvac_action = HVACAction.HEATING
                else:
                    self._attr_hvac_action = HVACAction.IDLE
            else:
                self._attr_hvac_action = HVACAction.IDLE
        finally:
            # 减少递归计数器
            _RECURSION_COUNTERS[key] -= 1
            if _RECURSION_COUNTERS[key] == 0:
                del _RECURSION_COUNTERS[key]
        
    @prevent_recursion
    async def async_set_temperature(self, **kwargs) -> None:
        """设置温度."""
        # 检查目标实体ID，防止递归调用
        entity_id = self.entity_id  # 获取当前实体的完整实体ID
        if self._ac_entity_id == entity_id or self._ac_entity_id.startswith(f"{DOMAIN}."):
            _LOGGER.error("检测到递归调用：无法将温度设置传递给虚拟空调实体 %s", self._ac_entity_id)
            return
            
        # 记录传入的参数，帮助调试
        _LOGGER.debug("设置温度请求参数: %s", kwargs)
        
        # 确保温度值正确传递
        service_data = {"entity_id": self._ac_entity_id}
        
        # 提取关键参数
        if ATTR_TEMPERATURE in kwargs:
            service_data[ATTR_TEMPERATURE] = kwargs[ATTR_TEMPERATURE]
            _LOGGER.debug("正在设置目标空调 %s 的温度为 %s", 
                          self._ac_entity_id, kwargs[ATTR_TEMPERATURE])
        else:
            _LOGGER.warning("设置温度请求中缺少温度参数")
            return
            
        # 传递其他可能的参数
        if "hvac_mode" in kwargs:
            service_data["hvac_mode"] = kwargs["hvac_mode"]
        if "target_temp_high" in kwargs:
            service_data["target_temp_high"] = kwargs["target_temp_high"]
        if "target_temp_low" in kwargs:
            service_data["target_temp_low"] = kwargs["target_temp_low"]

        # 将温度设置传递给源空调
        try:
            # 检查目标空调实体是否存在
            ac_state = self.hass.states.get(self._ac_entity_id)
            if ac_state is None:
                _LOGGER.error("无法设置温度: 目标空调实体 %s 不存在", self._ac_entity_id)
                return
                
            # 检查目标空调是否支持温度设置
            if not hasattr(ac_state.attributes, 'get') or ATTR_TEMPERATURE not in ac_state.attributes:
                _LOGGER.warning("目标空调实体 %s 可能不支持温度设置", self._ac_entity_id)
                # 继续尝试设置，因为有些实体可能接受设置但不报告属性
            
            # 直接调用服务设置温度
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                service_data,
                blocking=True,
            )
            
            # 在温度设置后主动更新一次状态，确保变化被反映
            self._update_state()
            self.async_write_ha_state()
            
            _LOGGER.debug("成功发送温度设置到目标空调: %s", service_data)
        except Exception as e:
            _LOGGER.error("设置目标空调温度时出错: %s, 错误: %s", self._ac_entity_id, str(e))
        
    @prevent_recursion
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """设置HVAC模式."""
        # 检查目标实体ID，防止递归调用
        entity_id = self.entity_id  # 获取当前实体的完整实体ID
        if self._ac_entity_id == entity_id or self._ac_entity_id.startswith(f"{DOMAIN}."):
            _LOGGER.error("检测到递归调用：无法将HVAC模式设置传递给虚拟空调实体 %s", self._ac_entity_id)
            return
            
        # 记录正在设置的模式
        _LOGGER.debug("设置HVAC模式: %s 到目标空调: %s", hvac_mode, self._ac_entity_id)
        
        try:
            # 将模式设置传递给源空调
            await self.hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {"entity_id": self._ac_entity_id, "hvac_mode": hvac_mode},
                blocking=True,
            )
            
            # 保存当前的目标温度，以备需要
            current_target_temp = self.target_temperature if hasattr(self, "target_temperature") else None
            
            # 更新状态以反映模式变化
            self._update_state()
            self.async_write_ha_state()
            
            # 如果模式变化后目标温度丢失，尝试重新设置
            if hvac_mode != HVACMode.OFF and current_target_temp is not None:
                # 获取更新后的状态
                ac_state = self.hass.states.get(self._ac_entity_id)
                if ac_state and ATTR_TEMPERATURE not in ac_state.attributes:
                    _LOGGER.debug("模式变化后目标温度丢失，尝试重新设置: %s", current_target_temp)
                    # 重新设置温度
                    await self.async_set_temperature(**{ATTR_TEMPERATURE: current_target_temp})
                    
            _LOGGER.debug("成功设置HVAC模式: %s", hvac_mode)
        except Exception as e:
            _LOGGER.error("设置HVAC模式时出错: %s, 错误: %s", hvac_mode, str(e))
        
    @prevent_recursion
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """设置风扇模式."""
        # 检查目标实体ID，防止递归调用
        entity_id = self.entity_id  # 获取当前实体的完整实体ID
        if self._ac_entity_id == entity_id or self._ac_entity_id.startswith(f"{DOMAIN}."):
            _LOGGER.error("检测到递归调用：无法将风扇模式设置传递给虚拟空调实体 %s", self._ac_entity_id)
            return
            
        # 将风扇模式设置传递给源空调
        await self.hass.services.async_call(
            "climate",
            "set_fan_mode",
            {"entity_id": self._ac_entity_id, "fan_mode": fan_mode},
            blocking=True,
        )
        
    @prevent_recursion
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """设置摆动模式."""
        # 检查目标实体ID，防止递归调用
        entity_id = self.entity_id  # 获取当前实体的完整实体ID
        if self._ac_entity_id == entity_id or self._ac_entity_id.startswith(f"{DOMAIN}."):
            _LOGGER.error("检测到递归调用：无法将摆动模式设置传递给虚拟空调实体 %s", self._ac_entity_id)
            return
            
        # 将摆动模式设置传递给源空调
        await self.hass.services.async_call(
            "climate",
            "set_swing_mode",
            {"entity_id": self._ac_entity_id, "swing_mode": swing_mode},
            blocking=True,
        ) 