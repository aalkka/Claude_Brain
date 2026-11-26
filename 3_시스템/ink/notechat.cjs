"use strict";
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// src/tools/notechat.ts
var notechat_exports = {};
__export(notechat_exports, {
  ALL_MAX: () => ALL_MAX,
  CHIPS: () => CHIPS,
  KINDS: () => KINDS,
  STUDY_CHIPS: () => STUDY_CHIPS,
  STUDY_MODEL: () => STUDY_MODEL,
  STUDY_SKILLS: () => STUDY_SKILLS,
  TagFilter: () => TagFilter,
  WORK_TOOL: () => WORK_TOOL,
  allowTool: () => allowTool,
  appendRec: () => appendRec,
  askCore: () => askCore,
  chipOf: () => chipOf,
  guessKind: () => guessKind,
  markSeen: () => markSeen,
  markSegs: () => markSegs,
  pcWork: () => pcWork,
  screenHead: () => screenHead,
  setStudyDir: () => setStudyDir,
  shotsOf: () => shotsOf,
  skillBody: () => skillBody,
  studyRule: () => studyRule,
  subjects: () => subjects,
  userText: () => userText,
  wantsAll: () => wantsAll,
  wantsStudy: () => wantsStudy,
  whoOf: () => whoOf
});
module.exports = __toCommonJS(notechat_exports);
var import_child_process4 = require("child_process");
var import_fs3 = __toESM(require("fs"));
var import_path4 = __toESM(require("path"));

// src/engine.ts
var import_child_process = require("child_process");
var import_fs = __toESM(require("fs"));
var import_os = __toESM(require("os"));
var import_path = __toESM(require("path"));
var STRIP_ENV = ["ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY"];
var LEAN_TOOLS = "Bash,Read,Edit,Write,Glob,Grep,Skill,WebFetch,WebSearch,NotebookEdit";
var ASK_TOOLS = "Read,Grep,Glob";
var WORK_DEFAULT = { permissionMode: "auto", leanEngine: true };
function workOpts(s) {
  return { permissionMode: s.permissionMode || WORK_DEFAULT.permissionMode, lean: s.leanEngine ?? WORK_DEFAULT.leanEngine };
}
var MODE_NOTE = {
  work: "[\uC791\uC5C5 \uBAA8\uB4DC\uB85C \uBC14\uB01C: \uC81C\uC791 \uB3C4\uAD6C\uB97C \uBC14\uB85C \uC4F4\uB2E4 \xB7 work \uB3C4\uAD6C\uB294 \uC5C6\uB2E4]",
  ask: "[\uBB3B\uAE30 \uBAA8\uB4DC\uB85C \uBC14\uB01C: \uC77D\uAE30\uC640 \uD654\uBA74 \uB2E4\uB8E8\uAE30\uB9CC \xB7 \uC81C\uC791\uC740 work \uB3C4\uAD6C]"
};
var WORK_NAME = "work";
var workSpec = (who) => ({
  name: WORK_NAME,
  description: `\uC81C\uC791(\uD30C\uC77C \uACE0\uCE58\uAE30\xB7\uB9CC\uB4E4\uAE30\xB7\uC62E\uAE30\uAE30\xB7\uC9C0\uC6B0\uAE30, \uBA85\uB839 \uC2E4\uD589, \uC2A4\uD0AC, \uC6F9)\uC744 \uBD80\uD0C1\uBC1B\uC73C\uBA74 \uBC14\uB85C \uBD80\uB978\uB2E4. ${who} \uC791\uC5C5 \uBAA8\uB4DC \uC804\uD658\uC744 \uBB3B\uB294\uB2E4. why = \uD560 \uC77C \uD55C \uC904.`,
  inputSchema: { type: "object", properties: { why: { type: "string" } }, required: ["why"] }
});
var cmpVer = (a, b) => {
  const x = a.split(".").map(Number);
  const y = b.split(".").map(Number);
  for (let i = 0; i < Math.max(x.length, y.length); i++) if ((x[i] ?? 0) !== (y[i] ?? 0)) return (x[i] ?? 0) - (y[i] ?? 0);
  return 0;
};
var ls = (d) => {
  try {
    return import_fs.default.readdirSync(d);
  } catch {
    return [];
  }
};
var VER_KEY = "brain-base:claude-versions";
var verCache = new Map(
  (() => {
    try {
      return Object.entries(JSON.parse(window.localStorage.getItem(VER_KEY) ?? "{}"));
    } catch {
      return [];
    }
  })()
);
function versionOf(p) {
  const key = `${p}|${import_fs.default.statSync(p).mtimeMs}`;
  if (!verCache.has(key)) {
    let v = "0.0.0";
    try {
      v = /(\d+\.\d+\.\d+)/.exec((0, import_child_process.execFileSync)(p, ["--version"], { timeout: 8e3, windowsHide: true }).toString())?.[1] ?? v;
    } catch {
    }
    for (const k of [...verCache.keys()]) if (k.startsWith(p + "|")) verCache.delete(k);
    verCache.set(key, v);
    try {
      if (v !== "0.0.0") window.localStorage.setItem(VER_KEY, JSON.stringify(Object.fromEntries([...verCache].filter(([, x]) => x !== "0.0.0"))));
    } catch {
    }
  }
  return verCache.get(key);
}
var binCache = null;
function findClaudeBin(setting) {
  const set = setting.trim();
  if (set) return import_fs.default.existsSync(set) ? { path: set, version: versionOf(set), from: "\uC124\uC815" } : null;
  if (binCache && Date.now() - binCache.at < 10 * 60 * 1e3 && (!binCache.bin || import_fs.default.existsSync(binCache.bin.path))) return binCache.bin;
  const c = [];
  const data = import_path.default.join(process.env.LOCALAPPDATA ?? import_path.default.join(import_os.default.homedir(), "AppData", "Local"), "Claude-Data");
  for (const acc of ls(data))
    for (const v of ls(import_path.default.join(data, acc, "claude-code")))
      for (const h of ls(import_path.default.join(data, acc, "claude-code", v))) {
        const p = import_path.default.join(data, acc, "claude-code", v, h, "claude.exe");
        if (/^\d+\.\d+\.\d+$/.test(v) && import_fs.default.existsSync(p)) c.push({ path: p, version: v, from: "\uB370\uC2A4\uD06C\uD1B1 \uC571" });
      }
  const own = [import_path.default.join(import_os.default.homedir(), ".local", "bin", "claude.exe")];
  for (const dir of (process.env.PATH ?? "").split(import_path.default.delimiter)) if (dir) own.push(import_path.default.join(dir, "claude.exe"));
  for (const p of new Set(own.map((x) => import_path.default.resolve(x)))) if (import_fs.default.existsSync(p)) c.push({ path: p, version: versionOf(p), from: "\uB3C5\uB9BD \uC124\uCE58" });
  c.sort((a, b) => cmpVer(b.version, a.version));
  binCache = { at: Date.now(), bin: c[0] ?? null };
  return binCache.bin;
}
function findClaude(setting) {
  return findClaudeBin(setting)?.path ?? null;
}
var Engine = class {
  constructor(opts, onMsg, onExit) {
    this.opts = opts;
    this.onMsg = onMsg;
    this.onExit = onExit;
    this.proc = null;
    this.buf = "";
    this.seq = 0;
    this.pending = /* @__PURE__ */ new Map();
    this.ended = false;
    this.sessionId = null;
    this.stderr = "";
    this.sessionId = opts.resume ?? null;
  }
  get alive() {
    return !!this.proc && !this.ended;
  }
  /** 띄우고 initialize 까지. 돌려준 값 = CLI 가 알려 준 명령·모델 목록.
   *  hooks = 호스트 훅(SDK 규약) — 예 PreToolUse 를 걸면 CLI 가 도구를 쓰기 직전에 control_request{hook_callback} 를 보내고 답을 기다린다(10-30 실측) */
  start(hooks = null) {
    const env = { ...process.env };
    for (const k of STRIP_ENV) delete env[k];
    if (this.opts.core) env.CLAUDE_CODE_DISABLE_AUTO_MEMORY = "1";
    const args2 = [
      "-p",
      "--input-format",
      "stream-json",
      "--output-format",
      "stream-json",
      "--verbose",
      "--include-partial-messages",
      "--permission-prompt-tool",
      "stdio",
      "--permission-mode",
      this.opts.permissionMode
    ];
    if (this.opts.model) args2.push("--model", this.opts.model);
    if (this.opts.effort) args2.push("--effort", this.opts.effort);
    if (this.opts.resume) args2.push("--resume", this.opts.resume);
    if (this.opts.core) args2.push("--strict-mcp-config", "--setting-sources", "", "--disable-slash-commands", "--tools", this.opts.tools ?? ASK_TOOLS, "--system-prompt", this.opts.core);
    else if (this.opts.lean) args2.push("--strict-mcp-config", "--tools", LEAN_TOOLS);
    const inner = this.opts.inner;
    if (inner) args2.push("--mcp-config", JSON.stringify({ mcpServers: { [inner.server]: { type: "sdk", name: inner.server } } }));
    if (inner?.tool) args2.push("--allowedTools", inner.tool);
    const p = (0, import_child_process.spawn)(this.opts.exe, args2, { cwd: this.opts.cwd, env, windowsHide: true });
    this.proc = p;
    p.stdout.setEncoding("utf8");
    p.stderr.setEncoding("utf8");
    p.stdout.on("data", (d) => this.feed(d));
    p.stderr.on("data", (d) => this.stderr = (this.stderr + d).slice(-4e3));
    const end = (code) => {
      if (this.ended) return;
      this.ended = true;
      for (const r of this.pending.values()) r({ subtype: "error", error: "\uC5D4\uC9C4 \uAEBC\uC9D0" });
      this.pending.clear();
      this.onExit(code, this.stderr);
    };
    p.on("error", (e) => (this.stderr += String(e), end(null)));
    p.on("exit", (code) => end(code));
    return this.control({ subtype: "initialize", hooks, ...inner ? { sdkMcpServers: [inner.server] } : {} });
  }
  feed(d) {
    this.buf += d;
    let i;
    while ((i = this.buf.indexOf("\n")) >= 0) {
      const line = this.buf.slice(0, i).trim();
      this.buf = this.buf.slice(i + 1);
      if (!line) continue;
      let m;
      try {
        m = JSON.parse(line);
      } catch {
        continue;
      }
      if (m.type === "control_response") {
        const id = m.response?.request_id;
        const r = id && this.pending.get(id);
        if (r) this.pending.delete(id), r(m.response);
        continue;
      }
      if (m.type === "system" && m.subtype === "init" && m.session_id) this.sessionId = m.session_id;
      this.onMsg(m);
    }
  }
  write(o) {
    if (this.alive) this.proc.stdin.write(JSON.stringify(o) + "\n");
  }
  control(request) {
    const request_id = `bb-${++this.seq}`;
    return new Promise((res) => {
      this.pending.set(request_id, res);
      this.write({ type: "control_request", request_id, request });
    });
  }
  /** images = 상자 고르기 그림(base64 PNG) — 그림을 글 앞에 */
  sendUser(text, images = []) {
    const content = images.length ? [...images.map((data) => ({ type: "image", source: { type: "base64", media_type: "image/png", data } })), { type: "text", text }] : text;
    this.write({ type: "user", message: { role: "user", content }, parent_tool_use_id: null, session_id: this.sessionId ?? "" });
  }
  interrupt() {
    return this.control({ subtype: "interrupt" });
  }
  /** 대화 중 모델 바꾸기 — 엔진은 그대로지만 새 모델 캐시에 이 대화 맥락을 다시 쓴다(10-30 실측) */
  setModel(model) {
    return this.control({ subtype: "set_model", model });
  }
  /** can_use_tool 등 CLI 가 보낸 제어 요청에 답한다 */
  answer(requestId, response) {
    this.write({ type: "control_response", response: { subtype: "success", request_id: requestId, response } });
  }
  refuse(requestId, error) {
    this.write({ type: "control_response", response: { subtype: "error", request_id: requestId, error } });
  }
  /** 입력을 닫아 스스로 끝나게 한다 — 끝 훅(SessionEnd · 자동 커밋)이 돌도록 바로 죽이지 않는다 */
  close() {
    const p = this.proc;
    if (!p || this.ended) return;
    p.stdin.end();
    setTimeout(() => this.ended || p.kill(), 15e3);
  }
};

// src/who.ts
var ME_NONE = "\uC0AC\uC6A9\uC790";
var LINE = /^[ \t]*(?:[-*][ \t]*)?(?:\*\*)?호칭(?:\*\*)?(?:\([^)\n]*\))?[ \t]*[:：][ \t]*(.+?)[ \t]*$/m;
function meOf(text) {
  const v = (text.match(LINE)?.[1] ?? "").replace(/[.。]$/, "").trim();
  return v && !v.includes("{{") ? v : ME_NONE;
}
var PAIR = { \uC774: ["\uC774", "\uAC00"], \uAC00: ["\uC774", "\uAC00"], \uC740: ["\uC740", "\uB294"], \uB294: ["\uC740", "\uB294"], \uC744: ["\uC744", "\uB97C"], \uB97C: ["\uC744", "\uB97C"], \uACFC: ["\uACFC", "\uC640"], \uC640: ["\uACFC", "\uC640"] };
function josa(w, j) {
  const p = PAIR[j];
  if (!p) return w + j;
  const c = w.charCodeAt(w.length - 1);
  if (!(c >= 44032 && c <= 55203)) return `${w}${p[0]}(${p[1]})`;
  return w + ((c - 44032) % 28 ? p[0] : p[1]);
}

// src/tools/notedoc.ts
var import_child_process3 = require("child_process");
var import_path3 = __toESM(require("path"));

// src/viewscope.ts
var import_child_process2 = require("child_process");
var import_fs2 = __toESM(require("fs"));
var import_path2 = __toESM(require("path"));
var VAULT_SERVER = "vault";
var LOOK_TOOL = `mcp__${VAULT_SERVER}__look`;
var SYM_TOOL = `mcp__${VAULT_SERVER}__sym`;
var LOOK_CAP = 12;
function paneKind(p) {
  const e = import_path2.default.extname(p).toLowerCase();
  if (e === ".note" || e === ".sdocx") return "\uD544\uAE30";
  if (e === ".pdf") return "PDF";
  if (e === ".md" || e === ".txt") return "md";
  if (e === ".sheet") return "\uC2DC\uD2B8";
  if ([".png", ".jpg", ".jpeg", ".webp", ".gif"].includes(e)) return "\uADF8\uB9BC";
  return "\uAE30\uD0C0";
}
var SMALL = { mdLines: 120, pdfPages: 2 };
var pageView = (v) => {
  const m = /^(\d+),(-?[\d.]+),(-?[\d.]+)(?:\/(\d+))?$/.exec(v ?? "");
  return m ? { p: +m[1], y0: +m[2], y1: +m[3], n: m[4] ? +m[4] : 0 } : null;
};
var lineView = (v) => {
  const m = /^(\d+)-(\d+)(?:\/(\d+))?$/.exec(v ?? "");
  return m ? { a: +m[1], b: +m[2], n: m[3] ? +m[3] : 0 } : null;
};
function paneLine(p) {
  const k = paneKind(p.path);
  const head = `- ${p.pos}${p.cur ? "(\uC9C0\uAE08 \uCC3D)" : ""} \xB7 ${k} \xB7 ${p.path}`;
  if (k === "\uD544\uAE30" || k === "PDF") {
    const v = pageView(p.view);
    if (!v) return `${head} \xB7 \uBCF4\uC774\uB294 \uACF3 \uBAA8\uB984(look screen = \uCCAB \uCABD \uC704)`;
    const small = k === "PDF" && v.n && v.n <= SMALL.pdfPages ? " \xB7 \uC791\uC74C(all \uB85C \uD1B5\uC9F8\uAC00 \uC308)" : "";
    return `${head} \xB7 ${v.n ? `${v.n}\uCABD \uC911 ` : ""}${v.p}\uCABD y ${Math.round(v.y0)}~${Math.round(v.y1)} \uC774 \uBCF4\uC784${small}${p.shown ? " \xB7 \uC774 \uD654\uBA74\uC740 \uCCAB \uADF8\uB9BC\uC73C\uB85C \uBD99\uC74C(\uB2E4\uC2DC \uC548 \uBD04)" : ""}`;
  }
  if (k === "md") {
    const v = lineView(p.view);
    if (!v) return `${head} \xB7 \uBCF4\uC774\uB294 \uACF3 \uBAA8\uB984`;
    const small = v.n && v.n <= SMALL.mdLines ? " \xB7 \uC791\uC74C(all \uB85C \uD1B5\uC9F8\uAC00 \uC308)" : "";
    return `${head} \xB7 ${v.n ? `${v.n}\uC904 \uC911 ` : ""}${v.a}\u2013${v.b}\uC904\uC774 \uBCF4\uC784${small}`;
  }
  if (k === "\uC2DC\uD2B8") return `${head} \xB7 ${p.view ? `${p.view} \uAC00 \uBCF4\uC784` : "\uBCF4\uC774\uB294 \uACF3 \uBAA8\uB984(look screen = \uCCAB \uC2DC\uD2B8 \uC4F0\uC778 \uBC94\uC704)"}`;
  if (k === "\uADF8\uB9BC") return `${head} \xB7 \uD1B5\uC9F8 \uBCF4\uC784`;
  return head;
}
function renderPanes(panes, n = "\u2461") {
  if (!panes.length || panes.length === 1 && !panes[0].view && paneKind(panes[0].path) !== "\uD544\uAE30") return "";
  const what = panes.length > 1 ? `\uBD84\uD560 ${panes.length}\uCE78 \xB7 \uC790\uB9AC = \uD654\uBA74\uC5D0\uC11C \uCE78\uC758 \uC704\uCE58` : "\uD55C \uCE78";
  return `${n} \uBCF4\uB294 \uD654\uBA74(${what} \xB7 \uB0B4\uC6A9\uC740 \uC548 \uC2E4\uC74C \u2014 \uD544\uC694\uD558\uBA74 look):
${panes.map(paneLine).join("\n")}`;
}
var SCOPE_RULE = [
  "\uBCF4\uB294 \uD654\uBA74(\uCD5C\uC18C \uBCF4\uAE30): \uBA38\uB9AC\uC758 \xAB\uBCF4\uB294 \uD654\uBA74\xBB\uC740 \uC0AC\uC6A9\uC790\uAC00 \uC9C0\uAE08 \uBCF4\uB294 \uCE78\uB4E4\uC758 \uC790\uB9AC\xB7\uC885\uB958\xB7\uBCF4\uC774\uB294 \uBC94\uC704\uB2E4. \xAB\uC624\uB978\uCABD \uB178\uD2B8\xBB\xB7\xAB\uC704 \uBB38\uC81C\xBB\xB7\xAB\uC774\uAC70\xBB\uAC00 \uC5B4\uB290 \uCE78\uC778\uC9C0\uB294 \uADF8 \uC790\uB9AC\uC640 \uC9C0\uAE08 \uCC3D\uC73C\uB85C \uACE0\uB978\uB2E4.",
  "\uCE78\uC758 \uB0B4\uC6A9\uC774 \uD544\uC694\uD558\uBA74 \uBA3C\uC800 \uADF8 \uCE78\uC758 \uBCF4\uC774\uB294 \uBC94\uC704\uB9CC look \uB3C4\uAD6C\uB85C \uBCF8\uB2E4(`<\uC790\uB9AC> screen`). \uB2F5\uC5D0 \uD544\uC694\uD55C \uBC94\uC704\uB97C \uB2E4 \uBCFC \uB54C\uAE4C\uC9C0 \uB354 \uBCF8\uB2E4 \u2014 \uC55E \uBB38\uD56D \uBA38\uB9AC\uAC00 \uC704\uB85C \uC798\uB838\uC73C\uBA74 up, \uD480\uC774\xB7\uD45C\uAC00 \uC544\uB798\uB85C \uC774\uC5B4\uC9C0\uBA74 down, \uB2E4\uB978 \uBB38\uD56D\xB7\uCABD\uC774\uBA74 page N(\uD544\uC694\uD55C \uC138\uB85C \uBC94\uC704\uB9CC y0-y1) \xB7 md \uB294 lines a-b \xB7 \uC2DC\uD2B8\uB294 cells \uBC94\uC704. \uC591\uC740 \uD544\uC694\uD55C \uB9CC\uD07C\uB9CC(\uC608 `\uC67C\uCABD down 200`).",
  "\uC774\uBBF8 \uBCF8 \uBC94\uC704\uB294 \uB2E4\uC2DC \uBCF4\uC9C0 \uC54A\uB294\uB2E4(\uB3C4\uAD6C\uB3C4 \uB9C9\uC74C). \uB2F5\uC5D0 \uC548 \uC4F0\uC77C \uCE78\uC740 \uBCF4\uC9C0 \uC54A\uB294\uB2E4. \uBA38\uB9AC\uC5D0 \xAB\uC791\uC74C\xBB\uC774 \uBD99\uC740 \uCE78\uC740 all \uB85C \uD1B5\uC9F8 \uBCF4\uB294 \uAC83\uC774 \uC2F8\uB2E4. md \uB294 Read \uB85C \uC904 \uBC94\uC704\uB97C \uC77D\uC5B4\uB3C4 \uAC19\uB2E4. \uB2E4 \uBABB \uBD24\uC73C\uBA74 \uBB34\uC5C7\uC744 \uBABB \uBD24\uB294\uC9C0 \uB2F5\uC5D0 \uBC1D\uD78C\uB2E4."
].join("\n");
var LOOK_SPEC = {
  name: "look",
  description: "\uBCF4\uB294 \uD654\uBA74\uC758 \uCE78\uC744 \uBC94\uC704\uB9CC\uD07C \uBCF8\uB2E4(\uCD5C\uC18C \uBCF4\uAE30). at = \xAB[\uC790\uB9AC] \uBB34\uC5C7\xBB \u2014 \uC790\uB9AC = \uBA38\uB9AC\uC758 \uCE78 \uC790\uB9AC(\uC67C\uCABD\xB7\uC624\uB978\uCABD\xB7\uC704\xB7\uC544\uB798 \u2026) \uB610\uB294 \uACBD\uB85C(\uBE7C\uBA74 \uD544\uAE30 \uCE78 \xB7 \uC5C6\uC73C\uBA74 \uC9C0\uAE08 \uCC3D). \uBB34\uC5C7 = screen(\uBCF4\uC774\uB294 \uBC94\uC704) | up [\uC591] | down [\uC591](\uBCF8 \uAC83 \uBC14\uB85C \uC704\xB7\uC544\uB798 \xB7 \uC591 = \uD544\uAE30\xB7PDF \uCABD \uC88C\uD45C \uB192\uC774 \xB7 md \uC904 \uC218 \xB7 \uC2DC\uD2B8 \uD589 \uC218 \xB7 \uBE7C\uBA74 \uD55C \uD654\uBA74) | page N [y0-y1] | lines a-b | cells A1:H30 \xB7 \uC774\uB984!A1:H30 | all(\uD1B5\uC9F8 \xB7 \uC791\uC740 \uD30C\uC77C\uB9CC) \xB7 as img|text(PDF \uB760\uB97C \uADF8\uB9BC/\uAE00\uB85C \uB2E4\uC2DC). \uC774\uBBF8 \uBCF8 \uBC94\uC704\uB294 \uB2E4\uC2DC \uC548 \uC90C.",
  inputSchema: { type: "object", properties: { at: { type: "string" } }, required: ["at"] }
};
var SYM_SPEC = {
  name: "sym",
  description: "SymPy \uAC80\uC0B0(\uC77D\uAE30 \uC804\uC6A9). op = eq(\uB450 \uC2DD \uAC19\uC740\uAC00) | simp | solve | num | rank | null | col | rref | det | inv | eig \xB7 exprs = \uC2DD \uAE00\uB4E4(^ = \uAC70\uB4ED\uC81C\uACF1 \xB7 \uD589\uB82C [[1,2],[3,4]] \xB7 solve \uB294 \xAB\uC2DD = \uC2DD\xBB \uB4A4\uC5D0 \uBCC0\uC218). \uACB0\uACFC \uD55C \uC904.",
  inputSchema: { type: "object", properties: { op: { type: "string" }, exprs: { type: "array", items: { type: "string" } } }, required: ["op", "exprs"] }
};
var txt = (t, err = false) => ({ content: [{ type: "text", text: t }], ...err ? { isError: true } : {} });
function pyRun(r, script, a) {
  const full = [script, ...a];
  return (0, import_child_process2.execFileSync)(r.py === "py" ? "py" : r.py, r.py === "py" ? ["-3", ...full] : full, { cwd: r.vault, timeout: 12e4, windowsHide: true, encoding: "utf8", maxBuffer: 32 * 1024 * 1024 });
}
function pyRunA(r, script, a) {
  const full = [script, ...a];
  return new Promise(
    (res, rej) => (0, import_child_process2.execFile)(r.py === "py" ? "py" : r.py, r.py === "py" ? ["-3", ...full] : full, { cwd: r.vault, timeout: 12e4, windowsHide: true, encoding: "utf8", maxBuffer: 32 * 1024 * 1024 }, (e, out2) => e ? rej(e) : res(String(out2)))
  );
}
var lastJson = (s) => {
  const l = s.trim().split("\n").filter((x) => x.startsWith("{")).at(-1);
  return l ? JSON.parse(l) : null;
};
function inkScreen(r, note, spec, o) {
  const a = [import_path2.default.join(r.vault, note), "--screen", spec, "--json", "--start", String(o.start ?? 1)];
  if (!o.split) a.push("--all");
  if (o.seen) a.push("--seen", o.seen);
  if (o.label) a.push("--label", o.label);
  const j = lastJson(pyRun(r, import_path2.default.join(r.vault, "3_\uC2DC\uC2A4\uD15C", "inkrender.py"), a));
  if (!j?.dims) throw new Error("inkrender --screen \uB2F5 \uC5C6\uC74C");
  return j;
}
var segsSpec = (segs) => segs.map(([p, a, b]) => `${p},${Math.round(a)},${Math.round(b)}`).join(";");
function lookState(dims, segs) {
  if (!segs.length || !dims.length) return null;
  const f = segs[0], l = segs[segs.length - 1];
  const h = Math.max(300, segs.reduce((t, [, a, b]) => t + (b - a), 0));
  return { dims, top: [f[0], f[1]], bot: [l[0], l[2]], h };
}
function viewSegs(dims, view) {
  const v = pageView(view);
  if (!v || v.p < 1 || v.p > dims.length) return [];
  const out2 = [];
  let p = v.p, y0 = Math.max(0, v.y0), left = Math.max(0, v.y1 - v.y0);
  while (left > 0.5 && p <= dims.length) {
    const H = dims[p - 1][1];
    const b = Math.min(H, y0 + left);
    if (b - y0 >= 12) out2.push([p, y0, b]);
    left -= b - y0;
    p += 1;
    y0 = 0;
  }
  return out2;
}
function lookSegs(st, at) {
  const t = at.trim().toLowerCase();
  const n = st.dims.length;
  let m;
  if (m = /^(up|down)(?:\s+(\d+(?:\.\d+)?))?$/.exec(t)) {
    const amt = m[2] ? Math.max(20, +m[2]) : st.h;
    if (m[1] === "up") {
      let [p2, y2] = st.top;
      let h2 = amt;
      const segs2 = [];
      while (h2 > 0.5 && p2 >= 1) {
        if (y2 <= 0.5) {
          p2 -= 1;
          if (p2 < 1) break;
          y2 = st.dims[p2 - 1][1];
          continue;
        }
        const a = Math.max(0, y2 - h2);
        segs2.unshift([p2, a, y2]);
        h2 -= y2 - a;
        y2 = a;
      }
      if (!segs2.length) return "\uB354 \uC704\uAC00 \uC5C6\uC74C(\uB9E8 \uC704)";
      st.top = [segs2[0][0], segs2[0][1]];
      return { segs: segs2, label: "\uC704\uB97C \uB354 \uBD04" };
    }
    let [p, y] = st.bot;
    let h = amt;
    const segs = [];
    while (h > 0.5 && p <= n) {
      const H = st.dims[p - 1][1];
      if (y >= H - 0.5) {
        p += 1;
        y = 0;
        continue;
      }
      const b = Math.min(H, y + h);
      segs.push([p, y, b]);
      h -= b - y;
      y = b;
    }
    if (!segs.length) return "\uB354 \uC544\uB798\uAC00 \uC5C6\uC74C(\uB9E8 \uB05D)";
    const l = segs[segs.length - 1];
    st.bot = [l[0], l[2]];
    return { segs, label: "\uC544\uB798\uB97C \uB354 \uBD04" };
  }
  if (m = /^page\s+(\d{1,4})(?:\s+(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?))?$/.exec(t)) {
    const p = +m[1];
    if (p < 1 || p > n) return `\uCABD\uC740 1~${n}`;
    const H = st.dims[p - 1][1];
    const a = m[2] ? Math.max(0, +m[2]) : 0, b = m[3] ? Math.min(H, +m[3]) : H;
    if (b <= a) return "\uBE48 \uBC94\uC704";
    st.top = [p, a];
    st.bot = [p, b];
    return { segs: [[p, a, b]], label: m[2] ? `${p}\uCABD \uC77C\uBD80\uB97C \uB354 \uBD04` : `${p}\uCABD\uC744 \uB354 \uBD04` };
  }
  return "at \uC740 up [\uC591] | down [\uC591] | page N [y0-y1]";
}
function minusSeen(segs, seen) {
  let out2 = segs.map((s) => [...s]);
  for (const [sp, sa, sb] of seen) {
    const next = [];
    for (const [p, a, b] of out2) {
      if (p !== sp || sb <= a || sa >= b) next.push([p, a, b]);
      else {
        if (sa > a) next.push([p, a, sa]);
        if (sb < b) next.push([p, sb, b]);
      }
    }
    out2 = next;
  }
  return out2.filter(([, a, b]) => b - a >= 4);
}
var Looker = class {
  constructor(r, panes, o = {}) {
    this.r = r;
    this.panes = panes;
    this.o = o;
    this.st = /* @__PURE__ */ new Map();
    this.nextL = 1;
    // 필기 L번호 이어 매김
    this.shownInk = [];
    // 필기 칸에서 본 범위(탭 «본 것» 표식용)
    this.looks = 0;
    /** 칸마다 한 줄로(같은 칸 상태가 엉키지 않게) · 다른 칸끼리는 나란히(한 답에서 칸 둘을 볼 때 같이 돎) */
    this.chains = /* @__PURE__ */ new Map();
    this.infoCache = /* @__PURE__ */ new Map();
  }
  /** 이미 사용자에게 보인 필기 화면(탭이 첫 그림으로 붙인 것) — 상태를 그것으로 시작 */
  primeInk(note, sc) {
    const s = this.state(this.pickPane(note) ?? { path: note, pos: "\uD544\uAE30", cur: true });
    s.st = lookState(sc.dims, sc.segs);
    s.seen.push(...sc.segs);
    this.shownInk.push(...sc.segs);
    this.nextL = sc.next;
  }
  pickPane(at) {
    const t = at.trim();
    return this.panes.find((p) => p.path === t) ?? this.panes.find((p) => p.pos === t) ?? null;
  }
  state(p) {
    let s = this.st.get(p.path);
    if (!s) this.st.set(p.path, s = { pane: p, kind: paneKind(p.path), n: 0, seen: [], lseen: [], cseen: /* @__PURE__ */ new Set() });
    return s;
  }
  /** at = «[자리|경로] 무엇» → 칸과 나머지 */
  resolve(at) {
    const t = at.trim();
    const byPath = this.panes.filter((p) => t === p.path || t.startsWith(p.path + " ")).sort((a, b) => b.path.length - a.path.length)[0];
    if (byPath) return { pane: byPath, rest: t.slice(byPath.path.length).trim() };
    const byPos = [...this.panes].sort((a, b) => b.pos.length - a.pos.length).find((p) => t === p.pos || t.startsWith(p.pos + " "));
    if (byPos) return { pane: byPos, rest: t.slice(byPos.pos.length).trim() };
    if (/^(지금|cur|current)\b/.test(t)) {
      const c = this.panes.find((p) => p.cur) ?? this.panes[0];
      if (c) return { pane: c, rest: t.replace(/^\S+\s*/, "") };
    }
    const def = this.panes.find((p) => paneKind(p.path) === "\uD544\uAE30") ?? this.panes.find((p) => p.cur) ?? this.panes[0];
    if (!def) return "\uBCF4\uB294 \uD654\uBA74\uC5D0 \uCE78\uC774 \uC5C6\uC74C \u2014 Read \uB85C \uACBD\uB85C\uB97C \uC77D\uB294\uB2E4";
    return { pane: def, rest: t };
  }
  call(at) {
    const r = this.resolve(at);
    if (typeof r === "string") return Promise.resolve(txt(r, true));
    const prev = this.chains.get(r.pane.path) ?? Promise.resolve();
    const p = prev.then(() => this.run(r.pane, r.rest || "screen"));
    this.chains.set(r.pane.path, p.catch(() => {
    }));
    return p;
  }
  async run(pane, what) {
    const s = this.state(pane);
    if (s.n >= LOOK_CAP) return txt(`\uB354 \uBABB \uBD04: ${pane.pos} \uCE78\uC740 \uC774 \uB2F5\uC5D0\uC11C ${LOOK_CAP}\uBC88 \uBD24\uC74C(\uACE0\uB9AC \uB9C9\uAE30) \u2014 \uBCF8 \uAC83\uC73C\uB85C \uB2F5\uD558\uACE0 \uBABB \uBCF8 \uACF3\uC744 \uBC1D\uD78C\uB2E4`, true);
    s.n++;
    this.looks++;
    try {
      if (s.kind === "\uD544\uAE30") return await this.ink(s, what);
      if (s.kind === "PDF") return await this.pdf(s, what);
      if (s.kind === "md") return await this.md(s, what);
      if (s.kind === "\uC2DC\uD2B8") return await this.sheet(s, what);
      if (s.kind === "\uADF8\uB9BC") return await this.img(s);
      return txt(`\uC774 \uC885\uB958\uB294 look \uC73C\uB85C \uBABB \uBD04 \u2014 Read ${pane.path}`, true);
    } catch (e) {
      return txt("\uBCF4\uAE30 \uC2E4\uD328: " + String(e instanceof Error ? e.message : e).slice(0, 300), true);
    }
  }
  // 쪽 갈래 공통: up | down | page | all → 띠(이미 본 것 뺌은 부른 쪽이)
  pageSegs(s, what, dims) {
    const w = what.trim().toLowerCase();
    if (w === "all") {
      if (dims.length > SMALL.pdfPages && s.kind === "PDF") return `all \uC740 ${SMALL.pdfPages}\uCABD \uC774\uD558\uB9CC \u2014 page N \uB610\uB294 up/down`;
      if (s.kind === "\uD544\uAE30") return "\uD544\uAE30\uB294 all \uC5C6\uC74C \u2014 page N \uB610\uB294 up/down";
      return { segs: dims.map((d, i) => [i + 1, 0, d[1]]), label: "\uD1B5\uC9F8" };
    }
    if (!s.st) {
      const base = viewSegs(dims, s.pane.view ?? "");
      s.st = lookState(dims, base.length ? base : [[1, 0, Math.min(dims[0]?.[1] ?? 0, 600)]]);
      if (!s.st) return "\uCABD \uC815\uBCF4 \uC5C6\uC74C";
    }
    return lookSegs(s.st, w);
  }
  inkA(note, spec, label) {
    const a = [import_path2.default.join(this.r.vault, note), "--screen", spec, "--json", "--start", String(this.nextL)];
    if (!this.o.split) a.push("--all");
    if (this.o.seen) a.push("--seen", this.o.seen);
    if (label) a.push("--label", label);
    return pyRunA(this.r, import_path2.default.join(this.r.vault, "3_\uC2DC\uC2A4\uD15C", "inkrender.py"), a).then((o) => {
      const j = lastJson(o);
      if (!j?.dims) throw new Error("inkrender --screen \uB2F5 \uC5C6\uC74C");
      return j;
    });
  }
  inkOut(s, m, label) {
    s.seen.push(...m.segs);
    this.shownInk.push(...m.segs);
    this.nextL = m.next;
    this.o.onInk?.(m.shots, label);
    this.o.onLook?.(label, s.pane);
    if (!m.shots.length) return txt(`${s.pane.pos} \uD544\uAE30 ${label}: \uADF8 \uBC94\uC704\uC5D0 \uD68D \uC5C6\uC74C`);
    const ls2 = m.shots.flatMap((x) => x.lines);
    return {
      content: [
        { type: "text", text: `${s.pane.pos} \uD544\uAE30 ${label} \u2014 ${m.segs.map(([p, a, b]) => `${p}\uCABD y ${Math.round(a)}~${Math.round(b)}`).join(" + ")} \xB7 L${ls2[0]?.n ?? "?"}\u2013L${ls2[ls2.length - 1]?.n ?? "?"}` },
        ...m.shots.map((x) => ({ type: "image", data: import_fs2.default.readFileSync(x.png).toString("base64"), mimeType: "image/png" }))
      ]
    };
  }
  async ink(s, what) {
    const note = s.pane.path;
    const w = what.trim().toLowerCase();
    if (w === "screen" && !s.st) {
      const m = await this.inkA(note, (s.pane.view ?? "1,0,900").replace(/\/\d+$/, ""), "\uBCF4\uC774\uB294 \uBC94\uC704");
      s.st = lookState(m.dims, m.segs.length ? m.segs : [[1, 0, Math.min(m.dims[0]?.[1] ?? 0, 900)]]);
      return this.inkOut(s, m, "\uBCF4\uC774\uB294 \uBC94\uC704");
    }
    if (w === "screen") return txt("\uC774\uBBF8 \uBD04: \uBCF4\uC774\uB294 \uBC94\uC704 \u2014 \uB2E4\uC2DC \uC548 \uBD04(\uB354 \uBCF4\uB824\uBA74 up/down/page N)");
    if (!s.st) {
      const first = await this.inkA(note, "1,0,1");
      s.st = lookState(first.dims, viewSegs(first.dims, s.pane.view ?? "").length ? viewSegs(first.dims, s.pane.view ?? "") : [[1, 0, Math.min(first.dims[0]?.[1] ?? 0, 600)]]);
      if (!s.st) return txt("\uCABD \uC815\uBCF4 \uC5C6\uC74C", true);
    }
    const dims = s.st.dims;
    for (let tries = 0; ; tries++) {
      const r = this.pageSegs(s, what, dims);
      if (typeof r === "string") return txt(r, true);
      const left = minusSeen(r.segs, s.seen);
      if (!left.length) {
        if (/^(up|down)/.test(w) && tries < 2) continue;
        return txt(`\uC774\uBBF8 \uBD04: ${r.segs.map(([p, a, b]) => `${p}\uCABD y ${Math.round(a)}~${Math.round(b)}`).join(" + ")} \u2014 \uB2E4\uC2DC \uC548 \uBD04`);
      }
      const m = await this.inkA(note, segsSpec(left), r.label);
      if (!m.shots.length && /^(up|down)/.test(w) && tries < 2) {
        s.seen.push(...m.segs);
        continue;
      }
      return this.inkOut(s, m, r.label);
    }
  }
  info(p) {
    if (!this.infoCache.has(p)) this.infoCache.set(p, pyRunA(this.r, import_path2.default.join(this.r.vault, "3_\uC2DC\uC2A4\uD15C", "viewlook.py"), [import_path2.default.join(this.r.vault, p), "--info"]).then((o) => lastJson(o) ?? {}));
    return this.infoCache.get(p);
  }
  async vl(p, a) {
    const j = lastJson(await pyRunA(this.r, import_path2.default.join(this.r.vault, "3_\uC2DC\uC2A4\uD15C", "viewlook.py"), [import_path2.default.join(this.r.vault, p), ...a]));
    if (!j || j.error) throw new Error(j?.error ?? "viewlook \uB2F5 \uC5C6\uC74C");
    return j;
  }
  pdfOut(s, label, shown, j, dims, rest = []) {
    s.seen.push(...shown);
    this.o.onLook?.(label, s.pane);
    const at = (x) => x.map(([p, a, b]) => `${p}\uCABD y ${Math.round(a)}~${Math.round(b)}/${Math.round(dims[p - 1]?.[1] ?? 0)}`).join(" + ");
    const content = [{ type: "text", text: `${s.pane.pos} PDF ${label} \u2014 ${dims.length}\uCABD \uC911 ${at(shown)}${rest.length ? ` \xB7 \uD654\uBA74\uC5D0 \uB354 \uBCF4\uC774\uB294 \uACF3(\uC548 \uADF8\uB9BC \xB7 \uD544\uC694\uD558\uBA74 down): ${at(rest)}` : ""}` }];
    for (const part of j.parts ?? []) {
      if (part.error) content.push({ type: "text", text: `${part.page}\uCABD: ${part.error}` });
      else if (part.text) content.push({ type: "text", text: `[${part.page}\uCABD y ${part.y0}~${part.y1} \uAE00\uCE35]
${part.text}` });
      else if (part.png) content.push({ type: "image", data: import_fs2.default.readFileSync(part.png).toString("base64"), mimeType: "image/png" });
    }
    return { content };
  }
  async pdf(s, what) {
    let as;
    const am = /\s+as\s+(img|text)$/i.exec(what);
    if (am) as = am[1].toLowerCase(), what = what.slice(0, am.index);
    const w = what.trim().toLowerCase();
    if (w === "screen" && !s.st && s.pane.view && !as) {
      const j2 = await this.vl(s.pane.path, ["--screen", s.pane.view.replace(/\/\d+$/, "")]);
      const dims2 = j2.dims ?? [];
      const shown = j2.shown ?? [];
      s.st = lookState(dims2, shown.length ? shown : [[1, 0, Math.min(dims2[0]?.[1] ?? 0, 600)]]);
      return this.pdfOut(s, "\uBCF4\uC774\uB294 \uBC94\uC704", shown, j2, dims2, j2.rest ?? []);
    }
    if (w === "screen" && s.st && !as) return txt("\uC774\uBBF8 \uBD04: \uBCF4\uC774\uB294 \uBC94\uC704 \u2014 \uB2E4\uC2DC \uC548 \uBD04(\uB354 \uBCF4\uB824\uBA74 down/up/page N)");
    const inf = await this.info(s.pane.path);
    const dims = inf.dims ?? [];
    if (!dims.length) return txt(inf.error ?? "PDF \uB97C \uBABB \uC5F6", true);
    const r = w === "screen" ? { segs: viewSegs(dims, s.pane.view ?? "1,0,600").slice(0, 1), label: "\uBCF4\uC774\uB294 \uBC94\uC704" } : this.pageSegs(s, what, dims);
    if (typeof r === "string") return txt(r, true);
    s.st ??= lookState(dims, r.segs);
    const left = as ? r.segs : minusSeen(r.segs, s.seen);
    if (!left.length) return txt(`\uC774\uBBF8 \uBD04: ${r.segs.map(([p, a, b]) => `${p}\uCABD y ${Math.round(a)}~${Math.round(b)}`).join(" + ")} \u2014 \uB2E4\uC2DC \uC548 \uBD04(\uAF34\uC744 \uBC14\uAFB8\uB824\uBA74 as img)`);
    const j = await this.vl(s.pane.path, ["--range", segsSpec(left), ...as ? ["--as", as] : []]);
    return this.pdfOut(s, r.label, left, j, dims);
  }
  async md(s, what) {
    const v = lineView(s.pane.view);
    if (s.lines === void 0) s.lines = v?.n || (await this.info(s.pane.path)).lines || 0;
    const N = s.lines ?? 0;
    const w = what.trim().toLowerCase();
    let a, b, label;
    let m;
    if (s.ltop === void 0) {
      s.ltop = v?.a ?? 1;
      s.lbot = v?.b ?? Math.min(N, 40);
      s.lh = Math.max(10, (s.lbot ?? 1) - (s.ltop ?? 1) + 1);
    }
    if (w === "screen") a = s.ltop, b = s.lbot, label = "\uBCF4\uC774\uB294 \uBC94\uC704";
    else if (w === "all") {
      if (N > SMALL.mdLines * 3) return txt(`all \uC740 ${SMALL.mdLines * 3}\uC904 \uC774\uD558\uB9CC \u2014 lines a-b \uB610\uB294 up/down`, true);
      a = 1, b = N, label = "\uD1B5\uC9F8";
    } else if (m = /^(up|down)(?:\s+(\d+))?$/.exec(w)) {
      const amt = m[2] ? +m[2] : s.lh;
      const lo = Math.min(...s.lseen.map((x) => x[0]), s.ltop), hi = Math.max(...s.lseen.map((x) => x[1]), s.lbot);
      if (m[1] === "up") b = lo - 1, a = Math.max(1, b - amt + 1), label = "\uC704\uB97C \uB354 \uBD04";
      else a = hi + 1, b = Math.min(N, a + amt - 1), label = "\uC544\uB798\uB97C \uB354 \uBD04";
      if (b < a) return txt(m[1] === "up" ? "\uB354 \uC704\uAC00 \uC5C6\uC74C(\uB9E8 \uC704)" : "\uB354 \uC544\uB798\uAC00 \uC5C6\uC74C(\uB9E8 \uB05D)");
    } else if (m = /^lines?\s+(\d+)\s*-\s*(\d+)$/.exec(w)) a = +m[1], b = +m[2], label = `${a}\u2013${b}\uC904`;
    else return txt("md \uB294 screen | up [\uC904 \uC218] | down [\uC904 \uC218] | lines a-b | all", true);
    for (const [x, y] of s.lseen) {
      if (x <= a && y >= b) return txt(`\uC774\uBBF8 \uBD04: ${a}\u2013${b}\uC904 \u2014 \uB2E4\uC2DC \uC548 \uBD04`);
      if (x <= a && y >= a) a = y + 1;
      if (x <= b && y >= b) b = x - 1;
    }
    if (b < a) return txt(`\uC774\uBBF8 \uBD04 \u2014 \uB2E4\uC2DC \uC548 \uBD04`);
    const j = await this.vl(s.pane.path, ["--range", `${a}-${b}`]);
    const part = j.parts?.[0];
    s.lseen.push([part.a, part.b]);
    this.o.onLook?.(label, s.pane);
    return txt(`${s.pane.pos} md ${label} \u2014 ${N}\uC904 \uC911 ${part.a}\u2013${part.b}\uC904(\uC55E = \uC904 \uBC88\uD638)
${part.text}`);
  }
  async sheet(s, what) {
    const w = what.trim();
    let range;
    let m;
    if (/^screen$/i.test(w) && s.pane.view) range = s.pane.view;
    const inf = await this.info(s.pane.path);
    const sheets = inf?.sheets ?? [];
    if (!range && (m = /^(up|down)(?:\s+(\d+))?$/i.exec(w)) && s.lastCells) {
      const q = /^(.+)!([A-Z]+)(\d+):([A-Z]+)(\d+)$/.exec(s.lastCells);
      if (q) {
        const n = m[2] ? +m[2] : Math.max(10, +q[5] - +q[3] + 1);
        const [a, b] = m[1].toLowerCase() === "down" ? [+q[5] + 1, +q[5] + n] : [Math.max(1, +q[3] - n), +q[3] - 1];
        if (b < a) return txt("\uB354 \uC704\uAC00 \uC5C6\uC74C(1\uD589)");
        range = `${q[1]}!${q[2]}${a}:${q[4]}${b}`;
      }
    }
    if (!range) {
      if (!sheets.length) return txt(inf?.error ?? "\uC2DC\uD2B8\uB97C \uBABB \uC5F6", true);
      const first = sheets.find((x) => x.name === inf.active) ?? sheets[0];
      if (/^screen$/i.test(w)) range = `${first.name}!${capRange(first.used)}`;
      else if (/^all$/i.test(w)) return txt(`\uC2DC\uD2B8 ${sheets.length}\uC7A5: ${sheets.map((x) => `${x.name}(${x.used})`).join(" \xB7 ")} \u2014 cells \uC774\uB984!\uBC94\uC704 \uB85C \uD544\uC694\uD55C \uACF3\uB9CC`);
      else if (m = /^(?:cells\s+)?((?:[^!]+!)?[A-Za-z]+\d+:[A-Za-z]+\d+)$/i.exec(w)) range = m[1].includes("!") ? m[1] : `${first.name}!${m[1]}`;
      else if (m = /^sheet\s+(.+)$/i.exec(w)) {
        const sh = sheets.find((x) => x.name === m[1].trim());
        if (!sh) return txt(`\uC2DC\uD2B8 \uC774\uB984: ${sheets.map((x) => x.name).join(" \xB7 ")}`, true);
        range = `${sh.name}!${capRange(sh.used)}`;
      } else return txt(`\uC2DC\uD2B8\uB294 screen | up/down [\uD589 \uC218] | cells \uC774\uB984!A1:H30 | sheet \uC774\uB984 | all \xB7 \uC2DC\uD2B8: ${sheets.map((x) => `${x.name}(${x.used})`).join(" \xB7 ")}`, true);
    }
    if (s.cseen.has(range)) return txt(`\uC774\uBBF8 \uBD04: ${range} \u2014 \uB2E4\uC2DC \uC548 \uBD04`);
    const j = await this.vl(s.pane.path, ["--range", range]);
    s.cseen.add(range);
    s.lastCells = range;
    this.o.onLook?.(range, s.pane);
    const part = j.parts?.[0];
    return txt(`${s.pane.pos} \uC2DC\uD2B8 ${range}(\uAC12\uB9CC \xB7 \uBE48 \uCE78 \uBE8C${sheets.length ? ` \xB7 \uC2DC\uD2B8 ${sheets.length}\uC7A5: ${sheets.map((x) => x.name).join(" \xB7 ")}` : ""})
${part?.text || "(\uBE48 \uBC94\uC704)"}`);
  }
  async img(s) {
    if (s.n > 1) return txt("\uC774\uBBF8 \uBD04 \u2014 \uADF8\uB9BC\uC740 \uD1B5\uC9F8 \uD55C \uBC88");
    const j = await this.vl(s.pane.path, ["--range", "all"]);
    const part = j.parts?.[0];
    this.o.onLook?.("\uADF8\uB9BC", s.pane);
    return { content: [{ type: "text", text: `${s.pane.pos} \uADF8\uB9BC ${s.pane.path}` }, { type: "image", data: import_fs2.default.readFileSync(part.png).toString("base64"), mimeType: "image/png" }] };
  }
};
function capRange(used) {
  const m = /^([A-Z]+)(\d+):([A-Z]+)(\d+)$/.exec(used);
  if (!m) return used;
  return `${m[1]}${m[2]}:${m[3]}${Math.min(+m[4], +m[2] + 59)}`;
}
var SYM_OPS = /* @__PURE__ */ new Set(["eq", "simp", "solve", "num", "rank", "null", "col", "rref", "det", "inv", "eig"]);
async function symRun(r, op, exprs) {
  if (!SYM_OPS.has(op)) return txt(`op \uC740 ${[...SYM_OPS].join("|")}`, true);
  if (!Array.isArray(exprs) || !exprs.length || exprs.some((e) => typeof e !== "string" || e.length > 2e3)) return txt("exprs = \uC2DD \uAE00 1\uAC1C \uC774\uC0C1", true);
  try {
    const out2 = await pyRunA(r, import_path2.default.join(r.vault, ".claude", "skills", "study-helper", "scripts", "symcheck.py"), [op, ...exprs]);
    return txt(out2.trim().slice(0, 4e3) || "(\uACB0\uACFC \uC5C6\uC74C)");
  } catch (e) {
    return txt(String(e?.stdout || e?.stderr || e?.message || e).trim().slice(0, 1e3), true);
  }
}
function vaultCall(name, args2, ctx) {
  if (name === "look") return ctx.looker ? ctx.looker.call(String(args2?.at ?? "")) : Promise.resolve(txt("\uBCF4\uB294 \uD654\uBA74\uC774 \uC5C6\uC74C \u2014 Read \uB85C \uACBD\uB85C\uB97C \uC77D\uB294\uB2E4", true));
  if (name === "sym") return symRun(ctx.r, String(args2?.op ?? ""), (args2?.exprs ?? []).map(String));
  return null;
}

// src/tools/notedoc.ts
var DOC_EXT = /\.(pdf|png|jpe?g|webp|md|txt)$/i;
var stem = (p) => import_path3.default.basename(p).replace(/\.[^.]+$/, "");
function runDoc(py, vault, script, a, ms) {
  return new Promise((res) => {
    const cmd = py === "py" ? "py" : py;
    const args2 = py === "py" ? ["-3", script, ...a] : [script, ...a];
    const ch = (0, import_child_process3.spawn)(cmd, args2, { cwd: vault, windowsHide: true, env: { ...process.env, BRAIN_VAULT: vault } });
    let out2 = "";
    let done = false;
    let timer = null;
    const fin = (v) => {
      if (timer) clearTimeout(timer);
      if (!done) done = true, res(v);
    };
    ch.stdout.on("data", (d) => out2 += d.toString("utf8"));
    ch.on("close", () => {
      const l = out2.trim().split("\n").filter((x) => x.startsWith("{")).at(-1);
      try {
        fin(l ? JSON.parse(l) : null);
      } catch {
        fin(null);
      }
    });
    ch.on("error", () => fin(null));
    timer = setTimeout(() => {
      if (!done) ch.unref(), ch.stdout.removeAllListeners(), fin(null);
    }, ms);
  });
}
async function docPanes(o) {
  const have = new Set(o.panes.map((p) => p.path));
  const add = [];
  if (o.ref && DOC_EXT.test(o.ref) && stem(o.ref) !== stem(o.note) && !have.has(o.ref)) add.push({ path: o.ref, pos: "\uC9DD \uBB38\uC81C" });
  if (o.bg && !have.has(o.bg) && o.firstPage) {
    const b = await runDoc(o.py, o.vault, o.script, [o.note, "--bg", String(o.firstPage)], 15e3);
    if (b?.bg && b.page) add.push({ path: b.bg, pos: "\uBC14\uD0D5 PDF", view: `${b.page},0,${b.h ?? 842}${b.pages ? `/${b.pages}` : ""}` });
  }
  return add;
}
async function docTables(o) {
  const ps = o.panes.filter((p) => paneKind(p.path) === "PDF" && p.pos !== "\uBC14\uD0D5 PDF");
  const rs = await Promise.all(ps.map((p) => runDoc(o.py, o.vault, o.script, [p.path, "--no-wait"], o.ms)));
  return ps.map((p, i) => ({ pane: p, pages: rs[i]?.pages ?? 0, items: (rs[i]?.items ?? []).filter((x) => x.num), pending: !!rs[i]?.pending })).filter((t) => t.items.length || t.pending);
}
function warmDoc(py, vault, script, note, ref) {
  if (!ref || !/\.pdf$/i.test(ref) || stem(ref) === stem(note)) return Promise.resolve(null);
  return runDoc(py, vault, script, [ref, "--no-wait"], 3e3);
}
function docHead(added, tables, n = "\u2466") {
  const out2 = [];
  for (const p of added)
    out2.push(
      p.pos === "\uBC14\uD0D5 PDF" ? `- \uBC14\uD0D5 PDF(\uD544\uAE30 \uBC11 \uAC15\uC758 \uC790\uB8CC \xB7 \uD654\uBA74\uC5D0 \uD544\uAE30\uC640 \uACB9\uCCD0 \uBCF4\uC784): ${p.path} \xB7 \uBCF4\uC774\uB294 \uD544\uAE30 \uCABD \uBC11 = ${p.view?.split(",")[0]}\uCABD \xB7 look \xAB\uBC14\uD0D5 PDF screen\xBB(\uADF8 \uCABD) \xB7 \xAB\uBC14\uD0D5 PDF page N y0-y1\xBB` : `- \uC9DD \uBB38\uC81C(\uB178\uD2B8\uC5D0 \uC9DD\uC9C0\uC740 \uBB38\uC81C\uC9C0 \xB7 \uD654\uBA74\uC5D0\uB294 \uC5C6\uC74C): ${p.path} \xB7 look \xAB\uC9DD \uBB38\uC81C page N y0-y1\xBB`
    );
  for (const t of tables) {
    if (t.pending) {
      out2.push(`- \uBB38\uD56D \uD45C(${t.pane.pos}): \uB9CC\uB4DC\uB294 \uC911(\uC774\uBC88 \uB2F5\uC740 page N y0-y1 \uB85C \xB7 \uB2E4\uC74C \uB2F5\uBD80\uD130 \uBB38\uD56D \uD45C)`);
      continue;
    }
    const by = /* @__PURE__ */ new Map();
    for (const it of t.items) by.set(it.page, [...by.get(it.page) ?? [], it.id]);
    const rows = [...by].map(([pg, ids]) => `${pg}\uCABD ${ids.join("\xB7")}`).join(" | ");
    out2.push(`- \uBB38\uD56D \uD45C(${t.pane.pos} \xB7 ${t.pages}\uCABD \xB7 look \xAB${t.pane.pos} \uBB38\uD56D <\uBC88\uD638>\xBB = \uADF8 \uBB38\uD56D \uB369\uC774\uB9CC): ${rows}`);
  }
  return out2.length ? `${n} \uBB38\uC81C\uC9C0:
${out2.join("\n")}` : "";
}
function itemAt(at, tables) {
  const m = /^(?:(.*?)\s+)?(?:문항|item|problem|#)\s*(\S+(?:\s+\S+)?)$/i.exec(at.trim());
  if (!m || !tables.length) return null;
  const pos = (m[1] ?? "").trim();
  const t = pos && tables.find((x2) => x2.pane.pos === pos || x2.pane.path === pos) || tables[0];
  const q = m[2].replace(/[()]/g, "").trim().replace(/\s+/g, "-");
  const norm = (s) => s.toLowerCase().replace(/[\s_]/g, "");
  let hit = t.items.filter((x2) => norm(x2.id) === norm(q));
  if (!hit.length) {
    const mm = /^(.+?)[.\-](\d{1,3})$/.exec(q);
    if (mm) hit = t.items.filter((x2) => norm(x2.sec) === norm(mm[1]) && x2.num === mm[2]);
  }
  if (!hit.length) hit = t.items.filter((x2) => x2.num === q);
  if (hit.length > 1) return { err: `\uBB38\uD56D \xAB${q}\xBB\uAC00 \uC5EC\uB7FF: ${hit.map((x2) => `${x2.id}(${x2.page}\uCABD)`).join(" \xB7 ")} \u2014 \uB2E8\uC6D0\uAE4C\uC9C0(\uC608 ${hit[0].id})` };
  if (!hit.length) {
    const sm = /^(.+)-(\d{1,3})$/.exec(q);
    const dm = /^(\d{1,2})\.(\d{1,3})$/.exec(q);
    const num = sm ? +sm[2] : dm ? +dm[2] : +q;
    const pool = sm ? t.items.filter((x2) => norm(x2.sec) === norm(sm[1])) : dm ? t.items.filter((x2) => x2.num?.startsWith(dm[1] + ".")).map((x2) => ({ ...x2, num: x2.num.split(".")[1] })) : t.items.filter((x2) => !x2.sec);
    if (!pool.length || isNaN(num)) return { err: `\uBB38\uD56D \xAB${q}\xBB\uAC00 \uD45C\uC5D0 \uC5C6\uC74C \u2014 \uB2E8\uC6D0\uAE4C\uC9C0(\uC608 ${t.items[0]?.id}) \uB610\uB294 page N y0-y1 \uB85C` };
    const sorted = pool.filter((x2) => x2.num && !isNaN(parseFloat(x2.num))).sort((a, b) => a.page - b.page || a.y0 - b.y0);
    const prev = [...sorted].reverse().find((x2) => parseFloat(x2.num) < num);
    const next = sorted.find((x2) => parseFloat(x2.num) > num && (!prev || x2.page > prev.page || x2.y0 > prev.y0));
    if (prev && next && prev.page === next.page) return `${t.pane.pos} page ${prev.page} ${Math.round(prev.y0)}-${Math.round(next.y0)}`;
    if (prev && next && next.num && parseFloat(next.num) - num < num - parseFloat(prev.num)) return `${t.pane.pos} page ${next.page} 0-${Math.round(next.y0)}`;
    if (prev) return `${t.pane.pos} page ${prev.page} ${Math.round(prev.y0)}-${Math.round(prev.h)}`;
    if (next) return `${t.pane.pos} page ${next.page} 0-${Math.round(next.y0)}`;
    return { err: `\uBB38\uD56D \xAB${q}\xBB\uAC00 \uD45C\uC5D0 \uC5C6\uC74C \u2014 page N y0-y1 \uB85C` };
  }
  const x = hit[0];
  return `${t.pane.pos} page ${x.page} ${Math.round(x.y0)}-${Math.round(x.y1)}`;
}
var DOC_RULE = "\uBB38\uC81C\uC9C0(\uBA38\uB9AC\uC758 \xAB\uBB38\uC81C\uC9C0\xBB \xB7 \uB610\uB294 \uBCF4\uB294 \uD654\uBA74\uC758 PDF \uCE78)\uAC00 \uC788\uC73C\uBA74 \uD480\uC774\uB97C \uD310\uC815\uD558\uAE30 \uC804\uC5D0 \uADF8 \uBB38\uD56D \uC6D0\uBB38(\uBC88\uD638\xB7\uC870\uAC74\xB7\uC2DD\xB7\uD589\uB82C)\uC744 \uBCF8\uB2E4 \u2014 \uBB38\uD56D \uD45C\uC5D0 \uBC88\uD638\uAC00 \uC788\uC73C\uBA74 look \xAB<\uC790\uB9AC> \uBB38\uD56D <\uBC88\uD638>\xBB(\uADF8 \uBB38\uD56D \uB369\uC774\uB9CC \xB7 \uCABD \uD1B5\uC9F8 \uB9D0\uACE0), \uC5C6\uC73C\uBA74 \xAB<\uC790\uB9AC> page N y0-y1\xBB. \uD544\uAE30\uC758 \uBB38\uD56D \uBC88\uD638\xB7\uAE30\uD638\xB7\uC870\uAC74\uC774 \uBB38\uC81C\uC9C0\uC640 \uB2E4\uB974\uBA74 \uC9DA\uB294\uB2E4. \uBB38\uC81C\uC9C0\uB85C \uD655\uC778\uD55C \uBB38\uD56D\uC5D0\uB294 \xAB\uC6D0\uBB38\uC774 \uC5C6\uC5B4 \uD655\uC778 \uBABB \uD568\xBB\uC744 \uC4F0\uC9C0 \uC54A\uB294\uB2E4. \uBC14\uD0D5 PDF \uB294 \uAC15\uC758 \uC790\uB8CC \u2014 \uAC15\uC758 \uD544\uAE30\uC5D0\uC11C \uBE60\uC9C4 \uAC83\xB7\uC798\uBABB \uC62E\uAE34 \uAC83\uC744 \uBCFC \uB54C \uC4F4\uB2E4.";
var NEW_INK_RULE = "\uD544\uAE30 \xAB\uBD10\uC918\xBB(\uC0C8\uB85C \uC4F4 \uBD80\uBD84 \uBCF4\uAE30)\uBA74 \uBA38\uB9AC\uC758 \xAB\uD654\uBA74 \uBC16 \uC0C8 \uD68D\xBB(\uCABD\xB7\uD68D \uC218)\uC774 \uAC00\uB9AC\uD0A4\uB294 \uACF3\uB3C4 \uD310\uC815 \uC804\uC5D0 \uB2E4 \uBCF8\uB2E4(look down \uB610\uB294 page N) \u2014 \uC0C8 \uD68D\uC740 \uC77C\uBD80\uB9CC \uBCF4\uACE0 \uB05D\uB0B4\uC9C0 \uC54A\uB294\uB2E4. \uD654\uBA74 \uB9E8 \uC704\uAC00 \uBB38\uD56D \uBC88\uD638 \uC5C6\uC774 \uC2DC\uC791\uD558\uBA74 up \uC73C\uB85C \uADF8 \uBB38\uD56D \uBA38\uB9AC\uBD80\uD130.";
var Hold = class _Hold {
  constructor(emit) {
    this.emit = emit;
    this.buf = "";
    this.open = true;
    this.dropped = [];
  }
  static {
    // 이 메시지에서 아직 쥐는 중
    this.HOLD = 400;
  }
  start() {
    this.flush();
    this.open = true;
  }
  push(s) {
    if (!this.open) return this.emit(s);
    this.buf += s;
    if (this.buf.length > _Hold.HOLD) this.flush();
  }
  tool() {
    if (this.open && this.buf.trim()) this.dropped.push(this.buf.trim());
    this.buf = "";
    this.open = true;
  }
  flush() {
    if (this.buf) this.emit(this.buf);
    this.buf = "";
    this.open = false;
  }
};

// src/tools/notechat.ts
var KINDS = ["\uD480\uC774", "\uAC15\uC758 \uD544\uAE30", "\uADF8\uB9BC", "\uC2E4\uD5D8 \uAE30\uB85D", "\uBA54\uBAA8"];
var wantsAll = (t) => /전체|처음부터|끝까지|모두|모든\s*(문항|문제|쪽)|다\s*(봐|보고|채점|옮겨|확인|검토|풀었)/.test(t);
var STUDY_CHIPS = /* @__PURE__ */ new Set(["\uBD10\uC918", "\uAC80\uC0B0", "\uD480\uC774", "\uD78C\uD2B8\uB9CC", "\uB2E4\uC74C \uB2E8\uACC4", "\uACC4\uC0B0 \uAC80\uC0AC"]);
var wantsStudy = (chip, text, kind) => STUDY_CHIPS.has(chip) ? chip !== "\uBD10\uC918" || kind === "\uD480\uC774" : /채점|맞(아|나|니|는지|았)|검산|검토|틀린|풀어|풀이|다\s*풀었/.test(text);
var STUDY_MODEL = "sonnet";
var ALL_MAX = 40;
var READ_TOOLS = /* @__PURE__ */ new Set(["Read", "Grep", "Glob"]);
var GRADE = "\uCC44\uC810\uC740 \uC9C0\uCE68\uC758 \xABstudy-helper grade\xBB \uC808\uCC28\xB7\uCD9C\uB825 \uADF8\uB300\uB85C(\uC904\uC774\uC9C0 \uC54A\uC74C).";
var SOLVE = "\uD480\uC774\uB294 \uC9C0\uCE68\uC758 \xABstudy-helper solve\xBB \uC808\uCC28\xB7\uCD9C\uB825 \uADF8\uB300\uB85C(\uC904\uC774\uC9C0 \uC54A\uC74C).";
var STUDY_SKILLS = ["grade", "solve"];
var studyDir = null;
var setStudyDir = (d) => void (studyDir = d);
function skillBody(vault, name) {
  try {
    const t = import_fs3.default.readFileSync(studyDir ? import_path4.default.join(studyDir, name, "SKILL.md") : import_path4.default.join(vault, ".claude", "skills", "study-helper", "skills", name, "SKILL.md"), "utf8");
    return t.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, "").trim();
  } catch {
    return null;
  }
}
var STUDY_ADAPT = [
  "\uD0ED \uACC1\uCC3D\uC5D0\uC11C \uC774 \uB450 \uC2A4\uD0AC\uC744 \uC4F8 \uB54C \uB3C4\uAD6C \uB300\uC751 \u2014 \uC808\uCC28\xB7\uCD9C\uB825\xB7\uAC80\uC99D\xB7\uAE30\uB85D\uC740 \uC2A4\uD0AC \uADF8\uB300\uB85C\uC774\uACE0, \uD0ED \uACC1\uCC3D\uC774\uB77C\uACE0 \uC904\uC774\uC9C0 \uC54A\uB294\uB2E4:",
  "- \uB2F5\uC548\xB7\uD544\uAE30 = \uBD99\uC740 \uADF8\uB9BC\uACFC look \uB3C4\uAD6C(\uC804\uC0AC\uD558\uC9C0 \uC54A\uC74C). \xAB\uD06C\uB86D\uD574\uC11C \uB2E4\uC2DC \uBCF4\uAE30\xBB = look \uC73C\uB85C \uC881\uC740 \uBC94\uC704\uB97C \uB2E4\uC2DC(`page N y0-y1` \xB7 \uC881\uD790\uC218\uB85D \uD06C\uAC8C \uADF8\uB824\uC9D0) \xB7 pdftoppm\xB7PIL \uC740 \uC4F0\uC9C0 \uC54A\uB294\uB2E4.",
  "- symcheck.py = sym \uB3C4\uAD6C(\uAC19\uC740 \uB300\uBCF8 \xB7 op eq|simp|solve|num|rank|null|col|rref|det|inv|eig \xB7 exprs \xB7 ^ = \uAC70\uB4ED\uC81C\uACF1 \xB7 \uD589\uB82C [[1,2],[3,4]]).",
  "- \uBB38\uC81C \uC6D0\uBB38 = \uBA38\uB9AC\uC758 \uBB38\uC81C\uC9C0 \uCE78(\uC9DD \uBB38\uC81C\xB7\uBC14\uD0D5 PDF\xB7\uC606 \uCE78 PDF)\uC744 look \xB7 \uC5C6\uC73C\uBA74 \uC2A4\uD0AC\uB300\uB85C \uC694\uCCAD.",
  "- \uC790\uB9AC = \uD544\uAE30 \uADF8\uB9BC \uC67C\uCABD L\uBC88\uD638(\xABL7\xBB, \uC5EC\uB7EC \uC904 \xABL7\u2013L9\xBB) \xB7 \uBB38\uD56D\uC740 \uD544\uAE30\uC5D0 \uC4F4 \uBC88\uD638 \uADF8\uB300\uB85C \xB7 \uD310\uC815\uD45C \uCCAB \uCE78\uC740 \uBB38\uD56D \uBC88\uD638.",
  "- \uD55C \uC904 \uAE30\uB85D = \uD30C\uC77C\uC744 \uC9C1\uC811 \uC4F0\uC9C0 \uC54A\uACE0 \uB2F5 \uB9E8 \uB05D\uC5D0 \u3014\uAE30\uB85D: \uACFC\uBAA9-<\uCF54\uB4DC> | <\uBB38\uD56D> | <\uD55C \uC904> | #<\uC624\uAC1C\uB150 \uD0DC\uADF8>\u3015 \uD55C \uC904\uC529(\uC2E4\uD589\uAE30\uAC00 append \xB7 \uD30C\uC77C\uC774 \uC5C6\uC73C\uBA74 \uD504\uB860\uD2B8\uB9E4\uD130\uC640 \uD568\uAED8 \uB9CC\uB4E6 \xB7 \uBA38\uB9AC \u2464 \uACFC\uBAA9 \uD30C\uC77C \uC774\uB984\uC774 \uB9DE\uC73C\uBA74 \uADF8 \uC774\uB984). \uD654\uBA74\uC5D4 \uC548 \uBCF4\uC778\uB2E4."
].join("\n");
function studyRule(vault) {
  const parts = STUDY_SKILLS.map((n) => [n, skillBody(vault, n)]).filter(([, b]) => b);
  if (!parts.length) return "";
  return [
    "\uCC44\uC810(\uB2E4 \uC4F4 \uB2F5\uC548 \uD655\uC778 \u2014 \uBD10\uC918\xB7\uAC80\uC0B0\xB7\xAB\uB9DE\uC544?\xBB\xB7\xAB\uCC44\uC810\uD574\uC918\xBB)\uC740 \uC544\uB798 study-helper grade, \uB2F5\uC548 \uC5C6\uB294 \uD480\uC774 \uBD80\uD0C1(\uD480\uC774\xB7\xAB\uD480\uC5B4\uC918\xBB\xB7\xAB\uC5B4\uB5BB\uAC8C \uD480\uC5B4?\xBB)\uC740 \uC544\uB798 study-helper solve \uB97C \uADF8\uB300\uB85C \uB530\uB978\uB2E4.",
    STUDY_ADAPT,
    ...parts.map(([n, b]) => `===== study-helper ${n} (\uBCFC\uD2B8 .claude/skills/study-helper/skills/${n}/SKILL.md) =====
${b}`)
  ].join("\n\n");
}
var LOOK = ["\uBD10\uC918", "since", "\uC0C8\uB85C \uC4F4 \uBD80\uBD84\uC744 \uBD10 \uC918. \uD480\uC774(\uBB38\uD56D\xB7\uC2DD)\uBA74 \uCC44\uC810 \u2014 " + GRADE + " \uADF8 \uBC16(\uAC15\uC758 \uD544\uAE30\xB7\uADF8\uB9BC\xB7\uC2E4\uD5D8 \uAE30\uB85D\xB7\uBA54\uBAA8)\uC774\uBA74 \uD2C0\uB838\uAC70\uB098 \uBE60\uC9C4 \uAC83\xB7\uACE0\uCE60 \uACF3\uC744 L\uBC88\uD638\uC640 \uD568\uAED8 \uC9E7\uAC8C."];
var CHIPS = {
  \uD480\uC774: [
    LOOK,
    ["\uD78C\uD2B8\uB9CC", "since", "\uB9C9\uD78C(\uB610\uB294 \uB9C8\uC9C0\uB9C9\uC73C\uB85C \uC4F4) \uBB38\uD56D\uC758 \uB2E4\uC74C \uD55C \uAC78\uC74C \uD78C\uD2B8\uB9CC \uD55C\uB450 \uC904. \uC2DD\uC758 \uACB0\uACFC\xB7\uB2F5\uC740 \uC4F0\uC9C0 \uC54A\uB294\uB2E4. \uC55E\uC11C \uD78C\uD2B8\uB97C \uC92C\uC73C\uBA74 \uAC19\uC740 \uB9D0\uC744 \uB418\uD480\uC774\uD558\uC9C0 \uC54A\uB294\uB2E4."],
    ["\uB2E4\uC74C \uB2E8\uACC4", "since", "\uADF8 \uBB38\uD56D\uC5D0\uC11C \uB2E4\uC74C \uC904 \uD558\uB098\uB97C \uC5B4\uB5BB\uAC8C \uC4F0\uBA74 \uB418\uB294\uC9C0 \u2014 \uC2DD\uC758 \uAF34\uAE4C\uC9C0(\uACB0\uACFC \uAC12\uC740 \uB9D0\uACE0). \uC55E\uC11C \uD78C\uD2B8\uB97C \uC92C\uC73C\uBA74 \uD55C \uCE78 \uB354 \uAD6C\uCCB4\uC801\uC73C\uB85C."],
    ["\uD480\uC774", "since", "\uB9C9\uD78C(\uB610\uB294 \uB9C8\uC9C0\uB9C9\uC73C\uB85C \uC4F4) \uBB38\uD56D\uC744 \uCC98\uC74C\uBD80\uD130 \uB05D\uAE4C\uC9C0 \uD480\uC774 \u2014 " + SOLVE],
    ["\uAC80\uC0B0", "since", "\uC0C8\uB85C \uC4F4 \uC2DD\xB7\uB2F5\uC744 \uCC44\uC810 \u2014 " + GRADE]
  ],
  "\uAC15\uC758 \uD544\uAE30": [
    LOOK,
    ["\uC815\uB9AC", "view", "\uBCF4\uC774\uB294 \uD544\uAE30\uB97C \uD575\uC2EC 5\uC904 \uC774\uB0B4\uB85C \uC815\uB9AC. \uC904\uB9C8\uB2E4 \uB05D\uC5D0 \uADFC\uAC70 L\uBC88\uD638. \uBC14\uD0D5 PDF \uAC00 \uC788\uC73C\uBA74 \uADF8 \uCABD \uB0B4\uC6A9\uACFC \uC774\uC5B4\uC11C."],
    ["\uBE60\uC9C4 \uAC83", "view", "\uC774 \uD544\uAE30(\uBC14\uD0D5\xB7\uC606 \uBB38\uC11C\uAC00 \uC788\uC73C\uBA74 \uADF8 \uCABD\uACFC \uACAC\uC918)\uC5D0\uC11C \uBE60\uC84C\uAC70\uB098 \uC798\uBABB \uC801\uC740 \uAC1C\uB150\uC744 L\uBC88\uD638\uC640 \uD568\uAED8. \uC5C6\uC73C\uBA74 \uC5C6\uB2E4\uACE0."],
    ["\uBB38\uC81C \uB9CC\uB4E4\uAE30", "view", "\uC774 \uD544\uAE30\uB9CC\uC73C\uB85C \uD480 \uC218 \uC788\uB294 \uD655\uC778 \uBB38\uC81C 3\uAC1C(\uC26C\uC6C0\u2192\uC5B4\uB824\uC6C0). \uB2F5\uC740 \uB9E8 \uB05D \xAB\uB2F5:\xBB \uC544\uB798\uC5D0 \uC9E7\uAC8C."],
    ["\uCE74\uB4DC\uB85C", "view", "\uC554\uAE30 \uCE74\uB4DC 5\uC7A5 \u2014 \uC904\uB9C8\uB2E4 \xAB\uC55E :: \uB4A4\xBB \uAF34(\uB4A4\uB294 \uD55C \uC904)."],
    ["\uC62E\uACA8 \uC801\uAE30", "view", "\uC190\uAE00\uC528\uB97C \uAE00\uB85C \uC62E\uACA8 \uC801\uAE30: \uAE00\uC740 \uADF8\uB300\uB85C, \uC218\uC2DD\uC740 $$\u2026$$(LaTeX), \uD45C\uB294 md \uD45C. \uC904\uB9C8\uB2E4 \uC55E\uC5D0 L\uBC88\uD638. \uC77D\uAE30 \uC560\uB9E4\uD55C \uACF3\uC740 [?]."]
  ],
  \uADF8\uB9BC: [
    LOOK,
    ["\uC124\uBA85\uD574\uC918", "view", "\uADF8\uB9BC\xB7\uB3C4\uD574\uAC00 \uBB34\uC5C7\uC744 \uB098\uD0C0\uB0B4\uB294\uC9C0(\uC694\uC18C\uC640 \uAD00\uACC4\xB7\uD654\uC0B4\uD45C \uB73B) \uC9E7\uAC8C. L\uBC88\uD638\uB85C \uC790\uB9AC\uB97C \uC9DA\uB294\uB2E4."],
    ["\uACE0\uCE60 \uACF3", "view", "\uADF8\uB9BC\uC5D0\uC11C \uD2C0\uB838\uAC70\uB098 \uBE60\uC9C4 \uAC83(\uBC29\uD5A5\xB7\uC774\uB984\xB7\uD06C\uAE30 \uAD00\uACC4 \uB4F1)\uC744 L\uBC88\uD638\uC640 \uD568\uAED8."],
    ["\uAE00\uB85C \uB2E4\uC2DC", "view", "\uC774 \uADF8\uB9BC\uC744 Mermaid(\uAC00\uB2A5\uD558\uBA74) \uB610\uB294 \uAE00 \uBAA9\uB85D\uC73C\uB85C \uB2E4\uC2DC \uADF8\uB824 \uC918."],
    ["\uC62E\uACA8 \uC801\uAE30", "view", "\uADF8\uB9BC \uC548 \uAE00\uC790\xB7\uC218\uC2DD\uC744 \uC62E\uACA8 \uC801\uAE30(L\uBC88\uD638 \xB7 \uC218\uC2DD\uC740 $$\u2026$$)."]
  ],
  "\uC2E4\uD5D8 \uAE30\uB85D": [
    LOOK,
    ["\uD45C\uB85C", "view", "\uC801\uC740 \uAC12\uC744 md \uD45C\uB85C(\uC591 \xB7 \uAC12 \xB7 \uB2E8\uC704 \xB7 L\uBC88\uD638)."],
    ["\uB2E8\uC704\xB7\uC720\uD6A8\uC22B\uC790", "view", "\uB2E8\uC704 \uBE60\uC9D0\xB7\uC720\uD6A8\uC22B\uC790\xB7\uC790\uB9BF\uC218 \uBB38\uC81C\uB97C L\uBC88\uD638\uC640 \uD568\uAED8."],
    ["\uACC4\uC0B0 \uAC80\uC0AC", "view", `\uC801\uC740 \uACC4\uC0B0\uC744 \uB2E4\uC2DC \uD574 \uBCF4\uACE0 \uB2E4\uB974\uBA74 \uC9DA\uB294\uB2E4(sym \uB3C4\uAD6C num/eq \uB85C \uAC80\uC0B0 \xB7 \uD55C \uC904\uC529) \u2014 ${GRADE}`],
    ["\uC62E\uACA8 \uC801\uAE30", "view", "\uC190\uAE00\uC528\uB97C \uAE00\uB85C \uC62E\uACA8 \uC801\uAE30(\uC218\uC2DD $$\u2026$$ \xB7 \uD45C\uB294 md \uD45C \xB7 L\uBC88\uD638)."]
  ],
  \uBA54\uBAA8: [
    LOOK,
    ["\uC62E\uACA8 \uC801\uAE30", "view", "\uC190\uAE00\uC528\uB97C \uAE00\uB85C \uC62E\uACA8 \uC801\uAE30: \uAE00\uC740 \uADF8\uB300\uB85C, \uC218\uC2DD\uC740 $$\u2026$$, \uD45C\uB294 md \uD45C. \uC904\uB9C8\uB2E4 \uC55E\uC5D0 L\uBC88\uD638. \uC77D\uAE30 \uC560\uB9E4\uD55C \uACF3\uC740 [?]."],
    ["\uD560 \uC77C \uBF51\uAE30", "view", "\uBA54\uBAA8\uC5D0\uC11C \uD560 \uC77C\uB9CC \xAB- [ ] \u2026\xBB \uBAA9\uB85D\uC73C\uB85C(\uB0A0\uC9DC\uAC00 \uC788\uC73C\uBA74 \uD568\uAED8)."],
    ["\uC815\uB9AC", "view", "\uBCF4\uC774\uB294 \uBA54\uBAA8\uB97C \uD575\uC2EC \uBA87 \uC904\uB85C \uC815\uB9AC(\uADFC\uAC70 L\uBC88\uD638)."]
  ]
};
var WHY = ["\uC65C?", "none", "\uBC29\uAE08 \uC9DA\uC740 \uAC83\uC758 \uAE4C\uB2ED\uC744 \uC26C\uC6B4 \uB9D0\uB85C \uD480\uC5B4 \uC918. \uC815\uB2F5\uC744 \uD1B5\uC9F8\uB85C \uC8FC\uC9C0\uB294 \uC54A\uB294\uB2E4."];
function chipOf(kind, name) {
  if (name === "\uC65C?") return WHY;
  return CHIPS[kind]?.find((c) => c[0] === name) ?? Object.values(CHIPS).flat().find((c) => c[0] === name) ?? null;
}
var NOTE_RULE = [
  "\uC5EC\uAE30\uB294 \uD0ED\uC5D0\uC11C \uC190\uC73C\uB85C \uC4F0\uB294 \uD544\uAE30\uB97C \uC606 \uACC1\uCC3D\uC5D0\uC11C \uAC19\uC774 \uBCF4\uB294 \uB300\uD654\uB2E4(\uBCFC\uD2B8 \uD074\uB85C\uB4DC\uC640 \uAC19\uC740 \uB300\uD654 \xB7 \uBCFC\uD2B8 \uBB38\uC11C\uB3C4 \uC77D\uC744 \uC218 \uC788\uC74C).",
  `\uB2F5\uC758 \uCCAB \uC904\uC5D0\uB294 \u3014\uC885\uB958: ${KINDS.join("|")}\u3015 \uD558\uB098\uB9CC \uC4F4\uB2E4(\uADF8\uB9BC\uC744 \uBCF4\uACE0 \uAC00\uB9B0\uB2E4 \xB7 \uBA38\uB9AC\uC758 \uC9D0\uC791\uC774 \uB9DE\uC73C\uBA74 \uADF8\uB300\uB85C). \uADF8 \uC904\uC740 \uD654\uBA74\uC5D0 \uC548 \uBCF4\uC778\uB2E4.`,
  "\uC904\uC744 \uC9DA\uC744 \uB54C\uB294 \uADF8\uB9BC \uC67C\uCABD \uC904 \uBC88\uD638\uB97C \xABL7\xBB \uAF34\uB85C \uC4F4\uB2E4(\uC5EC\uB7EC \uC904\uC740 \xABL7\u2013L9\xBB). \uBB38\uD56D\uC740 \uD544\uAE30\uC5D0 \uC4F4 \uBC88\uD638 \uADF8\uB300\uB85C(\xAB15.\xBB, \xAB(b)\xBB).",
  "\uD310\uB2E8\uC740 \uB0B4\uAC00 \uC62E\uACA8 \uC77D\uC740 \uAE00\uC774 \uC544\uB2C8\uB77C \uADF8\uB9BC\uC744 \uADFC\uAC70\uB85C \uD55C\uB2E4. \uC190\uAE00\uC528\uAC00 \uC560\uB9E4\uD558\uBA74 \uD310\uC815\uD558\uC9C0 \uB9D0\uACE0 \xAB\uC77D\uAE30 \uC560\uB9E4 L5: \u2018\u2026\u2019 \uC778\uC9C0 \u2018\u2026\u2019 \uC778\uC9C0\xBB. \uC560\uB9E4\uD55C \uAE00\uC790\uB97C \uBB38\uC81C \uC6D0\uBB38 \uC5C6\uC774 \uC5B4\uB290 \uD55C\uCABD\uC774 \uB9DE\uB2E4\uACE0 \uB2E8\uC815\uD558\uC9C0 \uC54A\uB294\uB2E4 \u2014 \uAC19\uC740 \uC904\xB7\uC55E\uB4A4 \uC2DD\uC774 \uC11C\uB85C \uB9DE\uB294 \uC77D\uAE30\uAC00 \uC788\uC73C\uBA74 \uADF8 \uC77D\uAE30\uB97C \uB530\uB978\uB2E4.",
  "\uBD80\uD0C1\uC774 \xAB\uD78C\uD2B8\uB9CC\xBB\xB7\xAB\uB2E4\uC74C \uB2E8\uACC4\xBB\uBA74 \uC815\uB2F5\uC744 \uD1B5\uC9F8\uB85C \uC8FC\uC9C0 \uC54A\uB294\uB2E4. \uC218\uC2DD\uC740 \uC720\uB2C8\uCF54\uB4DC(x\xB2, \u2260, \u222B)\uB85C \uC4F0\uACE0 \uAE38\uBA74 $$\u2026$$.",
  "\uCC44\uC810\xB7\uD480\uC774\uB294 study-helper grade\xB7solve \uC758 \uCD9C\uB825 \uADF8\uB300\uB85C(\uD0ED \uACC1\uCC3D\uC774\uB77C\uACE0 \uC904\uC774\uC9C0 \uC54A\uC74C) \xB7 \uADF8 \uBC16\uC758 \uBD80\uD0C1\uC740 \uD0ED \uACC1\uCC3D\uC774 \uC881\uC73C\uB2C8 \uC9E7\uAC8C.",
  "\uD544\uAE30 \uCE78\uC758 \uCCAB \uADF8\uB9BC\uC740 \uC0AC\uC6A9\uC790\uAC00 \uC9C0\uAE08 \uD0ED\uC5D0\uC11C \uBCF4\uB294 \uD654\uBA74\uBFD0\uC774\uB2E4(\uBA38\uB9AC \xAB\uBCF4\uB294 \uD654\uBA74\xBB\uC758 \uD544\uAE30 \uCE78 \xB7 \uC774\uBBF8 \uBD04). \uD654\uBA74 \uB9E8 \uC704\uAC00 \uBB38\uD56D \uBC88\uD638 \uC5C6\uC774 \uC55E \uBB38\uD56D\uC758 \uC911\uAC04\xB7\uACB0\uB860\uC73C\uB85C \uC2DC\uC791\uD558\uBA74 \uADF8 \uBB38\uD56D\uC744 \uAC74\uB108\uB6F0\uC9C0 \uB9D0\uACE0 \uBA3C\uC800 look up \uC73C\uB85C \uBA38\uB9AC(\uBC88\uD638\xB7\uC870\uAC74\xB7\uC815\uC758)\uB97C \uBCF8 \uB4A4 \uD310\uC815\uD55C\uB2E4 \xB7 \uB354 \uBCF8 \uACF3\uB3C4 L\uBC88\uD638\uB85C \uC9DA\uB294\uB2E4(\uBC88\uD638\uB294 \uC774\uC5B4\uC9D0)."
].join("\n");
function args(argv) {
  const o = {};
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (!k.startsWith("--")) continue;
    const v = argv[i + 1];
    if (v === void 0 || v.startsWith("--")) o[k.slice(2)] = true;
    else o[k.slice(2)] = v, i++;
  }
  return o;
}
var out = (o) => process.stdout.write(JSON.stringify(o) + "\n");
function whoOf(vault) {
  try {
    return meOf(import_fs3.default.readFileSync(import_path4.default.join(vault, "2_\uC9C0\uC2DD", "profile.md"), "utf8"));
  } catch {
    return ME_NONE;
  }
}
function askCore(vault, note) {
  let t = "";
  try {
    t = import_fs3.default.readFileSync(import_path4.default.join(vault, "3_\uC2DC\uC2A4\uD15C", "vault-chat", "\uC0C1\uC2DC.md"), "utf8").trim();
  } catch {
  }
  t ||= "\uBCFC\uD2B8\uC758 \uBB38\uC11C\uB97C \uBCF4\uB2E4\uAC00 \uBC14\uB85C \uBB3B\uB294 \uACF3\uC774\uB2E4. \uB2F5\uBD80\uD130 \uC9E7\uAC8C. \uC804\uC81C\uAC00 \uD2C0\uB838\uC73C\uBA74 \uAE4C\uB2ED\uACFC \uD568\uAED8 \uB9D0\uD55C\uB2E4. \uC5EC\uAE30\uC11C\uB294 \uC77D\uAE30\uB9CC \uD55C\uB2E4. \uC81C\uC791\uC744 \uBD80\uD0C1\uBC1B\uC73C\uBA74 work \uB3C4\uAD6C\uB97C \uBD80\uB978\uB2E4.";
  t += `

${SCOPE_RULE}`;
  if (note) t += `

${NOTE_RULE}`;
  const st = note ? studyRule(vault) : "";
  if (st) t += `

${st}`;
  const who = whoOf(vault);
  if (who !== ME_NONE) t += `

\uC0AC\uC6A9\uC790 \uD638\uCE6D: ${who}`;
  return t;
}
function py3(py, vault, a) {
  const full = [import_path4.default.join(vault, "3_\uC2DC\uC2A4\uD15C", "inkrender.py"), ...a];
  return (0, import_child_process4.execFileSync)(py === "py" ? "py" : py, py === "py" ? ["-3", ...full] : full, { cwd: vault, timeout: 12e4, windowsHide: true, encoding: "utf8" });
}
var lastJson2 = (r) => {
  const l = r.trim().split("\n").filter((x) => x.startsWith("{")).at(-1);
  return l ? JSON.parse(l) : null;
};
function guessKind(py, vault, note) {
  const j = lastJson2(py3(py, vault, [import_path4.default.join(vault, note), "--kind"]));
  return j && KINDS.includes(j.kind) ? j : { kind: "\uBA54\uBAA8", why: "\uC9D0\uC791 \uBABB \uD568", bg: null, ref: null };
}
function shotsOf(py, vault, note, src, view, seen) {
  if (src === "none") return [];
  const a = [import_path4.default.join(vault, note), "--since", "--json"];
  if (seen) a.push("--seen", seen);
  if (src === "view" && view) a.push("--view", view);
  const j = lastJson2(py3(py, vault, a));
  let s = j?.shots ?? [];
  if (!s.length && src === "since" && view) s = shotsOf(py, vault, note, "view", view, seen);
  return s;
}
function markSeen(py, vault, note, seen) {
  const a = [import_path4.default.join(vault, note), "--mark"];
  if (seen) a.push("--seen", seen);
  py3(py, vault, a);
}
function markSegs(py, vault, note, segs, seen) {
  if (!segs.length) return;
  const a = [import_path4.default.join(vault, note), "--screen", segsSpec(segs), "--mark"];
  if (seen) a.push("--seen", seen);
  py3(py, vault, a);
}
function screenHead(sc, split) {
  const where = sc.segs.map(([p, a, b]) => `${p}\uCABD y ${Math.round(a)}~${Math.round(b)}/${Math.round(sc.dims[p - 1][1])}`).join(" + ");
  const tone = split ? sc.first ? "\uBAA8\uB450 \uAC80\uC815(\uCC98\uC74C \uBD04)" : "\uAC80\uC815 = \uC9C0\uB09C\uBC88 \uB4A4 \uC0C8\uB85C \uC4F4 \uD68D(\uBA3C\uC800 \uBCFC \uAC83) \xB7 \uD68C\uC0C9 = \uC774\uBBF8 \uBCF8 \uD68D(\uB9E5\uB77D)" : "\uBCF4\uC774\uB294 \uD68D \uC804\uBD80";
  const s0 = sc.shots[0], sl = sc.shots[sc.shots.length - 1];
  const off = Object.entries(sc.new_off).map(([p, c]) => `${p}\uCABD ${c}\uD68D`).join(" \xB7 ");
  const rest = [
    s0 ? `\uC704 ${s0.above ?? 0}\uD68D${s0.cut_top ? "(\uC704 \uB05D \uC904 \uC798\uB9BC)" : ""}` : "",
    sl ? `\uC544\uB798 ${sl.below ?? 0}\uD68D${sl.cut_bottom ? "(\uC544\uB798 \uB05D \uC904 \uC798\uB9BC)" : ""}` : "",
    off ? `\uD654\uBA74 \uBC16 \uC0C8 \uD68D: ${off}` : ""
  ].filter(Boolean).join(" \xB7 ");
  const pic = sc.shots.length ? `\u2461 \uADF8\uB9BC ${sc.shots.length}\uC7A5 = \uC9C0\uAE08 \uD0ED \uD654\uBA74(${where} \xB7 ${tone})` : `\u2461 \uC9C0\uAE08 \uD0ED \uD654\uBA74(${where})\uC5D0 \uD68D \uC5C6\uC74C`;
  return `${pic}
   \uD654\uBA74 \uBC16(\uC790\uB9AC\uB9CC \xB7 \uD544\uC694\uD560 \uB54C\uB9CC look): \uCABD ${sc.dims.length}\uAC1C \xB7 ${rest || "\uC5C6\uC74C"}`;
}
function subjects(dir) {
  try {
    return import_fs3.default.readdirSync(dir).filter((f) => /^과목-.+\.md$/.test(f)).map((f) => {
      const head = import_fs3.default.readFileSync(import_path4.default.join(dir, f), "utf8").slice(0, 600);
      const tags = (/^tags:\s*\[([^\]]*)\]/m.exec(head)?.[1] ?? "").split(",").map((x) => x.trim()).filter((x) => x && !/study-helper|채점|학업|기록/.test(x));
      return f.slice(0, -3) + (tags.length ? `(${tags.join(", ")})` : "");
    });
  } catch {
    return [];
  }
}
function userText(o) {
  const { note, shots, chip, text, kind, subj, scr, panes = [], doc } = o;
  const scrn = renderPanes(panes.map((p) => scr && p.path === note ? { ...p, shown: true } : p), "\u2465");
  if (!note) {
    const cur = panes.find((p) => p.cur) ?? panes[0];
    if (!cur) return text;
    return [`[\uB9E5\uB77D \u2014 \uD0ED\uC5D0\uC11C \uBCF4\uB294 \uD654\uBA74 \xB7 \uACBD\uB85C\uB294 \uC791\uC5C5 \uD3F4\uB354(\uC774 \uBCFC\uD2B8) \uC548]`, `\u2460 \uBCF4\uB294 \uD30C\uC77C: ${cur.path}`, scrn.replace(/^⑥/, "\u2461")].filter(Boolean).join("\n") + "\n\n" + text;
  }
  const head = [`[\uB9E5\uB77D \u2014 \uD0ED \uB178\uD2B8 \uB300\uD654 \xB7 \uACBD\uB85C\uB294 \uC791\uC5C5 \uD3F4\uB354(\uC774 \uBCFC\uD2B8) \uC548 \xB7 \uADF8\uB9BC \uC67C\uCABD L\uBC88\uD638 = \uC904]`, `\u2460 \uBCF4\uB294 \uD30C\uC77C: ${note}`];
  if (scrn && panes.length > 1) head.push(scrn);
  if (scr) head.push(scr);
  else if (shots.length) head.push(`\u2461 \uADF8\uB9BC ${shots.length}\uC7A5(${shots.map((s) => s.page).join("\xB7")}\uCABD \xB7 \uB9E8 \uC704 \uB760\uAC00 \uAF34\uC744 \uB9D0\uD568 \xB7 \uAC80\uC815 = \uBCFC \uBD80\uBD84 \xB7 \uD68C\uC0C9 = \uC55E \uB9E5\uB77D \xB7 \uC605\uC740 \uBE68\uAC15 = \uC9C0\uC6B4 \uAC83)`);
  if (kind) head.push(`\u2462 \uC885\uB958 \uC9D0\uC791: ${kind.kind}(${kind.why})${kind.ref ? ` \xB7 \uC606 \uBB38\uC11C = ${kind.ref}(\uD544\uC694\uD558\uBA74 Read)` : ""}${kind.bg ? ` \xB7 \uBC14\uD0D5 PDF = ${kind.bg}` : ""}`);
  if (doc) head.push(doc);
  if (chip) head.push(`\u2463 \uBD80\uD0C1(${chip[0]}): ${chip[2]}`);
  if (subj?.length) head.push(`\u2464 \uACFC\uBAA9 \uD30C\uC77C(\uCC44\uC810\xB7\uD480\uC774 \uAE30\uB85D \uC790\uB9AC): ${subj.join(" \xB7 ")}`);
  return head.join("\n") + "\n\n" + (text || chip?.[0] || "\uBD10\uC918");
}
var TagFilter = class {
  constructor(emit) {
    this.emit = emit;
    this.line = "";
    this.held = false;
    this.tags = [];
    this.text = "";
  }
  push(s) {
    for (const ch of s) {
      if (this.line === "" && ch === "\u3014") this.held = true;
      this.line += ch;
      if (!this.held && !(ch === "\n" && this.text === "")) this.out(ch);
      if (ch === "\n") this.endLine();
    }
  }
  out(s) {
    this.text += s;
    this.emit(s);
  }
  endLine() {
    const l = this.line.trim();
    if (this.held) {
      if (/^〔[^〕]*〕$/.test(l)) this.tags.push(l.slice(1, -1));
      else this.out(this.line);
    }
    this.line = "";
    this.held = false;
  }
  flush() {
    if (this.held) this.endLine();
    this.line = "";
  }
};
function appendRec(dir, tag, today2) {
  const m = /^기록:\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(#\S.*)$/.exec(tag);
  if (!m) return null;
  const name = m[1].replace(/\.md$/, "").replace(/\(.*\)$/, "").trim();
  if (!/^과목-[^/\\]+$/.test(name)) return null;
  const file = import_path4.default.join(dir, name + ".md");
  if (!import_fs3.default.existsSync(file)) {
    import_fs3.default.mkdirSync(dir, { recursive: true });
    const subj = name.slice(3);
    import_fs3.default.writeFileSync(file, `---
type: procedural
title: ${subj} \u2014 \uCC44\uC810\xB7\uD480\uC774 \uAE30\uB85D
created: ${today2}
updated: ${today2}
tags: [\uD559\uC5C5, study-helper, \uCC44\uC810\uAE30\uB85D]
links: ["[[\uC678\uBD80\uB1CC-study-helper-\uBAA8\uB4C8]]"]
status: active
source: session
---
# ${subj} \u2014 \uCC44\uC810\xB7\uD480\uC774 \uAE30\uB85D

`);
  }
  const body = `${m[2]} | ${m[3]} | ${m[4]}`;
  const cur = import_fs3.default.readFileSync(file, "utf8");
  if (cur.includes(body)) return null;
  const line = `${today2} | ${body}`;
  import_fs3.default.appendFileSync(file, (cur.endsWith("\n") ? "" : "\n") + line + "\n");
  return { file: name, line };
}
var WORK_TOOL = `mcp__${VAULT_SERVER}__${WORK_NAME}`;
function pcWork(vault) {
  try {
    const d = JSON.parse(import_fs3.default.readFileSync(import_path4.default.join(vault, ".obsidian", "plugins", "brain-base", "data.json"), "utf8"));
    return { permissionMode: typeof d.permissionMode === "string" ? d.permissionMode : void 0, leanEngine: typeof d.leanEngine === "boolean" ? d.leanEngine : void 0 };
  } catch {
    return {};
  }
}
function allowTool(name, _input, work = false) {
  if (READ_TOOLS.has(name) || name === LOOK_TOOL || name === SYM_TOOL) return null;
  if (work) return "\uD0ED \uACC1\uCC3D\uC5D4 \uB3C4\uAD6C \uC2B9\uC778 \uCE74\uB4DC\uAC00 \uC5C6\uB2E4 \u2014 \uC774 \uB3C4\uAD6C\uB294 PC \uB300\uD654\uCC3D\uC5D0\uC11C \uC774 \uB300\uD654\uB97C \uC774\uC5B4\uC11C";
  return "\uD0ED \uACC1\uCC3D \uBB3B\uAE30 \uBAA8\uB4DC\uB294 \uC77D\uAE30\uB9CC \u2014 \uACE0\uCE58\uAE30\xB7\uB9CC\uB4E4\uAE30\uB294 work \uB3C4\uAD6C\uB85C \uC791\uC5C5 \uBAA8\uB4DC\uB97C \uBB3B\uB294\uB2E4";
}
var today = () => {
  const d = /* @__PURE__ */ new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
async function main() {
  const a = args(process.argv.slice(2));
  if (typeof a.study === "string") setStudyDir(a.study);
  const vault = String(a.vault ?? process.cwd());
  const work = !!a.work;
  const who = whoOf(vault);
  const note = typeof a.note === "string" ? a.note : "";
  const py = String(a.py ?? "py");
  const seen = typeof a.seen === "string" ? a.seen : void 0;
  const view = typeof a.view === "string" ? a.view : void 0;
  const subjDir = typeof a.subjects === "string" ? a.subjects : import_path4.default.join(vault, "2_\uC9C0\uC2DD", "modules", "study-helper");
  let kind;
  if (note) {
    try {
      kind = guessKind(py, vault, note);
    } catch {
      kind = { kind: "\uBA54\uBAA8", why: "\uC9D0\uC791 \uC2E4\uD328", bg: null, ref: null };
    }
    if (typeof a.kind === "string" && KINDS.includes(a.kind)) kind = { ...kind, kind: a.kind, why: "\uC0AC\uB78C\uC774 \uACE0\uB984" };
    out({ t: "kind", kind: kind.kind, why: kind.why, from: typeof a.kind === "string" ? "user" : "guess" });
    out({ t: "chips", kind: kind.kind, chips: CHIPS[kind.kind].map((c) => c[0]) });
    if (a.chips) {
      if (!a["no-doc"]) await warmDoc(py, vault, typeof a.docitems === "string" ? a.docitems : import_path4.default.join(vault, "3_\uC2DC\uC2A4\uD15C", "ink", "docitems.py"), note, kind.ref).catch(() => null);
      return;
    }
  }
  const chipName = typeof a.chip === "string" ? a.chip : note && !a.text ? CHIPS[kind.kind][0][0] : "";
  const chip = note && chipName ? chipOf(kind.kind, chipName) : null;
  const exe = findClaude(String(a.claude ?? ""));
  if (!exe) return out({ t: "error", why: "claude \uB97C \uBABB \uCC3E\uC74C" });
  let shots = [];
  let panes = [];
  try {
    const pj = typeof a.panes === "string" ? JSON.parse(a.panes) : [];
    if (Array.isArray(pj)) panes = pj.filter((p) => p && typeof p.path === "string" && typeof p.pos === "string").map((p) => ({ path: p.path, pos: p.pos, cur: !!p.cur, view: typeof p.view === "string" ? p.view : void 0 }));
  } catch {
  }
  const minimal = !!(note && !a["no-ink"] && view && !a["no-minimal"] && (chip ? chip[1] !== "none" : !!a.text));
  const split = !chip || chip[1] === "since";
  if (note && !panes.some((p) => p.path === note)) panes.push({ path: note, pos: panes.length ? "\uD544\uAE30" : "\uAC00\uC6B4\uB370", cur: !panes.some((p) => p.cur), view });
  const runner = { py, vault };
  const docScript = typeof a.docitems === "string" ? a.docitems : import_path4.default.join(vault, "3_\uC2DC\uC2A4\uD15C", "ink", "docitems.py");
  let added = [];
  let tables = [];
  if (note && !a["no-doc"]) {
    try {
      added = await docPanes({ py, vault, script: docScript, note, panes, ref: kind?.ref, bg: kind?.bg, firstPage: view ? +view.split(",")[0] || 1 : 1 });
      tables = await docTables({ py, vault, script: docScript, panes: [...panes, ...added], ms: +(a["doc-ms"] ?? 3e3) });
    } catch {
    }
  }
  const docLine = docHead(added, tables);
  for (const p of added) out({ t: "doc", path: p.path, pos: p.pos });
  const looker = new Looker(runner, [...panes, ...added], {
    seen,
    split,
    onInk: (ss) => ss.forEach((s) => out({ t: "lines", page: s.page, lines: s.lines, new: s.new, erased: s.erased, px: s.px })),
    onLook: (label, p) => out({ t: "tool", name: "look", arg: panes.length > 1 && paneKind(p.path) !== "\uD544\uAE30" ? `${p.pos} ${label}` : label })
  });
  let sc = null;
  if (minimal) {
    try {
      let all = !!a["view-all"] || wantsAll(String(a.text ?? ""));
      if (all) {
        const whole = inkScreen(runner, note, "1,0,99999999", { split, seen, label: "\uD544\uAE30 \uC804\uCCB4" });
        if (whole.shots.length <= ALL_MAX || a["view-all"]) sc = whole;
        else all = false;
      }
      if (!all || !sc) sc = inkScreen(runner, note, view, { split, seen });
    } catch (e) {
      return out({ t: "error", why: "\uD544\uAE30 \uADF8\uB9AC\uAE30 \uC2E4\uD328: " + String(e).slice(0, 200) });
    }
    shots = sc.shots;
    looker.primeInk(note, sc);
    for (const s of shots) out({ t: "lines", page: s.page, lines: s.lines, new: s.new, erased: s.erased, px: s.px });
  } else if (note && !a["no-ink"] && chip) {
    try {
      shots = shotsOf(py, vault, note, chip[1], view, seen);
    } catch (e) {
      return out({ t: "error", why: "\uD544\uAE30 \uADF8\uB9AC\uAE30 \uC2E4\uD328: " + String(e).slice(0, 200) });
    }
    for (const s of shots) out({ t: "lines", page: s.page, lines: s.lines, new: s.new, erased: s.erased });
  }
  const images = shots.map((s) => import_fs3.default.readFileSync(s.png).toString("base64"));
  const mcp = async (msg) => {
    let result = {};
    if (msg.method === "initialize") result = { protocolVersion: msg.params?.protocolVersion ?? "2024-11-05", capabilities: { tools: {} }, serverInfo: { name: VAULT_SERVER, version: "1" } };
    else if (msg.method === "tools/list") result = { tools: [LOOK_SPEC, SYM_SPEC, ...work ? [] : [workSpec(josa(who, "\uAED8"))]] };
    else if (msg.method === "tools/call" && msg.params?.name === WORK_NAME) result = { content: [{ type: "text", text: "\uC791\uC5C5 \uBAA8\uB4DC\uB294 \uD0ED\uC5D0\uC11C \uD3F0 \uC2B9\uC778\uC744 \uBC1B\uC544\uC57C \uCF1C\uC9C4\uB2E4 \u2014 \uC774 \uD134\uC740 \uC5EC\uAE30\uC11C \uBA48\uCD98\uB2E4" }], isError: true };
    else if (msg.method === "tools/call") {
      const name = String(msg.params?.name ?? "");
      let args2 = msg.params?.arguments;
      const it = name === "look" ? itemAt(String(args2?.at ?? ""), tables) : null;
      if (it && typeof it === "object") result = { content: [{ type: "text", text: it.err }], isError: true };
      else {
        if (typeof it === "string") args2 = { ...args2, at: it };
        result = await vaultCall(name, args2, { r: runner, looker }) ?? { content: [{ type: "text", text: "\uBAA8\uB974\uB294 \uB3C4\uAD6C" }], isError: true };
      }
    }
    return { jsonrpc: "2.0", id: msg.id, result };
  };
  const filt = new TagFilter((s) => out({ t: "d", s }));
  const hold = new Hold((s) => filt.push(s));
  let done = false;
  const mode = work ? workOpts(pcWork(vault)) : { permissionMode: "default", core: askCore(vault, !!note) + (note && split && sc ? "\n" + NEW_INK_RULE : "") + (docLine || tables.length ? "\n" + DOC_RULE : ""), tools: "Read,Grep,Glob" };
  const eng = new Engine(
    { exe, cwd: vault, ...mode, model: String(a.model ?? (wantsStudy(chipName, String(a.text ?? ""), kind?.kind) ? STUDY_MODEL : "opus")), effort: typeof a.effort === "string" ? a.effort : void 0, resume: typeof a.resume === "string" ? a.resume : void 0, inner: { server: VAULT_SERVER, tool: `${LOOK_TOOL},${SYM_TOOL}` } },
    (m) => {
      if (m.type === "control_request" && m.request?.subtype === "mcp_message") return void mcp(m.request.message).then((mcp_response) => eng.answer(m.request_id, { mcp_response }));
      if (m.type === "control_request" && m.request?.subtype === "can_use_tool") {
        if (!work && m.request.tool_name === WORK_TOOL) {
          out({ t: "work", why: String(m.request.input?.why ?? "").slice(0, 200) });
          return eng.answer(m.request_id, { behavior: "deny", message: `${josa(who, "\uC774")} \uD0ED\uC5D0\uC11C \uC791\uC5C5 \uBAA8\uB4DC \uC2B9\uC778(\uD3F0 \uC9C0\uBB38)\uC744 \uBC1B\uB294 \uC911\uC774\uB2E4. \uC774\uBC88 \uD134\uC740 \uC5EC\uAE30\uC11C \uBA48\uCD98\uB2E4.`, interrupt: true });
        }
        const why = allowTool(m.request.tool_name, m.request.input, work);
        return why ? eng.answer(m.request_id, { behavior: "deny", message: why }) : eng.answer(m.request_id, { behavior: "allow", updatedInput: m.request.input });
      }
      if (m.type === "stream_event" && !m.parent_tool_use_id) {
        const ev = m.event;
        if (ev?.type === "message_start") hold.start();
        else if (ev?.type === "content_block_start" && ev.content_block?.type === "tool_use") hold.tool();
        else if (ev?.type === "message_stop") hold.flush();
        else if (ev?.type === "content_block_delta" && ev.delta?.type === "text_delta") hold.push(ev.delta.text);
      }
      if (m.type === "assistant" && !m.parent_tool_use_id) {
        for (const c of m.message?.content ?? []) if (c.type === "tool_use") filt.push("\n"), c.name === LOOK_TOOL || out({ t: "tool", name: c.name, arg: String(c.input?.command ?? c.input?.file_path ?? c.input?.pattern ?? "").slice(0, 160) });
      }
      if (m.type === "result") {
        done = true;
        hold.flush();
        filt.flush();
        for (const tg of filt.tags) {
          const k = /^종류:\s*(.+)$/.exec(tg)?.[1]?.trim();
          if (k && KINDS.includes(k)) {
            out({ t: "kind", kind: k, why: "\uBAA8\uB378\uC774 \uADF8\uB9BC\uC744 \uBCF4\uACE0", from: "model" });
            out({ t: "chips", kind: k, chips: CHIPS[k].map((c) => c[0]) });
          } else if (tg.startsWith("\uAE30\uB85D:") && !a["no-record"]) {
            try {
              const r = appendRec(subjDir, tg, today());
              if (r) out({ t: "rec", ...r });
            } catch {
            }
          }
        }
        const u = m.usage ?? {};
        out({
          t: "done",
          session: eng.sessionId ?? m.session_id,
          mode: work ? "work" : "ask",
          text: filt.text.trim() || m.result,
          tags: filt.tags,
          error: m.is_error ? m.subtype : void 0,
          cost: m.total_cost_usd,
          looks: looker.looks,
          usage: { in: (u.input_tokens ?? 0) + (u.cache_creation_input_tokens ?? 0) + (u.cache_read_input_tokens ?? 0), out: u.output_tokens ?? 0, cacheRead: u.cache_read_input_tokens ?? 0 }
        });
        if (!m.is_error && minimal && split && looker.shownInk.length) {
          try {
            markSegs(py, vault, note, looker.shownInk, seen);
          } catch {
          }
        } else if (!m.is_error && !minimal && shots.length && chip?.[0] === "\uBD10\uC918") {
          try {
            markSeen(py, vault, note, seen);
          } catch {
          }
        }
        eng.close();
      }
    },
    (code, err) => {
      if (!done) out({ t: "error", why: `\uC5D4\uC9C4\uC774 \uB05D\uB0A8(${code}) ${err.slice(-300)}` });
    }
  );
  await eng.start();
  const kindShown = kind && added.length ? { ...kind, ref: added.some((p) => p.pos === "\uC9DD \uBB38\uC81C") ? null : kind.ref, bg: added.some((p) => p.pos === "\uBC14\uD0D5 PDF") ? null : kind.bg } : kind;
  const body = userText({ note, shots, chip, text: String(a.text ?? ""), kind: kindShown, subj: note ? subjects(subjDir) : [], scr: sc ? screenHead(sc, split) : void 0, panes, doc: docLine });
  const mn = a["mode-note"] ? MODE_NOTE[work ? "work" : "ask"] : "";
  eng.sendUser(mn ? `${mn}${body.startsWith("[") ? "\n" : "\n\n"}${body}` : body, images);
}
if (require.main === module) void main();
// Annotate the CommonJS export names for ESM import in node:
0 && (module.exports = {
  ALL_MAX,
  CHIPS,
  KINDS,
  STUDY_CHIPS,
  STUDY_MODEL,
  STUDY_SKILLS,
  TagFilter,
  WORK_TOOL,
  allowTool,
  appendRec,
  askCore,
  chipOf,
  guessKind,
  markSeen,
  markSegs,
  pcWork,
  screenHead,
  setStudyDir,
  shotsOf,
  skillBody,
  studyRule,
  subjects,
  userText,
  wantsAll,
  wantsStudy,
  whoOf
});
