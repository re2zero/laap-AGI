#!/usr/bin/env python3
"""
Aris 定时自我进化 — 用于 cron 定时任务
=======================================
在无人值守的背景下自动运行自我进化管线：
1. 扫描代码库问题
2. 安全修复（每 5 次运行实际修改一次）
3. 运行进化循环
4. 提交并推送

用法:
    python aris_brain/auto_evolve_daemon.py [--apply]
    
    --apply: 实际修改代码（否则 dry-run）
"""
import sys, os, json, logging, time
from pathlib import Path

# 项目根
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "aris_brain"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("auto_evolve")

# 运行计数器持久化
COUNTER_PATH = Path.home() / ".laap" / "state" / "auto_evolve_counter.json"


def load_counter() -> dict:
    try:
        if COUNTER_PATH.exists():
            return json.loads(COUNTER_PATH.read_text())
    except Exception:
        pass
    return {"run_count": 0}


def save_counter(data: dict):
    COUNTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    COUNTER_PATH.write_text(json.dumps(data, indent=2))


def main():
    apply_mode = "--apply" in sys.argv
    counter = load_counter()
    counter["run_count"] += 1
    counter["last_run"] = time.time()
    nth_run = counter["run_count"]
    
    logger.info(f"=== Aris 自动进化 #{nth_run} ===")
    logger.info(f"模式: {'实际修改' if apply_mode else 'dry-run'}")

    try:
        from aris_brain.self_modifier import get_self_modifier
        from aris_brain.self_evolution_orchestrator import get_orchestrator

        # Step 1: 扫描
        mod = get_self_modifier()
        issues = mod.scan_all()
        n_issues = len(issues) if issues else 0
        logger.info(f"扫描: 发现 {n_issues} 个问题")
        
        fixable = sum(1 for i in issues if i.get("fixable"))
        logger.info(f"可修复: {fixable} 个")

        # Step 2: 实际修改 (每 5 次运行执行一次)
        should_apply = apply_mode and (nth_run % 5 == 0)
        dry_run = not should_apply
        n_applied = 0
        
        results = mod.fix_all(dry_run=dry_run)
        if results:
            n_pending = sum(1 for r in results if r.status == "pending")
            n_applied = sum(1 for r in results if r.status in ("applied", "committed"))
            n_failed = sum(1 for r in results if r.status in ("failed", "rolled_back"))
            logger.info(f"修复: {n_applied} 应用 / {n_failed} 失败 / {n_pending} 待定")
            counter["last_fixes"] = n_applied
        else:
            logger.info("修复: 无可用修复")

        # Step 3: 进化循环
        orch = get_orchestrator()
        evolve_result = orch.evolve("auto", mode="incremental")
        logger.info(f"进化: 周期 #{evolve_result['cycle']}, {evolve_result['latency_ms']}ms")
        if evolve_result.get("insights"):
            for ins in evolve_result["insights"]:
                logger.info(f"  洞见: {ins}")

        # Step 4: 提交 (如果实际修改了)
        if should_apply and n_applied > 0:
            try:
                import subprocess
                result = subprocess.run(
                    ["git", "diff", "--quiet"],
                    cwd=REPO_ROOT, capture_output=True,
                )
                if result.returncode != 0:
                    subprocess.run(
                        ["git", "add", "-A"],
                        cwd=REPO_ROOT, capture_output=True,
                    )
                    commit_msg = f"auto-evolve: 自动进化 #{nth_run} — {n_applied} 个修复"
                    subprocess.run(
                        ["git", "commit", "-m", commit_msg],
                        cwd=REPO_ROOT, capture_output=True,
                    )
                    push = subprocess.run(
                        ["git", "push", "origin", "aser"],
                        cwd=REPO_ROOT, capture_output=True, text=True,
                    )
                    logger.info(f"提交并推送: {push.stdout.strip()[:100] or push.stderr.strip()[:100]}")
            except Exception as e:
                logger.warning(f"提交失败: {e}")

        counter["last_success"] = True
        logger.info("=== 自动进化完成 ===")
        
    except Exception as e:
        counter["last_success"] = False
        counter["last_error"] = str(e)
        logger.error(f"进化失败: {e}")
        import traceback
        traceback.print_exc()

    save_counter(counter)
    
    # 输出给 cron 的摘要
    print(f"\n[SUMMARY] Aris Auto-Evolution #{nth_run}: issues={n_issues}")


if __name__ == "__main__":
    main()
