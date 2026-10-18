---
version: 1

# 公众号项目生图偏好（baoyu-image-gen）
# 凭据不落盘：DashScope key 走环境变量 DASHSCOPE_API_KEY（调用前注入）

default_provider: dashscope

default_quality: 2k

default_aspect_ratio: "16:9"

default_model:
  dashscope: "qwen-image"

batch:
  max_workers: 4
  provider_limits:
    dashscope:
      concurrency: 3
      start_interval_ms: 1100
