# -*- coding: utf-8 -*-
"""받은 파일 검사 — 볼트 밖에서 들어오는 파일(웹 수집 첨부 · 학교 LMS 받기 등)을 들이기 전에 잰다(LLM 0 · 망 0).

    import filecheck   # 3_시스템 이 sys.path 에 있을 때 · 또는 importlib 로 이 파일을 연다

잰다: 확장자 ↔ 실제 형식(앞 바이트 MAGIC) · 실행 파일(EXEC_EXT) · PDF 위험 이름(pdf_risks — 원문과 /ObjStm 만 풂) ·
압축 안 실행 파일·경로 조작·Office 매크로(zip_risks) · Windows Defender(defender) · sha256 · 1_수집 안 같은 파일(vault_hashes).
11-16 lms-intake.py(학교 LMS · 개인 층)에서 떼어 냄 — 본체 수집 엔진(web-collect)의 첨부 검사가 개인 대본을 불러 배포판에서
«첨부»를 켜면 FileNotFoundError 로 깨졌다. lms-intake 는 이 이름들을 그대로 다시 내준다.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import zipfile
import zlib

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXEC_EXT = {".exe", ".js", ".vbs", ".lnk", ".hta", ".scr", ".bat", ".cmd", ".ps1", ".msi", ".jar", ".com", ".wsf"}
MAGIC = {".pdf": [b"%PDF-"], ".zip": [b"PK\x03\x04"], ".docx": [b"PK\x03\x04"], ".pptx": [b"PK\x03\x04"],
         ".xlsx": [b"PK\x03\x04"], ".hwpx": [b"PK\x03\x04"], ".hwp": [b"\xd0\xcf\x11\xe0"], ".doc": [b"\xd0\xcf\x11\xe0"],
         ".ppt": [b"\xd0\xcf\x11\xe0"], ".xls": [b"\xd0\xcf\x11\xe0"], ".png": [b"\x89PNG"], ".jpg": [b"\xff\xd8\xff"],
         ".jpeg": [b"\xff\xd8\xff"]}
# /OpenAction 은 뺐다 — LaTeX(hyperref)가 «열 때 보여 줄 쪽»으로 늘 넣는다(10-25 실험 매뉴얼 9개 오탐).
# 그것이 실제로 위험한 동작을 부르면 아래 이름(/JavaScript·/Launch·/SubmitForm…)이 함께 잡힌다.
PDF_RISK = [b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile", b"/AA", b"/RichMedia", b"/XFA",
            b"/SubmitForm", b"/ImportData"]
DEFENDER = r"C:\Program Files\Windows Defender\MpCmdRun.exe"


def sha256(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def pdf_risks(data: bytes) -> dict:
    """원문과 객체 스트림(/ObjStm — 사전이 압축돼 숨는 곳)만 풀어 위험 이름을 센다.
    글꼴·그림 스트림은 풀지 않는다 — 이진 데이터에 «/AA/» 같은 바이트가 우연히 있다(10-25 강의 PDF 두 개에서 오탐 3건).
    이름 뒤는 사전 구분자(공백·<<·[·(·/ 다음 이름)여야 한다. /JS 는 /JavaScript 와 겹치므로 단어 경계로."""
    blobs = [data]
    for m in re.finditer(rb"stream\r?\n", data):
        end = data.find(b"endstream", m.end())
        if end < 0 or b"/ObjStm" not in data[max(0, m.start() - 300):m.start()]:
            continue
        try:
            blobs.append(zlib.decompress(data[m.end():end]))
        except zlib.error:
            pass
    hits = {}
    for name in PDF_RISK:
        pat = re.escape(name) + rb"(?=\s|<<|\[|\(|/[A-Z])"
        n = 0
        for b in blobs:
            for m in re.finditer(pat, b):
                # PowerPoint 는 수식마다 MathML 을 내장 파일로 넣는다(접근성) — 실행되지 않는 XML(10-25 강의 슬라이드 PDF 오탐)
                if name == b"/EmbeddedFile" and re.match(rb"\s*/Subtype\s*/(application#2Fmathml\+xml|text#2Fxml|application#2Fxml)", b[m.end():m.end() + 80]):
                    continue
                n += 1
        if n:
            hits[name.decode()] = n
    uris = sum(len(re.findall(rb"/URI\s*\(", b)) for b in blobs)
    return {"risky": hits, "external_links": uris}


def zip_risks(p: str) -> dict:
    out = {"exec": [], "traversal": [], "macro": False}
    try:
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                low = n.lower()
                if os.path.splitext(low)[1] in EXEC_EXT:
                    out["exec"].append(n)
                if n.startswith(("/", "\\")) or ".." in n.replace("\\", "/").split("/"):
                    out["traversal"].append(n)
                if low.endswith("vbaproject.bin"):
                    out["macro"] = True
    except zipfile.BadZipFile:
        out["bad_zip"] = True
    return out


def defender(path: str) -> str:
    if not os.path.exists(DEFENDER):
        return "unavailable"
    p = subprocess.run([DEFENDER, "-Scan", "-ScanType", "3", "-File", path, "-DisableRemediation"],
                       capture_output=True, text=True, encoding="mbcs", errors="replace",
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))    # 예약 작업에서 창이 번쩍이지 않게
    return {0: "clean", 2: "THREAT"}.get(p.returncode, f"code{p.returncode}")


def vault_hashes() -> dict:
    out = {}
    root = os.path.join(VAULT, "1_수집")
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x != "_색인"]
        for f in files:
            if f.lower().endswith(".md"):
                continue
            p = os.path.join(d, f)
            try:
                out.setdefault(sha256(p), os.path.relpath(p, VAULT))
            except OSError:
                pass
    return out
