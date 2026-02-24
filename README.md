# 烤森 MySekai Xray

AstrBot 插件 —— 世界计划 MySekai 采集资源可视化分析

## 功能

- 绑定 QQ 号与游戏 UID
- 查询采集资源数量统计图
- 查询四宫格掉落物位置图

## 指令

| 指令 | 说明 |
|------|------|
| `/烤森绑定 <UID>` | 绑定当前 QQ 号与游戏 UID |
| `/烤森地图` | 查询已绑定 UID 的采集资源图片 |
| `/烤森帮助` | 查看帮助信息和代理模块安装地址 |

## 使用流程

1. 前往 [代理模块安装页面](https://www.artenas.online/MySekai/index.html) 安装抓包代理模块
2. 在游戏中进入 MySekai 触发数据上传
3. 在 QQ 中发送 `/烤森绑定 <你的游戏UID>` 完成绑定
4. 发送 `/烤森地图` 即可获取资源分析图片

## 依赖

- Python 3.10+
- AstrBot v4.5.0+
- Pillow（图片生成）
- aiohttp（HTTP 请求）
- pycryptodome（后端解密，插件本身不需要）

## 目录结构

```
astrbot_plugin_MySekaiXray/
├── main.py           # 插件主逻辑
├── metadata.yaml     # 插件元数据
├── bindings.json     # QQ-UID 绑定数据（运行时自动生成）
├── icon/             # 物品图标资源
├── map/              # 地图背景图资源
├── mappings/         # 物品名称映射 JSON
├── README.md
├── LICENSE
└── .gitignore
```

## 许可证

AGPL-3.0
