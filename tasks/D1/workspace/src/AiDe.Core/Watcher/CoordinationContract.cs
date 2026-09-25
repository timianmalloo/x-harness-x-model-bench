using System.Text.Json;

namespace AiDe.Core.Watcher;

/// <summary>
/// Pins the injected coordination-contract version. A record whose <c>contract</c> differs is rejected,
/// not re-parsed (Testing Strategy A6 - a schema change is a contract change). Bumping this is a
/// deliberate, gated change guarded by the version regression test.
/// </summary>
public static class CoordContract
{
    public const string Version = "loomkeeper/1";
    public const string VersionKey = "contract";

    /// <summary>
    /// The attribute keys an <c>episode-open</c> / <c>episode-close</c> line carries.
    /// </summary>
    /// <remarks>
    /// Deliberately <b>not</b> in <see cref="OtelAttributes"/>. Those keys are OpenTelemetry
    /// semantic conventions and are shared with the OTLP span path; a goal statement and a declared
    /// outcome are this contract's own vocabulary, with no OTel convention behind them. Putting
    /// them there would assert a standard that does not exist.
    /// </remarks>
    public static class EpisodeAttributes
    {
        public const string Goal = "episode.goal";
        public const string DoneWhen = "episode.done_when";
        public const string NotInScope = "episode.not_in_scope";
        public const string Outcome = "episode.outcome";

        /// <summary>
        /// Newline-separated repository-relative paths to the evidence for this episode.
        /// </summary>
        /// <remarks>
        /// <para><b>The one thing an agent may say about its own quality, and it is not a claim.</b>
        /// It names files; the product goes and looks. An agent cannot make a path exist by
        /// asserting it harder, which is what keeps this observation rather than testimony — and it
        /// is why <c>episode.acceptance_met</c> is deliberately absent and will stay absent.
        /// ADR-0019 advisory-evaluator-calibration's anti-Goodhart concern is about accepting a verdict, not a pointer.</para>
        ///
        /// <para><b>Optional.</b> An agent that never sends it loses nothing it had before: the
        /// episode still closes and still scores Not Scored, which was already the honest answer.
        /// </para>
        ///
        /// <para>Newline-separated because a path may contain spaces, commas and semicolons on a real
        /// filesystem but never a newline. A separator that can occur inside a value is a parser that
        /// silently splits one path into two.</para>
        /// </remarks>
        public const string Artifacts = "episode.artifacts";
    }

    /// <summary>The attribute keys a <c>board-post</c> line carries.</summary>
    /// <remarks>
    /// There is deliberately no repository key. The board is per-repository and a session's
    /// repository is fixed at registration, so it is <b>derived from the binding</b> rather than
    /// supplied — an attribute would let a session post onto another repository's board by naming
    /// it, which is the same class of hole as an update restating identity.
    /// </remarks>
    public static class BoardAttributes
    {
        public const string Kind = "board.kind";
        public const string Content = "board.content";
        public const string Parent = "board.parent";
    }
}

/// <summary>
/// A single injected-contract event emitted by a non-AI-Forward session over the <c>coord-core</c>
/// append log (spike S4). <see cref="ExternalSessionId"/> is the session's own id; the registrar mints
/// its own internal id, so the adapter owns the external-&gt;internal map.
/// </summary>
public abstract record CoordContractEvent(string ExternalSessionId, double At, int Seq);

/// <summary>A registration: carries the same <see cref="OtelAttributes"/> keys as the OTLP path.</summary>
public sealed record ContractRegister(
    string ExternalSessionId,
    IReadOnlyDictionary<string, string?> Attributes,
    double At,
    int Seq) : CoordContractEvent(ExternalSessionId, At, Seq);

/// <summary>A liveness heartbeat for an already-registered external session.</summary>
public sealed record ContractHeartbeat(string ExternalSessionId, double At, int Seq)
    : CoordContractEvent(ExternalSessionId, At, Seq);

/// <summary>A voluntary session end (minimal in slice 2: drops the external-&gt;internal mapping).</summary>
public sealed record ContractSessionEnd(string ExternalSessionId, double At, int Seq)
    : CoordContractEvent(ExternalSessionId, At, Seq);

/// <summary>
/// Later-known attributes for an already-registered session: the harness, the model.
/// </summary>
/// <remarks>
/// <para><b>Why a distinct kind rather than a second <c>register</c>.</b> A repeat registration is
/// dropped entirely — <c>ApplyRegister</c> returns before reaching the registrar, so the richer
/// attributes never arrive (observed:
/// <c>Apply_DuplicateRegister_DiscardsTheSecondAttributes_ItDoesNotMerge</c>). That is correct for a
/// duplicate: the first registration's capability must stand, or an external id could be used to
/// re-mint one. Enrichment is a different intent and needs its own verb.</para>
///
/// <para><b>Which is the whole reason it exists.</b> AI-DE registers a terminal before knowing what
/// runs inside it, and the model is knowable only by the agent — chosen inside the session and
/// changeable mid-session. Without this the model can never be recorded for any AI-DE-launched
/// session, no matter what anyone builds.</para>
///
/// <para><b>Additive within <c>loomkeeper/1</c>, deliberately.</b> The parser already skips a
/// syntactically valid line whose <c>kind</c> it does not handle, so an older reader ignores this
/// where a version bump would have made it reject the whole log. A schema change is a contract
/// change — but this adds a kind rather than altering one, and the existing tolerance is what makes
/// that safe rather than a hope.</para>
///
/// <para><b>It cannot mint or alter identity.</b> Only the attributes an update may carry are
/// merged; repository, worktree, terminal and agent are fixed at registration. An update naming an
/// unknown session is dropped and counted, exactly as a heartbeat for one is.</para>
/// </remarks>
public sealed record ContractUpdate(
    string ExternalSessionId,
    IReadOnlyDictionary<string, string?> Attributes,
    double At,
    int Seq) : CoordContractEvent(ExternalSessionId, At, Seq);

/// <summary>
/// A session declaring a bounded objective it is starting work on: the goal, the terminal condition
/// it will be judged against, and optionally what it is not doing.
/// </summary>
/// <remarks>
/// <para><b>Why the agent declares this and the shell cannot.</b> An episode is the unit scoring
/// attaches to, and it needs a goal. The workbench knows a terminal exists; it does not know what
/// the agent inside it is trying to do. Opening an episode per terminal with a placeholder goal
/// would <i>fabricate</i> one (NG1), and the scorer already treats a missing goal honestly — Not
/// Scored with the reason, never a low mark. So the declaration comes from the only party that has
/// it.</para>
///
/// <para><b>Why this is the multi-harness unblock.</b> Before it,
/// <see cref="AuditLogEpisodeSource"/> was the only producer of episodes, so an episode existed
/// only where the AI-Forward pack had written an audit entry. A GitHub Copilot session or a plain
/// shell produced none, and the leaderboard could not compare what it was built to compare.</para>
///
/// <para><b>A blank goal is malformed, not an empty episode.</b> Opening one with an empty
/// statement would score as Not Scored and read as "the agent declared nothing", when in fact the
/// declaration was invented here.</para>
/// </remarks>
public sealed record ContractEpisodeOpen(
    string ExternalSessionId,
    IReadOnlyDictionary<string, string?> Attributes,
    double At,
    int Seq) : CoordContractEvent(ExternalSessionId, At, Seq);

/// <summary>
/// A session closing its current episode with a declared outcome.
/// </summary>
/// <remarks>
/// The outcome is the <b>declared</b> lifecycle terminal state, not a quality judgement. Whether a
/// <c>Completed</c> claim is honest is the Weave's Outcome-integrity dimension, which reads
/// deterministic evidence rather than this field — so an agent claiming Completed on unmet
/// acceptance criteria is exactly the case the scorer already detects.
/// </remarks>
public sealed record ContractEpisodeClose(
    string ExternalSessionId,
    IReadOnlyDictionary<string, string?> Attributes,
    double At,
    int Seq) : CoordContractEvent(ExternalSessionId, At, Seq);

/// <summary>
/// A session posting to its repository's Message Board: a question, a decision, a breadcrumb, a
/// knowledge candidate, or a reply or acknowledgement of an existing message.
/// </summary>
/// <remarks>
/// <para><b>Why this kind exists.</b> The Message Board was implemented, tested and rendered, and
/// <see cref="MessageBoardService"/> had <b>no callers anywhere in the product</b> — no ingest path,
/// no MCP tool, no UI affordance. It was a read surface over a store nothing wrote to. An agent
/// asked to "post to the loomkeeper board" searched the repository for how, found nothing, and the
/// pane went on saying "No board posts yet". The agent was right; the mechanism did not exist. The
/// parser's own comment had been calling this "a future board post" since slice 2.</para>
///
/// <para><b>The repository is not the sender's to choose.</b> It is read from the registered
/// session's binding. Accepting it as an attribute would let a session post onto another
/// repository's board by naming it — the same hole as an update restating identity, and the board
/// is precisely where a forged origin would be most persuasive to a reader.</para>
///
/// <para><b>Content stays untrusted.</b> The service quarantines every post and flags
/// grader-injection shapes; this kind changes none of that. What arrives over a file anything can
/// append to is data, and the scorer reads typed signals rather than board prose, which is what
/// makes that guarantee hold rather than depend on the flag being accurate.</para>
/// </remarks>
public sealed record ContractBoardPost(
    string ExternalSessionId,
    IReadOnlyDictionary<string, string?> Attributes,
    double At,
    int Seq) : CoordContractEvent(ExternalSessionId, At, Seq);

/// <summary>Parse-layer counters (IO1): how many lines were malformed or rejected on version.</summary>
public sealed record CoordContractParseStats(long Parsed, long Malformed, long VersionRejected);

/// <summary>
/// Reads a <c>coord-core</c> append log tolerantly into ordered contract events, stdlib only. One JSON
/// object per line; a blank line (including the LOG-A leading newline), a CRLF terminator, and
/// surrounding whitespace are tolerated; a malformed line is skipped and counted; a line whose
/// <c>contract</c> version is not <see cref="CoordContract.Version"/> is rejected and counted. Events are
/// returned sorted <c>(at, externalSessionId, seq)</c> so replay is deterministic (mirrors coord-core fold).
///
/// A syntactically valid line whose <c>kind</c> is not one this slice handles (e.g. a future board post
/// sharing the same log) is silently skipped - it is not this parser's event, not an error.
/// </summary>
public static class CoordContractParser
{
    public static IReadOnlyList<CoordContractEvent> Parse(string jsonl)
        => Parse(jsonl, out _);

    public static IReadOnlyList<CoordContractEvent> Parse(string jsonl, out CoordContractParseStats stats)
    {
        var events = new List<CoordContractEvent>();
        long malformed = 0, versionRejected = 0;

        if (!string.IsNullOrEmpty(jsonl))
        {
            foreach (var raw in jsonl.Split('\n'))
            {
                var line = raw.Trim(); // tolerate CRLF, leading/trailing whitespace, the LOG-A leading newline
                if (line.Length == 0)
                {
                    continue;
                }

                JsonDocument doc;
                try
                {
                    doc = JsonDocument.Parse(line);
                }
                catch (JsonException)
                {
                    malformed++;
                    continue;
                }

                using (doc)
                {
                    var root = doc.RootElement;
                    if (root.ValueKind != JsonValueKind.Object)
                    {
                        malformed++;
                        continue;
                    }

                    if (Str(root, CoordContract.VersionKey) != CoordContract.Version)
                    {
                        versionRejected++;
                        continue;
                    }

                    var evt = ToEvent(root);
                    if (evt is not null)
                    {
                        events.Add(evt);
                    }
                }
            }
        }

        events.Sort(static (x, y) =>
        {
            var c = x.At.CompareTo(y.At);
            if (c != 0)
            {
                return c;
            }

            c = string.CompareOrdinal(x.ExternalSessionId, y.ExternalSessionId);
            return c != 0 ? c : x.Seq.CompareTo(y.Seq);
        });

        stats = new CoordContractParseStats(events.Count, malformed, versionRejected);
        return events;
    }

    private static CoordContractEvent? ToEvent(JsonElement root)
    {
        var session = Str(root, "session") ?? "";
        var at = root.TryGetProperty("at", out var atEl) && atEl.ValueKind == JsonValueKind.Number ? atEl.GetDouble() : 0;
        var seq = root.TryGetProperty("seq", out var seqEl) && seqEl.ValueKind == JsonValueKind.Number ? seqEl.GetInt32() : 0;

        return Str(root, "kind") switch
        {
            "register" => new ContractRegister(session, ReadAttrs(root), at, seq),
            "heartbeat" => new ContractHeartbeat(session, at, seq),
            "session-end" => new ContractSessionEnd(session, at, seq),
            "update" => new ContractUpdate(session, ReadAttrs(root), at, seq),
            "episode-open" => new ContractEpisodeOpen(session, ReadAttrs(root), at, seq),
            "episode-close" => new ContractEpisodeClose(session, ReadAttrs(root), at, seq),
            "board-post" => new ContractBoardPost(session, ReadAttrs(root), at, seq),
            _ => null, // a valid line of a kind this slice does not handle (e.g. a board post)
        };
    }

    private static IReadOnlyDictionary<string, string?> ReadAttrs(JsonElement root)
    {
        var attrs = new Dictionary<string, string?>(StringComparer.Ordinal);
        if (root.TryGetProperty("attrs", out var attrsEl) && attrsEl.ValueKind == JsonValueKind.Object)
        {
            foreach (var p in attrsEl.EnumerateObject())
            {
                attrs[p.Name] = p.Value.ValueKind == JsonValueKind.String ? p.Value.GetString() : null;
            }
        }

        return attrs;
    }

    private static string? Str(JsonElement e, string name)
        => e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;
}

/// <summary>A snapshot of the adapter counters (IO1 operator questions).</summary>
public sealed record CoordContractStats(
    long Registered, long Heartbeats, long Unknown, long DuplicateRegister, long Quarantined,
    long Updated = 0, long EpisodesOpened = 0, long EpisodesClosed = 0, long BoardPosts = 0,
    long ArtifactsDeclared = 0);

/// <summary>
/// The injected-contract ingest adapter: maps contract events onto the same
/// <see cref="TrustedRegistrar"/>/<see cref="IngestHost"/> as the OTLP path, so a non-AI-Forward session
/// appears identically in the fact store (one ledger, projected, not duplicated - US-5).
///
/// The append log is a local, forgeable surface (ADR-0007), so - symmetrically with the OTLP token -
/// the <see cref="SessionCapability"/> is never read from the file: this adapter <b>mints</b> it at
/// <c>register</c> and holds <c>external-id -&gt; RegisteredSession</c>, verifying every <c>heartbeat</c>
/// against the held capability. A heartbeat for a session never registered here has no capability and is
/// dropped and counted; a duplicate register is ignored (the first capability stands); a register whose
/// identity is incomplete is quarantined (LK-0004) without stopping the stream (US-11 fail honestly).
///
/// Pattern: Adapter over the ingest host's port (DDD ACL), keyed by the external session id.
/// </summary>
public sealed class InjectedContractIngest
{
    private readonly IngestHost _host;
    private readonly Dictionary<string, RegisteredSession> _byExternalId = new(StringComparer.Ordinal);

    private long _registered;
    private long _heartbeats;
    private long _unknown;
    private long _duplicateRegister;
    private long _quarantined;
    private long _updated;
    private long _episodesOpened;
    private long _episodesClosed;
    private long _artifactsDeclared;
    private long _boardPosts;

    // The external session's currently open episode. An episode-close names no episode id - the
    // agent knows it has one open, not what the registrar called it - so the adapter remembers.
    private readonly Dictionary<string, string> _openEpisodeByExternalId = new(StringComparer.Ordinal);

    public InjectedContractIngest(IngestHost host)
    {
        ArgumentNullException.ThrowIfNull(host);
        _host = host;
    }

    public CoordContractStats Stats => new(
        _registered, _heartbeats, _unknown, _duplicateRegister, _quarantined, _updated,
        _episodesOpened, _episodesClosed, _boardPosts, _artifactsDeclared);

    /// <summary>Applies a batch in order. Callers pass parser output, already sorted.</summary>
    public void ApplyAll(IEnumerable<CoordContractEvent> events)
    {
        ArgumentNullException.ThrowIfNull(events);
        foreach (var evt in events)
        {
            Apply(evt);
        }
    }

    /// <summary>Applies one contract event. Never throws on a bad event; every disposition is counted.</summary>
    public void Apply(CoordContractEvent evt)
    {
        ArgumentNullException.ThrowIfNull(evt);
        switch (evt)
        {
            case ContractRegister register:
                ApplyRegister(register);
                break;
            case ContractHeartbeat heartbeat:
                ApplyHeartbeat(heartbeat);
                break;

            case ContractUpdate update:
                ApplyUpdate(update);
                break;
            case ContractEpisodeOpen open:
                ApplyEpisodeOpen(open);
                break;
            case ContractEpisodeClose close:
                ApplyEpisodeClose(close);
                break;
            case ContractBoardPost post:
                ApplyBoardPost(post);
                break;
            case ContractSessionEnd end:
                if (_byExternalId.TryGetValue(end.ExternalSessionId, out var ending))
                {
                    // Mark the internal session ended so liveness reads Ended, not a lingering Alive/Stale.
                    _host.EndSession(ending.Session.SessionId);
                }

                _byExternalId.Remove(end.ExternalSessionId);

                // An episode left open when the session ends stays open. Closing it here would
                // invent an outcome, and EpisodeOutcome has no "unknown" member for a reason: the
                // scorer's Not-Scored gate already reports an episode that never closed, honestly
                // and with the reason. A fabricated Abandoned would score instead of abstaining.
                _openEpisodeByExternalId.Remove(end.ExternalSessionId);
                break;
        }
    }

    /// <summary>Merges later-known harness/model onto a session this adapter already registered.</summary>
    /// <remarks>
    /// An update for a session this adapter did not register is counted as <c>Unknown</c> and
    /// dropped, exactly as a heartbeat for one is — the capability lives here and was never minted
    /// for it, so there is nothing to authorise the write.
    /// </remarks>
    private void ApplyUpdate(ContractUpdate update)
    {
        if (!_byExternalId.TryGetValue(update.ExternalSessionId, out var known))
        {
            _unknown++;
            return;
        }

        var harnessName = Attr(update.Attributes, OtelAttributes.ServiceName);
        var modelName = Attr(update.Attributes, OtelAttributes.GenAiModel);
        if (harnessName is null && modelName is null)
        {
            // Nothing this event is allowed to carry. Counted rather than ignored, so a sender
            // writing the wrong keys shows up as a number instead of as silence.
            _unknown++;
            return;
        }

        _host.UpdateHarnessAndModel(
            known.Session.SessionId,
            known.Capability,
            harnessName is null
                ? null
                : new HarnessIdentity(harnessName, Attr(update.Attributes, OtelAttributes.ServiceVersion) ?? "unknown"),
            modelName is null
                ? null
                : new ModelIdentity(modelName, Attr(update.Attributes, OtelAttributes.GenAiModelVersion) ?? "unknown"));

        _updated++;
    }

    /// <summary>Opens a Work Episode a registered session declared over the contract log.</summary>
    /// <remarks>
    /// <para><b>An unregistered session is dropped, never auto-registered.</b> Registration is where
    /// trust is decided and where the capability is minted; letting an episode create a session
    /// would make it a side door into both.</para>
    ///
    /// <para><b>A second open supersedes through the service, not through logic here.</b> The
    /// episode service already defines what a changed goal means — close the current one
    /// <c>Superseded</c>, open the next generation — so this calls <c>Reframe</c> rather than
    /// re-deciding it. A rule implemented twice is a rule that will disagree with itself.</para>
    /// </remarks>
    private void ApplyEpisodeOpen(ContractEpisodeOpen open)
    {
        if (!_byExternalId.TryGetValue(open.ExternalSessionId, out var known))
        {
            _unknown++;
            return;
        }

        var goal = Attr(open.Attributes, CoordContract.EpisodeAttributes.Goal);
        var doneWhen = Attr(open.Attributes, CoordContract.EpisodeAttributes.DoneWhen);
        if (goal is null || doneWhen is null)
        {
            // Neither is defaulted. An episode with an invented goal or terminal condition would be
            // scored against something no agent declared.
            _quarantined++;
            return;
        }

        var notInScope = Attr(open.Attributes, CoordContract.EpisodeAttributes.NotInScope);

        try
        {
            var episode = _openEpisodeByExternalId.TryGetValue(open.ExternalSessionId, out var current)
                ? _host.ReframeEpisode(current, known.Capability, new Goal(goal), new DoneCondition(doneWhen), notInScope)
                : _host.OpenEpisode(known.Session.SessionId, known.Capability, new Goal(goal), new DoneCondition(doneWhen), notInScope);

            _openEpisodeByExternalId[open.ExternalSessionId] = episode.EpisodeId;
            _episodesOpened++;
        }
        catch (WatcherException)
        {
            // One bad event never kills the stream (US-11). Counted, so a sender getting it wrong
            // shows up as a number rather than as silence.
            _quarantined++;
        }
    }

    /// <summary>Closes the session's open episode with the outcome it declared.</summary>
    /// <remarks>
    /// A close naming no known open episode is <c>Unknown</c>, and an unparseable outcome is
    /// quarantined rather than defaulted to <c>Completed</c> — the one value it must never guess,
    /// because Outcome-integrity reads it.
    /// </remarks>
    private void ApplyEpisodeClose(ContractEpisodeClose close)
    {
        if (!_byExternalId.TryGetValue(close.ExternalSessionId, out var known)
            || !_openEpisodeByExternalId.TryGetValue(close.ExternalSessionId, out var episodeId))
        {
            _unknown++;
            return;
        }

        var declared = Attr(close.Attributes, CoordContract.EpisodeAttributes.Outcome);
        if (declared is null || !Enum.TryParse<EpisodeOutcome>(declared, ignoreCase: true, out var outcome))
        {
            _quarantined++;
            return;
        }

        // A malformed OPTIONAL attribute quarantines the whole line rather than being dropped so the
        // close can proceed. Dropping it would close the episode while discarding what the agent said
        // about its evidence — the agent believes it declared a Proof Pack, the product silently
        // disagrees, and nothing tells either of them. Quarantine is loud, it is counted, and the
        // episode stays open so a corrected re-close still works.
        // The RAW value, not Attr(). Attr collapses present-but-blank into null, which is right for
        // every required attribute here — a blank goal and a missing goal are both "no goal". It is
        // wrong for this one: absent means "I declare no evidence" and blank means "I meant to say
        // something", and those want opposite answers. Reading through Attr would have made a value
        // lost in transit indistinguishable from a deliberate silence, which is the two-states-one-
        // rendering shape this whole channel exists to remove. Caught by a test, not by review.
        var rawArtifacts = close.Attributes.TryGetValue(
            CoordContract.EpisodeAttributes.Artifacts, out var declaredArtifacts) ? declaredArtifacts : null;

        if (!DeclaredArtifactBounds.TryParse(rawArtifacts, out var artifacts))
        {
            _quarantined++;
            return;
        }

        try
        {
            // Declared BEFORE the close, deliberately. If the declaration failed after a successful
            // close we would have an episode whose evidence was silently lost; failing the other way
            // leaves rows whose episode never closed, which is detectable. Between a silent loss and
            // a visible orphan, take the orphan.
            _host.DeclareEpisodeArtifacts(episodeId, known.Capability, artifacts);

            _host.CloseEpisode(episodeId, known.Capability, outcome);
            _openEpisodeByExternalId.Remove(close.ExternalSessionId);
            _episodesClosed++;
            _artifactsDeclared += artifacts.Count;
        }
        catch (WatcherException)
        {
            _quarantined++;
        }
    }

    /// <summary>Applies a Message Board post from a registered session.</summary>
    /// <remarks>
    /// <para><b>The repository comes from the binding, never the wire.</b> A session's repository is
    /// fixed at registration; accepting it as an attribute would let any writer put a message on
    /// another repository's board by naming it. The board is exactly where a forged origin would be
    /// most persuasive, because its whole purpose is that another agent reads and believes it.</para>
    ///
    /// <para><b>Nothing is defaulted.</b> An unrecognised kind is quarantined rather than treated as
    /// a Question, and a post with no content is quarantined rather than posted empty — an empty
    /// message on a board is indistinguishable from one whose text was lost.</para>
    ///
    /// <para><b>The service keeps its own guarantees.</b> Capability verification, the orphan refusal
    /// on a reply or acknowledgement, quarantining and grader-injection flagging all still happen
    /// there; this method routes and refuses, it does not re-decide.</para>
    /// </remarks>
    private void ApplyBoardPost(ContractBoardPost post)
    {
        if (!_byExternalId.TryGetValue(post.ExternalSessionId, out var known))
        {
            _unknown++;
            return;
        }

        var declared = Attr(post.Attributes, CoordContract.BoardAttributes.Kind);
        if (declared is null
            || !Enum.TryParse<BoardMessageKind>(declared.Replace("-", ""), ignoreCase: true, out var kind))
        {
            _quarantined++;
            return;
        }

        var content = Attr(post.Attributes, CoordContract.BoardAttributes.Content);
        var parent = Attr(post.Attributes, CoordContract.BoardAttributes.Parent);

        // An acknowledgement carries no content by design; everything else must say something.
        if (kind != BoardMessageKind.Acknowledgement && content is null)
        {
            _quarantined++;
            return;
        }

        if (kind is BoardMessageKind.Reply or BoardMessageKind.Acknowledgement && parent is null)
        {
            _quarantined++;
            return;
        }

        var repository = known.Session.Binding.Repository.CanonicalPath;

        try
        {
            _ = kind switch
            {
                BoardMessageKind.Reply =>
                    _host.ReplyOnBoard(repository, known.Session.SessionId, known.Capability, parent!, content!),
                BoardMessageKind.Acknowledgement =>
                    _host.AcknowledgeOnBoard(repository, known.Session.SessionId, known.Capability, parent!),
                _ => _host.PostToBoard(repository, known.Session.SessionId, known.Capability, kind, content!),
            };

            _boardPosts++;
        }
        catch (WatcherException)
        {
            // A reply naming a parent that does not exist in this repository is refused by the
            // service as an orphan. Counted, never fatal: one bad line must not stop the stream.
            _quarantined++;
        }
    }

    private static string? Attr(IReadOnlyDictionary<string, string?> attrs, string key)
        => attrs.TryGetValue(key, out var v) && !string.IsNullOrWhiteSpace(v) ? v : null;

    private void ApplyRegister(ContractRegister register)
    {
        if (_byExternalId.ContainsKey(register.ExternalSessionId))
        {
            _duplicateRegister++; // idempotent: the first registration's capability stands
            return;
        }

        RegisteredSession session;
        try
        {
            session = _host.Register(new HarnessRegistration(register.Attributes));
        }
        catch (WatcherException ex) when (ex.Code == WatcherErrorCodes.MalformedEvent)
        {
            _quarantined++; // incomplete identity (LK-0004); the stream survives it (US-11)
            return;
        }

        _byExternalId[register.ExternalSessionId] = session;
        _registered++;
    }

    private void ApplyHeartbeat(ContractHeartbeat heartbeat)
    {
        // No capability was minted here for this external id -> it was never registered -> drop it.
        // The file cannot present a capability, so an unregistered heartbeat is unverifiable by design.
        if (!_byExternalId.TryGetValue(heartbeat.ExternalSessionId, out var session))
        {
            _unknown++;
            return;
        }

        _host.Heartbeat(session.SessionId, session.Capability);
        _heartbeats++;
    }
}
