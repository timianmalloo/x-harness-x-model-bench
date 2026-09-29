using System.Globalization;
using AiDe.Core.AgentPlane;
using AiDe.Core.Sessions;
using AiDe.Core.Watcher;

namespace AiDe.Core.Presentation.Sessions;

/// <summary>The derived state of one account row (Ruling 105 (2)): the weaker of (launch path observed?, account health).</summary>
public enum AccountRowState
{
    /// <summary>The engine's launch path is unobserved or its adapter is not installed — regardless of health.</summary>
    NotConfigured,

    /// <summary>Launch observed and installed; the account reads <c>needs-login</c>, or the provider has no account yet.</summary>
    NeedsSignIn,

    /// <summary>Launch observed and installed; the account reads <c>ready</c> (or <c>quota-degraded</c>, a pressure signal that still binds).</summary>
    Ready,
}

/// <summary>
/// One account row on the New Session sheet (Ruling 105 (2)): a provider, the catalog engine that
/// authenticates against it (the sub-line), <b>the registry's own account object</b> — or none, for
/// a provider that carries no account yet — and the state derived at open time, never stored
/// (Ruling 97 condition 2).
/// </summary>
/// <remarks>
/// <b>The account is carried, never copied.</b> Health is read through the registry's instance, so a
/// re-probe is visible here without a second health model.
/// </remarks>
/// <param name="ProviderId">The provider key.</param>
/// <param name="EngineId">The catalog engine whose <c>Provider</c> is this row's — derived, never stored.</param>
/// <param name="Account">The registry's account object, by reference; null when the provider carries none.</param>
/// <param name="State">The derived state.</param>
/// <param name="StateReason">Why — the launch refusal's own sentence, or the health as recorded.</param>
public sealed record AccountRow(string ProviderId, string EngineId, ProviderAccount? Account, AccountRowState State, string StateReason)
{
    /// <summary>The account by identity, or null for the "no account" row.</summary>
    public AccountRef? Ref => Account is null ? null : new AccountRef(ProviderId, Account.Label);

    /// <summary>What the row's first line reads: the label, or the zero-account sentence.</summary>
    public string AccountLabel => Account?.Label ?? "no account — Configure…";

    /// <summary>The state as a word the operator reads.</summary>
    public string StateWord => State switch
    {
        AccountRowState.Ready => "ready",
        AccountRowState.NeedsSignIn => "needs sign-in",
        _ => "not configured",
    };

    /// <summary>Whether a turn may bind this row now — <c>needs-login</c> is an absence (§4.3), an unobserved launch is not a backend.</summary>
    public bool RoutableForThisSession => State == AccountRowState.Ready;

    /// <summary>The row as the sheet reads it: <c>label · state (reason)</c>.</summary>
    public string DisplayLabel => $"{AccountLabel} · {StateWord} ({StateReason})";
}

/// <summary>What the sheet produced: the session it created, and the one field a run also needs.</summary>
/// <remarks>
/// <b>It deliberately carries NO lease (Ruling 42).</b> A lease belongs to the goal block
/// (spec §14.3's <c>lease.exclusive</c>), and nothing at sheet time can narrow one — so the only
/// lease this type could hand on is one covering everything, which
/// <c>AiDe.Core.AgentPlane.Lease</c>'s own remarks refuse: it never seams, and therefore "looks like
/// it is working". Absent rather than defaulted, so no downstream node can pick one up: the node
/// that wires the sheet to a run has to get the lease from the block or not build the request.
/// </remarks>
/// <param name="Config">The session container, as written to <c>session.json</c>.</param>
/// <param name="TaskClass">The operator's task class. Required — see the sheet's remarks.</param>
/// <param name="RenamedFrom">
/// The name the operator asked for when Create had to add a counter to it (Ruling 99) — what the
/// announcement names; null when the session got exactly the name that was typed.
/// </param>
public sealed record NewSessionResult(
    SessionConfig Config,
    string TaskClass,
    string? RenamedFrom = null);

/// <summary>
/// The New Session sheet (R13, A4.3), as state and rules with no view attached.
/// </summary>
/// <remarks>
/// <para><b>Bound at construction, or not constructible.</b> A2 is explicit that a session cannot
/// exist unbound, so the workspace is a constructor argument and there is no setter. That makes
/// "a session can exist unbound" unreachable rather than refused — <c>NewSessionFlow</c> is what
/// interposes the chooser when there is no active workspace, and a cancelled chooser never reaches
/// this type at all.</para>
///
/// <para><b><see cref="TaskClass"/> opens as <c>free-form</c> — the operator's declared default,
/// visible as a row and changeable (Ruling 72 (b), superseding Ruling 19's "no default" for the
/// session default; DC-110 was about a <i>guessed</i> class). It stays nullable so a cleared class
/// still blocks <see cref="CanCreate"/>.</para>
///
/// <para><b>The budget is a state, and a cap is optional (Ruling 72 (a)).</b> <see cref="BudgetCap"/>
/// is <c>null</c> — <i>bounded by your subscription</i> — until the operator enforces one with
/// <see cref="EnforceCap"/>; no number is ever required. <see cref="FanOutCeiling"/> is prefilled
/// from the session's ruled default (Ruling 56). <b>No tier is on the sheet</b> (Ruling 63): tier is
/// compiled, never typed.</para>
///
/// <para><b>What the sheet does NOT carry (Ruling 19's cut):</b> routing mode, autonomy, default
/// policy and per-session MCP selection. <c>GovernedRunRequest</c> takes none of them, so a field
/// for any of them would collect a value the run cannot consume. Ruling 26 (iii) additionally cuts
/// the "Start from template" row, which would create a back-edge from the composer to this sheet.</para>
/// </remarks>
public sealed class NewSessionSheetViewModel
{
    /// <summary>The one engine whose native login flow this phase can actually launch (Ruling 20).</summary>
    public const string SignInEngineId = "claude-code";

    private readonly ProviderRegistry _initialRegistry;
    private readonly Func<string, bool>? _launchEngineNativeLogin;
    private readonly Func<ProviderRegistry>? _reprobe;
    private readonly Func<string, AccountRef?>? _fallbackDefault;
    private string? _adapterInstallRoot;
    private readonly HashSet<AccountRef> _selected = [];
    private readonly HashSet<AccountRef> _deselected = [];

    private ProviderRegistry _registry;
    private AccountRef? _defaultAccount;

    /// <param name="workspaceRoot">The bound workspace's root. A session cannot exist unbound (R13).</param>
    /// <param name="workspaceId">The workspace's key, as the session config records it.</param>
    /// <param name="registry">The provider registry, carrying live per-account health.</param>
    /// <param name="now">Stamps the default name and the created session.</param>
    /// <param name="launchEngineNativeLogin">
    /// Launches the engine's own login flow and returns whether it was started. Null in a build with
    /// no way to launch one, which <see cref="SignIn"/> reports rather than pretending.
    /// </param>
    /// <param name="reprobe">Re-reads provider health after a login. Null means health is not re-read.</param>
    /// <param name="adapterInstallRoot">
    /// The directory whose <c>node_modules</c> holds the adapters (<c>ProviderConfiguration.AdapterInstallRoot</c>),
    /// or null when there is no provider file — every adapter engine then reads <i>not configured</i>.
    /// </param>
    /// <param name="fallbackDefault">
    /// The provider file's fallback default account for an engine (<c>engines.&lt;id&gt;.account</c>,
    /// or the provider's sole account; Ruling 105 condition 8) — preferred as the session's initial
    /// default when it is a ready row. Null when there is no file.
    /// </param>
    public NewSessionSheetViewModel(
        string workspaceRoot,
        string workspaceId,
        ProviderRegistry registry,
        DateTimeOffset now,
        Func<string, bool>? launchEngineNativeLogin = null,
        Func<ProviderRegistry>? reprobe = null,
        Func<string, AccountRef?>? fallbackDefault = null,
        string? adapterInstallRoot = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(workspaceRoot);
        ArgumentException.ThrowIfNullOrWhiteSpace(workspaceId);
        ArgumentNullException.ThrowIfNull(registry);

        WorkspaceRoot = workspaceRoot;
        WorkspaceId = workspaceId;
        _registry = registry;
        _initialRegistry = registry;
        _launchEngineNativeLogin = launchEngineNativeLogin;
        _reprobe = reprobe;
        _fallbackDefault = fallbackDefault;
        _adapterInstallRoot = adapterInstallRoot;

        // A4.3: the default name is a date slug, renameable later. Invariant culture so a session
        // directory listing sorts the same on every machine. Ruling 99: unique within the workspace
        // by a counter — the date alone is what put two "2026-09-14 session" tabs (and two
        // "Console — 2026-09-14 session" tabs) on the operator's screen — judged over every session
        // the store holds, so the operator SEES the "(2)" in the name box before Create.
        Name = SessionConfigStore.UniqueName(
            now.UtcDateTime.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture) + " session",
            SessionConfigStore.ExistingNames(workspaceRoot));

        // Every configured account starts selected, and the default is the first READY one. The two
        // answer different questions and must not be conflated: "selected" is what the operator
        // chose for this session, "ready" is what a turn may bind right now — a needs-sign-in account
        // stays selected so that its own Sign in, once it succeeds, makes it bindable without a
        // second choice.
        foreach (var row in AccountRows)
        {
            if (row.Ref is { } account)
            {
                _selected.Add(account);
            }
        }

        // The file's fallback default first (Ruling 105 c8: the operator wrote it), else the first ready.
        var ready = AccountRows.Where(r => r.RoutableForThisSession && r.Ref is not null).ToList();
        _defaultAccount = ready.FirstOrDefault(r => _fallbackDefault?.Invoke(r.EngineId) == r.Ref)?.Ref ?? ready.FirstOrDefault()?.Ref;
    }

    /// <summary>The bound workspace's root.</summary>
    public string WorkspaceRoot { get; }

    /// <summary>The bound workspace's key.</summary>
    public string WorkspaceId { get; }

    /// <summary>The operator-facing session name. Defaults to a date slug (A4.3).</summary>
    public string Name { get; set; }

    /// <summary>
    /// The session's default task class — <c>free-form</c> from open, changeable (Ruling 72 (b));
    /// see the type's remarks.
    /// </summary>
    public string? TaskClass { get; set; } = TaskClasses.FreeForm;

    /// <summary>
    /// The classes the sheet offers, so the operator CHOOSES one rather than spelling it (RQ1):
    /// <c>free-form</c> first — the declared default, a row like any other — then the provisional
    /// vocabulary.
    /// </summary>
    /// <remarks>
    /// Exposed here rather than reached for by the view, so the sheet's vocabulary and the sheet's
    /// rules are read from one object. The list is provisional and says so on
    /// <see cref="TaskClassVocabulary"/>; the first row is preselected by the dialog because it is
    /// what <see cref="TaskClass"/> already holds, never the other way round.
    /// </remarks>
    public IReadOnlyList<TaskClassOption> TaskClassOptions =>
    [
        // simplify: the free-form row is minted here because TaskClassVocabulary.cs is outside the
        // Conversation lane's paths this horizon. Ceiling: this one row. Upgrade trigger: move it
        // into TaskClassVocabulary.Offered (and retire the "no default" copy there) at the join.
        new(TaskClasses.FreeForm, "Conversation and unclassified work; the default for a session opened with no task in mind."),
        .. TaskClassVocabulary.Offered,
    ];

    /// <summary>
    /// The most sub-agents any turn in this session may convene (Ruling 56); prefilled from the
    /// ruled default. <c>null</c> is "not a number was written" — the platform's absent value, so a
    /// blocked reason can say so rather than read an unparseable entry as a negative bound.
    /// </summary>
    public int? FanOutCeiling { get; set; } = SessionConfig.DefaultFanOutCeiling;

    /// <summary>
    /// An enforced request/token cap, or <c>null</c> — bounded by the subscription (Ruling 72 (a)).
    /// Set through <see cref="EnforceCap"/>, cleared through <see cref="ClearCap"/>; never typed
    /// as a required number.
    /// </summary>
    public RunBudget? BudgetCap { get; private set; }

    /// <summary>What the sheet says about the budget: the state (Ruling 72 condition (1)), or the cap the operator enforced.</summary>
    public string BudgetDisplay => BudgetCap is { } cap
        ? string.Create(CultureInfo.InvariantCulture, $"cap: {cap.Requests} requests, {cap.Tokens} tokens")
        : RunBudget.SubscriptionBoundedDisplay;

    /// <summary>Enforces a cap on this session — the operator's deliberate act (Ruling 72 (a)).</summary>
    /// <exception cref="ArgumentOutOfRangeException">
    /// A zero or negative cap: the spawn contract's own rule — a spawn that can do nothing is a typo,
    /// not a budget — applied where the number is typed rather than at the first run.
    /// </exception>
    public void EnforceCap(RunBudget cap)
    {
        ArgumentNullException.ThrowIfNull(cap);
        ArgumentOutOfRangeException.ThrowIfLessThanOrEqual(cap.Requests, 0, nameof(cap));
        ArgumentOutOfRangeException.ThrowIfLessThanOrEqual(cap.Tokens, 0, nameof(cap));
        BudgetCap = cap;
    }

    /// <summary>Removes the cap: the session is bounded by the subscription again.</summary>
    public void ClearCap() => BudgetCap = null;

    /// <summary>
    /// Whether the task class is answered (RQ4) — true from open (Ruling 72), false only for a
    /// class cleared programmatically.
    /// </summary>
    /// <remarks>
    /// A visible STATE rather than an asterisk, and read by the view as a word and a glyph so it is
    /// never carried by colour alone.
    /// </remarks>
    public bool TaskClassAnswered => !string.IsNullOrWhiteSpace(TaskClass);

    /// <summary>
    /// The account rows (Ruling 105 (2)): every catalog engine's provider, grouped by provider, one
    /// row per configured account — or one "no account — Configure…" row for a provider with none
    /// (97's nothing-hidden doctrine) — each with its state derived now from the catalog, the adapter
    /// root and the registry as it reads. Never stored (Ruling 97 condition 2).
    /// </summary>
    public IReadOnlyList<AccountRow> AccountRows => RowsOf(_registry, _adapterInstallRoot);

    /// <summary>The account rows grouped by provider, in catalog order — what the dialog renders.</summary>
    public IReadOnlyList<IGrouping<string, AccountRow>> AccountGroups =>
        [.. AccountRows.GroupBy(r => r.ProviderId, StringComparer.Ordinal)];

    /// <summary>The accounts the operator has selected for this session, in row order.</summary>
    public IReadOnlyList<AccountRef> SelectedAccounts =>
        [.. AccountRows.Select(r => r.Ref).OfType<AccountRef>().Where(_selected.Contains)];

    /// <summary>
    /// The account a turn bills when the composer picks none (Ruling 105): the first ready account
    /// at open, or the operator's choice; null is "no default account — choose one".
    /// </summary>
    public AccountRef? DefaultAccount
    {
        get => _defaultAccount is { } d && _selected.Contains(d) ? d : null;
        set
        {
            if (value is not null && !_selected.Contains(value))
            {
                throw new ArgumentException($"{value} is not selected for this session", nameof(value));
            }

            _defaultAccount = value;
        }
    }

    /// <summary>Selects or deselects an account for this session; deselecting the default clears it.</summary>
    public void SetAccountSelected(AccountRef account, bool selected)
    {
        ArgumentNullException.ThrowIfNull(account);
        if (selected)
        {
            _selected.Add(account);
            _deselected.Remove(account);
            _defaultAccount ??= AccountRows.FirstOrDefault(r => r.Ref == account && r.RoutableForThisSession)?.Ref;
        }
        else
        {
            _selected.Remove(account);
            _deselected.Add(account);
        }
    }

    /// <summary>Whether this account is selected for the session.</summary>
    public bool IsAccountSelected(AccountRef account) => _selected.Contains(account);

    /// <summary>
    /// Re-derives the rows after Configure… wrote or changed the provider file (Ruling 104): the
    /// registry and the adapter root as they read now; an account that appeared is selected, and a
    /// missing default becomes the first ready row. Selections the operator made stand.
    /// </summary>
    public void Reload(ProviderRegistry registry, string? adapterInstallRoot)
    {
        ArgumentNullException.ThrowIfNull(registry);
        _registry = registry;
        _adapterInstallRoot = adapterInstallRoot;

        var known = new HashSet<AccountRef>();
        foreach (var row in AccountRows)
        {
            if (row.Ref is { } account && known.Add(account) && !_deselected.Contains(account))
            {
                _selected.Add(account);
            }
        }

        _selected.RemoveWhere(a => !known.Contains(a));
        _defaultAccount = DefaultAccount ?? AccountRows.FirstOrDefault(r => r.RoutableForThisSession && r.Ref is { } a && _selected.Contains(a))?.Ref;
    }

    /// <summary>
    /// Ruling 104 (3): the footer when zero accounts are ready — the exact ruled sentence — or null.
    /// Create is never disabled by it.
    /// </summary>
    public string? ReadinessFooter =>
        AccountRows.Any(r => r.State == AccountRowState.Ready) ? null : NoBackendReady;

    /// <summary>The ruled footer (Ruling 104 (3)).</summary>
    public const string NoBackendReady =
        "No backend is ready. The session will open; a run will not start until one is configured.";

    /// <summary>
    /// The state rule (Ruling 105 (2)), derived: <i>not configured</i> when the engine's launch is
    /// unobserved — <see cref="EngineCatalog.ResolveLaunch"/>'s own refusal is the input, not a
    /// re-derivation of its rule — or the resolved entry module is not on disk; <i>needs sign-in</i>
    /// when launch observed and health is <c>needs-login</c> or there is no account; <i>ready</i> otherwise.
    /// </summary>
    public static IReadOnlyList<AccountRow> RowsOf(ProviderRegistry registry, string? adapterInstallRoot)
    {
        ArgumentNullException.ThrowIfNull(registry);

        var rows = new List<AccountRow>();
        foreach (var engine in EngineCatalog.Rows)
        {
            var launch = LaunchRefusal(engine.Id, adapterInstallRoot);
            var accounts = registry.Rows
                .Where(r => string.Equals(r.ProviderId, engine.Provider, StringComparison.Ordinal))
                .SelectMany(r => r.Accounts)
                .ToList();

            if (accounts.Count == 0)
            {
                rows.Add(launch is { } refused
                    ? new AccountRow(engine.Provider, engine.Id, null, AccountRowState.NotConfigured, refused)
                    : new AccountRow(engine.Provider, engine.Id, null, AccountRowState.NeedsSignIn, "no account recorded"));
                continue;
            }

            foreach (var account in accounts)
            {
                rows.Add(launch is { } refused
                    ? new AccountRow(engine.Provider, engine.Id, account, AccountRowState.NotConfigured, refused)
                    : account.Health == AccountHealth.NeedsLogin
                        ? new AccountRow(engine.Provider, engine.Id, account, AccountRowState.NeedsSignIn, "needs login, as you recorded it, not probed")
                        : new AccountRow(engine.Provider, engine.Id, account, AccountRowState.Ready,
                            (account.Health == AccountHealth.QuotaDegraded ? "quota degraded" : "ready") + ", as you recorded it, not probed"));
            }
        }

        return rows;
    }

    /// <summary>
    /// Why the engine cannot launch now, or null when it is installed — the catalog's one reading
    /// (<see cref="EngineCatalog.InstallRefusal(string, string)"/>; DC-223: this sheet once read
    /// <c>Arguments[0]</c> as the entry, which for a native row is <c>--acp</c>).
    /// </summary>
    private static string? LaunchRefusal(string engineId, string? adapterInstallRoot)
        => adapterInstallRoot is null
            ? "no adapter root — no provider file"
            : EngineCatalog.InstallRefusal(engineId, adapterInstallRoot);

    /// <summary>
    /// What the sheet says about the lease. <b>A sentence, never a <c>Lease</c></b> (Ruling 42;
    /// Ruling 73).
    /// </summary>
    /// <remarks>
    /// <para>R19 asks the sheet to show the lease, and at sheet time there is nothing to derive one
    /// from: a lease is derived per prompt from the operator's <c>@mentions</c> in a goal block
    /// (Rulings 42, 66), and a prompt that names no write scope — the default conversation — runs
    /// read-only with no lease at all (Ruling 73). The honest display is therefore the rule, not a
    /// value.</para>
    ///
    /// <para><b>Why not derive "the whole workspace" and mark it <c>simplify:</c>.</b> That was this
    /// node's first implementation, and it is worse than a weak display rather than equivalent to
    /// one: the value travelled out of the sheet on <see cref="NewSessionResult"/>, and
    /// <c>GovernedRunRequest</c> <i>requires</i> a <c>Lease</c> — so the first node wiring sheet to
    /// run would have handed the exit run a lease covering everything, which
    /// <c>AiDe.Core.AgentPlane.Lease</c>'s own remarks refuse: it never seams, and therefore "looks
    /// like it is working". A <c>simplify:</c> whose stated ceiling is "the seam control does not
    /// discriminate" is not a bounded shortcut; it is a disabled control wearing one's clothes.</para>
    /// </remarks>
    public const string LeaseDisplay =
        "derived per prompt from the @mentions in a goal block; a prompt that names none runs read-only";

    /// <summary>Whether <see cref="Create"/> would succeed.</summary>
    public bool CanCreate => BlockedReason is null;

    /// <summary>Why <see cref="Create"/> would refuse, or null when it would not.</summary>
    public string? BlockedReason
    {
        get
        {
            if (string.IsNullOrWhiteSpace(Name))
            {
                return "A session needs a name.";
            }

            if (string.IsNullOrWhiteSpace(TaskClass))
            {
                // RQ2/RQ5 — a CONSEQUENCE, beside the control it is about. The previous sentence
                // ("a defaulted class ranks in the wrong cohort") named a mechanism, in the
                // vocabulary of the ranking subsystem, in a footnote 200px below the field. The
                // operator asked why the field was mandatory while the answer was on screen, and
                // asked again in the same session — which is evidence about the affordance, not
                // about the operator. The full explanation sits AT the field; this is the reason the
                // disabled button carries. Reachable only by clearing the class in code: the sheet
                // opens answered (Ruling 72).
                return TaskClassVocabulary.ChooseOneToCreate;
            }

            if (FanOutCeiling is null or < 0)
            {
                return "Write the fan-out ceiling as a whole number, 0 or more.";
            }

            return null;
        }
    }

    /// <summary>Whether the sheet can offer a Sign in action for this engine (Ruling 20).</summary>
    public bool CanSignIn(string engineId) =>
        string.Equals(engineId, SignInEngineId, StringComparison.Ordinal)
        && _launchEngineNativeLogin is not null;

    /// <summary>
    /// Launches the engine's own login flow and re-probes health on return, without leaving the
    /// sheet (R13 b2, Ruling 20).
    /// </summary>
    /// <remarks>
    /// simplify: claude-code only, and the flow is the engine's — this launches it and re-reads
    /// health, it does not implement authentication. Ceiling: no credential of any kind is handled
    /// here or anywhere in AI-DE (§4.3); codex and copilot are refused by name, which is the same
    /// refusal <c>EngineCatalog.ResolveLaunch</c> already makes for their launch paths. Upgrade
    /// trigger: a second engine's native login is observed working on a real install, at which point
    /// the engine list moves onto the catalog row rather than growing a second constant here.
    /// </remarks>
    /// <returns>What to announce. Never silence — a Sign in that did nothing is a dead control.</returns>
    public string SignIn(string engineId)
    {
        if (!string.Equals(engineId, SignInEngineId, StringComparison.Ordinal))
        {
            return $"Signing in from the sheet is proven for {SignInEngineId} only. "
                + $"Run {engineId}'s own login, then reopen this sheet.";
        }

        if (_launchEngineNativeLogin is null)
        {
            return "This build cannot launch an engine login.";
        }

        if (!_launchEngineNativeLogin(engineId))
        {
            return $"{engineId}'s login did not start. Its CLI may not be on PATH.";
        }

        if (_reprobe is null)
        {
            return $"{engineId}'s login was started. Health is not re-read in this build.";
        }

        _registry = _reprobe();
        var row = AccountRows.FirstOrDefault(b => string.Equals(b.EngineId, engineId, StringComparison.Ordinal) && b.Account is not null);
        if (row is { Ref: { } account } && row.RoutableForThisSession && _selected.Contains(account))
        {
            _defaultAccount ??= account;
        }

        return row is null
            ? $"{engineId}'s login was started; its provider is no longer configured."
            : $"{engineId} re-probed: {row.DisplayLabel}.";
    }

    /// <summary>
    /// Creates the session: writes <c>session.json</c>, emits <c>session.open</c>, and hands back
    /// the two fields a run also needs.
    /// </summary>
    /// <remarks>
    /// <b>This is the one site in <c>src/</c> that names <see cref="SessionOrigins.MainMenuNewSession"/></b>
    /// (F5 clause 1). This sheet is constructed at exactly one production site —
    /// <c>NewSessionFlow</c> — which is itself constructed at exactly one — <c>MainWindow.NewSession</c>,
    /// the handler wired to <c>WorkbenchController.NewSessionRequested</c> and reached only through
    /// the <c>session.new</c> command that <c>Ctrl+N</c> and <c>MainMenuBuilder</c>'s File entry both
    /// resolve to. Anything else that creates a session goes through
    /// <see cref="SessionConfigStore.Create"/> directly and its <c>session.open</c> reads
    /// <see cref="SessionOrigins.Direct"/>.
    /// </remarks>
    /// <exception cref="InvalidOperationException">
    /// <see cref="CanCreate"/> is false. The message is <see cref="BlockedReason"/> — a refusal that
    /// does not say why is a dead button.
    /// </exception>
    public NewSessionResult Create(DateTimeOffset now)
    {
        if (BlockedReason is { } reason)
        {
            // The operator's sentence, for the reader this one actually has: whoever wrote a call
            // that skipped CanCreate.
            throw new InvalidOperationException(reason);
        }

        // Ruling 99: a typed duplicate gets the same counter the default does, at the moment of
        // writing — the store is re-read here because a session may have been created since the
        // sheet opened. Never a refusal; the result says what changed so the flow can announce it.
        var requested = Name.Trim();
        var name = SessionConfigStore.UniqueName(requested, SessionConfigStore.ExistingNames(WorkspaceRoot));

        // Ruling 105: the session records ACCOUNTS (provider, label), never engine ids, and the
        // default — a needs-sign-in account may be selected but is never a default the sheet chose.
        var store = new SessionConfigStore(WorkspaceRoot, SessionId.New(now));
        var config = store.Create(
            name, WorkspaceId, SelectedAccounts, DefaultAccount, now,
            fanOutCeiling: FanOutCeiling!.Value,
            budgetCap: BudgetCap,
            defaultTaskClass: TaskClass!.Trim(),
            origin: SessionOrigins.MainMenuNewSession);

        // The result's class IS the config's default (Ruling 72; ADR-0033 §4) — one source, read
        // back from what was written, never a second copy of the sheet's field.
        return new NewSessionResult(
            config, config.DefaultTaskClass,
            RenamedFrom: string.Equals(config.Name, requested, StringComparison.Ordinal) ? null : requested);
    }

    /// <summary>The registry the sheet last read, so a re-probe is observable from outside.</summary>
    /// <remarks>
    /// Exposed because <see cref="SignIn"/>'s whole claim is that health was re-read: an invariant
    /// only the implementation can see is one only the implementation can be wrong about.
    /// </remarks>
    public bool HealthWasReprobed => !ReferenceEquals(_registry, _initialRegistry);

}
