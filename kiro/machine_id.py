"""Machine ID 生成 - 参考 src/kiro/machine_id.rs"""

import hashlib
import logging
import threading
import uuid as _uuid
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# 兜底 machineId 缓存（按凭据 id 分桶，进程生命周期内稳定）
# key 为 credentials.id；无 id 的凭据共享同一个兜底值（正常流程不会出现）
_FALLBACK_CACHE: Dict[Optional[int], str] = {}
_FALLBACK_LOCK = threading.Lock()


def _sha256_hex(input_str: str) -> str:
    return hashlib.sha256(input_str.encode()).hexdigest()


def _normalize_machine_id(machine_id: str) -> Optional[str]:
    """标准化 machineId 格式

    支持：
    - 64 字符十六进制字符串（直接返回）
    - UUID 格式（移除连字符后补齐到 64 字符）
    """
    trimmed = machine_id.strip()

    # 64 字符十六进制
    if len(trimmed) == 64 and all(c in "0123456789abcdefABCDEF" for c in trimmed):
        return trimmed

    # UUID 格式
    without_dashes = trimmed.replace("-", "")
    if len(without_dashes) == 32 and all(c in "0123456789abcdefABCDEF" for c in without_dashes):
        return without_dashes + without_dashes

    return None


def _fallback_machine_id(credentials) -> str:
    """为缺失派生材料的凭据生成兜底 machineId

    - 仍经 sha256("KiroFallback/<uuid>") 派生，输出格式与正常路径一致（64 字符十六进制）
    - 按 credentials.id 在进程内缓存；同一凭据多次调用返回同一值
    - 进程重启会重新随机；不持久化
    - 每个凭据首次生成时 warn 一次
    """
    cid = credentials.id
    with _FALLBACK_LOCK:
        existing = _FALLBACK_CACHE.get(cid)
        if existing:
            return existing

        seed = _uuid.uuid4()
        derived = _sha256_hex(f"KiroFallback/{seed}")
        logger.warning(
            "凭据 #%s 缺少派生材料（kiroApiKey/refreshToken 均不可用），使用随机兜底 machineId（进程内稳定）",
            cid,
        )
        _FALLBACK_CACHE[cid] = derived
        return derived


def generate_from_credentials(credentials, config) -> str:
    """根据凭证信息生成唯一的 Machine ID

    优先级：
    1. 凭据级 machineId（若配置且格式合法）
    2. 全局 config.machineId（若配置且格式合法）
    3. 根据凭据类型派生（互斥，由 is_api_key_credential 分流）：
       - API Key 凭据：基于 kiroApiKey 派生
       - OAuth 凭据：基于 refreshToken 派生
    4. 兜底：基于随机种子派生，按 credentials.id 在进程内缓存

    永远返回有效字符串。
    """
    # 凭据级 machineId
    if credentials.machine_id:
        normalized = _normalize_machine_id(credentials.machine_id)
        if normalized:
            return normalized

    # 全局 machineId
    if config.machine_id:
        normalized = _normalize_machine_id(config.machine_id)
        if normalized:
            return normalized

    # 按凭据类型派生（API Key 与 refreshToken 两条路径互斥，不回落）
    if credentials.is_api_key_credential():
        # API Key 凭据：基于 kiroApiKey 派生
        api_key = credentials.kiro_api_key
        if api_key:
            return _sha256_hex(f"KiroAPIKey/{api_key}")
    else:
        # OAuth 凭据：基于 refreshToken 派生
        rt = credentials.refresh_token
        if rt:
            return _sha256_hex(f"KotlinNativeAPI/{rt}")

    # 兜底：走派生流程生成随机 machineId，按凭据 id 进程内稳定
    return _fallback_machine_id(credentials)
