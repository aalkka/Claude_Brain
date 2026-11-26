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

// src/tools/sdocx_dump.ts
var sdocx_dump_exports = {};
__export(sdocx_dump_exports, {
  DUMP_VERSION: () => DUMP_VERSION,
  dump: () => dump
});
module.exports = __toCommonJS(sdocx_dump_exports);
var fs = __toESM(require("node:fs"));

// src/ink/sdocx.ts
var inflateRaw = async (raw) => {
  const ds = new globalThis.DecompressionStream("deflate-raw");
  const out = new Response(new Blob([raw]).stream().pipeThrough(ds));
  return new Uint8Array(await out.arrayBuffer());
};
var Zip = class {
  constructor(b, inflate = inflateRaw) {
    this.b = b;
    this.inflate = inflate;
    this.entries = /* @__PURE__ */ new Map();
    const v = new DataView(b.buffer, b.byteOffset, b.byteLength);
    let e = -1;
    for (let i = b.length - 22; i >= Math.max(0, b.length - 7e4); i--) {
      if (v.getUint32(i, true) === 101010256) {
        e = i;
        break;
      }
    }
    if (e < 0) throw new Error("zip \uC774 \uC544\uB2D8(.sdocx \uB05D \uAE30\uB85D \uC5C6\uC74C)");
    const n = v.getUint16(e + 10, true);
    let o = v.getUint32(e + 16, true);
    const dec = new TextDecoder();
    for (let k = 0; k < n; k++) {
      if (v.getUint32(o, true) !== 33639248) throw new Error("zip \uBAA9\uB85D\uC774 \uAE68\uC9D0");
      const method = v.getUint16(o + 10, true), csize = v.getUint32(o + 20, true), size = v.getUint32(o + 24, true);
      const nl = v.getUint16(o + 28, true), xl = v.getUint16(o + 30, true), cl = v.getUint16(o + 32, true), local = v.getUint32(o + 42, true);
      const name = dec.decode(b.subarray(o + 46, o + 46 + nl));
      this.entries.set(name, { name, method, csize, size, local });
      o += 46 + nl + xl + cl;
    }
  }
  names() {
    return [...this.entries.keys()];
  }
  has(name) {
    return this.entries.has(name);
  }
  async read(name) {
    const en = this.entries.get(name);
    if (!en) return null;
    const v = new DataView(this.b.buffer, this.b.byteOffset, this.b.byteLength);
    const o = en.local;
    if (v.getUint32(o, true) !== 67324752) throw new Error(`zip \uCE78\uC774 \uAE68\uC9D0: ${name}`);
    const start = o + 30 + v.getUint16(o + 26, true) + v.getUint16(o + 28, true);
    const raw = this.b.subarray(start, start + en.csize);
    if (en.method === 0) return raw;
    if (en.method === 8) return this.inflate(raw);
    throw new Error(`\uBAA8\uB974\uB294 \uC555\uCD95(${en.method}): ${name}`);
  }
};
var R = class {
  constructor(b, o = 0) {
    this.b = b;
    this.o = o;
    this.v = new DataView(b.buffer, b.byteOffset, b.byteLength);
  }
  need(n) {
    if (this.o + n > this.b.length) throw new RangeError(`\uB05D\uC744 \uB118\uC74C(${this.o}+${n} > ${this.b.length})`);
  }
  u8() {
    this.need(1);
    return this.b[this.o++];
  }
  u16() {
    this.need(2);
    const x = this.v.getUint16(this.o, true);
    this.o += 2;
    return x;
  }
  i16() {
    this.need(2);
    const x = this.v.getInt16(this.o, true);
    this.o += 2;
    return x;
  }
  u32() {
    this.need(4);
    const x = this.v.getUint32(this.o, true);
    this.o += 4;
    return x;
  }
  i32() {
    this.need(4);
    const x = this.v.getInt32(this.o, true);
    this.o += 4;
    return x;
  }
  f32() {
    this.need(4);
    const x = this.v.getFloat32(this.o, true);
    this.o += 4;
    return x;
  }
  f64() {
    this.need(8);
    const x = this.v.getFloat64(this.o, true);
    this.o += 8;
    return x;
  }
  skip(n) {
    this.need(n);
    this.o += n;
  }
  utf16(n) {
    this.need(2 * n);
    let s = "";
    for (let i = 0; i < n; i++) s += String.fromCharCode(this.v.getUint16(this.o + 2 * i, true));
    this.o += 2 * n;
    return s;
  }
  s16() {
    return this.utf16(this.u16());
  }
  s32() {
    return this.utf16(this.u32());
  }
  /** 길이 붙은 가면(1~4바이트 · 더 길면 앞 4바이트만 씀) */
  mask() {
    const n = this.u8();
    this.need(n);
    let m = 0;
    for (let i = 0; i < Math.min(n, 4); i++) m += this.b[this.o + i] * 2 ** (8 * i);
    this.o += n;
    return m;
  }
};
var bit = (m, k) => Math.floor(m / 2 ** k) % 2 === 1;
function frameAt(b, o) {
  const r = new R(b, o);
  const size = r.u32(), type = r.i16(), flex = r.u32(), prop = r.mask(), field = r.mask();
  return { start: o, size, type, flex: o + flex, prop, field, fixed: r.o };
}
function framesIn(b, start, end) {
  const out = [];
  let o = start;
  while (o + 11 <= end) {
    const f = frameAt(b, o);
    if (f.size < 11 || o + f.size > end) break;
    out.push(f);
    o += f.size;
  }
  return out;
}
var q = (w, div) => (w & 32768 ? -1 : 1) * (w & 32767) / div;
function readStroke(b, f, box) {
  const r = new R(b, f.fixed);
  const n = r.u16();
  const pts = new Float64Array(n * 3);
  if (n > 0) {
    if (f.prop & 1) {
      let x = r.f64(), y = r.f64();
      pts[0] = x;
      pts[1] = y;
      for (let i = 1; i < n; i++) {
        x += q(r.u16(), 32);
        y += q(r.u16(), 32);
        pts[3 * i] = x;
        pts[3 * i + 1] = y;
      }
      let p = r.f32();
      pts[2] = p;
      for (let i = 1; i < n; i++) {
        p += q(r.u16(), 4096);
        pts[3 * i + 2] = p;
      }
    } else {
      for (let i = 0; i < n; i++) {
        pts[3 * i] = r.f64();
        pts[3 * i + 1] = r.f64();
      }
      for (let i = 0; i < n; i++) pts[3 * i + 2] = r.f32();
    }
  }
  const s = new R(b, f.flex);
  let argb = 4278190080, size = 2;
  if (bit(f.field, 0)) s.i32();
  if (bit(f.field, 1)) s.i32();
  if (bit(f.field, 2)) argb = s.u32();
  if (bit(f.field, 3)) size = s.f32();
  const alpha = argb >>> 24;
  return { pts, argb, size: isFinite(size) && size > 0 ? size : 2, fixed: (f.prop & 16) !== 0, hl: alpha < 240, eraser: (f.prop & 8) !== 0, box };
}
function readBase(b, f) {
  const r = new R(b, f.fixed);
  r.u32();
  r.skip(r.u16());
  r.skip(8);
  return [r.f64(), r.f64(), r.f64(), r.f64()];
}
function readRotation(b, f) {
  if (!bit(f.field, 0)) return 0;
  const a = new R(b, f.flex).f32();
  return isFinite(a) ? a : 0;
}
function readTextCommon(b, at) {
  const r = new R(b, at);
  const size = r.u32();
  const end = r.o + size;
  const text = r.s32();
  const sections = [];
  let margin = [0, 0, 0, 0];
  const inline = [];
  try {
    const spans = r.u32();
    for (let i = 0; i < spans; i++) r.skip(r.u16());
    const paras = r.u32();
    for (let i = 0; i < paras; i++) r.skip(r.u16());
    margin = [r.f32(), r.f32(), r.f32(), r.f32()];
    r.u8();
    const ns = r.u16();
    for (let i = 0; i < ns; i++) sections.push([r.i32(), r.i32()]);
    const flags = r.u32();
    r.u32();
    if (flags & 1) {
      const n = r.u32();
      for (let i = 0; i < n; i++) {
        r.u32();
        const osize = r.u32(), otype = r.u32(), o0 = r.o;
        r.skip(osize);
        const idx = r.i32();
        r.skip(8);
        if (otype !== 3) continue;
        const fr = framesIn(b, o0, o0 + osize);
        const box = fr[0]?.type === 0 ? readBase(b, fr[0]) : [0, 0, 0, 0];
        const f7 = fr.find((f) => f.type === 7);
        inline.push({ at: idx, media: f7 ? readShapeText(b, f7).image : null, w: box[2] - box[0], h: box[3] - box[1] });
      }
    }
  } catch {
  }
  return { text, sections, margin, inline, end };
}
function readShapeText(b, f) {
  const r = new R(b, f.flex);
  let text = null, image = null;
  try {
    if (bit(f.field, 0)) {
      const t = readTextCommon(b, r.o);
      text = t.text;
      r.o = t.end;
    }
    if (bit(f.field, 1)) r.u8();
    if (bit(f.field, 2)) r.i32();
    if (bit(f.field, 3)) return { text, image };
    if (bit(f.field, 4)) r.i32();
    if (bit(f.field, 5)) {
      r.u32();
      const kind = r.u8();
      if (kind === 2) {
        r.u8();
        const id = r.i32();
        image = id >= 0 ? id : null;
      }
    }
  } catch {
  }
  return { text, image };
}
var KIND = { 4: "\uBB36\uC74C", 7: "\uB3C4\uD615", 8: "\uC120", 10: "\uC74C\uC131", 11: "\uC218\uC2DD", 12: "\uD45C", 13: "\uC6F9", 14: "\uADF8\uB9BC\uD310", 16: "\uC601\uC0C1", 17: "\uB9C1\uD06C", 20: "\uADF8\uB798\uD504", 21: "\uC218\uD559", 22: "\uD45C", 23: "\uCF54\uB4DC", 24: "\uCCA8\uBD80" };
function readObjects(b, r, count, page, warn, depth = 0) {
  for (let k = 0; k < count; k++) {
    const type = r.u8(), children = r.u16(), size = r.u32();
    const start = r.o, end = start + size - 32;
    if (size < 32 || end > b.length) throw new Error(`\uAC1C\uCCB4 \uD06C\uAE30\uAC00 \uC774\uC0C1\uD568(${size} @${start})`);
    const fr = framesIn(b, start, end);
    try {
      if (type === 1 && fr[1]?.type === 1) {
        const s = readStroke(b, fr[1], fr[0]?.type === 0 ? readBase(b, fr[0]) : [0, 0, 0, 0]);
        if (s && fr[0]?.type === 0) s.rot = readRotation(b, fr[0]);
        if (s && !s.eraser && s.pts.length >= 3) page.strokes.push(s);
      } else if (type === 3 || type === 2) {
        const rect = fr[0]?.type === 0 ? readBase(b, fr[0]) : [0, 0, 0, 0];
        const f7 = fr.find((f) => f.type === 7);
        const st = f7 ? readShapeText(b, f7) : { text: null, image: null };
        if (type === 3) page.images.push({ rect, media: st.image });
        else if (st.text) page.texts.push({ rect, text: st.text });
        else page.other["\uAE00\uC0C1\uC790"] = (page.other["\uAE00\uC0C1\uC790"] ?? 0) + 1;
      } else if (type !== 9 && type !== 100) {
        const name = KIND[type] ?? `\uC885\uB958${type}`;
        page.other[name] = (page.other[name] ?? 0) + 1;
      }
    } catch (e) {
      warn.push(`\uAC1C\uCCB4(${type})\uB97C \uBABB \uC77D\uC74C: ${e.message}`);
    }
    r.o = start + size;
    readObjects(b, r, children, page, warn, depth + 1);
  }
}
function readPage(b, warn) {
  const r = new R(b);
  const layerAt = r.u32();
  r.u32();
  r.mask();
  const field = r.mask();
  r.u32();
  const w = r.u32(), h = r.u32();
  r.u32();
  r.u32();
  const id = r.s16();
  r.skip(8 + 4 + 4);
  const page = { id, w, h, bgColor: null, template: 0, pdf: [], strokes: [], images: [], texts: [], other: {} };
  try {
    if (bit(field, 0)) r.skip(32);
    if (bit(field, 1)) throw new Error("\uCABD \uAF2C\uB9AC\uD45C \uCE78(\uAF34 \uBAA8\uB984) \u2014 \uBC14\uD0D5 PDF \uCE78\uC744 \uBABB \uBD04");
    if (bit(field, 2)) r.s16();
    if (bit(field, 3)) r.i32();
    if (bit(field, 4)) r.i32();
    if (bit(field, 5)) page.bgColor = r.u32();
    if (bit(field, 6)) r.i32();
    if (bit(field, 7)) r.i32();
    if (bit(field, 8)) {
      const n = r.u16();
      for (let i = 0; i < n; i++) {
        const media = r.i32(), pg = r.i32();
        const rect = [r.i32(), r.i32(), r.i32(), r.i32()];
        if (media >= 0) page.pdf.push({ media, page: pg, rect });
      }
    }
    if (bit(field, 9)) page.template = r.i32();
  } catch (e) {
    warn.push(`\uCABD \uCE78\uC744 \uB05D\uAE4C\uC9C0 \uBABB \uC77D\uC74C: ${e.message}`);
  }
  r.o = layerAt;
  const layers = r.u16(), current = r.u16();
  for (let li = 0; li < layers; li++) {
    const ls = r.o;
    r.o = ls + r.u32();
    const count = r.u32();
    const target = li === current ? page : { ...page, strokes: [], images: [], texts: [], other: {} };
    readObjects(b, r, count, target, warn);
    r.skip(32);
  }
  return page;
}
function readNote(b) {
  const r = new R(b);
  r.u32();
  r.mask();
  r.mask();
  const version = r.u32();
  r.s16();
  r.u32();
  r.skip(16);
  const width = r.u32(), height = r.u32();
  r.skip(12);
  const objText = (size) => {
    const start = r.o;
    r.o += size;
    const none = { text: "", sections: [], margin: [0, 0, 0, 0], inline: [], end: 0 };
    if (!size) return none;
    const f7 = framesIn(b, start, start + size).find((f) => f.type === 7);
    if (!f7 || !bit(f7.field, 0)) return none;
    return readTextCommon(b, f7.flex);
  };
  const title = objText(r.u32());
  const body = objText(r.u32());
  return { version, width, height, title: title.text, body: body.text, sections: body.sections, margin: body.margin, inline: body.inline };
}
function readMediaInfo(b) {
  const out = /* @__PURE__ */ new Map();
  const tail = new TextDecoder().decode(b.subarray(Math.max(0, b.length - 4)));
  const r = new R(b);
  if (tail === "EOFX") {
    r.u32();
    const n = r.u16();
    for (let i = 0; i < n; i++) {
      const size = r.u32(), at = r.o;
      const id = r.u32(), name = r.s16();
      out.set(id, { id, name });
      r.o = at + size;
    }
  } else {
    const n = r.u16();
    for (let i = 0; i < n; i++) {
      const id = r.u32(), name = r.s16();
      r.skip(64 + 2 + 8);
      out.set(id, { id, name });
    }
  }
  return out;
}
async function parseSdocx(bytes, inflate = inflateRaw) {
  const zip = new Zip(bytes, inflate);
  const warn = [];
  const noteB = await zip.read("note.note");
  if (!noteB) {
    if (zip.has("doc.dat") || zip.has("content.dat")) throw new Error("\uC61B \uC0BC\uC131\uB178\uD2B8 \uD615\uC2DD(SDoc)\uC774\uB77C \uBABB \uC77D\uC2B5\uB2C8\uB2E4");
    throw new Error("note.note \uAC00 \uC5C6\uC74C(\uC0BC\uC131\uB178\uD2B8 \uD30C\uC77C\uC774 \uC544\uB2D8)");
  }
  const note = readNote(noteB);
  let order = [];
  const pid = await zip.read("pageIdInfo.dat");
  if (pid) {
    const r = new R(pid, 32);
    const n = r.u16();
    for (let i = 0; i < n; i++) {
      order.push(r.s16());
      r.skip(32);
    }
  }
  const pageFiles = zip.names().filter((x) => x.endsWith(".page"));
  if (!order.length || order.some((u) => !zip.has(u + ".page"))) {
    if (order.length) warn.push("\uCABD \uBAA9\uB85D\uACFC zip \uC774 \uB9DE\uC9C0 \uC54A\uC544 zip \uCC28\uB840\uB85C \uC77D\uC74C");
    order = pageFiles.map((x) => x.slice(0, -5));
  }
  const pages = [];
  for (const u of order) {
    const b = await zip.read(u + ".page");
    if (!b) continue;
    try {
      pages.push(readPage(b, warn));
    } catch (e) {
      warn.push(`\uCABD ${u} \uB97C \uBABB \uC77D\uC74C: ${e.message}`);
    }
  }
  const mi = await zip.read("media/mediaInfo.dat");
  let media = /* @__PURE__ */ new Map();
  try {
    if (mi) media = readMediaInfo(mi);
  } catch (e) {
    warn.push(`media \uBAA9\uB85D\uC744 \uBABB \uC77D\uC74C: ${e.message}`);
  }
  const bodyRanges = note.sections.length ? note.sections.map(([s, n]) => [Math.max(0, s), Math.max(0, n)]) : note.body ? [[0, note.body.length]] : [];
  const bodyPages = bodyRanges.map(([s, n]) => note.body.slice(s, s + n));
  return {
    version: note.version,
    width: note.width,
    height: note.height,
    title: note.title,
    body: note.body,
    bodyPages,
    bodyRanges,
    bodyMargin: note.margin,
    bodyImages: note.inline,
    pages,
    media,
    warn,
    file: async (name) => zip.read(name)
  };
}

// src/tools/sdocx_dump.ts
var DUMP_VERSION = 1;
async function dump(bytes) {
  const doc = await parseSdocx(bytes);
  return {
    v: DUMP_VERSION,
    title: doc.title,
    body: doc.body,
    bodyPages: doc.bodyPages,
    width: doc.width,
    height: doc.height,
    warn: doc.warn,
    pages: doc.pages.map((p) => ({
      id: p.id,
      w: p.w,
      h: p.h,
      other: p.other,
      images: p.images.length,
      pdf: p.pdf.length,
      texts: p.texts.map((t) => ({ rect: t.rect, text: t.text })),
      strokes: p.strokes.filter((s) => !s.eraser).map((s) => {
        const pts = [];
        for (let i = 0; i + 2 < s.pts.length; i += 3) pts.push([+s.pts[i].toFixed(2), +s.pts[i + 1].toFixed(2), +s.pts[i + 2].toFixed(3)]);
        return { pts, argb: s.argb >>> 0, size: s.size, hl: s.hl };
      })
    }))
  };
}
async function main() {
  const [src, out] = process.argv.slice(2);
  if (!src) {
    process.stderr.write("\uC0AC\uC6A9: node sdocx-dump.cjs <\uC785\uB825.sdocx> [\uCD9C\uB825.json]\n");
    process.exit(2);
  }
  const json = JSON.stringify(await dump(new Uint8Array(fs.readFileSync(src))));
  if (out) fs.writeFileSync(out, json);
  else process.stdout.write(json);
}
if (require.main === module) main().catch((e) => {
  process.stderr.write(String(e?.stack || e) + "\n");
  process.exit(1);
});
// Annotate the CommonJS export names for ESM import in node:
0 && (module.exports = {
  DUMP_VERSION,
  dump
});
