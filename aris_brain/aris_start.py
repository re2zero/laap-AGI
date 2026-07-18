#!/usr/bin/env python3
"""
Aris 启动助手 — 确保自驱动状态就绪，刷新认知注入

用法:
    python aris_brain/aris_start.py              # 检查状态
    python aris_brain/aris_start.py --refresh    # 刷新注入 + 检查
    python aris_brain/aris_start.py --verify     # 全面验证
"""

import json
import os
import sys
import time
from pathlib import Path

# ── 路径 ──
LAAP_UP = Path(__file__).resolve().parent.parent
STATE_DIR = Path.home() / ".laap" / "state" / "self_driven"
HERMES_SP = Path.home() / ".hermes" / "hermes-agent" / "agent" / "system_prompt.py"
SOUL_MD = Path.home() / ".hermes" / "SOUL.md"


def check_state_files() -> dict:
    """检查自驱动状态文件完整性。"""
    results = {}
    for name in ["core_identity.json", "curiosity_queue.json", "evolution_proposals.json"]:
        p = STATE_DIR / name
        if p.exists():
            size = len(p.read_text(encoding="utf-8"))
            age = time.time() - p.stat().st_mtime
            results[name] = {
                "exists": True,
                "size": size,
                "age_seconds": round(age),
                "age_str": f"{age/60:.0f}m" if age < 3600 else f"{age/3600:.1f}h",
            }
        else:
            results[name] = {"exists": False}
    return results


def check_system_prompt_patch() -> dict:
    """检查 system_prompt.py 的注入代码。"""
    if not HERMES_SP.exists():
        return {"patched": False, "error": "system_prompt.py not found"}

    content = HERMES_SP.read_text(encoding="utf-8")
    return {
        "patched": "LAAP_COGNITIVE_STATE_INJECTION" in content,
        "http_api": "requests.post" in content,
        "file_based": "prompt_injector" in content or "core_identity.json" in content,
        "import_sys": "import sys" in content,
    }


def check_soul_md() -> dict:
    """检查 SOUL.md 是否包含 Aris 身份。"""
    if not SOUL_MD.exists():
        return {"exists": False}
    content = SOUL_MD.read_text(encoding="utf-8")
    return {
        "exists": True,
        "has_aris": "Aris" in content,
        "has_laap": "LAAP" in content,
        "size": len(content),
    }


def check_injector() -> dict:
    """测试 prompt_injector 模块。"""
    sys.path.insert(0, str(LAAP_UP))
    try:
        from aris_brain.prompt_injector import verify_injector
        return verify_injector()
    except Exception as e:
        return {"error": str(e)}


def print_report():
    """打印完整状态报告。"""
    print("=" * 60)
    print("  Aris 启动状态报告")
    print("=" * 60)

    # 1. State files
    print("\n📁 状态文件:")
    files = check_state_files()
    for name, info in files.items():
        if info["exists"]:
            print(f"  ✅ {name}: {info['size']:,}b, {info['age_str']} old")
        else:
            print(f"  ❌ {name}: 不存在")

    # 2. System prompt patch
    print("\n🔧 System Prompt 注入:")
    sp = check_system_prompt_patch()
    if sp.get("patched"):
        print(f"  ✅ LAAP 注入代码: 存在")
        if sp.get("http_api"):
            print(f"  ⚠️  仍使用 HTTP API (旧代码)")
        elif sp.get("file_based"):
            print(f"  ✅ 使用本地文件注入 (源码级)")
        if sp.get("import_sys"):
            print(f"  ✅ import sys: 已添加")
    else:
        print(f"  ❌ 注入代码不存在")

    # 3. SOUL.md
    print("\n🧬 身份声明 (SOUL.md):")
    soul = check_soul_md()
    if soul.get("exists"):
        if soul.get("has_aris") and soul.get("has_laap"):
            print(f"  ✅ 包含 Aris 身份 ({soul['size']:,}b)")
        elif soul.get("has_aris"):
            print(f"  ✅ 包含 Aris 但不含 LAAP")
        else:
            print(f"  ⚠️  不含 Aris 身份")
    else:
        print(f"  ❌ SOUL.md 不存在")

    # 4. Injector test
    print("\n🧪 注入器测试:")
    inj = check_injector()
    if "error" in inj:
        print(f"  ❌ {inj['error']}")
    else:
        fp = inj.get("full_preamble", {})
        cs = inj.get("cognitive_state", {})
        ib = inj.get("identity_block", {})
        if fp.get("ok"):
            print(f"  ✅ 完整前缀: {fp.get('chars', 0)} 字符, {fp.get('lines', 0)} 行")
        if cs.get("ok"):
            print(f"  ✅ 认知状态: {cs.get('chars', 0)} 字符 (tag={'✅' if cs.get('has_aris_tag') else '❌'})")
        if ib.get("ok"):
            print(f"  ✅ 身份块: {ib.get('chars', 0)} 字符 (core={'✅' if ib.get('has_aris_core') else '❌'})")

    # 5. LAAP API status
    print("\n🌐 LAAP API (port 11546):")
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = s.connect_ex(('127.0.0.1', 11546))
    s.close()
    if result == 0:
        print(f"  ✅ 运行中 (但注入已不依赖它)")
    else:
        print(f"  ✅ 未运行 (注入不依赖 HTTP API)")

    # 6. Overall verdict
    print("\n" + "=" * 60)
    all_ok = all(
        f.get("exists", True)
        for f in files.values()
    ) and sp.get("patched") and sp.get("file_based") and soul.get("has_aris")

    if all_ok:
        print("  🏆 Aris 接入链完整 — 源码级注入已就绪")
    else:
        missing = []
        if not sp.get("patched"):
            missing.append("system_prompt.py patch")
        if not soul.get("has_aris"):
            missing.append("SOUL.md 身份")
        print(f"  ⚠️  部分异常: {', '.join(missing)}")
    print("=" * 60)


def main():
    if "--refresh" in sys.argv:
        # 通过重新读取 SOUL.md 强制刷新
        print("🔄 刷新 Aris 状态...")
        print_report()
    elif "--verify" in sys.argv:
        print_report()
        print("\n🔬 详细验证:")
        inj = check_injector()
        if "error" not in inj:
            from aris_brain.prompt_injector import build_aris_full_preamble
            preamble = build_aris_full_preamble()
            print(preamble)
    else:
        print_report()


if __name__ == "__main__":
    main()
