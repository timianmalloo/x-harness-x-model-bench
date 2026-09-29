namespace AiDe.Core.Extraction;

/// <summary>
/// Node.js's own built-in module names — the runtime this product does not index.
/// </summary>
/// <remarks>
/// <para><b>Why this exists.</b> The sibling of <see cref="PythonStandardLibrary"/>, added for the
/// same reason and against the same measurement. DC-050 is registered for a disclosure that merges
/// what the product <i>will not</i> read with what it <i>could not</i> read, and its residual-risk
/// line named this reader as the next place it would appear: <i>"TypeScript discloses 11 unresolved
/// specifiers and has had no equivalent look."</i></para>
///
/// <para><b>MEASURED on TheTerrace.</b> Of the specifiers that survived the precision fix, the ones
/// this reader could not resolve were <c>node:url</c>, <c>node:fs/promises</c> and
/// <c>@playwright/test</c> — Node's runtime twice and npm once. Counting them as "something this
/// scope does not contain" is arithmetically true and reads as a coverage hole; drawing them puts
/// <c>fs</c>, <c>path</c> and <c>url</c> among the most connected nodes in the graph, which is what
/// drawing <c>sys</c>, <c>os</c> and <c>json</c> did to Python's.</para>
///
/// <para><b>Generated, not remembered.</b> Taken verbatim from <c>require('module').builtinModules</c>
/// on Node v24.18.0 — the runtime's own answer, the same discipline the Python list follows. A
/// hand-written list would be a guess about a set the runtime publishes.</para>
///
/// <para><b>The runtime distinguishes two kinds and so does this.</b> Most builtins answer to a bare
/// specifier (<c>fs</c>, <c>path</c>) <i>and</i> to the reserved <c>node:</c> prefix.
/// <c>node:test</c>, <c>node:sqlite</c> and <c>node:sea</c> answer only to the prefix — they appear
/// in <c>builtinModules</c> WITH it — so a bare <c>test</c> or <c>sqlite</c> is a package on npm and
/// not this. Reading that distinction out of the runtime rather than assuming it is the difference
/// between a boundary and a wrong one: <c>sqlite</c> is a real npm package.</para>
///
/// <para><b>It is a floor, not a promise.</b> A module added in a later Node is missing here and
/// falls back to being reported as unresolved, which is the safe direction — over-claiming would
/// hide a real unknown inside a name nobody checked. The <c>node:</c> prefix has no such problem: it
/// is reserved by the runtime, so nothing on npm can ever claim it and any name behind it is a
/// builtin by construction.</para>
/// </remarks>
public static class NodeBuiltinModules
{
    /// <summary>The reserved scheme Node gives its own modules. Nothing on npm may use it.</summary>
    public const string Prefix = "node:";

    // `require('module').builtinModules`, Node v24.18.0, minus the `_`-prefixed internals nothing
    // imports by name, reduced to the top-level segment: `fs/promises` is Node exactly as much as
    // `fs` is, and a set of every submodule is a set that goes stale one release at a time.
    private static readonly HashSet<string> Bare = new(StringComparer.Ordinal)
    {
        "assert", "async_hooks", "buffer", "child_process", "cluster", "console", "constants",
        "crypto", "dgram", "diagnostics_channel", "dns", "domain", "events", "fs", "http",
        "http2", "https", "inspector", "module", "net", "os", "path", "perf_hooks", "process",
        "punycode", "querystring", "readline", "repl", "stream", "string_decoder", "sys",
        "timers", "tls", "trace_events", "tty", "url", "util", "v8", "vm", "wasi",
        "worker_threads", "zlib",
    };

    /// <summary>
    /// Whether a module specifier names Node's own runtime.
    /// </summary>
    /// <remarks>
    /// A <c>node:</c> specifier is one by construction. A bare one is matched on its top-level
    /// segment. The known imprecision is stated rather than hidden: npm carries packages called
    /// <c>path</c>, <c>util</c> and <c>events</c> (browser polyfills), and a repository importing one
    /// of those is recorded here as importing Node. That is the same trade the Python list makes,
    /// and it errs towards calling a boundary a boundary rather than towards inventing a gap.
    /// </remarks>
    public static bool Contains(string specifier)
    {
        if (string.IsNullOrEmpty(specifier)) return false;

        if (specifier.StartsWith(Prefix, StringComparison.Ordinal))
        {
            return specifier.Length > Prefix.Length;
        }

        var slash = specifier.IndexOf('/', StringComparison.Ordinal);
        var root = slash < 0 ? specifier : specifier[..slash];

        return Bare.Contains(root);
    }
}
