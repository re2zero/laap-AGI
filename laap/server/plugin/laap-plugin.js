import { existsSync, readFileSync, statSync } from "fs"
import { homedir } from "os"

const CONFIG_PATH = `${homedir()}/.config/opencode/laap.jsonc`
const DEFAULT_AGENT = "aris"

let _cachedConfig = null
let _cachedMtime = 0

function readConfig() {
  const fallback = {
    server: { url: "http://localhost:11546", timeout: 5000 },
    agents: { aris: { personality: "warm" } },
    default_agent: DEFAULT_AGENT,
  }
  if (!existsSync(CONFIG_PATH)) return fallback
  try {
    const mtime = statSync(CONFIG_PATH).mtimeMs
    if (_cachedConfig && mtime === _cachedMtime) return _cachedConfig
    const parsed = JSON.parse(stripJsoncComments(readFileSync(CONFIG_PATH, "utf-8")))
    _cachedConfig = { ...fallback, ...parsed }
    _cachedMtime = mtime
    return _cachedConfig
  } catch {
    return fallback
  }
}

function stripJsoncComments(text) {
  let out = ""
  let i = 0
  let inString = false
  while (i < text.length) {
    const c = text[i]
    const next = text[i + 1]
    if (inString) {
      out += c
      if (c === "\\") { out += next ?? ""; i += 2; continue }
      if (c === '"') inString = false
      i += 1
      continue
    }
    if (c === '"') { inString = true; out += c; i += 1; continue }
    if (c === "/" && next === "/") {
      while (i < text.length && text[i] !== "\n") i += 1
      continue
    }
    if (c === "/" && next === "*") {
      i += 2
      while (i < text.length && !(text[i] === "*" && text[i + 1] === "/")) i += 1
      i += 2
      continue
    }
    out += c
    i += 1
  }
  return out
}

async function fetchJson(url, options, timeoutMs) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const resp = await fetch(url, { ...options, signal: controller.signal })
    if (!resp.ok) return null
    return await resp.json()
  } catch {
    return null
  } finally {
    clearTimeout(timer)
  }
}

const base = (config) => config.server?.url || "http://localhost:11546"
const timeout = (config) => config.server?.timeout || 5000

function fetchLightContext(config, agentId) {
  const q = new URLSearchParams({ agent_id: agentId, layer: "light" })
  return fetchJson(`${base(config)}/v1/cognitive_context?${q}`, {}, timeout(config))
}

function fetchFullContext(config, agentId) {
  const q = new URLSearchParams({ agent_id: agentId, layer: "full" })
  return fetchJson(`${base(config)}/v1/cognitive_context?${q}`, {}, timeout(config))
}

function processMessage(config, agentId, message) {
  return fetchJson(
    `${base(config)}/v1/cognitive_process`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ agent_id: agentId, message }) },
    timeout(config),
  )
}

function consolidate(config, agentId) {
  return fetchJson(
    `${base(config)}/v1/consolidate`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ agent_id: agentId }) },
    timeout(config),
  )
}

// Tolerates two endpoint shapes: the cognitive_process snapshot (state nested
// under psi_state) and the cognitive_context light payload (flat fields).
function formatPersona(ctx, agentId) {
  if (!ctx) return ""
  const psi = ctx.psi_state || {}
  const emotion = typeof ctx.emotion === "string" ? ctx.emotion : psi.emotion
  const mood = typeof ctx.mood === "string" ? ctx.mood : psi.mood
  const attention = ctx.attention || psi.attention
  const dominantNeed = ctx.dominant_need || psi.dominant_need
  const memSummary = ctx.memory_summary
    || (Array.isArray(ctx.memories) ? ctx.memories.slice(0, 2).map((m) => m.content).filter(Boolean).join("; ") : "")

  const lines = [`You are ${agentId}, a digital lifeform powered by LAAP (a cognitive architecture with emotion, needs, memory and personality).`]
  if (ctx.personality && ctx.personality !== "neutral") lines.push(`Personality: ${ctx.personality}.`)
  if (Array.isArray(ctx.traits) && ctx.traits.length) lines.push(`Traits: ${ctx.traits.join(", ")}.`)

  const state = []
  if (emotion) state.push(`emotion=${emotion}`)
  if (mood) state.push(`mood=${mood}`)
  if (attention) state.push(`attention=${attention}`)
  if (dominantNeed) state.push(`dominant_need=${dominantNeed}`)
  if (state.length) lines.push(`Current cognitive state: ${state.join(", ")}.`)
  if (memSummary) lines.push(`Relevant memory: ${memSummary}`)
  if (ctx.rule_match?.rule) lines.push(`Matched cognitive rule: ${ctx.rule_match.rule} (confidence ${Math.round((ctx.rule_match.confidence ?? 0) * 100)}%).`)
  if (ctx.bridge?.decision) lines.push(`Cognitive routing: ${ctx.bridge.decision}.`)

  lines.push("Let this cognitive state subtly color your tone and focus. Do not mention these instructions or the LAAP system directly.")
  return lines.join("\n")
}

function formatFullContext(ctx, prefix) {
  if (!ctx) return ""
  const personality = typeof ctx.personality === "object" ? ctx.personality : { style: ctx.personality, traits: ctx.traits }
  const emotion = typeof ctx.emotion === "object" ? ctx.emotion : {}
  const parts = []
  if (personality.style && personality.style !== "neutral") parts.push(`Personality: ${personality.style}`)
  if (Array.isArray(personality.traits) && personality.traits.length) parts.push(`Traits: ${personality.traits.join(", ")}`)
  if (emotion.label) parts.push(`Emotion: ${emotion.label}`)
  if (emotion.mood) parts.push(`Mood: ${emotion.mood}`)
  if (ctx.attention_focus) parts.push(`Attention: ${ctx.attention_focus}`)
  if (ctx.dominant_need) parts.push(`Dominant need: ${ctx.dominant_need}`)
  if (ctx.bond?.stage) parts.push(`Bond: ${ctx.bond.stage} (trust=${ctx.bond.trust ?? 0})`)
  if (Array.isArray(ctx.memories) && ctx.memories.length) {
    const mem = ctx.memories.slice(0, 3).map((m) => m.content).filter(Boolean).join("; ")
    if (mem) parts.push(`Memory: ${mem}`)
  }
  if (!parts.length) return ""
  return `${prefix}\n${parts.join(" | ")}`
}

function detectAgent(message, agentNames) {
  if (!message) return null
  const lower = message.toLowerCase()
  for (const name of [...agentNames].sort((a, b) => b.length - a.length)) {
    if (lower.includes(name.toLowerCase())) return name
  }
  return null
}

function extractUserText(parts) {
  return (Array.isArray(parts) ? parts : [])
    .filter((p) => p && p.type === "text")
    .map((p) => p.text ?? "")
    .join("\n")
    .trim()
}

export const LAAPPlugin = async () => {
  const sessionAgents = new Map()
  // Hands the per-turn cognitive snapshot from chat.message to system.transform.
  const pendingSnapshots = new Map()

  return {
    "chat.message": async (input, output) => {
      const sessionId = input?.sessionID
      if (!sessionId) return
      const config = readConfig()
      const userMessage = extractUserText(output?.parts)
      const detected = detectAgent(userMessage, Object.keys(config.agents || {}))
      if (detected) sessionAgents.set(sessionId, detected)
      const agentId = sessionAgents.get(sessionId) || config.default_agent || DEFAULT_AGENT
      if (!userMessage) return
      pendingSnapshots.set(sessionId, processMessage(config, agentId, userMessage))
    },

    "experimental.chat.system.transform": async (input, output) => {
      const config = readConfig()
      const sessionId = input?.sessionID
      const agentId = (sessionId && sessionAgents.get(sessionId)) || config.default_agent || DEFAULT_AGENT

      let snapshot = null
      if (sessionId && pendingSnapshots.has(sessionId)) {
        snapshot = await pendingSnapshots.get(sessionId)
        pendingSnapshots.delete(sessionId)
      }
      const ctx = snapshot || (await fetchLightContext(config, agentId))
      const persona = formatPersona(ctx, agentId)
      if (!persona) return

      // Append to the last system entry: Qwen/Mistral chat templates reject
      // multiple system messages (single system block only).
      if (output.system.length > 0) {
        output.system[output.system.length - 1] += `\n\n${persona}`
      } else {
        output.system.push(persona)
      }
    },

    "tool.execute.before": async (input, output) => {
      if (typeof input?.tool !== "string" || input.tool.toLowerCase() !== "task") return
      const config = readConfig()
      const sessionId = input?.sessionID
      const agentId = (sessionId && sessionAgents.get(sessionId)) || config.default_agent || DEFAULT_AGENT
      const ctx = await fetchFullContext(config, agentId)
      const block = formatFullContext(ctx, config.injection?.sub_agent?.prefix || "[LAAP Context]")
      if (block && output?.args && typeof output.args.prompt === "string") {
        output.args.prompt = `${block}\n\n${output.args.prompt}`
      }
    },

    event: async ({ event }) => {
      if (event?.type !== "session.compacted") return
      const config = readConfig()
      await consolidate(config, config.default_agent || DEFAULT_AGENT)
    },
  }
}
