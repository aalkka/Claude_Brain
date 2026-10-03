#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""외부뇌 검색 (Phase 3). 하이브리드 = 어휘(grep형) + 벡터(의미) RRF 융합.

CLI:
  python search.py --reindex            증분 재인덱스(hash 변경분만)
  python search.py --rebuild            전체 재인덱스
  python search.py --q "질의" --k 8     하이브리드 top-k → JSON lines (--mode lexical|vector|hybrid)
  python search.py --neighbors <path>   B1용 의미이웃 top-k(상대방식, 기본 k=3)
  python search.py --eval golden.jsonl  골든셋 hit@k 3자(lexical/vector/hybrid) 측정

모델: 3_시스템/config.json "embed_model" (기본 intfloat/multilingual-e5-small).

════════ 모델 티어 전환 (배포판 — 하드웨어별 1급 옵션, 폐기 아님) ════════
코드는 모델·차원 불가지(agnostic). 티어 변경 = config.json 한 줄 교체 + 전체 재빌드.
  | 티어 | 조건(설치 PC) | embed_model | 차원 | 실행 |
  |------|--------------|-------------|------|------|
  | 고   | CUDA GPU ≥8GB VRAM | BAAI/bge-m3                     | 1024 | GPU fp16 |
  | 중   | GPU 4~8GB / 강CPU  | intfloat/multilingual-e5-base  | 768  | GPU/CPU |
  | 저   | CPU-only           | intfloat/multilingual-e5-small | 384  | CPU (기본) |
전환 절차:
  1. config.json "embed_model" 교체.
  2. (bge-m3/고티어) CUDA torch 필요: `pip install torch --index-url https://download.pytorch.org/whl/cu121`.
  3. `python search.py --rebuild`  ← 차원 다르면 필수. 인덱스에 모델명 각인 →
     config 모델 ≠ 인덱스 모델이면 --reindex도 자동 전체 재빌드(차원혼합 방지 가드).
  e5 계열=쿼리 "query: "/문서 "passage: " 프리픽스 자동, bge 계열=프리픽스 생략(is_bge).
채택 근거: 빌더 환경(6GB)은 e5-small 하이브리드로 측정 충분 → 상향 불요(그에겐 DEFERRED).
  배포 사용자는 setup-interview 슬롯8이 하드웨어 감지→티어 자동선택. bge-m3는 상시 지원 옵션.
  전문·복원조건 = 3_시스템/_eval/results-hybrid.md.
═══════════════════════════════════════════════════════════════════════

인덱스: 3_시스템/_index/embeddings.json  {"_model":<name>, <path>:{hash,mtime,status,gist,vecs:[[..],..]}}
  - 청킹: 헤딩 단위 → 긴 섹션은 WINDOW줄 창. 노트 스코어 = max-chunk cosine(통짜희석 방지).
  - vector 스코어 = max_chunk_cos (+ recency_w*recency). archived ×0.5.
  - lexical 스코어 = BM25(k1=1.2, b=0.75 · 질의 토큰의 노트내 부분문자열 빈도 · IDF 는 노트 단위).
  - hybrid = RRF(lexical_rank, vector_rank), k_rrf=60.

측정 이력:
  - e5-small 통짜+recency0.2 = 66.7% / 순수cos = 73.3% (Phase 2 진단). grep = 100%.
  - 개정: 청킹 max-pool + recency off + 하이브리드. 재측정은 results-*.

"""
import argparse, glob, hashlib, json, os, re, sys, time, math

# stdout/stderr UTF-8 강제: Windows 콘솔 기본 cp949 → gist·경로의 비cp949 문자('—' 등)
# json.dumps(ensure_ascii=False) 출력 시 UnicodeEncodeError 크래시 방지(인시던트 #6·#9 계열).
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_DIR = os.path.join(VAULT, "3_시스템", "_index")
INDEX_PATH = os.path.join(INDEX_DIR, "embeddings.json")
CONFIG_PATH = os.path.join(VAULT, "3_시스템", "config.json")

TARGET_GLOBS = [
    "2_지식/**/*.md",   # notes(설계노트·사용자설명서 포함)·sessions·decisions·profile·MOC 등
    "3_시스템/_ref/**/*.md",
    "3_시스템/_claude-memory/**/*.md",
    "3_시스템/_index/pdf-cache/**/*.md",  # PDF 정제본(pdf-ingest step4). 청킹→부분읽기.
]
WINDOW = 40           # 헤딩 없는/긴 섹션 창 크기(줄)
MAX_CHUNKS = 120      # 노트당 청크 상한(거대 _변환본 비용 바운드)
RECENCY_W = 0.0       # 지식검색 recency 역효과(진단) → 기본 0. 필요시 상향.
HALF_LIFE_DAYS = 90.0
RRF_K = 60


def config_model_name():
    """config.json의 embed_model만 읽는다(모델 로드 없음 — 지연로드용)."""
    model_name = "intfloat/multilingual-e5-small"
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            model_name = json.load(f).get("embed_model", model_name)
    except (FileNotFoundError, json.JSONDecodeError, ValueError):  # H2: 손상 config → 기본 모델
        pass
    return model_name


def load_model():
    model_name = config_model_name()
    from sentence_transformers import SentenceTransformer  # 무거움(torch) → 실제 인코딩 필요 시에만 호출
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return SentenceTransformer(model_name, device=device), model_name


class _NumpyBert:
    """질의 1건용 BERT 순전파(numpy) — torch·transformers·sentence_transformers import 없이.

    왜(2026-09-24 실측): 질의 경로의 지연 40~49초 중 계산은 0.08초였고 나머지는 import 였다
    (`sentence_transformers` 26.5초 = transformers 5.x 가 fp8·deepgemm 통합을 거쳐 torch._dynamo 까지
    끌어옴 · torch 7.3초 · HF 허브 확인 ~9초). 이 경로는 import 0.5초 + 가중치 1.2초 + 인코딩 0.6초.
    등가성: 저장된 문서 벡터 41청크와 코사인 최소 1.000000 · 골든 두 셋 순위 결과 동일.
    범위: HF 캐시에 이미 받아 둔 model_type=bert + mean/cls 풀링만. 그 밖(bge-m3=xlm-roberta 등)이나
    어떤 실패든 예외를 내고 load_query_model() 이 기존 load_model() 로 떨어진다(fail-open · 09-24 실측:
    캐시 없는 환경에서 같은 순위). 재인덱스는 기존 경로 그대로.
    """

    def __init__(self, snap):
        import numpy as np
        from tokenizers import Tokenizer
        from safetensors import safe_open
        self.np = np
        cfg = json.load(open(os.path.join(snap, "config.json"), encoding="utf-8"))
        if cfg.get("model_type") != "bert" or cfg.get("hidden_act") != "gelu" \
                or cfg.get("position_embedding_type", "absolute") != "absolute":
            raise ValueError("unsupported")
        pool = {}
        pp = os.path.join(snap, "1_Pooling", "config.json")
        if os.path.exists(pp):
            pool = json.load(open(pp, encoding="utf-8"))
        self.cls = bool(pool.get("pooling_mode_cls_token")) and not pool.get("pooling_mode_mean_tokens")
        if not (self.cls or pool.get("pooling_mode_mean_tokens", True)):
            raise ValueError("unsupported pooling")
        maxlen = 512
        sp = os.path.join(snap, "sentence_bert_config.json")
        if os.path.exists(sp):
            maxlen = json.load(open(sp, encoding="utf-8")).get("max_seq_length", 512)
        self.tok = Tokenizer.from_file(os.path.join(snap, "tokenizer.json"))
        self.tok.enable_truncation(maxlen)
        f = safe_open(os.path.join(snap, "model.safetensors"), "np")
        pre = "bert." if any(k.startswith("bert.") for k in f.keys()) else ""
        self.W = {k[len(pre):]: f.get_tensor(k) for k in f.keys()
                  if k.startswith(pre) and not k.startswith(pre + "embeddings.word_")
                  and not k.startswith(pre + "pooler")}
        self.wemb = f.get_slice(pre + "embeddings.word_embeddings.weight")
        self.L, self.H = cfg["num_hidden_layers"], cfg["num_attention_heads"]
        self.D = cfg["hidden_size"] // self.H
        self.eps = cfg.get("layer_norm_eps", 1e-12)

    def _ln(self, x, p):
        m = x.mean(-1, keepdims=True); v = ((x - m) ** 2).mean(-1, keepdims=True)
        return (x - m) / self.np.sqrt(v + self.eps) * self.W[p + ".weight"] + self.W[p + ".bias"]

    def _gelu(self, x):  # 정확한 erf GELU (Abramowitz-Stegun 7.1.26, |오차|<1.5e-7)
        np = self.np
        z = x / math.sqrt(2.0); a = np.abs(z); t = 1.0 / (1.0 + 0.3275911 * a)
        y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t
                   + 0.254829592) * t * np.exp(-a * a)
        return 0.5 * x * (1.0 + np.sign(z) * y)

    def _one(self, text):
        np, W = self.np, self.W
        ids = self.tok.encode(text).ids; n = len(ids)
        x = np.stack([self.wemb[i:i + 1][0] for i in ids]) \
            + W["embeddings.position_embeddings.weight"][:n] + W["embeddings.token_type_embeddings.weight"][0]
        x = self._ln(x, "embeddings.LayerNorm")
        H, D = self.H, self.D
        lin = lambda h, p: h @ W[p + ".weight"].T + W[p + ".bias"]
        for l in range(self.L):
            p = "encoder.layer.%d." % l
            q, k, v = (lin(x, p + "attention.self." + s).reshape(n, H, D).transpose(1, 0, 2)
                       for s in ("query", "key", "value"))
            s = q @ k.transpose(0, 2, 1) / math.sqrt(D)
            s = np.exp(s - s.max(-1, keepdims=True)); s /= s.sum(-1, keepdims=True)
            c = (s @ v).transpose(1, 0, 2).reshape(n, H * D)
            x = self._ln(lin(c, p + "attention.output.dense") + x, p + "attention.output.LayerNorm")
            x = self._ln(lin(self._gelu(lin(x, p + "intermediate.dense")), p + "output.dense") + x,
                         p + "output.LayerNorm")
        e = x[0] if self.cls else x.mean(0)
        return e / np.linalg.norm(e)

    def encode(self, texts, normalize_embeddings=True, **_):
        return self.np.stack([self._one(t) for t in texts])


def _hf_snapshot(model_name):
    """HF 캐시에 받아 둔 스냅숏 경로(네트워크 없음). 없으면 None."""
    base = os.environ.get("HF_HUB_CACHE") or os.path.join(
        os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface"), "hub")
    d = os.path.join(base, "models--" + model_name.replace("/", "--"))
    try:
        rev = open(os.path.join(d, "refs", "main"), encoding="utf-8").read().strip()
        snap = os.path.join(d, "snapshots", rev)
    except OSError:
        snaps = glob.glob(os.path.join(d, "snapshots", "*"))
        snap = snaps[0] if len(snaps) == 1 else None
    return snap if snap and os.path.exists(os.path.join(snap, "model.safetensors")) else None


def load_query_model():
    """질의 인코더 — 빠른 numpy 경로를 먼저, 안 되면 기존 load_model()."""
    model_name = config_model_name()
    try:
        snap = _hf_snapshot(model_name)
        if snap:
            return _NumpyBert(snap), model_name
    except Exception:
        pass
    return load_model()


def is_bge(m): return "bge" in m.lower()
def pdoc(m, t): return t if is_bge(m) else "passage: " + t
def pqry(m, t): return t if is_bge(m) else "query: " + t
def rel(p): return os.path.relpath(p, VAULT).replace(os.sep, "/")


def iter_files():
    seen = set()
    for g in TARGET_GLOBS:
        for p in glob.glob(os.path.join(VAULT, g), recursive=True):
            ap = os.path.abspath(p)
            if ap not in seen and ap.endswith(".md"):
                seen.add(ap); yield ap


def file_hash(path):
    h = hashlib.sha1()
    with open(path, "rb") as f: h.update(f.read())
    return h.hexdigest()


def read_text(path):
    with open(path, encoding="utf-8", errors="replace") as f: return f.read()


# B1 관리블록 매치 패턴 — 3세대 공용(마이그레이션 시 구→신 무중복 교체 + 색인제거).
#  v3(현행): 콜아웃 제목줄에 인라인 마커 %%sl%% (독립 주석줄 없음 → 편집모드서도 안 보임).
#           블록 = 제목줄 + 이어지는 > 본문줄들([^\n]*라 re.S 무관).
#  v2: %% sl %% … %% /sl %% (독립 주석줄 — 편집모드서 노출되어 폐기).
#  v1: <!-- semantic-links:start/end -->.
_BLOCK_ALT = (
    r"(?:>\s*\[!info\]-\s*관련 노트\s*%%sl%%(?:\n>[^\n]*)*"
    r"|%% sl %%.*?%% /sl %%"
    r"|<!-- semantic-links:start -->.*?<!-- semantic-links:end -->)"
)

# 관리블록은 파생데이터 → 색인(임베딩·lexical) 유입 차단(이웃이름 피드백루프 방지).
_SEMLINK_RE = re.compile(r"\n*" + _BLOCK_ALT, re.S)
def strip_managed(text):
    return _SEMLINK_RE.sub("", text)


FM_STATUS = re.compile(r"^status:\s*(\w+)\s*$", re.M)
def parse_status(text):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            m = FM_STATUS.search(text[3:end])
            if m: return m.group(1).strip()
    return "active"


def gist(text):
    body = text   # M7: frontmatter 제거(헤딩 없는 노트 gist가 'type: ...' 누출 방지)
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1: body = text[end + 4:]
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("#"): return s.lstrip("#").strip()[:120]
    for line in body.splitlines():
        s = line.strip()
        if s: return s[:120]
    return ""


def chunk_text(text):
    """헤딩 단위 분할 → 긴 섹션은 WINDOW줄 창. 청크 리스트(문자열) 반환."""
    lines = text.splitlines()
    # frontmatter 제거
    if lines and lines[0].strip() == "---":
        try:
            end = lines.index("---", 1); lines = lines[end + 1:]
        except ValueError:
            pass
    # 헤딩 경계로 섹션 나눔
    sections, cur = [], []
    for ln in lines:
        if ln.lstrip().startswith("#") and cur:
            sections.append(cur); cur = [ln]
        else:
            cur.append(ln)
    if cur: sections.append(cur)
    chunks = []
    carry = []   # 본문 없는 제목-only 섹션 → 다음 섹션에 접두 병합(내용없는 청크가 이방성
                 # 원뿔서 무관노트에 max 세우는 허위 이웃 방지. 제목 텍스트는 보존).
    for sec in sections:
        if not any(l.strip() and not l.lstrip().startswith("#") for l in sec):
            carry += sec; continue      # 제목·공백뿐 → 이월(단독 배출 안 함)
        sec = carry + sec; carry = []
        if len(sec) <= WINDOW:
            c = "\n".join(sec).strip()
            if c: chunks.append(c)
        else:
            for i in range(0, len(sec), WINDOW):
                c = "\n".join(sec[i:i + WINDOW]).strip()
                if c: chunks.append(c)
    if carry:                            # 말미 제목-only(뒤 본문섹션 없음) → 마지막 청크에 흡수
        c = "\n".join(carry).strip()
        if c:
            if chunks: chunks[-1] = chunks[-1] + "\n" + c
            else: chunks.append(c)
    if not chunks:
        chunks = [text.strip()[:2000]]
    return chunks[:MAX_CHUNKS]


def load_index():
    try:
        with open(INDEX_PATH, encoding="utf-8") as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):  # H2: 손상 인덱스 → {} 반환(자동 전체재빌드)
        return {}


def notes(idx):
    """노트 항목만(메타키 '_model' 제외)."""
    return {k: v for k, v in idx.items() if k != "_model"}


def save_index(idx):
    os.makedirs(INDEX_DIR, exist_ok=True)
    tmp = INDEX_PATH + ".tmp"   # H1: tmp 기록 후 원자적 교체(kill 시 부분 파일·손상 방지)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False)
    os.replace(tmp, INDEX_PATH)


def reindex(full=False):
    model_name = config_model_name()   # 모델명만(로드 X). 실제 모델은 to_embed 있을 때만 지연로드.
    idx = {} if full else load_index()
    if not full and idx.get("_model") not in (None, model_name):
        print(f"model changed ({idx.get('_model')} -> {model_name}): forcing full rebuild (차원혼합 방지)", file=sys.stderr)
        idx = {}
    cur = set(); to_embed = []; meta = {}
    for ap in iter_files():
        rp = rel(ap); cur.add(rp)
        h = file_hash(ap)
        if idx.get(rp, {}).get("hash") == h:
            continue
        text = strip_managed(read_text(ap))
        ch = chunk_text(text)
        meta[rp] = (h, os.path.getmtime(ap), parse_status(text), gist(text), len(ch))
        for c in ch: to_embed.append((rp, c))
    for rp in list(notes(idx).keys()):
        if rp not in cur: del idx[rp]
    if to_embed:
        model, _ = load_model()   # 지연로드: 임베딩할 변경분 있을 때만 16s 모델로드(무변경 시 스킵)
        docs = [pdoc(model_name, c) for _, c in to_embed]
        vecs = model.encode(docs, normalize_embeddings=True, show_progress_bar=False, batch_size=32)
        by = {}
        for (rp, _), v in zip(to_embed, vecs):
            by.setdefault(rp, []).append([round(float(x), 6) for x in v])
        for rp, vs in by.items():
            h, mt, st, g, _ = meta[rp]
            idx[rp] = {"hash": h, "mtime": mt, "status": st, "gist": g, "vecs": vs}
    idx["_model"] = model_name
    save_index(idx)
    print(f"indexed {len(notes(idx))} notes, {len(to_embed)} chunks (model={model_name})", file=sys.stderr)
    return idx


def recency(mtime, now):
    age = max(0.0, (now - mtime) / 86400.0)
    return 0.5 ** (age / HALF_LIFE_DAYS)


def dot(a, b): return sum(x * y for x, y in zip(a, b))
def max_chunk_cos(qv, vecs): return max((dot(qv, v) for v in vecs), default=0.0)


# ---- lexical (grep형) arm ----
PARTICLE = re.compile(r"(은|는|이|가|을|를|의|에|에서|으로|로|와|과|도|만|한|의|들)$")
def toks(q):
    out = []
    for w in re.split(r"[\s,./()\[\]?!·:;\"']+", q):
        w = w.strip()
        if len(w) < 2: continue
        w2 = PARTICLE.sub("", w)
        if len(w2) < 2: w2 = w   # M2: 조사 스트립이 1글자 만들면(회의→회) 원형 유지
        out.append(w2.lower())
    return list(dict.fromkeys(out))


_TEXTCACHE = {}
def note_text(rp):
    if rp not in _TEXTCACHE:
        try:
            _TEXTCACHE[rp] = strip_managed(read_text(os.path.join(VAULT, rp))).lower()
        except OSError:
            _TEXTCACHE[rp] = ""
    return _TEXTCACHE[rp]


BM25_K1, BM25_B = 1.2, 0.75


def lexical_scores(query, idx):
    # BM25(2026-09-24 교체). 옛 식 «매칭 토큰수×10 + log(빈도)» 는 IDF·길이 보정이 없어 긴 노트
    # (MOC·인수인계)가 흔한 낱말만으로 위에 올랐다 — 패러프레이즈 정답을 밀어낸 자리의 청크 수 중앙값 37
    # (코퍼스 9). 세 평가셋 모두 비후퇴: lexical MRR@8 literal 0.58→0.96 · 패러프레이즈 3→5/12 ·
    # MOC 설명 167쌍 0.65→0.85, hybrid 0.89→0.94 · 4→5/12 · 0.76→0.82. 근거 = _eval/results-hybrid.md.
    ts = toks(query)
    docs = [(rp, note_text(rp)) for rp in notes(idx)]
    docs = [(rp, t) for rp, t in docs if t]
    if not docs or not ts: return []
    avg = sum(len(t) for _, t in docs) / len(docs)
    n = len(docs)
    idf = {}
    for w in ts:
        df = sum(1 for _, t in docs if w in t)
        idf[w] = math.log(1 + (n - df + 0.5) / (df + 0.5))
    rows = []
    for rp, txt in docs:
        norm = BM25_K1 * (1 - BM25_B + BM25_B * len(txt) / avg)
        score = 0.0
        for w in ts:
            tf = txt.count(w)
            if tf: score += idf[w] * tf * (BM25_K1 + 1) / (tf + norm)
        if score > 0:   # M2: 0매칭 노트 배제(토큰 없는 질의가 전 노트를 가짜 top-k로 반환 방지)
            rows.append((score, rp))
    rows.sort(reverse=True)
    return rows


def vector_scores(qv, idx, now):
    rows = []
    for rp, e in notes(idx).items():
        s = max_chunk_cos(qv, e["vecs"])
        if RECENCY_W: s = (1 - RECENCY_W) * s + RECENCY_W * recency(e["mtime"], now)
        if e.get("status") == "archived": s *= 0.5
        rows.append((s, rp))
    rows.sort(reverse=True)
    return rows


def rrf(rank_lists, k=RRF_K):
    agg = {}
    for rl in rank_lists:
        for i, (_, rp) in enumerate(rl):
            agg[rp] = agg.get(rp, 0.0) + 1.0 / (k + i + 1)
    return sorted(((v, rp) for rp, v in agg.items()), reverse=True)


def ranked(query, idx, mode, model=None, model_name=None):
    now = time.time()
    if mode == "lexical":
        return lexical_scores(query, idx)
    qv = model.encode([pqry(model_name, query)], normalize_embeddings=True)[0]
    qv = [float(x) for x in qv]
    vec = vector_scores(qv, idx, now)
    if mode == "vector":
        return vec
    lex = lexical_scores(query, idx)
    lex_matched = [(sc, rp) for sc, rp in lex if sc > 0]  # 0점 노트 순위노이즈 배제(RRF는 매칭리스트만)
    return rrf([lex_matched, vec])


def evaluate(golden_path, k=8):
    if not os.path.exists(golden_path):  # M1: 파일 부재 가드
        print(f"골든 파일 없음: {golden_path} — measure.md 절차로 작성하세요", file=sys.stderr); return {}
    pairs = [json.loads(l) for l in open(golden_path, encoding="utf-8") if l.strip()]
    if not pairs:  # M1: 빈 골든 가드(ZeroDivisionError 방지)
        print(f"골든 비어 있음: {golden_path}", file=sys.stderr); return {}
    model, model_name = load_query_model()
    idx = load_index()
    res = {}
    for mode in ("lexical", "vector", "hybrid"):
        hits = 0; miss = []
        for p in pairs:
            rows = ranked(p["q"], idx, mode, model, model_name)
            order = [rp for _, rp in rows]
            if p["a"] in order[:k]: hits += 1
            else:
                r = order.index(p["a"]) if p["a"] in order else -1
                miss.append((r, p["a"]))
        res[mode] = (hits, len(pairs), sorted(miss))
        print(f"[{mode:7}] hit@{k} = {hits}/{len(pairs)} = {hits/len(pairs)*100:.1f}%")
        for r, a in sorted(miss):
            print(f"    miss rank={r}: {a}")
    return res


# B1 이웃 기본값(config.json "graph"서 오버라이드 — setup-interview 슬롯). 근거=results-b1-neighbors.md.
NEIGH_K = 3          # 노드당 이웃 상한(per-node top-k). union 렌더 시 평균차수 ~4.5.
NEIGH_DUP = 0.999    # 중복드롭: cos>=이면 색인중복(변환본↔pdf-cache 동일본) → 이웃 아님(센터 후도 dup=1.0 실증).
NEIGH_TAU = 0.33     # 센터링 후 절대임계: top1(고립방지 레일) 외 이웃은 centered-cos>=이만 채택.


def graph_cfg():
    """config.json "graph" 블록(없으면 모듈 기본). k=이웃밀도는 인터뷰로 변경가능(소프트코딩)."""
    g = {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            g = json.load(f).get("graph", {}) or {}
    except (FileNotFoundError, ValueError):
        pass
    return (int(g.get("neigh_k", NEIGH_K)),
            float(g.get("neigh_dup", NEIGH_DUP)),
            float(g.get("neigh_tau", NEIGH_TAU)))


def _global_mean(ns):
    """전 색인 청크벡터 글로벌 평균 μ(이방성 센터링용). 노트<2면 None(센터링 스킵)."""
    if len(ns) < 2: return None
    dim = len(next(iter(ns.values()))["vecs"][0])
    mean = [0.0] * dim; n = 0
    for e in ns.values():
        for v in e["vecs"]:
            for i in range(dim): mean[i] += v[i]
            n += 1
    return [x / n for x in mean] if n else None


def _center(v, mean):
    """v − μ 후 재정규화(이방성 제거). norm 0(=μ와 동일 generic 청크)이면 0벡터 → max-pool 비기여."""
    w = [v[i] - mean[i] for i in range(len(mean))]
    nr = math.sqrt(sum(x * x for x in w)) or 1.0
    return [x / nr for x in w]


def neighbors(path, k=None, dup=None, tau=None):
    """B1 의미이웃 = 평균 센터링 후 top-k.

    근거(측정, results-b1-neighbors.md): e5-small 임베딩 **이방성** → 전 노트쌍 raw cos
    0.80~1.00 원뿔 압착(절대임계 = 헤어볼, 원리적 무용). **평균 센터링**(All-but-the-Top
    1단계 = 글로벌 μ 빼고 재정규화)이 원뿔을 펴 진짜 이웃을 노이즈 위로 분리 →
    센터 후엔 절대임계 유효. 규칙: top1 무조건 유지(고립방지 레일) + 2~k위는
    centered-cos>=tau. neighbors 전용(검색 vector_scores는 raw 유지 — 무영향).
    실측(손라벨 골든): raw-floor 대비 평지형 스퍼리어스(행정공지·계획류 등) 추가 제거.
    """
    ck, cdup, ctau = graph_cfg()
    if k is None: k = ck
    if dup is None: dup = cdup
    if tau is None: tau = ctau
    idx = load_index()
    tgt = rel(os.path.abspath(path))
    if tgt not in idx:
        print(f"not indexed: {tgt}", file=sys.stderr); return []
    ns = notes(idx)
    mean = _global_mean(ns)             # 소표본(<2)이면 None → 센터링 스킵(raw)
    cv = ({rp: [_center(v, mean) for v in e["vecs"]] for rp, e in ns.items()}
          if mean else {rp: e["vecs"] for rp, e in ns.items()})
    tv = cv[tgt]
    rows = []
    for rp, e in ns.items():
        if rp == tgt: continue
        cos = max(dot(a, b) for a in tv for b in cv[rp])
        if cos >= dup: continue            # 색인중복 억제(Phase5 dedup 전 임시)
        rows.append((cos, rp, e.get("gist", "")))
    rows.sort(reverse=True)
    if not rows: return []
    out = [rows[0]]                        # top1 무조건 유지(고립방지)
    for cos, rp, g in rows[1:k]:
        if cos >= tau: out.append((cos, rp, g))  # 2~k위는 센터 절대임계 통과분만
    return out


# ════════ B1 writer: 의미이웃 → Obsidian 위키링크 관리블록 ════════
# 스코프 = Claude소유 지식노트만(1_수집 사용자저작·설계노트·기계파생 제외).
WRITER_GLOBS = [
    "2_지식/notes/**/*.md",
    "2_지식/modules/**/*.md",   # 모듈 산출물(2026-07-27 신설) — 교차링크가 차별점이라 이웃블록 필수
    "2_지식/sessions/**/*.md",
    "3_시스템/_ref/**/*.md",
]
# 링크 대상서 제외(기계파생 중복본 — 지식은 통찰노트에 있음). 그래프 오염 방지.
LINK_TARGET_EXCLUDE = ("3_시스템/_index/pdf-cache/", "3_시스템/_claude-memory/",
                       "2_지식/notes/설계노트.md", "2_지식/notes/사용자설명서.md")
# 검색은 되나 B1 위키링크 대상서 제외: pdf캐시·개인메모리(gitignore=배포 미포함→dangling 방지)·시스템문서(지식그래프 오염 방지)
# 블록 매치 = 3세대 공용 패턴(_BLOCK_ALT). 마이그레이션 시 구→신 무중복 교체.
LINK_BLOCK_RE = re.compile(_BLOCK_ALT, re.S)


def link_targets():
    seen = set()
    for g in WRITER_GLOBS:
        for p in glob.glob(os.path.join(VAULT, g), recursive=True):
            ap = os.path.abspath(p)
            if ap not in seen and ap.endswith(".md"):
                seen.add(ap); yield ap


def build_link_block(path):
    """이웃 → basename dedup → 위키링크 관리블록 문자열(이웃 없으면 None)."""
    links, used = [], set()
    for cos, rp, g in neighbors(path):
        if any(rp.startswith(x) for x in LINK_TARGET_EXCLUDE):
            continue
        name = os.path.splitext(os.path.basename(rp))[0]
        if name in used:
            continue
        used.add(name); links.append(name)
    if not links:
        return None
    inner = " · ".join(f"[[{n}]]" for n in links)
    # 접이식 콜아웃([!info]- = 기본 접힘). 마커 %%sl%%는 제목줄 인라인(reading·편집 양쪽서 숨음).
    # 링크는 콜아웃 본문(그래프 인덱싱 유지). 독립 주석줄 없음.
    return f"> [!info]- 관련 노트 %%sl%%\n> {inner}"


def apply_link_block(text, block):
    """기존 블록 교체(idempotent) 또는 EOF append. block=None이면 기존블록 제거."""
    if LINK_BLOCK_RE.search(text):
        if block is None:
            # 블록+선행 공백줄 제거
            return re.sub(r"\n*" + LINK_BLOCK_RE.pattern, "", text, flags=re.S).rstrip() + "\n"
        return LINK_BLOCK_RE.sub(lambda _: block, text)
    if block is None:
        return text
    return text.rstrip() + "\n\n" + block + "\n"


def write_links(dry=True):
    changed = 0
    for ap in link_targets():
        rp = rel(ap)
        if any(rp.startswith(x) for x in LINK_TARGET_EXCLUDE):
            continue  # 시스템문서(설계노트·사용자설명서) = 블록 안 씀(소스 제외, 대상 제외와 대칭)
        try:  # C3: strict 디코드 — 비UTF-8(cp949 등) 노트면 스킵(errors=replace로 U+FFFD 파괴 후 재기록 방지)
            with open(ap, "rb") as f: text = f.read().decode("utf-8")
        except UnicodeDecodeError:
            print(f"[skip] {rp} — 비UTF-8 인코딩, 링크블록 건너뜀(파괴 방지)", file=sys.stderr)
            continue
        block = build_link_block(ap)
        new = apply_link_block(text, block)
        if new == text:
            continue
        changed += 1
        if dry:
            preview = block.splitlines()[1] if block else "(블록 제거)"
            print(f"[dry] {rp}\n      {preview}")
        else:
            with open(ap, "w", encoding="utf-8", newline="\n") as f:  # LF 고정(Windows CRLF 플립 방지)
                f.write(new)
            print(f"[write] {rp}", file=sys.stderr)
    tag = "dry-run" if dry else "written"
    print(f"{tag}: {changed} notes", file=sys.stderr)
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reindex", action="store_true")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--q")
    ap.add_argument("--k", type=int, default=None)  # None → 브랜치별 기본(검색8·이웃3)
    ap.add_argument("--mode", default="hybrid", choices=["lexical", "vector", "hybrid"])
    ap.add_argument("--neighbors")
    ap.add_argument("--eval")
    ap.add_argument("--link-dryrun", action="store_true", help="B1 위키링크 블록 미리보기(파일 수정 0)")
    ap.add_argument("--link-write", action="store_true", help="B1 위키링크 관리블록 실기입")
    args = ap.parse_args()

    if args.rebuild: reindex(full=True)
    elif args.reindex: reindex(full=False)

    if args.link_write:
        write_links(dry=False)
    elif args.link_dryrun:
        write_links(dry=True)
    elif args.eval:
        evaluate(args.eval, k=args.k or 8)
    elif args.neighbors:
        for cos, rp, g in neighbors(args.neighbors, k=args.k):
            print(json.dumps({"path": rp, "cosine": round(cos, 4), "gist": g}, ensure_ascii=False))
    elif args.q:
        model, model_name = (None, None)
        if args.mode != "lexical":
            model, model_name = load_query_model()
        idx = load_index()
        for sc, rp in ranked(args.q, idx, args.mode, model, model_name)[:(args.k or 8)]:
            e = idx.get(rp, {})
            print(json.dumps({"path": rp, "score": round(sc, 4), "gist": e.get("gist", "")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
