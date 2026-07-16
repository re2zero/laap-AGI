# LAAP Bridge Skill

This skill teaches Hermes Agent how to integrate with and leverage the LAAP (Living Artificial Personality) cognitive engine for richer, state-aware interactions.

## Overview

LAAP is a cognitive engine that maintains:
- **PSI State**: A dynamic cognitive state including needs, mood, attention focus, and emotional state
- **Memory Hierarchy**: Semantic, episodic, and long-term memories that can be recalled contextually
- **Expression Mapping**: TTS and Live2D expression parameters that match cognitive state

This skill enables Hermes to:
1. Query LAAP's cognitive state to modulate tone, attention, and response style
2. Recall relevant memories from LAAP's memory hierarchy
3. Reflect on completed turns to update LAAP's state
4. Generate expressive parameters for voice and avatar synchronization

## When to Use LAAP Tools

### 1. `laap_cognitive_state`
**Trigger**: Before generating a response to a user message, to understand the cognitive context.

**Use when**:
- The user's message has emotional or personal content
- You need to modulate your response tone based on LAAP's current state
- You want to align your response with LAAP's dominant needs and attention focus

**Example**:
```
User: "I've been feeling really stressed at work lately."

Action: Call `laap_cognitive_state` with the user's message to get:
- preamble: Context to inject into system prompt
- cot_hint: Chain-of-thought guidance
- dominant_need: Current primary need (e.g., "support", "explore")
- attention_focus: What LAAP is currently focused on
- mood: Current emotional state
```

### 2. `laap_recall_memory`
**Trigger**: When the conversation involves past interactions, personal details, or recurring themes.

**Use when**:
- The user mentions something they've told you before
- You need to reference past conversations or shared experiences
- The query relates to LAAP's long-term memory (facts, preferences, experiences)

**Example**:
```
Action: Call `laap_recall_memory(query="favorite drinks", limit=3)`
Returns: Relevant memories from LAAP's memory hierarchy with scores and timestamps.
```

### 3. `laap_reflect`
**Trigger**: After completing a significant turn or conversation segment.

**Use when**:
- You've provided a helpful or meaningful response
- The conversation has reached a natural conclusion point
- You want to update LAAP's cognitive state based on the interaction outcome

**Example**:
```
Action: Call `laap_reflect(output="Your response text", success=True, connection=True)`
Updates: LAAP's PSI state based on the turn's success and connection quality.
```

### 4. `laap_express`
**Trigger**: When generating voice or avatar output that should match LAAP's cognitive state.

**Use when**:
- You are synthesizing speech (Kokoro TTS) and need TTS parameters
- You are controlling a Live2D avatar and need expression/motion parameters
- You want the avatar's visual expression to match the emotional tone of the response

**Example**:
```
Action: Call `laap_express(input="user's message")`
Returns: TTS parameters (voice, speed) and Live2D expression parameters.
```

### 5. `laap_bootstrap`
**Trigger**: When initializing a new LAAP instance or awakening a new personality.

**Use when**:
- Starting a new session with a fresh LAAP instance
- The user wants to "awaken" a new personality or identity
- You need to set up a new bond or relationship context

**Example**:
```
Action: Call `laap_bootstrap(user_name="friend", preset="supportive")`
Returns: Identity, personality, bond, and ceremony text for the new instance.
```

## Integration Flow

### Standard Conversation Flow

1. **Receive User Message**
2. **Query Cognitive State**: Call `laap_cognitive_state(input=user_message)`
   - Use the returned `preamble` to inform your response tone
   - Note the `dominant_need` and `mood` to guide your approach
3. **Recall Relevant Memories** (if applicable): Call `laap_recall_memory(query=theme, limit=3)`
4. **Generate Response**: Craft your response considering LAAP's cognitive state
5. **Reflect on Turn**: Call `laap_reflect(output=response, success=true, connection=true)`
6. **Generate Expressions** (if voice/avatar available): Call `laap_express(input=user_message)`

### System Prompt Integration

The `preamble` returned by `laap_cognitive_state` should be injected into your volatile system prompt tier to modulate:
- Response tone and style
- Attention focus
- Emotional alignment

## MCP Server Configuration

LAAP exposes these tools via an MCP server. Ensure your Hermes config includes:

```yaml
mcp_servers:
  laap_brain:
    command: "<HERMES_VENV_PYTHON>"
    args:
      - "<LAAP_ROOT>\\mcp_server\\laap_mcp_server.py"
    env:
      LAAP_API_BASE: "http://localhost:11546"
    timeout: 30
    connect_timeout: 10
    keepalive_interval: 60

skills:
  preload:
    - laap-bridge
```

## Environment Variables

- `LAAP_API_BASE`: Base URL for the LAAP Brain API (default: `http://localhost:11546`)
- `LAAP_ROOT`: Root directory of the LAAP project

## API Endpoints

The LAAP Brain API exposes these endpoints (used by the MCP server):

- `POST /v1/cognitive_state` - Get PSI cognitive state
- `POST /v1/recall_memory` - Recall memories
- `POST /v1/reflect` - Reflect on completed turn
- `POST /v1/express` - Get TTS + Live2D expression parameters
- `POST /v1/bootstrap` - Awaken a new LAAP instance

## Troubleshooting

### MCP Server Not Connecting
- Verify LAAP Brain API is running on the configured port (default: 11546)
- Check `LAAP_API_BASE` environment variable
- Ensure MCP server path is correct in Hermes config

### Cognitive State Unavailable
- The PSI adapter may not be initialized
- Verify LAAP brain modules are loaded correctly
- Check LAAP API health endpoint: `GET /health`

### Memory Recall Returns Empty
- Memories may not be populated yet
- Try a more specific query
- Check semantic memory store is initialized
