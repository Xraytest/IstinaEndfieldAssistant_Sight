# 测试客户端命令说明

## 连接配置
- 服务端: `127.0.0.1:9999`
- 密码: `default_password`
- 超时: 300秒

## 核心命令

| 命令 | 用途 | 关键参数 |
|------|------|----------|
| register | 注册用户 | user_id |
| login | 用户登录 | user_id, key |
| get_default_tasks | 获取任务列表 | - |
| process_image | 处理图像(核心) | device_image, current_task |
| get_user_info | 获取用户信息 | user_id, session_id |

## 错误类型
session_expired, invalid_api_key, quota_exceeded, provider_rate_limit_exceeded
