import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_LAAP_ROOT = os.environ.get("LAAP_ROOT", "")
if not _LAAP_ROOT:
    _LAAP_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _LAAP_ROOT not in sys.path:
    sys.path.insert(0, _LAAP_ROOT)

from opencode_integration.integrator import (
    OpenCodeIntegrator,
    OpenCodeIntegrationConfig,
)
from opencode_integration.protocol import serialize_response, to_ndjson

logger = logging.getLogger("laap.bridge")

_PERSONALITY_DEFAULTS = {
    "personality": "neutral",
    "traits": [],
}


class Bridge:
    def __init__(self):
        self._integrators: Dict[str, OpenCodeIntegrator] = {}
        self._running = True

    def get_integrator(
        self,
        persona: str,
        config_overrides: Optional[dict] = None,
    ) -> OpenCodeIntegrator:
        if persona not in self._integrators:
            overrides = {**_PERSONALITY_DEFAULTS, **(config_overrides or {})}
            config = OpenCodeIntegrationConfig(
                persona=persona,
                personality=overrides["personality"],
                traits=overrides.get("traits", []),
            )
            self._integrators[persona] = OpenCodeIntegrator(config)
            logger.info(f"Integrator initialized for persona: {persona}")
        return self._integrators[persona]

    def handle_request(self, request: dict) -> dict:
        req_id = request.get("id")
        method = request.get("method", "")
        persona = request.get("persona") or "aris"
        params = request.get("params", {})

        try:
            integrator = self.get_integrator(
                persona, params.get("_config")
            )
            result = self._dispatch(integrator, persona, method, params)
            return serialize_response(req_id, result=result)
        except Exception as e:
            logger.exception(f"Error handling {method} for {persona}")
            return serialize_response(
                req_id, error={"message": str(e)}
            )

    def _dispatch(
        self,
        integrator: OpenCodeIntegrator,
        persona: str,
        method: str,
        params: dict,
    ) -> Any:
        if method == "attach_session":
            return integrator.attach_session(
                params.get("session_id", "")
            )
        if method == "before_turn":
            state = integrator.before_turn(
                params.get("user_message", "")
            )
            result = {
                "state": {
                    "focus": state.focus,
                    "emotion": state.emotion,
                    "confidence": state.confidence,
                    "needs": state.needs,
                },
                "preamble": integrator.format_persona_preamble(persona),
            }
            if integrator._bridge_result:
                result["decision"] = integrator._bridge_result.get("decision")
                result["cognitive_context"] = integrator._bridge_result.get(
                    "cognitive_context"
                )
            return result
        if method == "before_tool":
            return {
                "context_block": integrator.before_tool(
                    params.get("tool_name", "")
                )
            }
        if method == "after_tool":
            integrator.after_tool(
                params.get("tool_name", ""),
                params.get("tool_result", {}),
            )
            return {"status": "ok"}
        if method == "after_turn":
            integrator.after_turn(params.get("response", ""))
            return {"status": "ok"}
        if method == "consolidate":
            return integrator.consolidate()
        if method == "tool_cognitive_state":
            return integrator.get_cognitive_state(
                params.get("input", "")
            )
        if method == "tool_recall_memory":
            return integrator.recall_memory(
                params.get("query", ""), params.get("limit", 5)
            )
        if method == "tool_reflect":
            return integrator.reflect(
                params.get("output", ""),
                params.get("success", False),
                params.get("connection", False),
            )
        if method == "tool_inject_state":
            return integrator.inject_state(
                params.get("emotion"),
                params.get("confidence"),
                params.get("focus"),
            )
        if method == "tool_bootstrap":
            return integrator.bootstrap(
                params.get("user_name", "friend"),
                params.get("preset", ""),
            )
        if method == "get_status":
            return integrator.get_status()
        if method == "shutdown":
            self._shutdown()
            return {"status": "shutdown"}
        raise ValueError(f"Unknown method: {method}")

    def _shutdown(self):
        for persona, integrator in self._integrators.items():
            try:
                if integrator._psi_core_launcher:
                    integrator._psi_core_launcher.stop()
            except Exception:
                pass
            logger.info(f"Integrator shut down for persona: {persona}")
        self._running = False

    def run(self):
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self.handle_request(request)
                sys.stdout.write(to_ndjson(response))
                sys.stdout.flush()
                if not self._running:
                    break
            except json.JSONDecodeError:
                logger.warning("Invalid JSON input: %s", line[:100])
            except Exception as e:
                logger.error("Bridge error: %s", e)

    def check(self) -> dict:
        integrator = self.get_integrator("aris")
        status = integrator.get_status()
        return {
            "bridge": "ok",
            "persona": "aris",
            "engines": status.get("engines", {}),
        }


def main():
    log_level = os.environ.get("LAAP_LOG_LEVEL", "WARNING").upper()
    log_file = os.path.expanduser("~/.config/opencode/laap-bridge.log")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    logging.basicConfig(
        stream=open(log_file, "a"),
        level=getattr(logging, log_level, logging.WARNING),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if "--check" in sys.argv:
        bridge = Bridge()
        result = bridge.check()
        print(json.dumps(result, indent=2))
        return

    bridge = Bridge()
    logger.info("LAAP OpenCode bridge started")
    bridge.run()
    logger.info("LAAP OpenCode bridge stopped")


if __name__ == "__main__":
    main()
