# 洪绘空调 Home Assistant 集成

这个集成可以让你创建一个虚拟空调，它使用已有的空调实体进行控制，但使用你选择的温度传感器来显示当前温度。

## 快速安装

1. 将`custom_components/honghui_climate`文件夹复制到你的Home Assistant配置目录下的`custom_components`文件夹中
2. 重启Home Assistant
3. 在集成页面中搜索并添加"洪绘空调"

## 详细说明

详细的安装和使用说明请参见[集成文档](custom_components/honghui_climate/README.md)。

## 功能概述

- 创建虚拟空调设备，继承源空调的所有功能
- 使用单独的温度传感器来显示当前温度
- 所有控制命令会传递给源空调实体
- 支持服务API更新配置

## 支持

如有问题，请查看[故障排除指南](custom_components/honghui_climate/README.md#故障排除)。 