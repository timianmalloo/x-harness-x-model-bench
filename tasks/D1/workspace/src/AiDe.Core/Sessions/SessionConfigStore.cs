using System.Text.Json;
using AiDe.Core.AgentPlane;
using System.Text.Json.Nodes;

namespace AiDe.Core.Sessions;

/// <summary>
/// Reads and writes one session's <c>session.json</c> and <c>session-events.jsonl</c> (clauses 1-3).
/// </summary>
/// <remarks>
/// <para><b>Changes apply to new turns only (clause 3; Ruling 105 condition 2).</b>
/// <see cref="SessionConfig"/> is an immutable record; <see cref="SetDefaultAccount"/> and
/// <see cref="SetAccounts"/> never mutate an existing instance, they write a new one. A caller that
/// already captured a <see cref="SessionConfig"/> (a turn reading its config at start) is holding a
/// value a later change cannot reach — proven in
/// <c>SessionAccountsTests.SetDefaultAccount_NeverMutatesAConfigARunAlreadyCaptured_AndAppliesToTheNextTurnOnly</c>.
/// The append-only event log gives the same guarantee one layer down, at the persisted bytes: earlier
/// lines are never rewritten (<c>SessionEventsFile_EarlierEventsSurviveByteForByteAfterALaterToggle</c>).
/// </para>
///
/// <para><b>The legacy <c>EnabledBackends</c> key is read, kept, and contracted only once mapped.</b>
/// A <c>session.json</c> written before Ruling 105 carries engine ids. <see cref="Load"/> reads them
/// into <see cref="SessionConfig.LegacyEnabledBackends"/> (no accounts, no default) and every write
/// re-emits the key verbatim until <see cref="MigrateLegacyBackends"/> maps them against a provider
/// file — an engine id maps to its provider's account only when the file names one
/// (<c>engines.&lt;id&gt;.account</c>, the fallback default) or the provider carries exactly one;
/// otherwise the session keeps "no default account — choose one" and the key stays. Never a guessed label.</para>
///
/// <para>Idiom matches <c>Health.HealthIncidentSidecar</c>: a single lock around read-modify-write,
/// plain <c>System.Text.Json</c>, tolerant JSONL reads.</para>
/// </remarks>
public sealed class SessionConfigStore
{
    private static readonly JsonSerializerOptions ConfigJsonOptions = new() { WriteIndented = true };

    private readonly Lock _gate = new();

    public SessionConfigStore(string workspaceRoot, string sessionId)
    {
        WorkspaceRoot = workspaceRoot;
        SessionId = sessionId;
    }

    public string WorkspaceRoot { get; }

    public string SessionId { get; }

    /// <summary>Creates the session: writes <c>session.json</c> and emits <c>session.open</c>.</summary>
    /// <param name="name">The operator-facing name.</param>
    /// <param name="workspaceId">The workspace this session is bound to.</param>
    /// <param name="accounts">The accounts selected for it (Ruling 105).</param>
    /// <param name="defaultAccount">The default account, or null — no default until the operator chooses.</param>
    /// <param name="now">Stamps the config and the event.</param>
    /// <param name="fanOutCeiling">The session's fan-out ceiling (Ruling 56); <c>null</c> writes the ruled default.</param>
    /// <param name="budgetCap">An enforced cap, or <c>null</c> — bounded by the subscription (Ruling 72).</param>
    /// <param name="defaultTaskClass">The session's default task class; <c>null</c> writes <c>free-form</c> (Ruling 72).</param>
    /// <param name="origin">
    /// How this session came to exist — see <see cref="SessionOrigins"/>. <b>Defaulted to
    /// <see cref="SessionOrigins.Direct"/> deliberately:</b> F5 clause 1's claim is that the front
    /// door is distinguishable from every other way of reaching this method, and that is only
    /// checkable if something which did not come through it reads differently. The default is what
    /// makes the other value evidence.
    /// </param>
    /// <remarks>The sheet's three decisions at create (Rulings 56, 63, 72); absent, the record's own defaults apply. The origin is F5's clause 1.</remarks>
    public SessionConfig Create(
        string name,
        string workspaceId,
        IReadOnlyList<AccountRef> accounts,
        AccountRef? defaultAccount,
        DateTimeOffset now,
        int? fanOutCeiling = null,
        RunBudget? budgetCap = null,
        string? defaultTaskClass = null,
        string origin = SessionOrigins.Direct)
    {
        lock (_gate)
        {
            ArgumentNullException.ThrowIfNull(accounts);
            if (defaultAccount is not null && !accounts.Contains(defaultAccount))
            {
                throw new ArgumentException($"the default account {defaultAccount} is not among the session's accounts", nameof(defaultAccount));
            }

            var config = new SessionConfig(SessionId, name, workspaceId, now, [.. accounts], defaultAccount);
            config = config with
            {
                FanOutCeiling = fanOutCeiling ?? config.FanOutCeiling,
                BudgetCap = budgetCap,
                DefaultTaskClass = defaultTaskClass ?? config.DefaultTaskClass,
            };

            WriteConfigUnsafe(config);
            AppendEventUnsafe(SessionEventKinds.Open, config, now, origin);
            return config;
        }
    }

    /// <summary>The current, live config — what a NEW run would pick up.</summary>
    public SessionConfig Load()
    {
        lock (_gate)
        {
            return ReadConfigUnsafe();
        }
    }

    /// <summary>
    /// The name of every session the workspace holds — every <c>session.json</c> under
    /// <see cref="SessionPaths.SessionsRoot"/>, open tab or not. Empty when there is no sessions
    /// root yet; a session whose file cannot be read is skipped, never a throw.
    /// </summary>
    /// <remarks>Ruling 99: uniqueness is judged against the STORE, not the open tabs — a session the
    /// operator closed still owns its name.</remarks>
    public static IReadOnlyList<string> ExistingNames(string workspaceRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(workspaceRoot);

        var root = SessionPaths.SessionsRoot(workspaceRoot);
        if (!Directory.Exists(root))
        {
            return [];
        }

        var names = new List<string>();
        foreach (var directory in Directory.EnumerateDirectories(root))
        {
            var file = Path.Combine(directory, SessionPaths.SessionFileName);
            if (!File.Exists(file))
            {
                continue;
            }

            try
            {
                if (Deserialize(File.ReadAllText(file))?.Name is { } name)
                {
                    names.Add(name);
                }
            }
            catch (Exception error) when (error is IOException or JsonException or UnauthorizedAccessException)
            {
                // A session whose file is mid-write or malformed does not own a name yet.
            }
        }

        return names;
    }

    /// <summary>
    /// The one rule for a session name that is unique within its workspace (Ruling 99): the
    /// requested name when nothing holds it, else the name with a counter — <c>" (2)"</c>, <c>" (3)"</c>,
    /// … — counted up from 2 until it is free. A counter the requested name already carries is not
    /// part of the base, so <c>"X (2)"</c> over <c>{"X", "X (2)"}</c> is <c>"X (3)"</c>, never
    /// <c>"X (2) (2)"</c>. Never refuses; no time-of-day.
    /// </summary>
    /// <remarks>
    /// Called by the sheet for its default name and for an operator-typed duplicate at Create, and by
    /// the later parallel-session slice on its parent's name — one function, so the three cannot drift.
    /// </remarks>
    public static string UniqueName(string requested, IEnumerable<string> existing)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(requested);
        ArgumentNullException.ThrowIfNull(existing);

        var taken = existing.ToHashSet(StringComparer.Ordinal);
        if (!taken.Contains(requested))
        {
            return requested;
        }

        var baseName = StripCounter(requested);
        for (var n = 2; ; n++)
        {
            var candidate = $"{baseName} ({n})";
            if (!taken.Contains(candidate))
            {
                return candidate;
            }
        }
    }

    /// <summary>"X (n)" → "X" for a trailing counter of this rule's own shape; anything else unchanged.</summary>
    private static string StripCounter(string name)
    {
        var open = name.LastIndexOf(" (", StringComparison.Ordinal);
        if (open <= 0 || !name.EndsWith(')'))
        {
            return name;
        }

        var digits = name.AsSpan(open + 2, name.Length - open - 3);
        return digits.Length > 0 && int.TryParse(digits, System.Globalization.NumberStyles.None, System.Globalization.CultureInfo.InvariantCulture, out _)
            ? name[..open]
            : name;
    }

    /// <summary>
    /// Changes the default account for new turns only and emits <c>session.config</c> (Ruling 105
    /// condition 2). Never mutates a <see cref="SessionConfig"/> a caller already holds — see the
    /// remarks on this type.
    /// </summary>
    /// <exception cref="ArgumentException">The account is not among the session's accounts.</exception>
    public SessionConfig SetDefaultAccount(AccountRef? account, DateTimeOffset now)
    {
        lock (_gate)
        {
            var current = ReadConfigUnsafe();
            if (account is not null && !current.Accounts.Contains(account))
            {
                throw new ArgumentException($"the account {account} is not among this session's accounts", nameof(account));
            }

            var updated = current with { DefaultAccount = account };
            WriteConfigUnsafe(updated);
            AppendEventUnsafe(SessionEventKinds.Config, updated, now);
            return updated;
        }
    }

    /// <summary>
    /// Replaces the session's account list for new turns only and emits <c>session.config</c>. A
    /// default no longer in the list is dropped to <c>null</c> — never kept as a phantom the next turn
    /// would bill.
    /// </summary>
    public SessionConfig SetAccounts(IReadOnlyList<AccountRef> accounts, DateTimeOffset now)
    {
        ArgumentNullException.ThrowIfNull(accounts);

        lock (_gate)
        {
            var current = ReadConfigUnsafe();
            var updated = current with
            {
                Accounts = [.. accounts],
                DefaultAccount = current.DefaultAccount is { } d && accounts.Contains(d) ? d : null,
            };
            WriteConfigUnsafe(updated);
            AppendEventUnsafe(SessionEventKinds.Config, updated, now);
            return updated;
        }
    }

    /// <summary>
    /// Maps a pre-Ruling-105 session's <c>EnabledBackends</c> engine ids to accounts against the
    /// provider file: each id → its catalog row's provider → the file's fallback default for that
    /// engine (<c>engines.&lt;id&gt;.account</c>) or the provider's sole account; the first mapped
    /// account becomes the default. Contracts the legacy key and emits <c>session.config</c> only when
    /// at least one id mapped; otherwise nothing is written — the session opens with "no default
    /// account — choose one" and the key survives for a later, better-informed run.
    /// </summary>
    /// <returns>The config as it now reads.</returns>
    public SessionConfig MigrateLegacyBackends(ProviderConfiguration providers, DateTimeOffset now)
    {
        ArgumentNullException.ThrowIfNull(providers);

        lock (_gate)
        {
            var current = ReadConfigUnsafe();
            if (current.LegacyEnabledBackends.Count == 0)
            {
                return current;
            }

            var mapped = new List<AccountRef>();
            foreach (var engineId in current.LegacyEnabledBackends)
            {
                if (providers.FallbackDefaultAccount(engineId) is { } fallback
                    && new AccountRef(fallback.Provider, fallback.Label) is { } account
                    && !mapped.Contains(account))
                {
                    mapped.Add(account);
                }
            }

            if (mapped.Count == 0)
            {
                return current;
            }

            var updated = current with
            {
                Accounts = mapped,
                DefaultAccount = mapped[0],
                LegacyEnabledBackends = [],
            };
            WriteConfigUnsafe(updated);
            AppendEventUnsafe(SessionEventKinds.Config, updated, now);
            return updated;
        }
    }

    /// <summary>Appends a <c>session.open</c> line for a file a test wrote by hand (the file predates the code).</summary>
    internal void AppendOpenForTests(DateTimeOffset now)
    {
        lock (_gate)
        {
            AppendEventUnsafe(SessionEventKinds.Open, ReadConfigUnsafe(), now, SessionOrigins.Direct);
        }
    }

    /// <summary>
    /// Applies the attach toggle for new runs and emits <c>session.config</c> (C21).
    /// </summary>
    /// <remarks>
    /// <para><b>Through the store, exactly like the backend toggle.</b> C21 needs no Settings surface
    /// and invents no config concept: it is a new field on an existing record, written with an
    /// existing event kind, by the same read-modify-write under the same lock.</para>
    ///
    /// <para><b>Host-owned and unreachable from the page (C21(e)).</b> No page-to-host kind reads or
    /// writes it and none may be added — the page may be <i>told</i> the state so it can render a
    /// disabled affordance; it may never <i>report</i> it. The asymmetry is deliberate: the composer
    /// may not carry a dial that loosens governance, and this one only restricts.</para>
    /// </remarks>
    public SessionConfig SetAttachEnabled(bool attachEnabled, DateTimeOffset now)
    {
        lock (_gate)
        {
            var updated = ReadConfigUnsafe() with { AttachEnabled = attachEnabled };
            WriteConfigUnsafe(updated);
            AppendEventUnsafe(SessionEventKinds.Config, updated, now);
            return updated;
        }
    }

    /// <summary>
    /// Selects the session's <c>compile_mode</c> for new envelopes, <b>through the gate</b>
    /// (ADR-0036 rule 1): a rung the evaluated <paramref name="availability"/> does not admit is
    /// refused with the gate's own code and the file is not touched. Emits <c>session.config</c>,
    /// and — when the mode actually changes — <c>compile.mode.changed{from, to, trigger}</c>
    /// (CV-4; ADR-0036's transition history).
    /// </summary>
    /// <param name="trigger">
    /// Why the mode is changing — one of <see cref="PromptCompilation.CompileModeChangeTriggers.All"/>.
    /// Defaults to <see cref="PromptCompilation.CompileModeChangeTriggers.Operator"/> (the settings
    /// sheet is the only caller today); the gate/ring/drift triggers are for an automated demotion
    /// or re-admission to name its own cause.
    /// </param>
    /// <exception cref="PromptCompilation.EnvelopeStoreException">
    /// <see cref="PromptCompilation.EnvelopeStoreErrorCodes.CompileModeUnknown"/> for a word outside
    /// the ladder; otherwise the refusal the gate computed (<c>CE-0016</c>–<c>CE-0029</c>).
    /// </exception>
    public SessionConfig SetCompileMode(string compileMode, CompileModeAvailability availability, DateTimeOffset now, string trigger = PromptCompilation.CompileModeChangeTriggers.Operator)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(compileMode);
        ArgumentNullException.ThrowIfNull(availability);
        ArgumentException.ThrowIfNullOrWhiteSpace(trigger);

        if (!CompileModeGate.Modes.Contains(compileMode, StringComparer.Ordinal))
        {
            throw new PromptCompilation.EnvelopeStoreException(
                PromptCompilation.EnvelopeStoreErrorCodes.CompileModeUnknown,
                $"'{compileMode}' is not a compile mode; the ladder is {string.Join(" → ", CompileModeGate.Modes)}");
        }

        if (!PromptCompilation.CompileModeChangeTriggers.All.Contains(trigger, StringComparer.Ordinal))
        {
            throw new ArgumentOutOfRangeException(nameof(trigger), trigger, $"the trigger vocabulary is {string.Join(", ", PromptCompilation.CompileModeChangeTriggers.All)}");
        }

        if (availability.RefusalFor(compileMode) is { } refusal)
        {
            throw new PromptCompilation.EnvelopeStoreException(refusal.Code, refusal.Reason);
        }

        lock (_gate)
        {
            var previous = ReadConfigUnsafe();
            var updated = previous with { CompileMode = compileMode };
            WriteConfigUnsafe(updated);
            AppendEventUnsafe(SessionEventKinds.Config, updated, now);
            if (!string.Equals(previous.CompileMode, compileMode, StringComparison.Ordinal))
            {
                PromptCompilation.CompileSignal.ModeChanged(previous.CompileMode, compileMode, trigger);
            }

            return updated;
        }
    }

    /// <summary>Every event this session has ever emitted, in append order.</summary>
    public IReadOnlyList<SessionEvent> ReadEvents()
    {
        lock (_gate)
        {
            return ReadEventsUnsafe();
        }
    }

    /// <summary>
    /// The Session aggregate's own delete: removes the session directory, and with it — by
    /// containment, never by a second delete path — the compile history the composer keeps beside
    /// <c>session.json</c> (ADR-0034 rule 6; F-12).
    /// </summary>
    /// <remarks>
    /// <para><b>Probe → move to a tombstone → delete the envelope file → delete the rest.</b> The
    /// envelope file is first opened exclusively as a probe, so a composer (or a second AI-DE) that
    /// holds it refuses the whole delete by name before anything is removed. The directory is then
    /// moved to a tombstone: a directory move fails on Windows while any file inside is open, so it
    /// is the directory-level lock the design lacked — a writer that opened in the window after the
    /// probe refuses the delete whole, and once moved no writer can open at the session's path
    /// (<c>EnvelopeStore.Open</c> refuses <c>NoSessionDirectory</c>). Then the envelope file, then
    /// the siblings. The naive order — acquire, release, recursive delete — reopens the race: a
    /// recursive delete on Windows removes the siblings and then fails on a locked file, leaving
    /// <c>session.json</c> gone and <c>envelope-events.jsonl</c> orphaned, the exact orphan the
    /// cascade exists to prevent (the D&amp;P Architect's finding, twice).</para>
    /// </remarks>
    /// <exception cref="PromptCompilation.EnvelopeStoreException">
    /// <see cref="PromptCompilation.EnvelopeStoreErrorCodes.HeldByAnotherWriter"/> — refused whole, nothing removed.
    /// </exception>
    /// <exception cref="IOException">A sibling could not be removed; the envelope file is already gone by then.</exception>
    public void Delete()
    {
        lock (_gate)
        {
            var directory = SessionPaths.SessionDirectory(WorkspaceRoot, SessionId);
            if (!Directory.Exists(directory))
            {
                return;
            }

            var envelopes = Path.Combine(directory, PromptCompilation.EnvelopeStore.FileName);
            if (File.Exists(envelopes))
            {
                try
                {
                    // A PROBE, not the deletion: an exclusive open detects a live writer and names it;
                    // the file itself goes with its directory below, after the move has made a new
                    // writer impossible — so a refusal here leaves everything exactly as it was.
                    using var held = new FileStream(envelopes, FileMode.Open, FileAccess.ReadWrite, FileShare.None);
                }
                catch (IOException error) when (error is not FileNotFoundException)
                {
                    throw new PromptCompilation.EnvelopeStoreException(
                        PromptCompilation.EnvelopeStoreErrorCodes.HeldByAnotherWriter,
                        $"another AI-DE has this session's compile history open ({envelopes}); the session was not deleted",
                        error);
                }
            }

            // THE TOMBSTONE CLOSES THE WINDOW between the handle's release and the recursive delete: a
            // writer that opened the file in that window (OpenOrCreate) would otherwise leave the
            // recursive delete removing session.json and failing on the held file — the orphan. A
            // directory move fails on Windows while any file inside is open, so the move is the
            // directory-level lock the design lacks; once moved, EnvelopeStore.Open at the session's
            // path refuses NoSessionDirectory, and the tombstone is removed whole.
            var tombstone = directory + ".deleting-" + Guid.NewGuid().ToString("n")[..8];
            try
            {
                Directory.Move(directory, tombstone);
            }
            catch (IOException error)
            {
                throw new PromptCompilation.EnvelopeStoreException(
                    PromptCompilation.EnvelopeStoreErrorCodes.HeldByAnotherWriter,
                    $"a file in '{directory}' is open elsewhere; the session was not deleted",
                    error);
            }

            // The envelope file first, then the siblings — the order ADR-0034 rule 6 names, now with
            // no window in which a writer could recreate it.
            var moved = Path.Combine(tombstone, PromptCompilation.EnvelopeStore.FileName);
            if (File.Exists(moved))
            {
                File.Delete(moved);
            }

            Directory.Delete(tombstone, recursive: true);
        }
    }

    /// <summary>The pre-Ruling-105 key, read and re-written verbatim until migrated.</summary>
    private const string LegacyBackendsKey = "EnabledBackends";

    private SessionConfig ReadConfigUnsafe()
    {
        var path = SessionPaths.SessionFile(WorkspaceRoot, SessionId);
        var json = File.ReadAllText(path);
        return Deserialize(json) ?? throw new InvalidOperationException($"{path} deserialized to null");
    }

    /// <summary>
    /// Reads a <c>session.json</c> of either shape: today's (<c>Accounts</c>, <c>DefaultAccount</c>) or
    /// the legacy one (<c>EnabledBackends</c>), whose ids land on
    /// <see cref="SessionConfig.LegacyEnabledBackends"/> with no accounts and no default.
    /// </summary>
    internal static SessionConfig? Deserialize(string json)
    {
        var node = JsonNode.Parse(json) as JsonObject;
        if (node is null)
        {
            return null;
        }

        var legacy = node[LegacyBackendsKey] as JsonArray;
        node.Remove(LegacyBackendsKey);
        node[nameof(SessionConfig.Accounts)] ??= new JsonArray();

        var config = node.Deserialize<SessionConfig>();
        return config is null || legacy is null
            ? config
            : config with { LegacyEnabledBackends = [.. legacy.Select(n => n?.GetValue<string>()).OfType<string>()] };
    }

    private void WriteConfigUnsafe(SessionConfig config)
    {
        Directory.CreateDirectory(SessionPaths.SessionDirectory(WorkspaceRoot, SessionId));

        // EXPAND, NOT CONTRACT: an unmigrated session's legacy key rides every write verbatim, so a
        // toggle on a session read with no provider file cannot lose the ids a later migration maps.
        var node = JsonSerializer.SerializeToNode(config, ConfigJsonOptions)!.AsObject();
        if (config.LegacyEnabledBackends.Count > 0)
        {
            node[LegacyBackendsKey] = new JsonArray([.. config.LegacyEnabledBackends.Select(b => JsonValue.Create(b))]);
        }

        File.WriteAllText(
            SessionPaths.SessionFile(WorkspaceRoot, SessionId),
            node.ToJsonString(ConfigJsonOptions));
    }

    private void AppendEventUnsafe(string kind, SessionConfig config, DateTimeOffset now, string? origin = null)
    {
        Directory.CreateDirectory(SessionPaths.SessionDirectory(WorkspaceRoot, SessionId));

        var nextSeq = ReadEventsUnsafe() is { Count: > 0 } existing ? existing[^1].Seq + 1 : 1;
        // The body carries the resulting config: the accounts and the default (Ruling 105 — a default
        // change is this event, applying to new turns only), and the toggles. `attachEnabled` joins
        // the same line rather than getting a kind of its own: C21 is a field on an existing record
        // with an existing event kind, and its presence in a `session.config` line is what
        // distinguishes an operator decision from the shipped default (C21(c)).
        var body = new JsonObject
        {
            ["accounts"] = new JsonArray([.. config.Accounts.Select(a => (JsonNode)new JsonObject { ["provider"] = a.Provider, ["label"] = a.Label })]),
            ["defaultAccount"] = config.DefaultAccount is { } account
                ? new JsonObject { ["provider"] = account.Provider, ["label"] = account.Label }
                : null,
            ["attachEnabled"] = config.AttachEnabled,
            // The compile mode joins the same line (ADR-0036): its presence in a `session.config`
            // event is what distinguishes an operator's selection from the shipped default.
            ["compileMode"] = config.CompileMode,
        };

        // `origin` rides `session.open` ONLY. A config toggle has no origin — the session was
        // already open — and writing one there would be a field carrying a value that answers no
        // question, which is how a reader learns to stop trusting the field.
        if (origin is not null)
        {
            body["origin"] = origin;
        }
        var line = JsonSerializer.Serialize(new SessionEvent(nextSeq, now, kind, body));

        File.AppendAllText(SessionPaths.EventsFile(WorkspaceRoot, SessionId), line + Environment.NewLine);
    }

    private List<SessionEvent> ReadEventsUnsafe()
    {
        var path = SessionPaths.EventsFile(WorkspaceRoot, SessionId);
        if (!File.Exists(path))
        {
            return [];
        }

        var events = new List<SessionEvent>();
        foreach (var line in File.ReadAllLines(path))
        {
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            var evt = JsonSerializer.Deserialize<SessionEvent>(line);
            if (evt is not null)
            {
                events.Add(evt);
            }
        }

        return events;
    }
}
