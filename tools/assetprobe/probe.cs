using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;

/// <summary>
/// assetprobe —— 侦察工具（只读）：
///   types                 列出 SoulsFormats 里容器/贴图相关类型
///   bhd5                  打印 BHD5 的公开成员与 Game 枚举
///   try <bhd> <bdt>       用 BHD5 尝试读 NR 菜单贴图 binder，报真实错误
/// </summary>
class Probe
{
    static string SbDir;

    static int Main(string[] args)
    {
        try
        {
            SbDir = FindSmithbox();
            AppDomain.CurrentDomain.AssemblyResolve += Resolve;
            Run(args);
            return 0;
        }
        catch (Exception ex)
        {
            var e = ex is TargetInvocationException && ex.InnerException != null ? ex.InnerException : ex;
            Console.WriteLine("ERROR: " + e.GetType().Name + ": " + e.Message);
            return 1;
        }
    }

    static Assembly Resolve(object sender, ResolveEventArgs e)
    {
        string name = new AssemblyName(e.Name).Name + ".dll";
        string p = Path.Combine(SbDir, name);
        return File.Exists(p) ? Assembly.LoadFrom(p) : null;
    }

    static string FindSmithbox()
    {
        string env = Environment.GetEnvironmentVariable("SMITHBOX_DIR");
        if (!string.IsNullOrEmpty(env) && File.Exists(Path.Combine(env, "Andre.SoulsFormats.dll")))
            return env;
        string root = Environment.GetEnvironmentVariable("ERTOOLS_ROOT");
        if (string.IsNullOrEmpty(root)) root = @"E:\ERtools";
        var cands = Directory.GetDirectories(root, "Smithbox*")
            .Where(d => File.Exists(Path.Combine(d, "Andre.SoulsFormats.dll")))
            .OrderByDescending(d => Directory.GetLastWriteTime(d))
            .ToList();
        if (cands.Count > 0) return cands[0];
        throw new Exception("Smithbox not found");
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    static void Run(string[] args)
    {
        string mode = args.Length > 0 ? args[0].ToLowerInvariant() : "types";

        if (mode == "types")
        {
            var asm = typeof(SoulsFormats.SFUtil).Assembly;
            Type[] ts;
            try { ts = asm.GetTypes(); }
            catch (ReflectionTypeLoadException ex) { ts = ex.Types.Where(t => t != null).ToArray(); }
            Console.WriteLine($"types={ts.Length}");
            foreach (var t in ts.Where(t => t.Name.IndexOf("TPF", StringComparison.OrdinalIgnoreCase) >= 0
                                        || t.Name.IndexOf("BHD", StringComparison.OrdinalIgnoreCase) >= 0
                                        || t.Name.IndexOf("BHF", StringComparison.OrdinalIgnoreCase) >= 0)
                                  .OrderBy(t => t.FullName))
                Console.WriteLine("  " + t.FullName);
            return;
        }

        if (mode == "bhd5")
        {
            var t = typeof(SoulsFormats.BHD5);
            Console.WriteLine("== BHD5 members ==");
            foreach (var m in t.GetMembers(BindingFlags.Public | BindingFlags.Static | BindingFlags.Instance | BindingFlags.DeclaredOnly))
                Console.WriteLine($"  {m.MemberType,-10} {m}");
            Console.WriteLine("== Game enum ==");
            Type g = t.GetNestedType("Game");
            if (g != null) foreach (var n in Enum.GetNames(g)) Console.WriteLine("  " + n);
            Console.WriteLine("== nested types ==");
            foreach (var n in t.GetNestedTypes()) Console.WriteLine("  " + n.FullName);
            return;
        }

        if (mode == "dcx")
        {
            Console.WriteLine("== DCX static ==");
            foreach (var m in typeof(SoulsFormats.DCX).GetMethods(BindingFlags.Public | BindingFlags.Static))
                Console.WriteLine("  " + m);
            Console.WriteLine("== TPF static ==");
            foreach (var m in typeof(SoulsFormats.TPF).GetMethods(BindingFlags.Public | BindingFlags.Static))
                Console.WriteLine("  " + m);
            Console.WriteLine("== TPF instance ==");
            foreach (var m in typeof(SoulsFormats.TPF).GetMembers(BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly))
                Console.WriteLine("  " + m);
            Console.WriteLine("== TPF.Texture members ==");
            var tt = typeof(SoulsFormats.TPF).GetNestedType("Texture");
            if (tt != null) foreach (var m in tt.GetMembers(BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly))
                Console.WriteLine("  " + m);
            return;
        }

        if (mode == "list")
        {
            byte[] hdr = File.ReadAllBytes(args[1]);
            Type g = typeof(SoulsFormats.BHD5).GetNestedType("Game");
            object val = Enum.Parse(g, args.Length > 2 ? args[2] : "EldenRing");
            var method = typeof(SoulsFormats.BHD5).GetMethods()
                .First(mm => mm.Name == "Read" && mm.GetParameters().Length == 2);
            object bhd = method.Invoke(null, new object[] { (Memory<byte>)hdr, val });
            Type t = bhd.GetType();
            Console.WriteLine("salt=" + t.GetProperty("Salt").GetValue(bhd));
            var buckets = (System.Collections.IList)t.GetProperty("Buckets").GetValue(bhd);
            Console.WriteLine("buckets=" + buckets.Count);
            object b0 = buckets[0];
            Console.WriteLine("bucket props: " + string.Join(", ", b0.GetType().GetProperties().Select(p => p.Name)));
            var files0 = (System.Collections.IList)b0.GetType().GetProperty("Files").GetValue(b0);
            Console.WriteLine("files0=" + files0.Count);
            Console.WriteLine("file props: " + string.Join(", ", files0[0].GetType().GetProperties().Select(p => p.Name)));
            long total = 0; int cnt = 0;
            foreach (object b in buckets)
            {
                var fs = (System.Collections.IList)b.GetType().GetProperty("Files").GetValue(b);
                foreach (object f in fs) { total += Convert.ToInt64(f.GetType().GetProperty("Size").GetValue(f)); cnt++; }
            }
            Console.WriteLine($"files={cnt} totalBytes={total:N0}");
            return;
        }

        if (mode == "try")
        {
            string bhd = args[1], bdt = args[2];
            byte[] hdr = File.ReadAllBytes(bhd);
            byte[] dat = File.ReadAllBytes(bdt);
            Console.WriteLine($"bhd={hdr.Length:N0}  bdt={dat.Length:N0}");
            Type g = typeof(SoulsFormats.BHD5).GetNestedType("Game");
            foreach (var name in Enum.GetNames(g))
            {
                try
                {
                    var val = Enum.Parse(g, name);
                    var method = typeof(SoulsFormats.BHD5).GetMethods()
                        .FirstOrDefault(mm => mm.Name == "Read" && mm.GetParameters().Length == 2);
                    var res = method.Invoke(null, new object[] { (Memory<byte>)hdr, val });
                    Console.WriteLine($"[OK] {name}: {res}");
                }
                catch (Exception ex)
                {
                    var e = ex.InnerException ?? ex;
                    Console.WriteLine($"[FAIL] {name}: {e.GetType().Name}: {e.Message}");
                }
            }
            return;
        }

        Console.WriteLine("usage: probe types | probe bhd5 | probe try <bhd> <bdt>");
    }
}
