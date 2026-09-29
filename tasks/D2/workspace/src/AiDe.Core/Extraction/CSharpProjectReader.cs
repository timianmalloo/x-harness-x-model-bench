using System.Text.Json;
using System.Xml.Linq;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;

namespace AiDe.Core.Extraction;

/// <summary>Why a compilation could not see everything a build would.</summary>
/// <remarks>
/// These are the extractor's <b>disclosures</b>. Each becomes a fact on the scope, so a projection
/// over an affected scope reports the omission instead of answering as though nothing were missing.
/// A silently incomplete answer is the failure mode this whole design exists to avoid.
/// </remarks>
public static class ExtractionDisclosures
{
    /// <summary>No <c>obj/project.assets.json</c>: package types are unresolved.</summary>
    public const string PackagesNotRestored = "packages-not-restored";

    /// <summary>A WPF project's XAML-generated partial members are not analysed.</summary>
    public const string XamlGeneratedMembersNotAnalysed = "xaml-generated-members-not-analysed";

    /// <summary>Source generators are never run, so generated symbols are absent (S2/S1).</summary>
    public const string GeneratedCodeNotAnalysed = "generated-code-not-analysed";

    /// <summary>A <c>ProjectReference</c> could not be resolved; edges into it are missing.</summary>
    public const string ProjectReferenceUnresolved = "project-reference-unresolved";

    /// <summary>
    /// A source file did not parse, so every type in it is absent from the graph.
    /// </summary>
    /// <remarks>
    /// <b>The state a developer is in most often, and it was invisible.</b> Measured on a copy of a
    /// real repository with one deliberate syntax error: the index reported <c>10 of 10 scopes, 0
    /// failed</c> and produced 106 fewer assertions than the working copy, with nothing anywhere
    /// saying a file had not been read. Roslyn parses broken source into a tree with error nodes
    /// rather than throwing, so the extraction succeeds and simply finds less — which is
    /// indistinguishable from a smaller file (DC-025).
    /// </remarks>
    public const string SourceDidNotParse = "source-did-not-parse";

    /// <summary>
    /// A property carried a <c>Condition</c> that was taken at face value rather than evaluated.
    /// </summary>
    /// <remarks>
    /// Evaluating conditions IS MSBuild evaluation, which this design refuses. Taking them at face
    /// value is right far more often than it is wrong — but when it is wrong it changes which code
    /// compiles, so it is stated rather than assumed away.
    /// </remarks>
    public const string BuildConditionsNotEvaluated = "build-conditions-not-evaluated";

    /// <summary>A Bicep resource name is an expression only the compiler could resolve.</summary>
    public const string BicepExpressionsNotEvaluated = "bicep-expressions-not-evaluated";

    /// <summary>
    /// A template declares loops or conditional resources, so the DECLARATION count is not the
    /// deployment count.
    /// </summary>
    /// <remarks>
    /// A <c>[for ...]</c> resource becomes one deployed resource per item in a collection nothing
    /// here evaluates, and an <c>if (...)</c> resource may not be deployed at all. Reporting "24
    /// resources" for a template that deploys forty, or eighteen, would be a confident wrong number.
    /// </remarks>
    public const string BicepResourceCountIndeterminate = "bicep-resource-count-indeterminate";

    /// <summary>
    /// The schema is what the migrations INTEND, not what a server holds.
    /// </summary>
    /// <remarks>
    /// They diverge — a hand-applied change, a failed deployment, a database restored from an older
    /// backup — and a join that pretended otherwise would be exactly the inferred-edge failure this
    /// phase is most exposed to.
    /// </remarks>
    public const string SchemaFromMigrationsNotDatabase = "schema-from-migrations-not-database";

    /// <summary>
    /// A migration changed the schema through raw <c>Sql()</c>, which is not legible as syntax.
    /// </summary>
    /// <remarks>
    /// Owed by the spike rather than invented here: the corpus repository has four such statements,
    /// and they create indexes and move data. A fold that stayed silent about them would report a
    /// schema that looks complete.
    /// </remarks>
    public const string SchemaChangedByRawSqlNotRead = "schema-changed-by-raw-sql-not-read";
}

/// <summary>One project, compiled for one target framework, plus what could not be seen.</summary>
public sealed record CSharpCompilationResult(
    Compilation? Compilation,
    string TargetFramework,
    IReadOnlyList<string> Disclosures,
    IReadOnlyList<string> Notes);

/// <summary>
/// Reads a C# project file <b>as data</b> and produces a Roslyn compilation from it.
/// </summary>
/// <remarks>
/// <para><b>Nothing here evaluates MSBuild or runs a target.</b> That is the entire point: spike D3
/// measured that loading a repository through <c>MSBuildWorkspace</c> executes code the repository
/// supplied — an <c>Exec</c> in <c>InitialTargets</c> or a <c>RoslynCodeTaskFactory</c> inline task
/// needs nothing but a checked-in <c>.csproj</c>. Reading the file as XML cannot do that.</para>
///
/// <para><b>Measured at parity, not assumed.</b> Against <c>MSBuildWorkspace</c> on four project
/// shapes — plain, <c>ProjectReference</c>+WPF, <c>ProjectReference</c>, and multi-targeted — this
/// recovers 100% of dependency edges and loses no types, ~25x faster
/// (<c>spikes/extraction-fidelity</c>).</para>
/// </remarks>
public sealed class CSharpProjectReader
{
    /// <summary>How deep <c>ProjectReference</c> recursion may go before it is disclosed and stopped.</summary>
    /// <remarks>
    /// <c>simplify: recursive ProjectReference compilation rather than a build-order graph; ceiling is
    /// a depth of 8; upgrade trigger = a real repository exceeds it, or the repeated sub-compilation
    /// shows up in P2-PERF-01.</c>
    /// </remarks>
    private const int MaxReferenceDepth = 8;

    /// <summary>
    /// Parsed trees, reused across index runs for files that have not changed.
    /// </summary>
    /// <remarks>
    /// Per reader instance, so a long-lived daemon keeps it and a one-shot spike does not leak it.
    /// Parsing is ~96% of everything extraction does — profiled twice — which is what makes this the
    /// one cache worth having and every other one premature.
    /// </remarks>
    public SyntaxTreeCache Trees { get; } = new();

    /// <summary>Every target framework the project declares. One scope per (project, framework).</summary>
    /// <remarks>
    /// Not per project: a multi-targeted project's <c>#if</c>-gated types genuinely differ between
    /// frameworks, so a single scope would have to pick one and be silently wrong about the others.
    /// Measured — <c>MSBuildWorkspace</c> loads one framework and sees one of two conditional types.
    /// </remarks>
    public IReadOnlyList<string> TargetFrameworks(string projectPath)
    {
        var context = Context(projectPath);
        if (context is null) return [];

        var many = Property(context, "TargetFrameworks");
        if (!string.IsNullOrWhiteSpace(many))
        {
            return many.Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).ToList();
        }

        var one = Property(context, "TargetFramework");
        return string.IsNullOrWhiteSpace(one) ? ["net10.0"] : [one];
    }

    public CSharpCompilationResult Compile(string projectPath, string targetFramework, CancellationToken cancellationToken)
    {
        var disclosures = new List<string>();
        var notes = new List<string>();

        // Source generators are never run — there is no analyzer host at all here — so their symbols
        // are absent by construction. Disclosed always, because "absent" must never read as "none".
        disclosures.Add(ExtractionDisclosures.GeneratedCodeNotAnalysed);

        var compilation = Build(
            projectPath, targetFramework, disclosures, notes,
            new Dictionary<string, Compilation>(StringComparer.OrdinalIgnoreCase), 0, cancellationToken);

        return new CSharpCompilationResult(
            compilation, targetFramework, disclosures.Distinct(StringComparer.Ordinal).ToList(), notes);
    }

    private Compilation? Build(
        string projectPath, string tfm, List<string> disclosures, List<string> notes,
        Dictionary<string, Compilation> visited, int depth, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();

        var full = Path.GetFullPath(projectPath);
        if (visited.TryGetValue(full, out var already)) return already;

        if (depth > MaxReferenceDepth)
        {
            disclosures.Add(ExtractionDisclosures.ProjectReferenceUnresolved);
            notes.Add($"project-reference depth limit ({MaxReferenceDepth}) reached at {Path.GetFileName(full)}");
            return null;
        }

        var context = Context(full);
        if (context is null)
        {
            notes.Add($"could not parse {Path.GetFileName(full)} as XML");
            return null;
        }

        var doc = context.Project;
        var dir = Path.GetDirectoryName(full)!;

        if (context.HadConditions)
        {
            disclosures.Add(ExtractionDisclosures.BuildConditionsNotEvaluated);
        }

        var parse = new CSharpParseOptions(preprocessorSymbols: Defines(context, tfm));

        // The read phase is 98% of extraction; this splits it again, into PARSING and everything
        // else, because "the read is the cost" would send the next optimisation at whichever half a
        // guess picked. A tree cache is only worth building if parsing is the part that dominates.
        var parseWatch = new System.Diagnostics.Stopwatch();
        var ioWatch = new System.Diagnostics.Stopwatch();

        var trees = new List<SyntaxTree>();
        var unparsed = new List<string>();

        // Enumeration timed on its own. Raw File.ReadAllText of 120 files costs ~5ms outside this
        // process, and the in-extractor "read" timer said 600ms — a hundredfold gap that has to be
        // somewhere, and a lazy IEnumerable evaluated inside the loop is the obvious candidate.
        var sourcesWatch = System.Diagnostics.Stopwatch.StartNew();
        var sources = Sources(doc, dir).ToList();
        sourcesWatch.Stop();

        foreach (var file in sources)
        {
            cancellationToken.ThrowIfCancellationRequested();
            try
            {
                // DISK and PARSE timed apart. They were together, and the first conclusion drawn
                // from that timer — "parsing is 97% of the read" — could not distinguish a slow
                // parser from a cold file cache. Two numbers with opposite remedies.
                var tree = Trees.GetOrParse(file, parse, path =>
                {
                    ioWatch.Start();
                    var text = File.ReadAllText(path);
                    ioWatch.Stop();

                    parseWatch.Start();
                    var parsed = CSharpSyntaxTree.ParseText(text, parse, path: path);
                    parseWatch.Stop();
                    return parsed;
                });

                trees.Add(tree);

                // Roslyn does not throw on broken source: it returns a tree with error nodes, and
                // the types inside are simply not there. The extraction then succeeds and finds
                // less, which looks exactly like a smaller file. Counted here so the scope can say
                // so — the file is still parsed and its good parts still contribute, because half a
                // file's evidence is better than none as long as the gap is stated.
                if (tree.GetDiagnostics().Any(d => d.Severity == DiagnosticSeverity.Error))
                {
                    unparsed.Add(Path.GetFileName(file));
                }
            }
            catch (IOException ex)
            {
                notes.Add($"unreadable source {Path.GetFileName(file)}: {ex.Message}");
                unparsed.Add(Path.GetFileName(file));
            }
        }

        if (Environment.GetEnvironmentVariable("AIDE_EXTRACTION_TIMING") is not null)
        {
            Console.Error.WriteLine(
                $"[timing]   enumerate {sourcesWatch.ElapsedMilliseconds}ms, read {ioWatch.ElapsedMilliseconds}ms, " +
                $"parse {parseWatch.ElapsedMilliseconds}ms " +
                $"for {trees.Count} file(s) ({Trees.Hits:N0} reused, {Trees.Misses:N0} parsed)");
        }

        if (unparsed.Count > 0)
        {
            // Named with a count, because "some source did not parse" and "47 files did not parse"
            // are different statements about how much of the project is missing from the graph.
            disclosures.Add($"{ExtractionDisclosures.SourceDidNotParse} ({unparsed.Count:N0} file(s): " +
                            string.Join(", ", unparsed.Take(3)) +
                            (unparsed.Count > 3 ? ", …" : string.Empty) + ")");
        }

        // ImplicitUsings are generated by the SDK into obj/, which this reader does not read.
        // Reproducing the documented set is reading a specification, not evaluating the project —
        // and without it every Console, Task and IReadOnlyList in a modern project is unresolved.
        var usings = ImplicitUsings(context);
        if (usings.Count > 0)
        {
            var text = string.Concat(usings.Select(u => $"global using global::{u};\n"));
            trees.Add(CSharpSyntaxTree.ParseText(text, parse, path: "__ImplicitUsings.g.cs"));
        }

        if (IsWpf(context) && Directory.EnumerateFiles(dir, "*.xaml", SearchOption.AllDirectories).Any())
        {
            disclosures.Add(ExtractionDisclosures.XamlGeneratedMembersNotAnalysed);
        }

        var references = new List<MetadataReference>();
        references.AddRange(FrameworkReferences(context, tfm, notes));
        references.AddRange(PackageReferences(dir, disclosures, notes, depth));

        // Placeholder before recursing, so a reference cycle terminates instead of stack-overflowing.
        visited[full] = CSharpCompilation.Create(Path.GetFileNameWithoutExtension(full));

        foreach (var referenced in ProjectReferences(doc, dir))
        {
            var child = Build(
                referenced, BestTargetFramework(referenced, tfm), disclosures, notes,
                visited, depth + 1, cancellationToken);

            if (child is not null)
            {
                references.Add(child.ToMetadataReference());
            }
            else
            {
                disclosures.Add(ExtractionDisclosures.ProjectReferenceUnresolved);
                notes.Add($"unresolved ProjectReference: {Path.GetFileName(referenced)}");
            }
        }

        var compilation = CSharpCompilation.Create(
            Path.GetFileNameWithoutExtension(full), trees, references,
            new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary));

        visited[full] = compilation;
        return compilation;
    }

    // ---------------------------------------------------------------- the project file, as data

    private static XDocument? Load(string path)
    {
        try { return XDocument.Load(path); }
        catch (Exception ex) when (ex is IOException or System.Xml.XmlException) { return null; }
    }

    /// <summary>
    /// A property as the compiler would see it: the project's own value, else the nearest
    /// <c>Directory.Build.props</c>'s.
    /// </summary>
    /// <remarks>
    /// <para><b>Measured necessity, not completeness for its own sake.</b> Against a real repository
    /// (TheTerrace) five test classes were missing because <c>REHEARSAL</c> is defined in
    /// <c>Directory.Build.props</c> and nothing here read it — the types were simply compiled out.
    /// A whole feature's tests vanishing from the graph is exactly the silent incompleteness this
    /// design exists to prevent.</para>
    ///
    /// <para><b>Conditions are NOT evaluated.</b> Evaluating <c>Condition="'$(X)' == 'true'"</c> is
    /// MSBuild evaluation, which is the thing this design refuses. A conditioned property is taken
    /// at face value and the scope <b>discloses</b> that it was, so a wrong answer is a stated one.
    /// </para>
    /// </remarks>
    private static string? Property(ProjectContext context, string name) =>
        Local(context.Project, name) ?? (context.Inherited is null ? null : Local(context.Inherited, name));

    private static string? Local(XDocument? doc, string name) =>
        doc?.Descendants(name).Select(e => e.Value).FirstOrDefault(v => !string.IsNullOrWhiteSpace(v));

    /// <summary>A project plus the <c>Directory.Build.props</c> it inherits from, if any.</summary>
    private sealed record ProjectContext(XDocument Project, XDocument? Inherited, bool HadConditions);

    /// <summary>
    /// The nearest <c>Directory.Build.props</c> at or above <paramref name="startDirectory"/>.
    /// </summary>
    /// <remarks>
    /// Nearest only, which is MSBuild's own default: the SDK imports the first one it finds walking
    /// up and stops. A props file that chains to its parent does so with an explicit Import, and
    /// following those is not attempted — it is disclosed instead of guessed.
    /// </remarks>
    private static XDocument? FindDirectoryBuildProps(string startDirectory)
    {
        var directory = new DirectoryInfo(startDirectory);

        while (directory is not null)
        {
            var candidate = Path.Combine(directory.FullName, "Directory.Build.props");
            if (File.Exists(candidate))
            {
                var doc = Load(candidate);
                if (doc is not null) return doc;
            }

            directory = directory.Parent;
        }

        return null;
    }

    private static bool IsTrue(ProjectContext context, string name) =>
        string.Equals(Property(context, name), "true", StringComparison.OrdinalIgnoreCase);

    private static bool IsWpf(ProjectContext context) => IsTrue(context, "UseWPF");

    /// <summary>
    /// Whether this project implicitly or explicitly references ASP.NET Core.
    /// </summary>
    /// <remarks>
    /// The SDK attribute is the implicit route (<c>Microsoft.NET.Sdk.Web</c> and the Razor/Worker
    /// SDKs), and <c>&lt;FrameworkReference&gt;</c> the explicit one. Both are read because a class
    /// library that opts in explicitly is as common as a web app that gets it from its SDK.
    /// </remarks>
    private static bool UsesAspNetCore(ProjectContext context)
    {
        var sdk = (string?)context.Project.Root?.Attribute("Sdk") ?? string.Empty;
        if (sdk.Contains("Sdk.Web", StringComparison.OrdinalIgnoreCase) ||
            sdk.Contains("Sdk.Razor", StringComparison.OrdinalIgnoreCase) ||
            sdk.Contains("Sdk.Worker", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        return context.Project.Descendants("FrameworkReference")
            .Select(e => (string?)e.Attribute("Include"))
            .Any(v => v is not null && v.Contains("AspNetCore", StringComparison.OrdinalIgnoreCase));
    }

    /// <summary>Loads a project and the nearest <c>Directory.Build.props</c> above it.</summary>
    private static ProjectContext? Context(string projectPath)
    {
        var doc = Load(projectPath);
        if (doc is null) return null;

        var directory = Path.GetDirectoryName(Path.GetFullPath(projectPath));
        var inherited = directory is null ? null : FindDirectoryBuildProps(directory);

        var conditioned =
            doc.Descendants().Any(e => e.Attribute("Condition") is not null) ||
            (inherited?.Descendants().Any(e => e.Attribute("Condition") is not null) ?? false);

        return new ProjectContext(doc, inherited, conditioned);
    }

    private static string Normalise(string p) => p.Replace((char)92, '/');

    private static List<string> Sources(XDocument doc, string dir)
    {
        var removed = doc.Descendants("Compile")
            .Select(e => (string?)e.Attribute("Remove"))
            .Where(v => !string.IsNullOrWhiteSpace(v))
            .Select(v => Normalise(v!).TrimEnd('*', '/'))
            .ToList();

        var included = doc.Descendants("Compile")
            .Select(e => (string?)e.Attribute("Include"))
            .Where(v => !string.IsNullOrWhiteSpace(v) && !v!.Contains('*'))
            .Select(v => Path.GetFullPath(Path.Combine(dir, v!)))
            .Where(File.Exists);

        var globbed = Directory
            .EnumerateFiles(dir, "*.cs", SearchOption.AllDirectories)
            .Where(f =>
            {
                var rel = Normalise(Path.GetRelativePath(dir, f));
                if (rel.StartsWith("bin/", StringComparison.OrdinalIgnoreCase)) return false;
                if (rel.StartsWith("obj/", StringComparison.OrdinalIgnoreCase)) return false;
                return !removed.Any(r => rel.StartsWith(r, StringComparison.OrdinalIgnoreCase));
            });

        return globbed.Concat(included).Distinct(StringComparer.OrdinalIgnoreCase).ToList();
    }

    private static List<string> ProjectReferences(XDocument doc, string dir) =>
        doc.Descendants("ProjectReference")
            .Select(e => (string?)e.Attribute("Include"))
            .Where(v => !string.IsNullOrWhiteSpace(v))
            .Select(v => Path.GetFullPath(Path.Combine(dir, v!)))
            .Where(File.Exists)
            .ToList();

    private static List<string> ImplicitUsings(ProjectContext context)
    {
        var doc = context.Project;
        var result = new List<string>();
        var enabled = Property(context, "ImplicitUsings");

        if (string.Equals(enabled, "enable", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(enabled, "true", StringComparison.OrdinalIgnoreCase))
        {
            result.AddRange([
                "System", "System.Collections.Generic", "System.IO", "System.Linq",
                "System.Net.Http", "System.Threading", "System.Threading.Tasks",
            ]);

            if (UsesAspNetCore(context))
            {
                result.AddRange([
                    "System.Net.Http.Json", "Microsoft.AspNetCore.Builder",
                    "Microsoft.AspNetCore.Hosting", "Microsoft.AspNetCore.Http",
                    "Microsoft.AspNetCore.Routing", "Microsoft.Extensions.Configuration",
                    "Microsoft.Extensions.DependencyInjection", "Microsoft.Extensions.Hosting",
                    "Microsoft.Extensions.Logging",
                ]);
            }

            if (IsWpf(context))
            {
                result.AddRange([
                    "System.Windows", "System.Windows.Controls", "System.Windows.Data",
                    "System.Windows.Documents", "System.Windows.Input", "System.Windows.Media",
                ]);
            }

            if (IsTrue(context, "UseWindowsForms"))
            {
                result.AddRange(["System.Drawing", "System.Windows.Forms"]);
            }
        }

        result.AddRange(doc.Descendants("Using")
            .Select(e => (string?)e.Attribute("Include"))
            .Where(v => !string.IsNullOrWhiteSpace(v))
            .Select(v => v!.Trim()));

        return result.Distinct(StringComparer.Ordinal).ToList();
    }

    /// <summary>The preprocessor symbols the compiler would see, synthesised from the TFM.</summary>
    private static List<string> Defines(ProjectContext context, string tfm)
    {
        var symbols = new List<string>();
        var bare = tfm.Split('-')[0];
        var moniker = bare.ToUpperInvariant().Replace('.', '_');

        if (moniker.StartsWith("NETSTANDARD", StringComparison.Ordinal))
        {
            symbols.Add(moniker);
            symbols.Add("NETSTANDARD");
        }
        else if (moniker.StartsWith("NET", StringComparison.Ordinal) && Version.TryParse(bare[3..], out var v))
        {
            symbols.Add(moniker);
            symbols.Add("NET");
            symbols.Add("NETCOREAPP");
            for (var major = 5; major <= v.Major; major++)
            {
                var minorMax = major == v.Major ? v.Minor : 0;
                for (var minor = 0; minor <= minorMax; minor++)
                {
                    symbols.Add($"NET{major}_{minor}_OR_GREATER");
                }
            }
        }

        if (tfm.Contains("-windows", StringComparison.OrdinalIgnoreCase)) symbols.Add("WINDOWS");

        // BOTH the project's and the inherited file's constants, because DefineConstants ACCUMULATES
        // in MSBuild ($(DefineConstants);EXTRA). Taking only the nearest one silently dropped
        // REHEARSAL on a real repository and five test classes disappeared from the graph with it.
        foreach (var declared in new[] { Property(context, "DefineConstants"), Local(context.Inherited, "DefineConstants") })
        {
            if (string.IsNullOrWhiteSpace(declared)) continue;

            // $(…) references are MSBuild expressions; evaluating them is exactly what this design
            // refuses to do, so they are skipped rather than guessed at.
            symbols.AddRange(declared
                .Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Where(x => !x.StartsWith("$(", StringComparison.Ordinal)));
        }

        return symbols.Distinct(StringComparer.Ordinal).ToList();
    }

    private string BestTargetFramework(string referencedProject, string preferred)
    {
        var available = TargetFrameworks(referencedProject);
        if (available.Count == 0) return preferred;
        if (available.Contains(preferred, StringComparer.OrdinalIgnoreCase)) return preferred;

        // A net10.0-windows consumer is satisfied by a net10.0 dependency.
        var bare = preferred.Split('-')[0];
        return available.FirstOrDefault(a => a.Split('-')[0].Equals(bare, StringComparison.OrdinalIgnoreCase))
            ?? available[0];
    }

    // ---------------------------------------------------------------- references

    private static List<MetadataReference> FrameworkReferences(ProjectContext context, string tfm, List<string> notes)
    {
        var doc = context.Project;
        var refs = new List<MetadataReference>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var bare = tfm.Split('-')[0];

        var wanted = bare.StartsWith("net", StringComparison.OrdinalIgnoreCase) &&
                     Version.TryParse(bare.Length > 3 ? bare[3..] : string.Empty, out var v)
            ? v
            : null;

        // The desktop pack goes FIRST when it applies. Both packs ship a WindowsBase.dll — the base
        // pack's is a 4.0.0.0 facade, the desktop pack's the real 10.0.0.0 assembly — and adding the
        // base pack first lets the facade win on filename, producing CS1705 on every WPF type.
        if ((IsWpf(context) || IsTrue(context, "UseWindowsForms")) &&
            tfm.Contains("-windows", StringComparison.OrdinalIgnoreCase))
        {
            var desktop = RefPack("Microsoft.WindowsDesktop.App.Ref", wanted);
            if (desktop is not null) Add(desktop);
            else notes.Add("UseWPF/UseWindowsForms is set but no WindowsDesktop reference pack was found");
        }

        // The WEB SDK implies a framework reference to Microsoft.AspNetCore.App, which lives in its
        // own pack. Measured on a real Blazor repository: without it, 165 edges pointed at ILogger,
        // IOptions, IServiceScopeFactory, IHostEnvironment and BackgroundService — types the project
        // uses everywhere and that no NuGet package supplies.
        if (UsesAspNetCore(context))
        {
            var aspnet = RefPack("Microsoft.AspNetCore.App.Ref", wanted);
            if (aspnet is not null) Add(aspnet);
            else notes.Add("this project needs Microsoft.AspNetCore.App but no reference pack was found");
        }

        var basePack = bare.StartsWith("netstandard", StringComparison.OrdinalIgnoreCase)
            ? RefPack("NETStandard.Library.Ref", null)
            : RefPack("Microsoft.NETCore.App.Ref", wanted);

        if (basePack is null) notes.Add($"no reference pack found for {tfm}");
        else Add(basePack);

        return refs;

        void Add(string directory)
        {
            foreach (var dll in Directory.EnumerateFiles(directory, "*.dll"))
            {
                if (!seen.Add(Path.GetFileName(dll))) continue;
                try { refs.Add(MetadataReference.CreateFromFile(dll)); }
                catch (Exception ex) when (ex is IOException or BadImageFormatException) { }
            }
        }
    }

    /// <summary>Where a .NET installation might be, most authoritative first.</summary>
    /// <remarks>
    /// <para><b>This used to be <c>ProgramFiles</c> and nothing else</b>, which made every reference
    /// pack unfindable anywhere but Windows — and worse than unfindable. On Unix
    /// <c>Environment.GetFolderPath(SpecialFolder.ProgramFiles)</c> returns the EMPTY STRING, so
    /// <c>Path.Combine</c> produced the RELATIVE path <c>dotnet/packs/…</c>, which is resolved against
    /// the current directory rather than rejected.</para>
    ///
    /// <para><b>What that cost.</b> With no pack found the compilation carries no framework
    /// references at all, so nothing from the BCL resolves: <c>[Table]</c> is not recognised as the
    /// EF attribute and no <c>declares_table</c> is emitted, and <c>Console</c> and <c>List&lt;T&gt;</c>
    /// stop being classified as runtime types. Extraction still succeeds and still returns facts —
    /// just fewer, quieter ones. Found when the Core suite first ran on a Linux runner (INV-0005).</para>
    ///
    /// <para>The runtime's own location is the reliable answer, because the process is already running
    /// on it: <c>System.Private.CoreLib</c> sits in <c>&lt;root&gt;/shared/Microsoft.NETCore.App/&lt;version&gt;</c>,
    /// three levels below the root that also holds <c>packs/</c>.</para>
    /// </remarks>
    private static IEnumerable<string> DotnetRoots()
    {
        // An explicit install wins: this is the variable the SDK itself honours.
        var declared = Environment.GetEnvironmentVariable("DOTNET_ROOT");
        if (!string.IsNullOrWhiteSpace(declared)) yield return declared;

        // Empty in a single-file publish, hence the guard rather than an assumption.
        var coreLib = typeof(object).Assembly.Location;
        if (!string.IsNullOrEmpty(coreLib))
        {
            var root = Directory.GetParent(coreLib)?.Parent?.Parent?.Parent?.FullName;
            if (!string.IsNullOrEmpty(root)) yield return root;
        }

        // The Windows default — but only when ProgramFiles actually resolved, so a relative
        // "dotnet/packs/…" can never be probed against the current directory.
        var programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        if (!string.IsNullOrEmpty(programFiles)) yield return Path.Combine(programFiles, "dotnet");

        // Where the Linux packages put it.
        yield return "/usr/share/dotnet";
        yield return "/usr/lib/dotnet";
    }

    /// <summary>Newest reference pack not above <paramref name="wanted"/>, ordered by parsed version.</summary>
    private static string? RefPack(string packName, Version? wanted)
    {
        foreach (var dotnetRoot in DotnetRoots())
        {
            var root = Path.Combine(dotnetRoot, "packs", packName);
            if (!Directory.Exists(root)) continue;

            // Ordered by parsed VERSION, not lexically: a string sort puts 8.0.28 above 10.0.11 and
            // silently compiles against the wrong framework.
            var found = Directory.EnumerateDirectories(root)
                .Select(d => (Dir: d, Ok: Version.TryParse(Path.GetFileName(d), out var v), Version: v))
                .Where(x => x.Ok && (wanted is null || x.Version!.Major <= wanted.Major))
                .OrderByDescending(x => x.Version)
                .Select(x => SafeDirectories(Path.Combine(x.Dir, "ref"))
                    .OrderByDescending(r => r, StringComparer.OrdinalIgnoreCase).FirstOrDefault())
                .FirstOrDefault(d => d is not null && Directory.EnumerateFiles(d, "*.dll").Any());

            if (found is not null) return found;
        }

        return null;

        static IEnumerable<string> SafeDirectories(string path) =>
            Directory.Exists(path) ? Directory.EnumerateDirectories(path) : [];
    }

    private static List<MetadataReference> PackageReferences(
        string dir, List<string> disclosures, List<string> notes, int depth)
    {
        var refs = new List<MetadataReference>();
        var assets = Path.Combine(dir, "obj", "project.assets.json");

        if (!File.Exists(assets))
        {
            // Reading this file executes nothing — but PRODUCING it requires `dotnet restore`, which
            // is itself MSBuild evaluation. A freshly cloned repository is in this state, and the
            // honest answer is to disclose rather than to run a restore.
            disclosures.Add(ExtractionDisclosures.PackagesNotRestored);
            if (depth == 0) notes.Add("obj/project.assets.json absent — package references unresolved");
            return refs;
        }

        try
        {
            using var stream = File.OpenRead(assets);
            using var json = JsonDocument.Parse(stream);

            if (!json.RootElement.TryGetProperty("packageFolders", out var folders) ||
                !json.RootElement.TryGetProperty("targets", out var targets))
            {
                disclosures.Add(ExtractionDisclosures.PackagesNotRestored);
                return refs;
            }

            var roots = folders.EnumerateObject().Select(p => p.Name).ToList();

            foreach (var target in targets.EnumerateObject())
            foreach (var lib in target.Value.EnumerateObject())
            {
                if (!lib.Value.TryGetProperty("compile", out var compile)) continue;
                foreach (var item in compile.EnumerateObject())
                {
                    if (item.Name.EndsWith("_._", StringComparison.Ordinal)) continue;
                    foreach (var root in roots)
                    {
                        var path = Path.Combine(
                            root,
                            lib.Name.Replace('/', Path.DirectorySeparatorChar),
                            item.Name.Replace('/', Path.DirectorySeparatorChar));

                        if (!File.Exists(path)) continue;
                        try { refs.Add(MetadataReference.CreateFromFile(path)); }
                        catch (Exception ex) when (ex is IOException or BadImageFormatException) { }
                        break;
                    }
                }
            }
        }
        catch (Exception ex) when (ex is IOException or JsonException)
        {
            disclosures.Add(ExtractionDisclosures.PackagesNotRestored);
            notes.Add($"project.assets.json unreadable: {ex.Message}");
        }

        return refs;
    }
}
