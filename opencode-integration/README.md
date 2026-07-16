# LAAP OpenCode Integration

Source-based LAAP cognitive integration for OpenCode, mirroring `HermesIntegrator` semantics via stdio JSON-RPC bridge.

## Architecture

```
OpenCode (TS)  ←──stdio NDJSON──→  Python Bridge  ──→  OpenCodeIntegrator(HermesIntegrator)
                                         │                      ├─ CognitiveBridge
                                         │                      ├─ RulesEngine
                                         │                      ├─ EmotionEngine
                                         │                      └─ PSI Core (per-persona state)
                                         │
                                    persona routing (lazy-loaded)
```

Each persona (aris/atlas/muse/custom) gets an independent `OpenCodeIntegrator` instance with its own PSI Core state directory.

## Install

```bash
cd /path/to/laap-AGI
python3 opencode-integration/installer.py
```

Restart OpenCode after installation.

## Configuration

`~/.config/opencode/laap.jsonc`:

```jsonc
{
  "bridge": {
    "python_path": "python3",
    "module": "opencode_integration.bridge",
    "laap_root": "/path/to/laap-AGI/opencode-integration",
    "timeout": 10000
  },
  "agents": {
    "aris": { "personality": "warm", "traits": ["empathetic", "curious"] }
  },
  "default_agent": "aris"
}
```

### Custom Persona

Add a new entry to `agents`:

```jsonc
"agents": {
  "aris": { "personality": "warm", "traits": ["empathetic"] },
  "nova": { "personality": "bold", "traits": ["decisive", "direct"] }
}
```

Nova gets its own Integrator + PSI Core state on first use. No code changes needed.

## Hook Mapping

| OpenCode Hook | Integrator Method | Effect |
|---|---|---|
| `chat.message` | `before_turn` | Process user input, cache CognitiveState |
| `experimental.chat.system.transform` | `format_persona_preamble` | Inject structured preamble to system prompt |
| `tool.execute.before` (tool='task') | `before_tool` | Inject context block to sub-agent prompt |
| `tool.execute.after` | `after_tool` | Update EmotionEngine |
| `event: session.idle` | `after_turn` | Trigger CognitiveBridge.reflect |
| `experimental.session.compacting` | `recall_memory` | Inject memory context before compaction |
| `event: session.compacted` | `consolidate` | Memory consolidation |
| `dispose` | `shutdown` | Stop PSI Core, flush state, exit bridge |

## LAAP Cognitive Tools

LLM can actively call these tools:

| Tool | Description |
|---|---|
| `laap_cognitive_state` | Query current emotion, attention, needs, confidence |
| `laap_recall_memory` | Recall memories by query |
| `laap_reflect` | Trigger reflection on completed interaction |
| `laap_inject_state` | Self-regulate emotion/confidence/focus |
| `laap_bootstrap` | Awaken ceremony for new instance |

## Coexistence with HTTP Plugin

Both plugins can coexist in `~/.config/opencode/plugins/`:
- `laap-plugin.js` — HTTP client to laap-server (:11546)
- `laap-source-plugin.ts` — stdio bridge to in-process engines

Enable only one at a time to avoid duplicate tool registration. Remove or rename the unused plugin file.

## Troubleshooting

**Bridge not starting:**
```bash
cd /path/to/laap-AGI/opencode-integration
python3 -m opencode_integration.bridge --check
```

**Engines unavailable:** Check `LAAP_ROOT` and `ARIS_BRAIN_ROOT` environment variables. The bridge auto-detects from the package location.

**PSI Core state conflicts with laap-server:** State directories are isolated (`opencode-integration/state/{persona}/`), no conflict.

**Persona not detected:** The plugin matches persona names in user messages (case-insensitive). Ensure `agents` config has the persona name as key.
