/**
 * Real agent brain — Anthropic Claude turns free-form language into structured home
 * actions. For voice, Gemini (if a token is present) transcribes the audio and Claude
 * decides. Falls back to the keyword NLU in home.ts when no provider is available.
 */
import * as home from "./home.ts";
import { spawn } from "node:child_process";
import { writeFile, readFile, unlink } from "node:fs/promises";
import { tmpdir } from "node:os";

const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY || "";
const GEMINI_TOKEN = process.env.GOOGLE_GENAI_TOKEN || "";
const CLAUDE_MODEL = "claude-haiku-4-5-20251001";
const GEMINI_MODEL = "gemini-3-flash-preview";

export function aiEnabled(): boolean { return !!ANTHROPIC_KEY || !!GEMINI_TOKEN; }
export function provider(): string { return ANTHROPIC_KEY ? "Anthropic Claude" : GEMINI_TOKEN ? "Gemini" : "keyword"; }

function systemPrompt(): string {
  const devs = home.allDevices()
    .map((d) => `- ${d.id} (${d.type}, ${d.room}) = ${JSON.stringify(d.state)}`).join("\n");
  const scenes = home.getScenes().map((s) => `- ${s.id}: ${s.description}`).join("\n");
  return `You are "openhome", a warm, concise local smart-home agent. Control the house by returning actions.

DEVICES (id, type, room = current state):
${devs}

SCENES (id: effect):
${scenes}

PATCH KEYS by type: light {on:bool, brightness:0-100}; lock {locked:bool}; camera {recording:bool}; speaker {playing:bool, volume:0-100, track:string}; thermostat {target:int, mode:"auto"|"heat"|"cool"|"off"}; plug {on:bool}; garage {open:bool}; shade {position:0-100}; vacuum {status:"docked"|"cleaning"|"returning"}. doorbell and sensor are read-only.

Respond with ONLY a JSON object (no prose, no code fences): {"reply":"<one short friendly sentence>","actions":[ ... ]}.
Each action is exactly one of:
  {"device":"<id>","patch":{...}}        // set one device
  {"type":"<deviceType>","patch":{...}}  // set ALL devices of a type (e.g. all lights off)
  {"scene":"<sceneId>"}                  // run a scene
Prefer a scene when the request matches one. For "all lights" use the "type" form. If the
request is not about the home, return "actions":[] with a brief helpful reply.`;
}

interface AiResult { reply: string; transcript?: string; actions: any[]; }

function normalize(out: any): AiResult {
  return { reply: String(out?.reply ?? ""), transcript: out?.transcript, actions: Array.isArray(out?.actions) ? out.actions : [] };
}
function parseJson(text: string): AiResult {
  try { return normalize(JSON.parse(text)); } catch { /* try to extract */ }
  const m = text.match(/\{[\s\S]*\}/);
  if (m) { try { return normalize(JSON.parse(m[0])); } catch { /* give up */ } }
  return { reply: text.slice(0, 200), actions: [] };
}

// --- Anthropic ---
async function claude(userText: string): Promise<AiResult> {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "content-type": "application/json", "x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01" },
    body: JSON.stringify({
      model: CLAUDE_MODEL, max_tokens: 400, system: systemPrompt(),
      messages: [{ role: "user", content: `User command: ${userText}\n\nReturn only the JSON object.` }],
    }),
    signal: AbortSignal.timeout(15000),
  });
  if (!res.ok) throw new Error("anthropic_" + res.status);
  const data: any = await res.json();
  const text = (data?.content ?? []).map((b: any) => b?.text).filter(Boolean).join("");
  return parseJson(text);
}

// --- Gemini (fallback brain + audio transcription) ---
async function gemini(parts: unknown[], jsonMode = true, useSystem = true): Promise<any> {
  const payload: any = {
    contents: [{ role: "user", parts }],
    generationConfig: jsonMode ? { responseMimeType: "application/json", temperature: 0.2 } : { temperature: 0 },
  };
  if (useSystem) payload.systemInstruction = { parts: [{ text: systemPrompt() }] };
  const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-goog-api-key": GEMINI_TOKEN },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(20000),
  });
  if (!res.ok) throw new Error("gemini_" + res.status);
  const data: any = await res.json();
  return (data?.candidates?.[0]?.content?.parts ?? []).map((p: any) => p.text).filter(Boolean).join("") || "{}";
}

// Normalize any browser audio (iOS mp4/AAC, Android webm/opus) to 16k mono WAV,
// which Gemini transcription reliably accepts. Falls back to the raw bytes if ffmpeg fails.
async function toWav(base64: string): Promise<{ data: string; mime: string }> {
  const stamp = `${process.pid}-${process.hrtime.bigint()}`;
  const inPath = `${tmpdir()}/oh-in-${stamp}`;
  const outPath = `${tmpdir()}/oh-out-${stamp}.wav`;
  try {
    await writeFile(inPath, Buffer.from(base64, "base64"));
    await new Promise<void>((resolve, reject) => {
      const p = spawn("ffmpeg", ["-y", "-i", inPath, "-ac", "1", "-ar", "16000", outPath], { stdio: "ignore" });
      p.on("error", reject);
      p.on("close", (code) => (code === 0 ? resolve() : reject(new Error("ffmpeg_" + code))));
    });
    const wav = await readFile(outPath);
    return { data: wav.toString("base64"), mime: "audio/wav" };
  } finally {
    unlink(inPath).catch(() => {});
    unlink(outPath).catch(() => {});
  }
}

async function geminiTranscribe(base64: string, mime: string): Promise<string> {
  let audio = { data: base64, mime: mime || "audio/webm" };
  try { audio = await toWav(base64); } catch { /* use raw bytes if transcode fails */ }
  const out = await gemini([
    { text: 'Transcribe this audio to plain text. Reply with only the exact words spoken, nothing else.' },
    { inlineData: { mimeType: audio.mime, data: audio.data } },
  ], false, false);
  return String(out).trim();
}

export async function aiText(text: string): Promise<AiResult> {
  if (ANTHROPIC_KEY) return claude(text);
  return parseJson(await gemini([{ text: `User command: ${text}` }]));
}

export async function aiAudio(base64: string, mime: string): Promise<AiResult> {
  if (!GEMINI_TOKEN) throw new Error("no_speech_to_text"); // Claude can't transcribe; needs Gemini STT
  const transcript = await geminiTranscribe(base64, mime);
  const r = await aiText(transcript);
  return { ...r, transcript };
}

/** Apply the model's actions to the mock house. Returns what changed for events. */
export function execute(actions: any[]): Array<{ label: string }> {
  const done: Array<{ label: string }> = [];
  for (const a of actions ?? []) {
    try {
      if (a?.scene) { home.activateScene(String(a.scene)); done.push({ label: `scene.${a.scene}` }); }
      else if (a?.type && a?.patch) { home.setByType(String(a.type), a.patch); done.push({ label: `type.${a.type}` }); }
      else if (a?.device && a?.patch) { if (home.setDevice(String(a.device), a.patch)) done.push({ label: `device.${a.device}` }); }
    } catch { /* skip bad action */ }
  }
  return done;
}
