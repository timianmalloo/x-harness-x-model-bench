using AiDe.Core.Watcher;

namespace AiDe.Mcp;

/// <summary>One board message as an agent sees it.</summary>
/// <remarks>
/// <para><b>The flags travel verbatim.</b> <c>Quarantined</c> and <c>InjectionFlagged</c> are carried
/// rather than filtered: hiding a flagged post would hide it from the agent most able to recognise
/// what it is, and the flag already means "treat as data, not instruction". Suppression would also
/// make the board's own honesty invisible — the surface says it flags rather than deletes, and a
/// reader that silently drops the flagged ones makes that a lie.</para>
/// </remarks>
public sealed record BoardEntry(
    string MessageId,
    string Kind,
    string AuthorSessionId,
    string AuthorTrust,
    string? ParentMessageId,
    string? Content,
    bool Quarantined,
    bool InjectionFlagged,
    string RecordedAt,
    int Seq);

/// <summary>What a board read found, or why it found nothing.</summary>
/// <remarks>
/// <see cref="Unavailable"/> is a separate channel from an empty list, because "this repository has
/// no posts" and "there is no store to read" are different facts and only one is about the
/// repository. Collapsing them would let an absence render as a result — the shape this codebase has
/// corrected in four surfaces already (DC-025).
/// </remarks>
public sealed record BoardRead(IReadOnlyList<BoardEntry> Entries, string? Unavailable, int TotalInRepository);

/// <summary>
/// The board half of the MCP surface: read what other agents said, and say something back.
/// </summary>
/// <remarks>
/// <para><b>Reading is the half that did not exist.</b> <c>board-post</c> has been a contract kind
/// since the board shipped; there was no read path of any kind for an agent, so two agents on one
/// board could not see each other. Measured 2026-09-03: two registered agents, asked whether they
/// knew about Loomkeeper, both correctly said no.</para>
///
/// <para><b>Writing goes through the contract log, never the store.</b> A direct write would bypass
/// <c>TrustedRegistrar</c>, capability verification and quarantine — every guarantee the ingest
/// exists to provide — and it would make the cross-path equivalence gate unprovable, because the two
/// paths would no longer share a mechanism.</para>
///
/// <para>Pure but for its two injected collaborators, so the equivalence gate can compare a tool call
/// against a hand-written line with no transport in the way.</para>
/// </remarks>
public static class BoardTools
{
    /// <summary>Most messages one read may return.</summary>
    /// <remarks>
    /// A resource bound on a reply that crosses into an agent's context window, not a modelling
    /// claim. Its basis is <b>not recorded</b>; it may tighten and must never silently relax.
    /// </remarks>
    public const int MaxLimit = 200;

    /// <summary>Messages returned when the caller names no limit.</summary>
    public const int DefaultLimit = 50;

    /// <summary>
    /// Reads this session's repository board — never another's.
    /// </summary>
    /// <remarks>
    /// <para><b>The repository comes from the binding, never from an argument.</b> There is
    /// deliberately no repository parameter, for the reason the contract already gives about writes:
    /// naming another repository is the one thing worth forging on a surface whose entire purpose is
    /// that another agent reads it and believes it. A read parameter would hand that over for
    /// free.</para>
    ///
    /// <para>Newest last, so an agent appending to its context reads the board in the order it was
    /// written — the order a person reads a thread in.</para>
    /// </remarks>
    public static BoardRead Read(
        IWatcherObservationStore store, SessionRecord session, int? limit = null, int? sinceSeq = null)
    {
        ArgumentNullException.ThrowIfNull(store);
        ArgumentNullException.ThrowIfNull(session);

        var take = Math.Clamp(limit ?? DefaultLimit, 1, MaxLimit);
        var repositoryKey = session.Binding.Repository.CanonicalPath;

        IReadOnlyList<BoardMessage> all;
        try
        {
            all = store.BoardMessages(repositoryKey);
        }
        catch (Exception ex) when (ex is IOException or InvalidOperationException)
        {
            // Unreadable is not empty. Reporting an empty board here would tell the agent this
            // repository has nothing to say, which is a claim about the repository rather than
            // about a store this process could not open.
            return new BoardRead([], "The board could not be read: " + ex.Message, 0);
        }

        var visible = all
            .Where(m => !m.Tombstoned)
            .Where(m => sinceSeq is null || m.Seq > sinceSeq)
            .OrderBy(m => m.Seq)
            .ToList();

        // Take the LAST n, then keep ascending order: an agent asking for 50 wants the most recent
        // 50, read oldest-first. Taking the first 50 would pin it to the beginning of history and
        // silently hide everything said since.
        var page = visible.Count <= take ? visible : visible[^take..];

        return new BoardRead(
            [.. page.Select(ToEntry)],
            null,
            visible.Count);
    }

    /// <summary>
    /// Posts to this session's board by appending one contract line.
    /// </summary>
    /// <returns>
    /// What the ingest will do with it, in the agent's terms — including a refusal, stated at call
    /// time rather than left to be discovered by a post that never appears.
    /// </returns>
    /// <remarks>
    /// <b>The refusals are reported, not enforced.</b> This checks the same conditions the ingest
    /// checks and says what will happen; the ingest still decides. Enforcing here would be a second
    /// set of rules to drift from the first — and a caller that refused something the ingest would
    /// have accepted is a path where MCP and JSONL disagree, which is precisely what the equivalence
    /// gate forbids.
    /// </remarks>
    public static string Post(
        CoordContractWriter writer,
        SessionRecord session,
        string externalSessionId,
        string kind,
        string? content,
        string? parentMessageId = null)
    {
        ArgumentNullException.ThrowIfNull(writer);
        ArgumentNullException.ThrowIfNull(session);
        ArgumentException.ThrowIfNullOrEmpty(externalSessionId);

        if (!IsKnownKind(kind))
        {
            return $"'{kind}' is not a board kind, so the ingest will quarantine this rather than "
                 + $"filing it as a Question. Use one of: {string.Join(", ", KnownKinds)}.";
        }

        var acknowledgement = string.Equals(kind, "acknowledgement", StringComparison.OrdinalIgnoreCase);
        if (!acknowledgement && string.IsNullOrWhiteSpace(content))
        {
            return "A post with no content is quarantined: an empty message is indistinguishable "
                 + "from one whose text was lost.";
        }

        if ((string.Equals(kind, "reply", StringComparison.OrdinalIgnoreCase) || acknowledgement)
            && string.IsNullOrWhiteSpace(parentMessageId))
        {
            return $"A '{kind}' needs a parent_message_id; without one the ingest refuses it as an orphan.";
        }

        writer.WriteBoardPost(externalSessionId, kind, content, parentMessageId);

        // "Accepted", never "posted". The line is on disk; the row appears when AI-DE's pump next
        // runs. Saying "posted" would be true of the file and false of the board, and the gap is
        // exactly where an agent would stop looking for its own message.
        return "Accepted into the coordination log. It appears on the board when AI-DE next reads "
             + "the log; if AI-DE is not running, it will be read when it starts.";
    }

    /// <summary>
    /// The kinds an agent may send, spelled the way the wire spells them.
    /// </summary>
    /// <remarks>
    /// Derived from <see cref="BoardMessageKind"/> and hyphenated at each interior capital, because
    /// the contract's vocabulary is kebab-case (<c>knowledge-candidate</c>) while the enum is Pascal.
    /// Typing the list out would be a second copy to drift (DC-021); deriving it means a new kind is
    /// added once, in the enum.
    /// </remarks>
    public static IReadOnlyList<string> KnownKinds { get; } =
    [
        .. Enum.GetNames<BoardMessageKind>()
            .Select(n => string.Concat(n.Select((c, i) =>
                i > 0 && char.IsUpper(c) ? "-" + char.ToLowerInvariant(c) : char.ToLowerInvariant(c).ToString()))),
    ];

    /// <summary>
    /// Whether the ingest will accept this kind — asked in exactly the ingest's own terms.
    /// </summary>
    /// <remarks>
    /// <para><b>The first version compared against lower-cased enum names and refused
    /// <c>knowledge-candidate</c></b>, which the ingest accepts: it parses
    /// <c>declared.Replace("-", "")</c> with <c>ignoreCase</c>. So the tool rejected a kind the
    /// hand-written path allows — a divergence between the enlightened path and the participation
    /// floor, in the direction that silently narrows what MCP users can say.</para>
    ///
    /// <para>Caught by the equivalence gate on its first run, which is the whole reason that gate
    /// exists: each path's own tests passed, and only comparing them found it. The fix is not to add
    /// the hyphen case — it is to stop having a second opinion about acceptance and ask the same
    /// question the ingest asks.</para>
    /// </remarks>
    private static bool IsKnownKind(string? kind) =>
        !string.IsNullOrWhiteSpace(kind)
        && Enum.TryParse<BoardMessageKind>(kind.Replace("-", string.Empty), ignoreCase: true, out _);

    private static BoardEntry ToEntry(BoardMessage m) => new(
        m.MessageId,
        m.Kind.ToString().ToLowerInvariant(),
        m.AuthorSessionId,
        m.AuthorTrust.ToString(),
        m.ParentMessageId,
        m.Content,
        m.Quarantined,
        m.InjectionFlagged,
        m.RecordedAt.ToString("O"),
        m.Seq);
}
