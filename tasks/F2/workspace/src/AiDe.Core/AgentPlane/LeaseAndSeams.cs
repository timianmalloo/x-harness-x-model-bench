using System.Text;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace AiDe.Core.AgentPlane;

/// <summary>
/// A lane's exclusive write scope — spec §14.3's <c>lease: { exclusive: [ … ] }</c>.
/// </summary>
/// <remarks>
/// <para><b>Repository-relative patterns, matched ordinally.</b> The patterns are written the way a
/// person writes them in a plan (<c>src/Payments/**</c>), so they are relative and use forward
/// slashes; a path observed on the wire is absolute and platform-shaped, and
/// <see cref="LeaseMonitor"/> is where the two meet.</para>
///
/// <para><b>Case-sensitive, and that direction is deliberate.</b> On Windows <c>src/payments/X.cs</c>
/// and <c>src/Payments/X.cs</c> are one file; here they are two, so the first does not match the
/// lease and <b>raises a seam</b>. The two errors are not symmetric: an extra seam is reported,
/// read and resolved, while a missed one is an edit that escaped the lease with nothing recorded.
/// A governance control degrades toward saying something.</para>
///
/// <para><b>An empty lease is not a lease.</b> It is refused rather than read as "covers nothing"
/// (every edit seams — useless) or as "covers everything" (no edit ever seams — worse, because it
/// looks like it is working). A lane with no declared scope simply has no monitor.</para>
/// </remarks>
/// <param name="Exclusive">The glob patterns this lane may write within. At least one.</param>
public sealed record Lease(IReadOnlyList<string> Exclusive)
{
    private readonly Regex[] _compiled = Compile(Exclusive);

    /// <summary>Whether a repository-relative path falls inside this lease.</summary>
    public bool Covers(string relativePath)
    {
        ArgumentNullException.ThrowIfNull(relativePath);

        var normalized = relativePath.Replace('\\', '/');
        return Array.Exists(_compiled, r => r.IsMatch(normalized));
    }

    private static Regex[] Compile(IReadOnlyList<string> patterns)
    {
        ArgumentNullException.ThrowIfNull(patterns);

        var usable = patterns.Where(p => !string.IsNullOrWhiteSpace(p)).ToList();
        if (usable.Count == 0)
        {
            throw new ArgumentException(
                "a lease with no exclusive pattern is not a lease: it would either seam on every edit "
                + "or on none, and both look like a working control",
                nameof(patterns));
        }

        return [.. usable.Select(CompileOne)];
    }

    /// <summary>
    /// Turns one glob into an anchored regex: <c>**</c> crosses separators, <c>*</c> and <c>?</c> do
    /// not.
    /// </summary>
    /// <remarks>
    /// <b><c>**/</c> swallows its own separator</b>, so <c>docs/**/*.md</c> also matches
    /// <c>docs/a.md</c>. Written as a scanner rather than a chain of string replacements, because
    /// replacing <c>*</c> after <c>**</c> rewrites the output of the first pass.
    /// </remarks>
    private static Regex CompileOne(string pattern)
    {
        var glob = pattern.Trim().Replace('\\', '/');
        var expression = new StringBuilder("^");

        for (var i = 0; i < glob.Length; i++)
        {
            var c = glob[i];
            if (c == '*')
            {
                if (i + 1 < glob.Length && glob[i + 1] == '*')
                {
                    if (i + 2 < glob.Length && glob[i + 2] == '/')
                    {
                        expression.Append("(?:.*/)?");
                        i += 2;
                    }
                    else
                    {
                        expression.Append(".*");
                        i += 1;
                    }
                }
                else
                {
                    expression.Append("[^/]*");
                }
            }
            else if (c == '?')
            {
                expression.Append("[^/]");
            }
            else
            {
                expression.Append(Regex.Escape(c.ToString()));
            }
        }

        expression.Append('$');
        return new Regex(expression.ToString(), RegexOptions.CultureInvariant, TimeSpan.FromSeconds(1));
    }
}

/// <summary>
/// One coordination seam: an edit a lane made outside its lease.
/// </summary>
/// <remarks>
/// <para><b>A ledger entry, not yet a run event.</b> Spec §7.2 lists <c>seam.open</c> and
/// <c>seam.resolve</c> among the v1 kinds, and both are produced by the <b>conductor</b> (§5.3
/// Stage 4, <c>seam_resolve</c>), which Phase 1 does not have. Minting a <see cref="RunEvent"/> here
/// would need a second writer of the per-run <c>Seq</c>, and two sequence sources for one run is a
/// defect with no symptom until the log is read in order. So the seam carries the run, the agent and
/// the ordinal of the edit that caused it, and Phase 2's conductor is what turns it into an event.
/// </para>
/// </remarks>
/// <param name="SeamId">Stable within the lane, and readable in a log line.</param>
/// <param name="RunId">The run the offending edit belonged to.</param>
/// <param name="AgentId">The lane that made it.</param>
/// <param name="ToolCallId">The engine's own id for the edit — what makes one edit one seam.</param>
/// <param name="Path">The path as observed, verbatim.</param>
/// <param name="CausedBySeq">The <see cref="RunEvent.Seq"/> of the frame the edit was seen on.</param>
/// <param name="RaisedAt">When that frame was received.</param>
public sealed record Seam(
    string SeamId,
    string RunId,
    string AgentId,
    string ToolCallId,
    string Path,
    long CausedBySeq,
    DateTimeOffset RaisedAt);

/// <summary>
/// Watches a governed lane's run events and raises a seam for every edit outside its lease — spec
/// R4's third bullet and §6.1 ("Leases: enforced").
/// </summary>
/// <remarks>
/// <para><b>Edits are recognized by the shape that exists.</b> §7.2 names <c>file.edit</c> as a v1
/// kind, and <b>no Phase-1 producer emits it</b>: the captured corpus
/// (<c>spikes/acp-subscription-lane/frames/write.jsonl</c>) shows a file write arriving as a
/// <c>tool_call</c>/<c>tool_call_update</c> carrying <c>kind:"edit"</c> and a <c>locations[]</c>
/// array, which <see cref="AcpRunEventMapper"/> normalizes to <c>tool.call</c>/<c>tool.result</c>.
/// Adding a handler for a kind nothing produces is what N1 forbade; when a producer of
/// <c>file.edit</c> appears, it is a row here, not a redesign.</para>
///
/// <para><b>One edit is one seam.</b> The corpus shows the same write four times — a pending
/// <c>tool_call</c> with an <i>empty</i> <c>locations</c> array, two <c>tool_call_update</c>s and a
/// permission request. Raising per frame would report four violations for one, and
/// <c>seam_resolution_ratio</c> would then be a measure of adapter chattiness. The identity is
/// <c>(toolCallId, path)</c> — the engine's own id for the call, and the file it touched.</para>
///
/// <para><b>A frame with no path observes nothing.</b> The pending frame genuinely does not say what
/// will be written; treating "no path" as "not covered" would make the first announcement of every
/// edit a violation.</para>
/// </remarks>
public sealed class LeaseMonitor
{
    /// <summary>The <c>update.kind</c> the corpus carries for a write. Observed, not assumed.</summary>
    private const string EditToolKind = "edit";

    private readonly Lease _lease;
    private readonly string _worktreeRoot;
    private readonly Lock _gate = new();
    private readonly List<Seam> _raised = [];
    private readonly HashSet<string> _seen = new(StringComparer.Ordinal);
    private readonly Dictionary<string, string> _rulings = new(StringComparer.Ordinal);

    /// <param name="lease">The lane's exclusive scope.</param>
    /// <param name="worktreeRoot">
    /// The lane's provisioned tree. Observed paths are absolute, lease patterns are relative, and
    /// this is what relates them — so a lane's lease is scoped to <i>its own</i> tree and an edit
    /// anywhere else is outside it by construction.
    /// </param>
    public LeaseMonitor(Lease lease, string worktreeRoot)
    {
        ArgumentNullException.ThrowIfNull(lease);
        ArgumentException.ThrowIfNullOrWhiteSpace(worktreeRoot);
        _lease = lease;
        _worktreeRoot = worktreeRoot;
    }

    /// <summary>Every seam raised, in raise order.</summary>
    public IReadOnlyList<Seam> AllSeams
    {
        get
        {
            lock (_gate)
            {
                return [.. _raised];
            }
        }
    }

    /// <summary>The seams still awaiting a ruling.</summary>
    public IReadOnlyList<Seam> OpenSeams
    {
        get
        {
            lock (_gate)
            {
                return [.. _raised.Where(s => !_rulings.ContainsKey(s.SeamId))];
            }
        }
    }

    /// <summary>How many seams this lane raised.</summary>
    public int RaisedCount
    {
        get
        {
            lock (_gate)
            {
                return _raised.Count;
            }
        }
    }

    /// <summary>
    /// <c>seam_resolution_ratio</c> (spec §8.2): resolved over raised, and <b>1.0 when none were
    /// raised</b>.
    /// </summary>
    /// <remarks>
    /// A run that never violated its lease has nothing outstanding, and reporting 0 for it would
    /// block every clean run — the empty-numerator error that reads as a working gate.
    /// </remarks>
    public double SeamResolutionRatio
    {
        get
        {
            lock (_gate)
            {
                return _raised.Count == 0 ? 1.0 : (double)_rulings.Count / _raised.Count;
            }
        }
    }

    /// <summary>
    /// Observes one run event, and returns the seams it newly raised (empty for anything that is not
    /// an out-of-lease edit).
    /// </summary>
    public IReadOnlyList<Seam> Observe(RunEvent runEvent)
    {
        ArgumentNullException.ThrowIfNull(runEvent);

        if (runEvent.Body["kind"] is not JsonValue kindValue
            || !kindValue.TryGetValue<string>(out var kind)
            || !string.Equals(kind, EditToolKind, StringComparison.Ordinal))
        {
            return [];
        }

        var toolCallId = AcpJson.Text(runEvent.Body["toolCallId"]) ?? runEvent.Kind + ":" + runEvent.Seq;
        var raised = new List<Seam>();

        foreach (var path in Locations(runEvent.Body))
        {
            if (IsCovered(path))
            {
                continue;
            }

            lock (_gate)
            {
                // A unit separator, so a tool-call id or a path containing it cannot collide
                // two different edits into one seam.
                if (!_seen.Add(toolCallId + "" + path))
                {
                    continue;
                }

                var seam = new Seam(
                    $"{runEvent.AgentId}-seam-{_raised.Count + 1:0000}",
                    runEvent.RunId,
                    runEvent.AgentId,
                    toolCallId,
                    path,
                    runEvent.Seq,
                    runEvent.Ts);

                _raised.Add(seam);
                raised.Add(seam);
            }
        }

        return raised;
    }

    /// <summary>
    /// Records a ruling on one seam. Returns <c>false</c> for an id nobody raised, or one already
    /// ruled on.
    /// </summary>
    /// <remarks>
    /// <b>Idempotent and non-overwriting.</b> A second ruling on one seam would change what the run
    /// closed against after the fact; the first ruling stands and the caller is told it did nothing.
    /// </remarks>
    public bool Resolve(string seamId, string ruling)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(seamId);
        ArgumentException.ThrowIfNullOrWhiteSpace(ruling);

        lock (_gate)
        {
            return _raised.Exists(s => string.Equals(s.SeamId, seamId, StringComparison.Ordinal))
                && _rulings.TryAdd(seamId, ruling);
        }
    }

    /// <summary>Whether the run may close with the outcome it declared (spec §8.2's precondition).</summary>
    public bool MayCloseCleanly => SeamResolutionRatio >= 1.0;

    /// <summary>
    /// Whether an observed path is inside the lease.
    /// </summary>
    /// <remarks>
    /// A path that is not under the lane's tree at all is outside the lease, whatever the patterns
    /// say — the lease scopes a lane within its own worktree, and an edit elsewhere is the larger
    /// violation, not an exempt one.
    /// </remarks>
    private bool IsCovered(string path)
    {
        string relative;
        try
        {
            relative = Path.GetRelativePath(_worktreeRoot, path);
        }
        catch (ArgumentException)
        {
            // A path shape the platform cannot relate to the root at all. Not covered, and therefore
            // reported — never silently exempt.
            return false;
        }

        if (Path.IsPathRooted(relative) || relative.Equals("..", StringComparison.Ordinal)
            || relative.StartsWith("../", StringComparison.Ordinal)
            || relative.StartsWith("..\\", StringComparison.Ordinal))
        {
            return false;
        }

        return _lease.Covers(relative);
    }

    /// <summary>Every <c>path</c> the frame's <c>locations[]</c> named. Empty is ordinary.</summary>
    private static IEnumerable<string> Locations(JsonObject body)
    {
        if (body["locations"] is not JsonArray locations)
        {
            yield break;
        }

        foreach (var location in locations.OfType<JsonObject>())
        {
            if (AcpJson.Text(location["path"]) is { } path)
            {
                yield return path;
            }
        }
    }
}
