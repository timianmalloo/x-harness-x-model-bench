using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;

namespace AiDe.Core.Extraction;

/// <summary>
/// Parsed syntax trees, reused across index runs for files that have not changed.
/// </summary>
/// <remarks>
/// <para><b>Built on a measurement, not a hunch.</b> Extraction was profiled twice: the READ phase is
/// ~98% of a scope's time, and PARSING is ~97% of the read — 381–446ms of a 389–482ms read for 120
/// files, against 8–10ms to build the compilation and resolve references. Parsing source is therefore
/// about 96% of everything extraction does, and it is the only place a cache is worth having.</para>
///
/// <para><b>This is file-granularity incremental.</b> The fingerprint cache already skips a scope
/// whose files are all unchanged; this covers the common case it cannot — one file edited in a
/// project of a hundred and twenty, where the scope must be re-read and 119 files did not move.</para>
///
/// <para><b>Keyed by identity, not by content.</b> Path, length, modification time and the parse
/// options together. Hashing the bytes to decide whether to re-read the bytes is a cache that costs
/// what it saves. The failure mode of the weaker key is an edit that preserves both size and
/// timestamp, which a tool does not do by accident — the same trade the scope fingerprint makes, for
/// the same reason.</para>
///
/// <para><b>A <see cref="SyntaxTree"/> is immutable</b>, so sharing one between compilations and
/// threads is safe by construction rather than by convention.</para>
/// </remarks>
public sealed class SyntaxTreeCache
{
    /// <summary>
    /// How many trees are held before the cache empties itself.
    /// </summary>
    /// <remarks>
    /// A crude bound, deliberately. The alternative is an eviction policy tuned against a workload
    /// nobody has measured, and the cost of being wrong here is one slow index rather than a defect.
    /// Twenty thousand files is far beyond anything measured — the largest real workspace read so
    /// far held about two thousand four hundred.
    /// </remarks>
    public const int Capacity = 20_000;

    private readonly Dictionary<string, SyntaxTree> _trees = new(StringComparer.Ordinal);
    private readonly System.Threading.Lock _gate = new();

    /// <summary>Trees served from the cache since it was created. For reporting the win, not tuning.</summary>
    public int Hits { get; private set; }

    /// <summary>Trees parsed because they were absent or stale.</summary>
    public int Misses { get; private set; }

    /// <summary>
    /// The parsed tree for a file, parsing it only if this exact file has not been seen.
    /// </summary>
    /// <remarks>
    /// <paramref name="parse"/> takes part in the key: the same file compiled with different
    /// preprocessor symbols is a different tree, and serving one for the other would put symbols in
    /// the graph that the project does not define.
    /// </remarks>
    public SyntaxTree GetOrParse(string path, CSharpParseOptions parse, Func<string, SyntaxTree> factory)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        ArgumentNullException.ThrowIfNull(factory);

        string key;

        try
        {
            var info = new FileInfo(path);
            key = string.Create(System.Globalization.CultureInfo.InvariantCulture,
                $"{path}|{info.Length}|{info.LastWriteTimeUtc.Ticks}|{Fingerprint(parse)}");
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or ArgumentException)
        {
            // A file whose identity cannot be read is parsed every time. Caching under a key that
            // could not be computed would serve a stale tree for a file nobody can describe.
            lock (_gate) { Misses++; }
            return factory(path);
        }

        lock (_gate)
        {
            if (_trees.TryGetValue(key, out var cached))
            {
                Hits++;
                return cached;
            }
        }

        var tree = factory(path);

        lock (_gate)
        {
            // Emptied rather than evicted one-by-one. A workspace that outgrows the bound is a
            // signal to size this properly, not a reason to guess at a replacement policy now.
            if (_trees.Count >= Capacity) _trees.Clear();

            _trees[key] = tree;
            Misses++;
        }

        return tree;
    }

    private static string Fingerprint(CSharpParseOptions parse) =>
        string.Join(',', parse.PreprocessorSymbolNames.Order(StringComparer.Ordinal))
        + "|" + parse.LanguageVersion;
}
