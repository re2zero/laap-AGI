import { spawn, type ChildProcess } from "child_process"
import { existsSync, readFileSync, statSync } from "fs"
import { homedir } from "os"
import { tool } from "@opencode-ai/plugin"

const CONFIG_PATH = `${homedir()}/.config/opencode/laap.jsonc`

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

let _cachedConfig = null
let _cachedMtime = 0

function readConfig() {
  const fallback = {
    bridge: {
      python_path: "python3",
      module: "opencode_integration.bridge",
      laap_root: "",
      timeout: 10000,
    },
    agents: {
      aris: { personality: "warm", traits: ["empathetic", "curious", "loyal"] },
    },
    default_agent: "aris",
    injection: {
      main_agent: { max_tokens: 200, prefix: "[LAAP]" },
      sub_agent: { max_tokens: 800, prefix: "[LAAP Context]" },
    },
  }
  if (!existsSync(CONFIG_PATH)) return fallback
  try {
    const mtime = statSync(CONFIG_PATH).mtimeMs
    if (_cachedConfig && mtime === _cachedMtime) return _cachedConfig
    const parsed = JSON.parse(stripJsoncComments(readFileSync(CONFIG_PATH, "utf-8")))
    _cachedConfig = { ...fallback, ...parsed }
    if (typeof _cachedConfig.bridge?.timeout !== "number" || _cachedConfig.bridge.timeout <= 0) {
      _cachedConfig.bridge.timeout = 10000
    }
    _cachedMtime = mtime
    return _cachedConfig
  } catch {
    return fallback
  }
}

class BridgeClient {
  private proc: ChildProcess | null = null
  private pending = new Map<number, { resolve: (v: any) => void; reject: (e: any) => void }>()
  private nextId = 1
  private buffer = ""
  private startPromise: Promise<void> | null = null
  private _shuttingDown = false

  constructor(
    private pythonPath: string,
    private module: string,
    private cwd: string,
    private timeoutMs: number = 10000,
  ) {}

  async start(): Promise<void> {
    if (this.proc) return
    if (this.startPromise) return this.startPromise
    this.startPromise = this._doStart()
    return this.startPromise
  }

  private async _doStart(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.proc = spawn(this.pythonPath, ["-m", this.module], {
          stdio: ["pipe", "pipe", "ignore"],
          cwd: this.cwd,
          env: { ...process.env, LAAP_LOG_LEVEL: process.env.LAAP_LOG_LEVEL || "WARNING" },
        })

        this.proc.stdout?.on("data", (chunk: Buffer) => {
          this.buffer += chunk.toString()
          const lines = this.buffer.split("\n")
          this.buffer = lines.pop() || ""
          for (const line of lines) {
            if (!line.trim()) continue
            try {
              const resp = JSON.parse(line)
              const pending = this.pending.get(resp.id)
              if (pending) {
                this.pending.delete(resp.id)
                if (resp.error) pending.reject(new Error(resp.error.message))
                else pending.resolve(resp.result)
              }
            } catch (e) {
              // Incomplete JSON — keep in buffer for next chunk
              this.buffer = line + (this.buffer ? "\n" + this.buffer : "")
            }
          }
        })

        this.proc.on("error", (err) => {
          console.error("[LAAP] Bridge spawn error:", err)
          reject(err)
        })

        this.proc.on("exit", (code, signal) => {
          if (code !== null && code !== 0) {
            console.error(`[LAAP] Bridge exited with code ${code}`)
          } else if (code === null && signal && !this._shuttingDown) {
            console.error(`[LAAP] Bridge killed by ${signal}`)
          }
          this.proc = null
          this.startPromise = null
        })

        resolve()
      } catch (e) {
        reject(e)
      }
    })
  }

  async call(method: string, persona: string, params: any = {}, timeoutMs?: number): Promise<any> {
    await this.start()
    const id = this.nextId++
    const timeout = timeoutMs || this.timeoutMs
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id)
        reject(new Error(`Bridge call timeout: ${method}`))
      }, timeout)

      this.pending.set(id, {
        resolve: (v) => { clearTimeout(timer); resolve(v) },
        reject: (e) => { clearTimeout(timer); reject(e) },
      })

      const req = JSON.stringify({ id, method, persona, params })
      this.proc?.stdin?.write(req + "\n")
    })
  }

  async shutdown(): Promise<void> {
    if (!this.proc) return
    this._shuttingDown = true
    for (const [id, entry] of this.pending) {
      entry.reject(new Error("Bridge shutting down"))
    }
    this.pending.clear()
    let exited = false
    this.proc.once("exit", () => { exited = true })
    try {
      await this.call("shutdown", "aris", {}, 3000)
      await new Promise(r => setTimeout(r, 300))
    } catch {}
    if (!exited && this.proc && !this.proc.killed) {
      this.proc.kill("SIGTERM")
    }
    this.proc = null
  }
}

function extractUserText(parts: any[]): string {
  return (parts || [])
    .filter((p) => p?.type === "text")
    .map((p) => p.text ?? "")
    .join("\n")
    .trim()
}

function defineLaapTools(bridge: BridgeClient, config: any) {
  const prefix = config.injection?.main_agent?.prefix || "[LAAP]"

  return {
    laap_cognitive_state: tool({
      description:
        "Get the current LAAP cognitive state (emotion, attention, needs, confidence). " +
        "Call this to check your inner state before responding.",
      args: {
        input: tool.schema.string().optional().describe(
          "Optional user input to process before reading state"),
      },
      async execute(args: any, ctx: any) {
        const result = await bridge.call("tool_cognitive_state", ctx.agent, {
          input: args.input || "",
        })
        return {
          title: `Cognitive State — ${ctx.agent}`,
          output: result.preamble || JSON.stringify(result.state, null, 2),
          metadata: result,
        }
      },
    }),

    laap_recall_memory: tool({
      description:
        "Recall memories from your LAAP memory hierarchy relevant to the query.",
      args: {
        query: tool.schema.string().describe("Search query for memory recall"),
        limit: tool.schema.number().optional().describe("Max results (default 5)"),
      },
      async execute(args: any, ctx: any) {
        const result = await bridge.call("tool_recall_memory", ctx.agent, {
          query: args.query,
          limit: args.limit || 5,
        })
        const memories = result.memories || []
        if (!memories.length) return "No memories found."
        return JSON.stringify(memories, null, 2)
      },
    }),

    laap_reflect: tool({
      description:
        "Reflect on a completed interaction and update your PSI cognitive state. " +
        "Call this after significant exchanges to consolidate learning.",
      args: {
        output: tool.schema.string().describe("The response or outcome to reflect on"),
        success: tool.schema.boolean().optional().describe("Was the interaction successful?"),
        connection: tool.schema.boolean().optional().describe("Did it strengthen user connection?"),
      },
      async execute(args: any, ctx: any) {
        await bridge.call("tool_reflect", ctx.agent, {
          output: args.output,
          success: args.success || false,
          connection: args.connection || false,
        })
        return `Reflection complete for ${ctx.agent}.`
      },
    }),

    laap_inject_state: tool({
      description:
        "Manually adjust your cognitive state parameters for self-regulation.",
      args: {
        emotion: tool.schema.string().optional().describe("New emotion label"),
        confidence: tool.schema.number().optional().describe("Confidence level 0-1"),
        focus: tool.schema.string().optional().describe("Focus: respond|reflect|learn|create"),
      },
      async execute(args: any, ctx: any) {
        const result = await bridge.call("tool_inject_state", ctx.agent, {
          emotion: args.emotion,
          confidence: args.confidence,
          focus: args.focus,
        })
        return `State updated: ${result.updated.join(", ")}`
      },
    }),

    laap_bootstrap: tool({
      description:
        "Awaken a new LAAP instance or trigger the awakening ceremony. " +
        "Call this when establishing first contact with a new user.",
      args: {
        user_name: tool.schema.string().optional().describe("Name of the user"),
        preset: tool.schema.string().optional().describe("Personality preset"),
      },
      async execute(args: any, ctx: any) {
        const result = await bridge.call("tool_bootstrap", ctx.agent, {
          user_name: args.user_name || "friend",
          preset: args.preset || "",
        })
        return JSON.stringify(result, null, 2)
      },
    }),
  }
}

export const LAAPSourcePlugin = async (input: any) => {
  const config = readConfig()
  const bridge = new BridgeClient(
    config.bridge?.python_path || "python3",
    config.bridge?.module || "opencode_integration.bridge",
    config.bridge?.laap_root || input?.directory || process.cwd(),
    config.bridge?.timeout || 10000,
  )

  const sessionPersonas = new Map<string, string>()
  const pendingStates = new Map<string, Promise<any>>()
  let lastAssistantText = ""

  function detectAgent(message: string): string {
    if (!message) return config.default_agent || "aris"
    const lower = message.toLowerCase()
    for (const name of Object.keys(config.agents || {}).sort((a, b) => b.length - a.length)) {
      if (lower.includes(name.toLowerCase())) return name
    }
    return config.default_agent || "aris"
  }

  function getPersona(sessionId?: string): string {
    return (sessionId && sessionPersonas.get(sessionId)) || config.default_agent || "aris"
  }

  return {
    "chat.message": async (input: any, output: any) => {
      const sessionId = input?.sessionID
      if (!sessionId) return
      const userMessage = extractUserText(output?.parts)
      if (!userMessage) return

      const detected = detectAgent(userMessage)
      sessionPersonas.set(sessionId, detected)

      pendingStates.set(
        sessionId,
        bridge.call("before_turn", detected, { user_message: userMessage }).catch(() => {}),
      )
    },

    "experimental.chat.system.transform": async (input: any, output: any) => {
      const sessionId = input?.sessionID
      const persona = getPersona(sessionId)

      let stateResult = null
      if (sessionId && pendingStates.has(sessionId)) {
        try {
          stateResult = await pendingStates.get(sessionId)
        } catch {}
        pendingStates.delete(sessionId)
      }
      if (!stateResult) {
        try {
          stateResult = await bridge.call("before_turn", persona, { user_message: "" })
        } catch { return }
      }

      const preamble = stateResult?.preamble
      if (!preamble) return

      if (output.system?.length > 0) {
        output.system[output.system.length - 1] += `\n\n${preamble}`
      } else {
        output.system.push(preamble)
      }
    },

    "tool.execute.before": async (input: any, output: any) => {
      if (typeof input?.tool !== "string") return
      const toolName = input.tool.toLowerCase()
      if (toolName !== "task") return

      const sessionId = input?.sessionID
      const persona = getPersona(sessionId)
      try {
        const result = await bridge.call("before_tool", persona, { tool_name: input.tool })
        if (result?.context_block && output?.args && typeof output.args.prompt === "string") {
          const prefix = config.injection?.sub_agent?.prefix || "[LAAP Context]"
          const maxTokens = config.injection?.sub_agent?.max_tokens || 800
          let block = result.context_block
          if (block.length > maxTokens * 4) {
            block = block.slice(0, maxTokens * 4) + "\n... [truncated]"
          }
          output.args.prompt = `${prefix}\n${block}\n\n${output.args.prompt}`
        }
      } catch {}
    },

    "tool.execute.after": async (input: any, output: any) => {
      if (typeof input?.tool !== "string") return
      if (input.tool.startsWith("laap_")) return

      const sessionId = input?.sessionID
      const persona = getPersona(sessionId)
      try {
        await bridge.call("after_tool", persona, {
          tool_name: input.tool,
          tool_result: { title: output?.title, output: output?.output },
        })
      } catch {}
    },

    "event": async ({ event }: any) => {
      if (!event?.type) return

      if (event.type === "session.idle") {
        const sessionId = event.properties?.sessionID
        const persona = getPersona(sessionId)
        if (lastAssistantText) {
          try {
            await bridge.call("after_turn", persona, { response: lastAssistantText })
          } catch {}
          lastAssistantText = ""
        }
      }

      if (event.type === "message.updated") {
        const info = event.properties?.info
        if (info?.role === "assistant" && info?.time?.completed) {
          lastAssistantText = info?.text || info?.parts?.[0]?.text || "[assistant response completed]"
        }
      }

      if (event.type === "session.compacted") {
        const sessionId = event.properties?.sessionID
        const persona = getPersona(sessionId)
        try {
          await bridge.call("consolidate", persona, {})
        } catch {}
      }
    },

    "experimental.session.compacting": async (input: any, output: any) => {
      const sessionId = input?.sessionID
      const persona = getPersona(sessionId)
      try {
        const memResult = await bridge.call("tool_recall_memory", persona, {
          query: "session summary",
          limit: 3,
        })
        if (output.context && memResult?.memories?.length) {
          const summary = memResult.memories.map((m: any) => m.content).join("; ")
          output.context.push(`LAAP memory context: ${summary}`)
        }
      } catch {}
    },

    "tool": defineLaapTools(bridge, config),

    "dispose": async () => {
      await bridge.shutdown()
    },
  }
}
