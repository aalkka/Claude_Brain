// 가짜 claude.exe 껍데기 — 같은 폴더 fake_claude.py 를 py -3 로 부르고 표준 입출력을 그대로 잇는다(시험 전용).
// .exe 여야 하는 까닭: 옵시디언(node spawn)은 .cmd·.bat 를 셸 없이 못 띄운다. 만들기 = subguard_check.py 가 csc 로(산출은 시험 폴더 · git 밖).
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;

class FakeClaude {
    static string Q(string a) {
        if (a.Length > 0 && a.IndexOfAny(new[] { ' ', '\t', '"' }) < 0) return a;
        var sb = new StringBuilder("\"");
        int bs = 0;
        foreach (char c in a) {
            if (c == '\\') { bs++; continue; }
            if (c == '"') { sb.Append('\\', bs * 2 + 1); sb.Append('"'); bs = 0; continue; }
            sb.Append('\\', bs); bs = 0; sb.Append(c);
        }
        sb.Append('\\', bs * 2); sb.Append('"');
        return sb.ToString();
    }

    static void Pump(Stream from, Stream to, bool closeTo) {
        var buf = new byte[65536];
        try {
            int n;
            while ((n = from.Read(buf, 0, buf.Length)) > 0) { to.Write(buf, 0, n); to.Flush(); }
        } catch (IOException) { }
        if (closeTo) try { to.Close(); } catch (IOException) { }
    }

    static int Main(string[] args) {
        string dir = AppDomain.CurrentDomain.BaseDirectory;
        var cl = new StringBuilder("-3 -u -X utf8 " + Q(Path.Combine(dir, "fake_claude.py")));
        foreach (var a in args) cl.Append(' ').Append(Q(a));
        Console.InputEncoding = new UTF8Encoding(false);   // 자식 stdin 쓰개가 BOM 을 앞에 붙여 첫 JSON 줄이 깨졌다(11-11 잼)
        var psi = new ProcessStartInfo("py.exe", cl.ToString()) {
            UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
        };
        var p = Process.Start(psi);
        var tin = new Thread(() => Pump(Console.OpenStandardInput(), p.StandardInput.BaseStream, true)) { IsBackground = true };
        var tout = new Thread(() => Pump(p.StandardOutput.BaseStream, Console.OpenStandardOutput(), false));
        var terr = new Thread(() => Pump(p.StandardError.BaseStream, Console.OpenStandardError(), false));
        tin.Start(); tout.Start(); terr.Start();
        p.WaitForExit();
        tout.Join(); terr.Join();
        return p.ExitCode;
    }
}
