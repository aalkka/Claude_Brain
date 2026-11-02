# -*- coding: utf-8 -*-
"""**docpdf** — docx → PDF(Word · 2026-11-03). 끝난 보고서 작업에서 PDF 만 남길 때 fileops 계획(`pdf`)이 부른다.

왜 Word: 제출본을 만드는 프로그램과 같은 조판이다. 보이지 않는 창에서 읽기 전용으로 연다(원본을 고치지 않는다).
실패하면 예외를 낸다 — 계획이 거기서 멈춰 docx 를 지우지 않는다.

  py -3 3_시스템/docpdf.py <docx> <pdf>
"""
import os
import shutil
import subprocess
import sys
import tempfile

# 함수를 쓰지 않는다 — 함수 안에서 바깥 COM 객체가 null 로 보인다(brain-source verify_docx_word.ps1 · 10-15)
# Quit() 은 인자 없이 — PS 5.1 의 Quit(0) 은 «PSReference» 예외로 실패해 숨은 Word 가 남는다(11-03 실측)
PS = r"""
param([string]$src, [string]$dst)
$ErrorActionPreference = 'Stop'
$wd = New-Object -ComObject Word.Application
try {
    for ($i = 0; $i -lt 60; $i++) { try { if ($null -ne $wd.Documents) { break } } catch { }; Start-Sleep -Milliseconds 500 }
    $wd.Visible = $false
    $wd.DisplayAlerts = 0
    $d = $wd.Documents.Open($src, $false, $true, $false)
    $d.ExportAsFixedFormat($dst, 17)
    $d.Close(0)
} finally {
    for ($i = 0; $i -lt 20; $i++) { try { $wd.Quit(); break } catch { Start-Sleep -Milliseconds 500 } }
}
"""


def to_pdf(src, dst, timeout=180):
    """src(docx) → dst(pdf) · 실패하면 RuntimeError(까닭 한 줄)."""
    d = tempfile.mkdtemp(prefix="docpdf-")
    try:
        ps1 = os.path.join(d, "to_pdf.ps1")
        with open(ps1, "w", encoding="utf-8-sig", newline="\n") as f:
            f.write(PS)
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, os.path.abspath(src), os.path.abspath(dst)],
                               capture_output=True, timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            raise RuntimeError("Word 가 %d초 안에 끝내지 못함" % timeout)
        except OSError as e:
            raise RuntimeError("PowerShell 을 못 띄움: %s" % e)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    if r.returncode != 0:
        lines = r.stderr.decode("utf-8", "replace").strip().splitlines()
        raise RuntimeError(lines[0][:160] if lines else "Word 변환 실패(종료 %d)" % r.returncode)
    try:
        with open(dst, "rb") as f:
            if f.read(5) != b"%PDF-":
                raise RuntimeError("만든 파일이 PDF 가 아님")
    except OSError:
        raise RuntimeError("PDF 가 만들어지지 않음")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    to_pdf(sys.argv[1], sys.argv[2])
