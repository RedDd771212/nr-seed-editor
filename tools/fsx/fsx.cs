using System;
using System.IO;
using System.Linq;
using System.Reflection;

static class Fsx
{
    static string SbDir;

    static void Main(string[] args)
    {
        SbDir = FindSmithbox();
        AppDomain.CurrentDomain.AssemblyResolve += Resolve;
        try { Run(args); }
        catch (Exception ex)
        {
            var e = ex is TargetInvocationException && ex.InnerException != null ? ex.InnerException : ex;
            Console.WriteLine("ERROR: " + e.GetType().Name + ": " + e.Message);
            Environment.Exit(1);
        }
    }

    static Assembly Resolve(object s, ResolveEventArgs e)
    {
        string p = Path.Combine(SbDir, new AssemblyName(e.Name).Name + ".dll");
        return File.Exists(p) ? Assembly.LoadFrom(p) : null;
    }

    static string FindSmithbox()
    {
        string root = Environment.GetEnvironmentVariable("ERTOOLS_ROOT") ?? @"E:\ERtools";
        var c = Directory.GetDirectories(root, "Smithbox*")
            .Where(d => File.Exists(Path.Combine(d, "Andre.SoulsFormats.dll")))
            .OrderByDescending(Directory.GetLastWriteTime).FirstOrDefault();
        if (c == null) throw new Exception("Smithbox not found");
        return c;
    }

    static void Run(string[] a)
    {
        string cmd = a[0].ToLowerInvariant();
        if (cmd == "dcx")
        {
            byte[] b = File.ReadAllBytes(a[1]);
            byte[] raw = SoulsFormats.DCX.Decompress(b).ToArray();
            File.WriteAllBytes(a[2], raw);
            Console.WriteLine($"{a[1]} -> {a[2]} ({b.Length:N0} -> {raw.Length:N0})");
            return;
        }
        if (cmd == "bnd")
        {
            byte[] b = File.ReadAllBytes(a[1]);
            if (SoulsFormats.DCX.Is(b)) b = SoulsFormats.DCX.Decompress(b).ToArray();
            var bnd = SoulsFormats.BND4.Read(b);
            string dir = a.Length > 2 ? a[2] : null;
            if (dir != null) Directory.CreateDirectory(dir);
            foreach (var f in bnd.Files)
            {
                Console.WriteLine($"  {f.Name}  {f.Bytes.Length:N0} bytes");
                if (dir != null)
                {
                    var invalid = Path.GetInvalidFileNameChars();
                    string safe = new string(f.Name.Select(c => invalid.Contains(c) ? '_' : c).ToArray());
                    File.WriteAllBytes(Path.Combine(dir, safe + ".bin"), f.Bytes.ToArray());
                }
            }
            Console.WriteLine($"BND4 files={bnd.Files.Count}");
            return;
        }
        if (cmd == "tpf")
        {
            byte[] b = File.ReadAllBytes(a[1]);
            if (SoulsFormats.DCX.Is(b)) b = SoulsFormats.DCX.Decompress(b).ToArray();
            var tpf = SoulsFormats.TPF.Read(b);
            string dir = a.Length > 2 ? a[2] : null;
            if (dir != null) Directory.CreateDirectory(dir);
            foreach (var t in tpf.Textures)
            {
                string nm = string.IsNullOrWhiteSpace(t.Name) ? "tex" : t.Name;
                Console.WriteLine($"  {nm}  fmt={t.Format} type={t.Type} mips={t.Mipmaps}");
                if (dir != null) File.WriteAllBytes(Path.Combine(dir, nm + ".dds"), t.Headerize());
            }
            return;
        }
        Console.WriteLine("usage: fsx dcx <in> <out> | fsx tpf <in> [outdir]");
    }
}
