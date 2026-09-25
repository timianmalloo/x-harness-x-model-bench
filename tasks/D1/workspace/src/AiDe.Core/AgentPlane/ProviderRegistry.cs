namespace AiDe.Core.AgentPlane;

/// <summary>
/// What a per-account health probe observed — spec §4.3's three states, and only those three.
/// </summary>
/// <remarks>
/// A closed set, unlike a run-event <c>kind</c>: the spec names exactly these, and each has a
/// different consequence for routing. There is deliberately no <c>Unknown</c> member — an account
/// whose probe has not run yet is not in the registry, which is a different fact from an account
/// that answered.
/// </remarks>
public enum AccountHealth
{
    /// <summary>The probe answered and the account can take a lane.</summary>
    Ready,

    /// <summary>The engine's login has not been run, or has expired. The router treats this as absent (§4.3).</summary>
    NeedsLogin,

    /// <summary>Under quota pressure — a signal, not an absence. A lane still binds, and carries the pressure.</summary>
    QuotaDegraded,
}

/// <summary>How a provider authenticates. §14.2's <c>auth:</c> field.</summary>
public enum ProviderAuth
{
    /// <summary>A subscription the engine owns the credentials for. AI-DE never handles them (§4.3).</summary>
    Subscription,

    /// <summary>An API key, held in Windows Credential Manager / DPAPI. Opt-in, disabled by default.</summary>
    ApiKey,
}

/// <summary>
/// One account under a provider. <b>Accounts are first-class</b> (§4.3): quota pressure, standings
/// cohorts and the profiler all key on the account, not on the provider.
/// </summary>
/// <param name="Label">The label the operator configured. AI-DE stores labels, never credentials.</param>
/// <param name="Health">What the last health probe observed.</param>
/// <param name="ObservedAuthLabel">
/// What the engine's own adapter calls this account, <b>as the operator recorded it after seeing
/// it</b> — e.g. <c>"Claude Max"</c>. <c>null</c> means not recorded, and the spawn gate then checks
/// the auth <i>kind</i> alone. It is deliberately not derived: <see cref="Label"/> is an operator's
/// name for a login and this is the adapter's name for a plan tier, so nothing in either determines
/// the other, and a mapping invented inside a control that exists because guessing is expensive is
/// how the control starts lying.
/// </param>
/// <param name="Host">
/// The enterprise host this account signs in against — <c>mycompany.ghe.com</c> — or <c>null</c>
/// for the provider's default. <b>On the account, never the engine row</b> (Ruling 97 condition 3;
/// Ruling 105 (1)): it is a fact about a login, and <see cref="EngineCatalog.LaunchEnvironment"/>
/// turns it into the CLI's own variable at launch. Extends §14.2.
/// </param>
public sealed record ProviderAccount(string Label, AccountHealth Health, string? ObservedAuthLabel = null, string? Host = null);

/// <summary>
/// One <c>providers.json</c> row (§14.2) — a provider, how it authenticates, and its accounts.
/// </summary>
/// <remarks>
/// <b>It deliberately carries no engine id.</b> <see cref="EngineRow.Provider"/> already states the
/// engine → provider mapping, and two definitions of one mapping is a defect signature (DM7): the
/// day they disagree, a lane binds to one provider's catalog row and another provider's account.
/// </remarks>
/// <param name="ProviderId">The provider key — <c>anthropic</c>, <c>openai</c>, <c>github</c>, <c>google</c>, <c>xai</c>: whatever <see cref="EngineRow.Provider"/> names.</param>
/// <param name="Auth">Subscription or API key.</param>
/// <param name="Accounts">The configured accounts, as labels plus probe state.</param>
public sealed record ProviderRow(
    string ProviderId,
    ProviderAuth Auth,
    IReadOnlyList<ProviderAccount> Accounts);

/// <summary>
/// What a lane is actually bound to: <c>(engine, model, account)</c> — never just a provider (§4.3).
/// </summary>
/// <param name="EngineId">The catalog engine.</param>
/// <param name="Model">The model the lane runs on. A cohort axis in the standings.</param>
/// <param name="Account">The account the work bills against and the quota drains from.</param>
/// <param name="Provider">The provider row the account came from.</param>
public sealed record LaneBinding(string EngineId, string Model, ProviderAccount Account, ProviderRow Provider);

/// <summary>
/// The provider registry — spec §4.3. Resolves a lane's <c>(engine, model, account)</c> triple, and
/// refuses everything it cannot resolve.
/// </summary>
/// <remarks>
/// <para><b>Refused, never defaulted.</b> A registry that answered a typo with its only configured
/// provider would bind a lane to somebody else's account, and the first thing to notice would be the
/// bill. Every lookup here fails loudly, and the message names the value that was not found.</para>
///
/// <para><b>Constructed from configuration, with no built-in default.</b> §14.2's example rows carry
/// account labels like <c>max-personal</c>, which are one operator's names for one operator's
/// logins. A registry that shipped them would assert an account nobody had signed into. The rows
/// come from <c>~/.aide/providers.json</c> — §14.2's <c>providers.yaml</c>, with the <c>.yaml</c>
/// filed as an erratum (<c>docs/notes/conductor-spec-errata-providers-json.md</c>) — and
/// <see cref="ProviderConfiguration"/> is the reader. Per-workspace overrides are not built.</para>
/// </remarks>
public sealed class ProviderRegistry
{
    /// <summary>
    /// The engine id §14.2 gives the direct-API path — the one spec §4.2 forbids for Anthropic while
    /// a subscription is configured. It is deliberately <b>not</b> an <see cref="EngineCatalog"/>
    /// row: Phase 1 implements no direct-API launch path at all.
    /// </summary>
    public const string DirectApiEngineId = "direct-api";

    /// <summary>The provider whose terms of service §4.2 quotes.</summary>
    public const string AnthropicProviderId = "anthropic";

    private readonly Dictionary<string, ProviderRow> _byId;

    /// <param name="rows">The configured provider rows.</param>
    /// <exception cref="AgentPlaneException">
    /// <see cref="AgentPlaneErrorCodes.UnknownProvider"/> when two rows claim one provider id — a
    /// configuration whose meaning depends on read order, refused rather than resolved by "last wins".
    /// </exception>
    public ProviderRegistry(IReadOnlyList<ProviderRow> rows)
    {
        ArgumentNullException.ThrowIfNull(rows);

        _byId = new Dictionary<string, ProviderRow>(StringComparer.Ordinal);
        foreach (var row in rows)
        {
            if (!_byId.TryAdd(row.ProviderId, row))
            {
                throw new AgentPlaneException(
                    AgentPlaneErrorCodes.UnknownProvider,
                    $"provider '{row.ProviderId}' is configured twice; one provider is one row, "
                    + "because two rows would make a binding depend on which was read last");
            }
        }

        Rows = rows;
    }

    /// <summary>The configured rows, in configuration order.</summary>
    public IReadOnlyList<ProviderRow> Rows { get; }

    /// <summary>Finds a provider row by id.</summary>
    /// <exception cref="AgentPlaneException">
    /// <see cref="AgentPlaneErrorCodes.UnknownProvider"/> — refused, never defaulted, and least of
    /// all when exactly one provider is configured and "they must have meant that one" is tempting.
    /// </exception>
    public ProviderRow Find(string providerId)
        => _byId.TryGetValue(providerId ?? string.Empty, out var row)
            ? row
            : throw new AgentPlaneException(
                AgentPlaneErrorCodes.UnknownProvider,
                $"unknown provider id '{providerId}'; the registry carries: "
                + (_byId.Count == 0 ? "(none configured)" : string.Join(", ", _byId.Keys)));

    /// <summary>
    /// Binds a lane to <c>(engine, model, account)</c>.
    /// </summary>
    /// <param name="engineId">A catalog engine id. The engine → provider mapping is the catalog's.</param>
    /// <param name="model">The model this lane runs on.</param>
    /// <param name="accountLabel">The configured account label.</param>
    /// <exception cref="AgentPlaneException">
    /// <see cref="AgentPlaneErrorCodes.UnknownEngine"/> for an engine the catalog does not carry;
    /// <see cref="AgentPlaneErrorCodes.UnknownProvider"/> for a catalogued engine whose provider is
    /// not configured; <see cref="AgentPlaneErrorCodes.UnknownAccount"/> for a label the provider
    /// does not carry; <see cref="AgentPlaneErrorCodes.AccountNotReady"/> for an account whose probe
    /// says <c>needs-login</c>.
    /// </exception>
    public LaneBinding Bind(string engineId, string model, string accountLabel)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(model);
        ArgumentException.ThrowIfNullOrWhiteSpace(accountLabel);

        var engine = EngineCatalog.Find(engineId);
        var provider = Find(engine.Provider);

        var account = provider.Accounts.FirstOrDefault(
            a => string.Equals(a.Label, accountLabel, StringComparison.Ordinal))
            ?? throw new AgentPlaneException(
                AgentPlaneErrorCodes.UnknownAccount,
                $"provider '{provider.ProviderId}' carries no account '{accountLabel}'; configured: "
                + (provider.Accounts.Count == 0
                    ? "(none)"
                    : string.Join(", ", provider.Accounts.Select(a => a.Label))));

        // needs-login is an ABSENCE, per §4.3. quota-degraded is a pressure signal and still binds:
        // refusing it would turn a soft signal into an outage, and the health travels on the binding
        // so a caller sees the degradation instead of inferring it.
        if (account.Health == AccountHealth.NeedsLogin)
        {
            throw new AgentPlaneException(
                AgentPlaneErrorCodes.AccountNotReady,
                $"account '{account.Label}' on provider '{provider.ProviderId}' reads needs-login, "
                + "which the router treats as absent; run the engine's own login and re-probe");
        }

        return new LaneBinding(engine.Id, model, account, provider);
    }

    /// <summary>
    /// Whether the provider has a configured subscription account — the condition spec §4.2 attaches
    /// its direct-API prohibition to.
    /// </summary>
    /// <remarks>
    /// Health is deliberately not consulted. A subscription that needs a login is still a configured
    /// subscription, and the prohibition is about what the operator has, not about what is reachable
    /// this minute. Reading health here would lift the ban exactly when a login expired.
    /// </remarks>
    public bool HasSubscriptionAccount(string providerId)
        => _byId.TryGetValue(providerId ?? string.Empty, out var row)
            && row.Auth == ProviderAuth.Subscription
            && row.Accounts.Count > 0;
}
