"""HongHui Climate 集成."""
from __future__ import annotations

import logging
import voluptuous as vol
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.const import Platform, ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_STARTED
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import (
    EntityRegistry,
    async_get as async_get_entity_registry,
)

from .const import DOMAIN, CONF_AC_ENTITY_ID, CONF_TEMP_ENTITY_ID

# 防止递归锁
_SERVICE_LOCKS = {}
_MAX_SERVICE_FREQUENCY = 1.0  # 服务调用最小间隔时间（秒）

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE]

# 服务架构
SERVICE_SET_AC_ENTITY = "set_ac_entity"
SERVICE_SET_TEMP_ENTITY = "set_temp_entity"

SET_AC_ENTITY_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_AC_ENTITY_ID): cv.entity_id,
})

SET_TEMP_ENTITY_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_TEMP_ENTITY_ID): cv.entity_id,
})

# 定义 CONFIG_SCHEMA
CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN): vol.Schema({
        vol.Optional(CONF_AC_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_TEMP_ENTITY_ID): cv.entity_id,
    })
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """设置HongHui Climate集成。"""
    _LOGGER.info("设置洪绘空调集成")
    
    # 初始化数据结构
    hass.data.setdefault(DOMAIN, {})
    
    # 注册服务
    async def async_handle_set_ac_entity(call: ServiceCall) -> None:
        """处理设置空调实体服务。"""
        entity_id = call.data[ATTR_ENTITY_ID]
        ac_entity_id = call.data[CONF_AC_ENTITY_ID]
        
        # 防止服务频繁调用
        lock_key = f"set_ac_{entity_id}"
        current_time = time.time()
        if lock_key in _SERVICE_LOCKS:
            elapsed = current_time - _SERVICE_LOCKS[lock_key]
            if elapsed < _MAX_SERVICE_FREQUENCY:
                _LOGGER.warning(
                    "服务调用过于频繁，距离上次调用仅 %.2f 秒，已跳过: %s", 
                    elapsed, lock_key
                )
                return
        _SERVICE_LOCKS[lock_key] = current_time
        
        # 检查是否试图将实体设置为虚拟空调
        if ac_entity_id.startswith(f"{DOMAIN}."):
            _LOGGER.error("不能将空调实体设置为虚拟空调实体: %s", ac_entity_id)
            return
        
        # 获取实体条目ID
        entity_registry = hass.helpers.entity_registry.async_get(hass)
        entity_entry = entity_registry.async_get(entity_id)
        
        if not entity_entry or not entity_entry.config_entry_id:
            _LOGGER.error("找不到实体 %s 或其配置条目", entity_id)
            return
            
        entry_id = entity_entry.config_entry_id
        
        # 更新配置条目
        config_entries = hass.config_entries
        entry = config_entries.async_get_entry(entry_id)
        
        if not entry:
            _LOGGER.error("找不到配置条目 %s", entry_id)
            return
            
        new_data = {**entry.data, CONF_AC_ENTITY_ID: ac_entity_id}
        hass.config_entries.async_update_entry(entry, data=new_data)
        
        # 更新内存中的数据
        if entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN][entry_id][CONF_AC_ENTITY_ID] = ac_entity_id
            
        # 刷新条目
        await hass.config_entries.async_reload(entry_id)
        
    async def async_handle_set_temp_entity(call: ServiceCall) -> None:
        """处理设置温度传感器实体服务。"""
        entity_id = call.data[ATTR_ENTITY_ID]
        temp_entity_id = call.data[CONF_TEMP_ENTITY_ID]
        
        # 防止服务频繁调用
        lock_key = f"set_temp_{entity_id}"
        current_time = time.time()
        if lock_key in _SERVICE_LOCKS:
            elapsed = current_time - _SERVICE_LOCKS[lock_key]
            if elapsed < _MAX_SERVICE_FREQUENCY:
                _LOGGER.warning(
                    "服务调用过于频繁，距离上次调用仅 %.2f 秒，已跳过: %s", 
                    elapsed, lock_key
                )
                return
        _SERVICE_LOCKS[lock_key] = current_time
        
        # 获取实体条目ID
        entity_registry = hass.helpers.entity_registry.async_get(hass)
        entity_entry = entity_registry.async_get(entity_id)
        
        if not entity_entry or not entity_entry.config_entry_id:
            _LOGGER.error("找不到实体 %s 或其配置条目", entity_id)
            return
            
        entry_id = entity_entry.config_entry_id
        
        # 更新配置条目
        config_entries = hass.config_entries
        entry = config_entries.async_get_entry(entry_id)
        
        if not entry:
            _LOGGER.error("找不到配置条目 %s", entry_id)
            return
            
        new_data = {**entry.data, CONF_TEMP_ENTITY_ID: temp_entity_id}
        hass.config_entries.async_update_entry(entry, data=new_data)
        
        # 更新内存中的数据
        if entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN][entry_id][CONF_TEMP_ENTITY_ID] = temp_entity_id
            
        # 刷新条目
        await hass.config_entries.async_reload(entry_id)
    
    hass.services.async_register(
        DOMAIN, SERVICE_SET_AC_ENTITY, async_handle_set_ac_entity, 
        schema=SET_AC_ENTITY_SCHEMA
    )
    
    hass.services.async_register(
        DOMAIN, SERVICE_SET_TEMP_ENTITY, async_handle_set_temp_entity, 
        schema=SET_TEMP_ENTITY_SCHEMA
    )
    
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HongHui Climate from a config entry."""
    _LOGGER.info("设置洪绘空调配置项: %s", entry.entry_id)
    
    # 检查必要的配置项
    if CONF_AC_ENTITY_ID not in entry.data or CONF_TEMP_ENTITY_ID not in entry.data:
        _LOGGER.error("配置项缺少必要参数: %s", entry.data)
        return False
    
    # 存储配置数据到hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        CONF_AC_ENTITY_ID: entry.data.get(CONF_AC_ENTITY_ID),
        CONF_TEMP_ENTITY_ID: entry.data.get(CONF_TEMP_ENTITY_ID),
    }
    
    # 如果Home Assistant已经启动完成，立即设置平台
    if hass.is_running:
        await async_setup_platforms(hass, entry)
    else:
        # 否则，等待Home Assistant启动完成后再设置
        async def setup_platforms_after_start(_event):
            """在Home Assistant启动完成后设置平台"""
            await async_setup_platforms(hass, entry)
            
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, setup_platforms_after_start
        )
    
    # 设置配置项更新监听
    entry.async_on_unload(entry.add_update_listener(update_listener))
    
    _LOGGER.info("洪绘空调配置设置完成: %s", entry.entry_id)
    return True

async def async_setup_platforms(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """设置集成平台."""
    _LOGGER.debug("正在设置平台: %s", PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """处理配置项更新."""
    _LOGGER.info("更新洪绘空调配置: %s", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("卸载洪绘空调配置: %s", entry.entry_id)
    
    # 卸载平台
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # 如果卸载成功，移除数据
    if unload_ok and entry.entry_id in hass.data.get(DOMAIN, {}):
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.debug("已移除洪绘空调数据: %s", entry.entry_id)
        
    return unload_ok 