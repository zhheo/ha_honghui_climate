# 洪绘空调 Home Assistant 集成

[English](/README.md) | 简体中文

这是一个Home Assistant自定义集成，可创建虚拟空调设备，该设备使用现有的空调实体进行控制，并使用单独的温度传感器实体来显示当前温度。

## 功能

- 允许用户选择现有的空调实体和温度传感器实体
- 创建虚拟空调设备，继承源空调的所有功能
- 使用单独的温度传感器来显示当前温度
- 所有控制命令会传递给源空调实体

## 安装方法

### 方法一：

1. 将`custom_components/honghui_climate`文件夹复制到你的Home Assistant安装目录的`custom_components`文件夹中
   ```
   # 例如，如果你使用的是HASS.IO：
   /config/custom_components/honghui_climate
   ```
2. 重启Home Assistant
3. 在Home Assistant的集成页面中，点击"添加集成"按钮
4. 搜索"洪绘空调"并选择它
5. 按照配置流程进行操作

### 方法2：

HACS > 右上角三个点 > Custom repositories > Repository: https://github.com/zhheo/ha_honghui_climate & Category or Type: Integration > ADD > 点击 HACS 的 New 或 Available for download 分类下的 Xiaomi Home ，进入集成详情页 > DOWNLOAD

## 配置方法

1. 在配置流程中选择一个现有的空调实体
2. 选择一个现有的温度传感器实体
3. 保存配置后，新的虚拟空调实体将被创建

## 使用场景

- 当空调自带的温度传感器不准确时
- 需要使用位于不同位置的温度传感器来控制空调
- 创建更精确的空调控制逻辑

## 可用服务

集成提供两个服务：

- `honghui_climate.set_ac_entity`: 更新虚拟空调使用的空调实体
- `honghui_climate.set_temp_entity`: 更新虚拟空调使用的温度传感器实体

## 注意事项

- 源空调实体必须是有效的climate类型实体
- 温度传感器必须提供有效的温度数据
- 虚拟空调的功能取决于源空调的功能

## 故障排除

如果安装后找不到实体，请尝试以下步骤：

1. 检查Home Assistant的日志是否有错误信息
2. 确保你已经在配置流程中正确选择了空调实体和温度传感器实体
3. 重启Home Assistant
4. 如果问题仍然存在，请尝试删除集成并重新安装 