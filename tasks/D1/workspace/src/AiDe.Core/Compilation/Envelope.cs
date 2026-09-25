using AiDe.Core.Sessions;

namespace AiDe.Core.PromptCompilation;

/// <summary>
/// The <b>Envelope</b> — the aggregate root of Prompt Compilation: the fold of its events (§A6).
/// Opened by the Send gesture, closed by <c>submitted</c> + <c>consumed</c>; an envelope with no
/// accepted <c>submitted</c> is abandoned.
/// </summary>
/// <remarks>
/// <para><b>One invariant:</b> it only grows — every event carries a <c>seq</c> strictly greater
/// than every event before it, no event is mutated or removed, and no <c>decorated</c> follows an
/// accepted <c>submitted</c>. The writer enforces it (<see cref="EnvelopeStore.Append"/>); the fold
/// reads the rows in <c>seq</c> order and never re-sorts them by source.</para>
///
/// <para><b>Derive, don't store (DM7).</b> The shape, the tier and its rationale, the effective
/// fan-out, the CT19 block, the lease and every count are <see cref="Projection.Project"/>'s over
/// this fold; nothing here is a stored copy of one. <see cref="Current"/>, <see cref="Confirmed"/>
/// and <see cref="EffectiveMode"/> have one definition each, read by Prepare, Submit and the eval
/// alike (DM11 b).</para>
/// </remarks>
public sealed class Envelope
{
    /// <summary>The word for an absent measurement or identity — never a plausible substitute (IO12).</summary>
    public const string NotRecorded = "not recorded";

    private readonly List<EnvelopeEvent> _events;

    private Envelope(string envelopeId, List<EnvelopeEvent> events)
    {
        EnvelopeId = envelopeId;
        _events = events;
    }

    /// <summary>The envelope's id.</summary>
    public string EnvelopeId { get; }

    /// <summary>Every event, in <c>seq</c> order.</summary>
    public IReadOnlyList<EnvelopeEvent> Events => _events;

    /// <summary>The <c>opened</c> row, or null when the fold holds none (an incomplete envelope — <see cref="Projection.Project"/> refuses it).</summary>
    public Opened? Opened => _events.OfType<Opened>().FirstOrDefault();

    /// <summary>Every decoration, in <c>seq</c> order.</summary>
    public IEnumerable<Decorated> Decorations => _events.OfType<Decorated>();

    /// <summary>The last <c>called</c> row, or null when no call was made.</summary>
    public Called? LastCall => _events.OfType<Called>().LastOrDefault();

    /// <summary>The one accepted <c>submitted</c>, or null.</summary>
    public Submitted? Submitted => _events.OfType<Submitted>().FirstOrDefault(s => s.Accepted);

    /// <summary>The <c>consumed</c> row, or null.</summary>
    public Consumed? Consumed => _events.OfType<Consumed>().FirstOrDefault();

    /// <summary>Abandoned: no accepted <c>submitted</c>. A stable read, because no writer holds the file while a reader folds it.</summary>
    public bool IsAbandoned => Submitted is null;

    /// <summary>
    /// The run's outcome: the <c>consumed</c> row's word; <see cref="NotRecorded"/> for an accepted
    /// <c>submitted</c> with no <c>consumed</c>; null for an envelope that was never submitted.
    /// </summary>
    public string? Outcome => Consumed?.Outcome ?? (Submitted is null ? null : NotRecorded);

    /// <summary><c>Current(name)</c>: the <c>decorated</c> event with the highest <c>seq</c> for that name (§A6).</summary>
    public Decorated? Current(string name) =>
        Decorations.LastOrDefault(d => string.Equals(d.Name, name, StringComparison.Ordinal));

    /// <summary>
    /// <c>Confirmed(name)</c>: <see cref="Current"/> ignoring <c>derived</c> rows when
    /// <c>opened.compile_mode = agentic-advisory</c> — the one definition the shape, the tier rule's
    /// P and the CT19 projection all read, so an unkept derived line is blank for all three at once.
    /// </summary>
    public Decorated? Confirmed(string name)
    {
        var advisory = string.Equals(Opened?.CompileMode, CompileModes.AgenticAdvisory, StringComparison.Ordinal);
        return Decorations.LastOrDefault(d =>
            string.Equals(d.Name, name, StringComparison.Ordinal)
            && !(advisory && string.Equals(d.Source, DecorationSources.Derived, StringComparison.Ordinal)));
    }

    /// <summary>
    /// <c>EffectiveMode</c>: <c>agentic</c> iff <c>opened.compile_mode ∈ {agentic-advisory, agentic}</c>
    /// and the last <c>called.outcome ∈ {succeeded, succeeded_no_structure, suspect}</c>; else
    /// <c>mechanical</c>. A function of the fold, never a stored decoration (§A10.2).
    /// </summary>
    public string EffectiveMode
    {
        get
        {
            var mode = Opened?.CompileMode;
            var agenticMode = string.Equals(mode, CompileModes.AgenticAdvisory, StringComparison.Ordinal)
                || string.Equals(mode, CompileModes.Agentic, StringComparison.Ordinal);
            return agenticMode && LastCall is { } call && CallOutcomes.Agentic.Contains(call.Outcome, StringComparer.Ordinal)
                ? EffectiveModes.Agentic
                : EffectiveModes.Mechanical;
        }
    }

    /// <summary>
    /// Folds events into envelopes, grouped by id, each in <c>seq</c> order. Every event must carry
    /// a positive <c>seq</c> — the writer's, or <see cref="Pending"/>'s for a live pre-compile.
    /// </summary>
    public static IReadOnlyList<Envelope> Fold(IEnumerable<EnvelopeEvent> events)
    {
        ArgumentNullException.ThrowIfNull(events);

        var byId = new Dictionary<string, List<EnvelopeEvent>>(StringComparer.Ordinal);
        var order = new List<string>();
        foreach (var evt in events)
        {
            if (evt.Seq <= 0)
            {
                throw new ArgumentException($"event '{evt.Kind}' on envelope '{evt.EnvelopeId}' has no seq; number a live envelope with Envelope.Pending first", nameof(events));
            }

            if (!byId.TryGetValue(evt.EnvelopeId, out var list))
            {
                list = [];
                byId[evt.EnvelopeId] = list;
                order.Add(evt.EnvelopeId);
            }

            list.Add(evt);
        }

        return [.. order.Select(id => new Envelope(id, [.. byId[id].OrderBy(e => e.Seq)]))];
    }

    /// <summary>
    /// The live, in-memory envelope the pre-compile builds and persists nothing of (§A10.1):
    /// the events numbered 1..n in order, folded. The same <see cref="Fold"/> the store's rows take,
    /// so what Prepare renders before Send and what the store holds after it are one function's output.
    /// </summary>
    public static Envelope Pending(IReadOnlyList<EnvelopeEvent> events)
    {
        ArgumentNullException.ThrowIfNull(events);
        if (events.Count == 0)
        {
            throw new ArgumentException("a pending envelope has at least its opened row", nameof(events));
        }

        var id = events[0].EnvelopeId;
        var numbered = events.Select((e, i) => e with { Seq = i + 1 }).ToList();
        if (numbered.Any(e => !string.Equals(e.EnvelopeId, id, StringComparison.Ordinal)))
        {
            throw new ArgumentException("a pending envelope's events all carry one envelope id", nameof(events));
        }

        return new Envelope(id, numbered);
    }
}

/// <summary>The effective compile mode after degradation — a projection's vocabulary, never a stored decoration.</summary>
public static class EffectiveModes
{
    public const string Mechanical = "mechanical";
    public const string Agentic = "agentic";
}

/// <summary>
/// What a reader folded from one file: the envelopes it could read, the rows it skipped and
/// counted, and where the chain broke (DM11 g).
/// </summary>
/// <param name="Envelopes">Every envelope no row of which lies at or past <see cref="BrokenAt"/>.</param>
/// <param name="Rows">Lines in the file, torn and unknown included.</param>
/// <param name="SkippedUnknownSchema">Rows whose <c>schema</c> is not <c>compiled-envelope/1</c> — a rolled-back binary skips what it cannot read and never truncates.</param>
/// <param name="SkippedUnknownKind">Rows of a kind this reader does not know.</param>
/// <param name="SkippedTorn">Lines that did not parse — a torn last line, or a line written broken.</param>
/// <param name="BrokenAt">The 1-based line whose bytes no longer match the next line's <c>prev_sha</c>, or null.</param>
public sealed record EnvelopeFold(
    IReadOnlyList<Envelope> Envelopes,
    int Rows,
    int SkippedUnknownSchema,
    int SkippedUnknownKind,
    int SkippedTorn,
    int? BrokenAt)
{
    /// <summary>The reader's report, in one sentence — <i>record broken at line N</i> when it is.</summary>
    public string Report => BrokenAt is { } n
        ? $"record broken at line {n}; {Envelopes.Count} envelope(s) before it, none past it"
        : $"{Envelopes.Count} envelope(s) over {Rows} row(s); skipped {SkippedUnknownSchema} unknown-schema, {SkippedUnknownKind} unknown-kind, {SkippedTorn} torn";

    /// <summary>The newest <c>at</c> across every readable row, or null when none.</summary>
    public DateTimeOffset? NewestAt => Envelopes.SelectMany(e => e.Events).Select(e => e.At).Where(a => a is not null).Max();

    /// <summary>One envelope by id, or null.</summary>
    public Envelope? Find(string envelopeId) =>
        Envelopes.FirstOrDefault(e => string.Equals(e.EnvelopeId, envelopeId, StringComparison.Ordinal));
}
