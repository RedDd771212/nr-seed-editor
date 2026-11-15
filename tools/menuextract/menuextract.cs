using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;

static class MenuExtract
{
    static string GameRoot = @"C:\Program Files (x86)\Steam\steamapps\common\ELDEN RING NIGHTREIGN\Game";

    static void Main(string[] args)
    {
        string bdt = args[0];
        string outDir = args[1];
        bool namesOnly = args.Length > 2 && args[2] == "--names";
        Directory.CreateDirectory(outDir);
        string root = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        AppDomain.CurrentDomain.AssemblyResolve += (s, e) =>
        {
            string name = new AssemblyName(e.Name).Name;
            string p = Path.Combine(root, name + ".dll");
            if (File.Exists(p)) return Assembly.LoadFrom(p);
            string smith = @"E:\ERtools\Smithbox_2_2_5_2026_08_29_a";
            string p2 = Path.Combine(smith, name + ".dll");
            if (File.Exists(p2)) return Assembly.LoadFrom(p2);
            return null;
        };
        Run(bdt, outDir, namesOnly);
    }

    static void Run(string bdt, string outDir, bool namesOnly)
    {
        byte[] data = File.ReadAllBytes(bdt);
        var offs = new List<int>();
        for (int i = 0; i + 3 < data.Length; i++)
            if (data[i] == (byte)'D' && data[i + 1] == (byte)'C' && data[i + 2] == (byte)'X' && data[i + 3] == 0)
                offs.Add(i);
        Console.WriteLine($"DCX offsets: {offs.Count}");

        int ok = 0, fail = 0, texCount = 0;
        var byExt = new Dictionary<string, int>();
        var log = new StringBuilder();
        for (int k = 0; k < offs.Count; k++)
        {
            int off = offs[k];
            int len = (k + 1 < offs.Count ? offs[k + 1] : data.Length) - off;
            try
            {
                var mem = new Memory<byte>(data, off, len);
                byte[] raw = SoulsFormats.DCX.Decompress(mem).ToArray();
                if (raw.Length < 4 || raw[0] != (byte)'T' || raw[1] != (byte)'P' || raw[2] != (byte)'F')
                {
                    Console.WriteLine($"  #{k} off=0x{off:X} not TPF: {raw.Length} bytes head={BitConverter.ToString(raw, 0, Math.Min(16, raw.Length))}");
                    fail++;
                    continue;
                }
                var tpf = SoulsFormats.TPF.Read(raw);
                foreach (var t in tpf.Textures)
                {
                    string nm = string.IsNullOrWhiteSpace(t.Name) ? $"tex{texCount:D4}" : Sanitize(t.Name);
                    if (namesOnly) { Console.WriteLine(nm); texCount++; continue; }
                    string ext = ".dds";
                    byExt[ext] = byExt.GetValueOrDefault(ext) + 1;
                    string fn = Path.Combine(outDir, nm + ext);
                    int dup = 1;
                    while (File.Exists(fn))
                        fn = Path.Combine(outDir, nm + "_" + (dup++) + ext);
                    File.WriteAllBytes(fn, t.Headerize());
                    texCount++;
                }
                ok++;
            }
            catch (Exception ex)
            {
                fail++;
                if (fail <= 5) Console.WriteLine($"  #{k} off=0x{off} FAILED: {ex.GetType().Name}: {ex.Message}");
            }
        }
        Console.WriteLine($"TPF ok={ok} fail={fail} textures={texCount}");
        foreach (var kv in byExt) Console.WriteLine($"  {kv.Key}: {kv.Value}");
    }

    static string Sanitize(string s)
    {
        var sb = new StringBuilder();
        foreach (char c in s) sb.Append(Path.GetInvalidFileNameChars().Contains(c) ? '_' : c);
        return sb.ToString().Trim();
    }
}
