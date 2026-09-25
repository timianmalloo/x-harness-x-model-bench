namespace AiDe.Core.Presentation.Composer;

/// <summary>One thing a mention can name, as the picker offers it.</summary>
/// <param name="Label">What is inserted after the <c>@</c> — characters in the draft, nothing more.</param>
/// <param name="Detail">The secondary line in the picker row.</param>
public sealed record MentionCandidate(string Label, string Detail);

/// <summary>
/// A source of mention candidates, with a counter on every query.
/// </summary>
/// <remarks>
/// <b>The counter is what makes C15 checkable.</b> "No late binding" is a claim about a window —
/// between the compiled view rendering and the prompt reaching the run host — and a claim about a
/// window needs an observable inside it. Both sources are queried while the operator types and
/// <b>never</b> on the send path.
/// </remarks>
public interface IMentionSource
{
    /// <summary>Which source this is, for a picker that shows two.</summary>
    string SourceId { get; }

    /// <summary>How many times this source has been asked anything.</summary>
    long QueryCount { get; }

    /// <summary>The candidates for a prefix. Called while composing, never while sending.</summary>
    IReadOnlyList<MentionCandidate> Query(string prefix);
}

/// <summary>Workspace files, as mention candidates.</summary>
/// <remarks>
/// <para><b>It enumerates once, at construction, and answers from that.</b> A source that walked the
/// disk per keystroke would put a file-system read inside the send window the moment anything called
/// it late — the defect C15 names, arriving through a performance decision rather than a security
/// one.</para>
/// </remarks>
public sealed class FileMentionSource : IMentionSource
{
    private readonly List<MentionCandidate> _candidates;
    private long _queries;

    /// <param name="relativePaths">Repository-relative paths, already enumerated by the caller.</param>
    public FileMentionSource(IReadOnlyList<string> relativePaths)
    {
        ArgumentNullException.ThrowIfNull(relativePaths);
        _candidates = [.. relativePaths.Select(p => new MentionCandidate(p.Replace('\\', '/'), "file"))];
    }

    /// <inheritdoc/>
    public string SourceId => "files";

    /// <inheritdoc/>
    public long QueryCount => Interlocked.Read(ref _queries);

    /// <inheritdoc/>
    public IReadOnlyList<MentionCandidate> Query(string prefix)
    {
        ArgumentNullException.ThrowIfNull(prefix);
        Interlocked.Increment(ref _queries);

        return [.. _candidates.Where(c => c.Label.Contains(prefix, StringComparison.OrdinalIgnoreCase))];
    }
}

/// <summary>Graph nodes, as mention candidates — the picker's second source.</summary>
public sealed class GraphMentionSource : IMentionSource
{
    private readonly List<MentionCandidate> _candidates;
    private long _queries;

    /// <param name="nodeNames">Node names, already read by the caller.</param>
    public GraphMentionSource(IReadOnlyList<string> nodeNames)
    {
        ArgumentNullException.ThrowIfNull(nodeNames);
        _candidates = [.. nodeNames.Select(n => new MentionCandidate(n, "graph node"))];
    }

    /// <inheritdoc/>
    public string SourceId => "graph";

    /// <inheritdoc/>
    public long QueryCount => Interlocked.Read(ref _queries);

    /// <inheritdoc/>
    public IReadOnlyList<MentionCandidate> Query(string prefix)
    {
        ArgumentNullException.ThrowIfNull(prefix);
        Interlocked.Increment(ref _queries);

        return [.. _candidates.Where(c => c.Label.Contains(prefix, StringComparison.OrdinalIgnoreCase))];
    }
}
