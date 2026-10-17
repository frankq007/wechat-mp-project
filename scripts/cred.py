#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微信凭据统一解析（项目级共享，供 newspic.py / sync/api.py 使用）。

- 优先级：环境变量 WECHAT_APP_ID / WECHAT_APP_SECRET 优先；
  其次展开 config.json 里的 $VAR 占位（不落明文密钥）。
- 与 vendored skill 的 publish.py `_resolve_credential` 逻辑一致；
  若上游 xiaohu-wechat-format 升级，需同步比对这里的实现。
"""
import os


def resolve_credential(value, env_name: str) -> str:
    """解析单个凭据：环境变量优先，其次展开 $VAR 占位。"""
    env_val = os.environ.get(env_name, "").strip()
    if env_val:
        return env_val
    if not value:
        return ""
    val = str(value).strip()
    expanded = os.path.expandvars(val)
    if expanded != val and not expanded.startswith("$"):
        return expanded.strip()
    return ""


def get_credentials(wechat: dict) -> tuple[str, str]:
    """从 config 的 wechat 字段解析 (app_id, app_secret)；缺失返回空串。"""
    app_id = resolve_credential(wechat.get("app_id"), "WECHAT_APP_ID")
    app_secret = resolve_credential(wechat.get("app_secret"), "WECHAT_APP_SECRET")
    return app_id, app_secret