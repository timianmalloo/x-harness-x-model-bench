using System.Text.Json;

namespace AiDe.Core.AgentPlane;

/// <summary>
/// Why a lane could not be bound, as a <b>field</b> plus a sentence.
/// </summary>
/// <remarks>
/// <b>A field, never prose alone.</b> The operator's next action is to edit one line of one file, so
/// the refusal has to say which line. It is deliberately the same shape as
/// <c>AiDe.Core.Presentation.Composer.ComposerFieldError</c> without being that type: this namespace
/// is below Presentation and must not reach up into it.
/// </remarks>
/// <param name="Field">
/// The field to fix, in the wire name <see cref="GovernedRunRequest"/> and the configuration file
/// both use — <c>model</c>, <c>accountLabel</c>, <c>engineId</c>, <c>providers</c>.
/// </param>
/// <param name="Message">What is wrong, naming the file and the values that were found.</param>
public sealed record BindingRefusal(string Field, string Message);

/// <summary>
/// <c>~/.aide/providers.json</c> — the configured providers, accounts, adapter install root and
/// per-engine model, as read from the file the operator hand-edits.
/// </summary>
/// <remarks>
/// <para><b>JSON, and the <c>.yaml</c> in spec §14.2 is an erratum.</b> The spec names
/// <c>~/.aide/providers.yaml</c>; this repository reads <c>~/.aide/providers.json</c>. The reason is
/// the Ruling 36 YAML guard: the only YAML reader in this product is scoped to the template
/// frontmatter loader, and widening it to a file that carries account identity is a larger security
/// decision than a config reader is allowed to make on its own. The transcription is otherwise
/// one-for-one, so a §14.2 file becomes this one by re-punctuating it. Filed as an Addendum erratum
/// per the Ruling 23 precedent; see <c>docs/notes/conductor-spec-errata-policy.md</c>.</para>
///
/// <para><b>Three fields EXTEND §14.2, and each is marked where it is read.</b>
/// <c>adapterInstallRoot</c>, <c>engines.&lt;id&gt;.model</c> and <c>engines.&lt;id&gt;.account</c> are
/// not in the spec's schema. <see cref="GovernedRunRequest"/> requires a root and a model, §14.2
/// supplies neither, and §14.2's own answer for the model — <c>routing.roles</c> / <c>best_fit</c> —
/// is a routing engine this phase does not build. The model is read here rather than defaulted in
/// code. <c>adapterInstallRoot</c> is <b>optional since Ruling 104 (2)</b>: absent reads as the
/// <c>adapters</c> directory beside this file (<c>~/.aide/adapters</c> at <see cref="DefaultPath"/>),
/// present overrides, and the product writes the key only for a non-default root — a default root
/// is a derivation, not a stored value (DM: derive, don't store). <c>engines.&lt;id&gt;.account</c>
/// is the <b>fallback default only</b> (Ruling 105 condition 8): the session's own
/// <c>DefaultAccount</c> is what a turn bills; this key decides an engine's account only when a
/// session says nothing — the migration of a pre-105 session, and <see cref="Bind(string, out BindingRefusal?)"/>.</para>
///
/// <para><b>Refused, never defaulted, and never silently empty.</b> A missing file is an absence:
/// <see cref="ReadIfPresent"/> answers <c>null</c> and the shell renders "no agent backend is
/// configured", which is true. A file that exists and is wrong is a refusal that names the file and
/// the field — because an empty registry read out of a malformed file renders as the absence state,
/// which is a wrong claim about a file the operator wrote.</para>
///
/// <para><b>Health is the operator's record, not a probe.</b> There is no health prober in this
/// phase, so <c>health:</c> is what the operator observed and wrote down — the posture
/// <see cref="ProviderAccount.ObservedAuthLabel"/> already takes. It is required per account rather
/// than defaulted: a defaulted <c>ready</c> is indistinguishable afterwards from an observed one.</para>
/// </remarks>
public sealed class ProviderConfiguration
{
    /// <summary>The file name, and the erratum's subject: <c>.json</c>, not <c>.yaml</c>.</summary>
    public const string FileName = "providers.json";

    // Every member this reader understands. A key outside these sets is REFUSED rather than ignored:
    // `acounts` silently ignored is a provider with no accounts, which renders as the absence state.
    //
    // FOUR OF THEM ARE ACCEPTED AND NOT READ — `routing` here, and `engine`, `acp`, `metered` on a
    // provider row. §14.2 declares all four and this phase reads none: a transcription of the spec's
    // own example file must load without being edited down, and `engine:` in particular MUST NOT be
    // read, because EngineRow.Provider already states that mapping and two definitions of one mapping
    // is a defect signature (DM7).
    private static readonly HashSet<string> TopLevelMembers =
        new(StringComparer.Ordinal) { "adapterInstallRoot", "providers", "engines", "routing" };

    private static readonly HashSet<string> ProviderMembers =
        new(StringComparer.Ordinal) { "auth", "accounts", "engine", "acp", "metered" };

    // `host` EXTENDS §14.2 (Ruling 97 condition 3; Ruling 105 (1)): the enterprise host an account
    // signs in against, on the account and never on a provider or engine row.
    private static readonly HashSet<string> AccountMembers =
        new(StringComparer.Ordinal) { "label", "health", "observedAuthLabel", "host" };

    // BOTH MEMBERS EXTEND §14.2 — see the type's remarks. The spec's schema has no per-engine model.
    private static readonly HashSet<string> EngineMembers =
        new(StringComparer.Ordinal) { "model", "account" };

    private readonly Dictionary<string, EngineChoice> _engines;

    private ProviderConfiguration(
        string path,
        string? adapterInstallRoot,
        ProviderRegistry registry,
        Dictionary<string, EngineChoice> engines)
    {
        Path = path;
        AdapterInstallRoot = adapterInstallRoot ?? DefaultAdapterInstallRoot(path);
        AdapterInstallRootIsDefault = adapterInstallRoot is null;
        Registry = registry;
        _engines = engines;
    }

    /// <summary>
    /// The root an absent <c>adapterInstallRoot</c> means (Ruling 104 (2)): the <c>adapters</c>
    /// directory beside the provider file — <c>~/.aide/adapters</c> for a file at <see cref="DefaultPath"/>.
    /// </summary>
    public static string DefaultAdapterInstallRoot(string providerFilePath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(providerFilePath);
        return System.IO.Path.Combine(
            System.IO.Path.GetDirectoryName(System.IO.Path.GetFullPath(providerFilePath)) ?? string.Empty, "adapters");
    }

    /// <summary>Where the file is, by default: <c>~/.aide/providers.json</c> (§4.3).</summary>
    public static string DefaultPath => System.IO.Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".aide", FileName);

    /// <summary>The file this configuration was read from. Every refusal names it.</summary>
    public string Path { get; }

    /// <summary>
    /// The directory whose <c>node_modules</c> holds the ACP adapter. <b>Extends §14.2.</b> The file's
    /// value, or <see cref="DefaultAdapterInstallRoot"/> when the file carries none (Ruling 104 (2)).
    /// </summary>
    public string AdapterInstallRoot { get; }

    /// <summary>Whether <see cref="AdapterInstallRoot"/> is the derived default (the file carries no key).</summary>
    public bool AdapterInstallRootIsDefault { get; }

    /// <summary>The providers and accounts, as the registry §4.3 describes.</summary>
    public ProviderRegistry Registry { get; }

    /// <summary>
    /// Reads the file, or answers <c>null</c> when there is none.
    /// </summary>
    /// <param name="path">The file to read. <see cref="DefaultPath"/> when the caller has no reason to differ.</param>
    /// <exception cref="AgentPlaneException">
    /// <see cref="AgentPlaneErrorCodes.ProviderConfigurationMalformed"/> — the file exists and is
    /// wrong. <b>Never collapsed into <c>null</c>:</b> a caller that could not tell "no file" from
    /// "bad file" would render the second as the first.
    /// </exception>
    public static ProviderConfiguration? ReadIfPresent(string path)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        return File.Exists(path) ? Read(path) : null;
    }

    /// <summary>Reads the file. The file must exist.</summary>
    /// <exception cref="AgentPlaneException">
    /// <see cref="AgentPlaneErrorCodes.ProviderConfigurationMalformed"/>, naming the file and the field.
    /// </exception>
    public static ProviderConfiguration Read(string path)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);

        string text;
        try
        {
            text = File.ReadAllText(path);
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        {
            throw Malformed(path, "the file could not be read: " + error.Message);
        }

        using var document = Parse(path, text);
        var root = document.RootElement;

        if (root.ValueKind != JsonValueKind.Object)
        {
            throw Malformed(path, $"the top level is {Describe(root.ValueKind)}, and it must be an object");
        }

        RefuseUnknownMembers(path, root, TopLevelMembers, "the top level");

        // OPTIONAL since Ruling 104 (2): absent ⇒ the adapters directory beside this file.
        var adapterInstallRoot = OptionalString(path, root, "adapterInstallRoot", "the top level");
        if (adapterInstallRoot is not null && string.IsNullOrWhiteSpace(adapterInstallRoot))
        {
            throw Malformed(path, "the top level has \"adapterInstallRoot\", and it is blank; omit the key for the default root");
        }

        if (!root.TryGetProperty("providers", out var providers) || providers.ValueKind != JsonValueKind.Object)
        {
            throw Malformed(path, "the top level carries no \"providers\" object");
        }

        var rows = new List<ProviderRow>();
        foreach (var provider in providers.EnumerateObject())
        {
            rows.Add(ReadProvider(path, provider.Name, provider.Value));
        }

        return new ProviderConfiguration(
            path, adapterInstallRoot, new ProviderRegistry(rows), ReadEngines(path, root));
    }

    /// <summary>
    /// Binds one engine to the <c>(engine, model, account)</c> triple a run needs, or says which
    /// field is missing.
    /// </summary>
    /// <remarks>
    /// <para><b>Nothing here decides anything the file did not say.</b> The model comes from
    /// <c>engines.&lt;id&gt;.model</c>. The account comes from <c>engines.&lt;id&gt;.account</c>, or
    /// from the provider carrying exactly one — which is the file choosing, not this method. Two
    /// accounts and no selection is a refusal, because picking one would be right in every case
    /// anyone checks by hand and wrong in the case that bills the wrong account (DC-110).</para>
    ///
    /// <para><b>The registry's rules are called, not restated.</b> Unknown engine, unconfigured
    /// provider, unknown account and <c>needs-login</c> are all <see cref="ProviderRegistry"/>'s
    /// refusals; this maps each to the field the operator must edit. A second opinion about what
    /// binds would be a second place for the rule to change.</para>
    /// </remarks>
    /// <param name="engineId">A catalog engine id — normally the session's one enabled backend.</param>
    /// <param name="refusal">Why not, when the result is null.</param>
    public LaneBinding? Bind(string engineId, out BindingRefusal? refusal)
    {
        EngineRow engine;
        try
        {
            engine = EngineCatalog.Find(engineId);
        }
        catch (AgentPlaneException error)
        {
            refusal = new BindingRefusal("engineId", error.Message);
            return null;
        }

        if (!_engines.TryGetValue(engine.Id, out var choice))
        {
            refusal = new BindingRefusal(
                "model",
                $"no model is configured for engine '{engine.Id}'. Add "
                + $"\"engines\": {{ \"{engine.Id}\": {{ \"model\": \"…\" }} }} to {Path} — there is no "
                + "default, because a defaulted model ranks the run in the wrong standings cohort");
            return null;
        }

        ProviderRow provider;
        try
        {
            provider = Registry.Find(engine.Provider);
        }
        catch (AgentPlaneException error)
        {
            refusal = new BindingRefusal("providers", error.Message);
            return null;
        }

        if (!Account(provider, choice, out var accountLabel, out refusal))
        {
            return null;
        }

        try
        {
            var binding = Registry.Bind(engine.Id, choice.Model, accountLabel);
            refusal = null;
            return binding;
        }
        catch (AgentPlaneException error)
        {
            refusal = new BindingRefusal(FieldFor(error.Code), error.Message);
            return null;
        }
    }

    /// <summary>
    /// Binds a session's chosen account to the <c>(engine, model, account)</c> triple a turn needs
    /// (Ruling 105 (1)): the engine is the one catalog row whose provider is the account's — derived,
    /// never stored on the session — the model is <c>engines.&lt;id&gt;.model</c>, and the registry's
    /// rules decide the rest.
    /// </summary>
    /// <param name="provider">The account's provider id.</param>
    /// <param name="accountLabel">The account label — the session's default, or the operator's per-turn override.</param>
    /// <param name="refusal">Why not, when the result is null.</param>
    public LaneBinding? Bind(string provider, string accountLabel, out BindingRefusal? refusal)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(provider);
        ArgumentException.ThrowIfNullOrWhiteSpace(accountLabel);

        var engines = EngineCatalog.Rows.Where(r => string.Equals(r.Provider, provider, StringComparison.Ordinal)).ToList();
        if (engines.Count != 1)
        {
            // Two engines on one provider is a ruling, not a config knob (Ruling 105 (1)).
            refusal = new BindingRefusal(
                "engineId",
                engines.Count == 0
                    ? $"no catalog engine authenticates against provider '{provider}'; the catalog carries: "
                      + string.Join(", ", EngineCatalog.Rows.Select(r => $"{r.Id} ({r.Provider})"))
                    : $"provider '{provider}' carries {engines.Count} catalog engines ("
                      + string.Join(", ", engines.Select(e => e.Id)) + "); which one is a ruling, not a guess");
            return null;
        }

        var engine = engines[0];
        if (!_engines.TryGetValue(engine.Id, out var choice))
        {
            refusal = new BindingRefusal(
                "model",
                $"no model is configured for engine '{engine.Id}'. Add "
                + $"\"engines\": {{ \"{engine.Id}\": {{ \"model\": \"…\" }} }} to {Path} — there is no "
                + "default, because a defaulted model ranks the run in the wrong standings cohort");
            return null;
        }

        try
        {
            var binding = Registry.Bind(engine.Id, choice.Model, accountLabel);
            refusal = null;
            return binding;
        }
        catch (AgentPlaneException error)
        {
            refusal = new BindingRefusal(FieldFor(error.Code), error.Message);
            return null;
        }
    }

    /// <summary>The model the file names for an engine, or null when it names none.</summary>
    public string? ModelFor(string engineId) =>
        _engines.TryGetValue(engineId ?? string.Empty, out var choice) ? choice.Model : null;

    /// <summary>
    /// The account the file makes an engine's <b>fallback default</b> (Ruling 105 condition 8): the
    /// <c>engines.&lt;id&gt;.account</c> key when the operator wrote one, else the provider's sole
    /// account; <c>null</c> for anything else — never one of several by reading order.
    /// </summary>
    /// <returns>The provider id and label, or null.</returns>
    public (string Provider, string Label)? FallbackDefaultAccount(string engineId)
    {
        EngineRow engine;
        ProviderRow provider;
        try
        {
            engine = EngineCatalog.Find(engineId);
            provider = Registry.Find(engine.Provider);
        }
        catch (AgentPlaneException)
        {
            return null;
        }

        if (_engines.TryGetValue(engine.Id, out var choice) && choice.Account is { } named
            && provider.Accounts.Any(a => string.Equals(a.Label, named, StringComparison.Ordinal)))
        {
            return (provider.ProviderId, named);
        }

        // The sole account is the file choosing, not this method (the same rule as Account below).
        return provider.Accounts.Count == 1 ? (provider.ProviderId, provider.Accounts.Single().Label) : null;
    }

    /// <summary>Which field an agent-plane refusal points the operator at.</summary>
    private static string FieldFor(string code) => code switch
    {
        AgentPlaneErrorCodes.UnknownEngine => "engineId",
        AgentPlaneErrorCodes.UnknownProvider => "providers",
        _ => "accountLabel",
    };

    /// <summary>
    /// Resolves the engine's <b>fallback default</b> account, or refuses. Never picks one from more
    /// than one. Since Ruling 105 the session's own <c>DefaultAccount</c> is what a turn bills; this is
    /// consulted only when a session says nothing (the migration; the headless entry).
    /// </summary>
    private bool Account(
        ProviderRow provider, EngineChoice choice, out string accountLabel, out BindingRefusal? refusal)
    {
        if (choice.Account is { } selected)
        {
            accountLabel = selected;
            refusal = null;
            return true;
        }

        if (provider.Accounts.Count == 1)
        {
            accountLabel = provider.Accounts.Single().Label;
            refusal = null;
            return true;
        }

        accountLabel = string.Empty;

        refusal = provider.Accounts.Count == 0
            ? new BindingRefusal(
                "accountLabel",
                $"provider '{provider.ProviderId}' is configured in {Path} with no accounts, so there "
                + "is nothing for a lane to bill against")
            : new BindingRefusal(
                "accountLabel",
                $"provider '{provider.ProviderId}' carries {provider.Accounts.Count} accounts and "
                + $"engine '{choice.EngineId}' names none: "
                + string.Join(", ", provider.Accounts.Select(a => a.Label))
                + $". Add \"account\" to the engine's entry in {Path} — an ambiguous binding is "
                + "refused rather than resolved by reading order");

        return false;
    }

    private static Dictionary<string, EngineChoice> ReadEngines(string path, JsonElement root)
    {
        var engines = new Dictionary<string, EngineChoice>(StringComparer.Ordinal);

        if (!root.TryGetProperty("engines", out var element))
        {
            return engines;
        }

        if (element.ValueKind != JsonValueKind.Object)
        {
            throw Malformed(path, $"\"engines\" is {Describe(element.ValueKind)}, and it must be an object");
        }

        foreach (var entry in element.EnumerateObject())
        {
            // A typo'd engine id would otherwise sit in the file looking configured while the engine
            // it was meant for refuses for "no model". The catalog is the closed set, so say so here.
            try
            {
                EngineCatalog.Find(entry.Name);
            }
            catch (AgentPlaneException error)
            {
                throw Malformed(path, $"\"engines\" carries '{entry.Name}': {error.Message}");
            }

            var where = $"\"engines.{entry.Name}\"";
            RequireObject(path, entry.Value, where);
            RefuseUnknownMembers(path, entry.Value, EngineMembers, where);

            engines[entry.Name] = new EngineChoice(
                entry.Name,
                RequiredString(path, entry.Value, "model", where),
                OptionalString(path, entry.Value, "account", where));
        }

        return engines;
    }

    private static ProviderRow ReadProvider(string path, string providerId, JsonElement element)
    {
        var where = $"\"providers.{providerId}\"";

        RequireObject(path, element, where);
        RefuseUnknownMembers(path, element, ProviderMembers, where);

        var auth = RequiredString(path, element, "auth", where) switch
        {
            "subscription" => ProviderAuth.Subscription,
            "api-key" => ProviderAuth.ApiKey,
            var other => throw Malformed(
                path, $"{where} has \"auth\": \"{other}\"; §14.2 declares subscription and api-key"),
        };

        if (!element.TryGetProperty("accounts", out var accounts) || accounts.ValueKind != JsonValueKind.Array)
        {
            throw Malformed(path, $"{where} carries no \"accounts\" array");
        }

        var read = new List<ProviderAccount>();
        foreach (var account in accounts.EnumerateArray())
        {
            read.Add(ReadAccount(path, providerId, account));
        }

        return new ProviderRow(providerId, auth, read);
    }

    private static ProviderAccount ReadAccount(string path, string providerId, JsonElement element)
    {
        var where = $"\"providers.{providerId}.accounts\"";

        RequireObject(path, element, where);
        RefuseUnknownMembers(path, element, AccountMembers, where);

        var label = RequiredString(path, element, "label", where);

        // REQUIRED, and this is condition (c)'s whole mechanism. Nothing probes health in this phase,
        // so the value is what the operator observed and recorded. Defaulting it to `ready` would
        // manufacture an observation, and "ready" is exactly the value nobody would question.
        var health = RequiredString(path, element, "health", where) switch
        {
            "ready" => AccountHealth.Ready,
            "needs-login" => AccountHealth.NeedsLogin,
            "quota-degraded" => AccountHealth.QuotaDegraded,
            var other => throw Malformed(
                path,
                $"{where} account '{label}' has \"health\": \"{other}\"; §4.3 declares exactly "
                + "ready, needs-login and quota-degraded"),
        };

        // A blank host looks configured and configures nothing; refused like a blank required string.
        var host = OptionalString(path, element, "host", where);
        if (host is not null && string.IsNullOrWhiteSpace(host))
        {
            throw Malformed(path, $"{where} account '{label}' has a blank \"host\"; omit the key for the provider's default host");
        }

        return new ProviderAccount(label, health, OptionalString(path, element, "observedAuthLabel", where), host);
    }

    private static JsonDocument Parse(string path, string text)
    {
        try
        {
            return JsonDocument.Parse(text);
        }
        catch (JsonException error)
        {
            throw Malformed(path, "the file is not valid JSON: " + error.Message);
        }
    }

    private static void RequireObject(string path, JsonElement element, string where)
    {
        if (element.ValueKind != JsonValueKind.Object)
        {
            throw Malformed(path, $"{where} is {Describe(element.ValueKind)}, and it must be an object");
        }
    }

    private static void RefuseUnknownMembers(
        string path, JsonElement element, HashSet<string> known, string where)
    {
        foreach (var member in element.EnumerateObject())
        {
            if (!known.Contains(member.Name))
            {
                throw Malformed(
                    path,
                    $"{where} carries \"{member.Name}\", which this reader does not know. Known here: "
                    + string.Join(", ", known.OrderBy(k => k, StringComparer.Ordinal)));
            }
        }
    }

    private static string RequiredString(string path, JsonElement element, string name, string where)
    {
        if (!element.TryGetProperty(name, out var value)
            || value.ValueKind != JsonValueKind.String
            || value.GetString() is not { } text
            || string.IsNullOrWhiteSpace(text))
        {
            throw Malformed(path, $"{where} carries no \"{name}\" string");
        }

        return text;
    }

    private static string? OptionalString(string path, JsonElement element, string name, string where)
    {
        if (!element.TryGetProperty(name, out var value))
        {
            return null;
        }

        if (value.ValueKind != JsonValueKind.String || value.GetString() is not { } text)
        {
            throw Malformed(path, $"{where} has \"{name}\", and it is not a string");
        }

        return text;
    }

    private static string Describe(JsonValueKind kind) => kind switch
    {
        JsonValueKind.Array => "an array",
        JsonValueKind.String => "a string",
        JsonValueKind.Number => "a number",
        JsonValueKind.Null => "null",
        _ => "not an object",
    };

    private static AgentPlaneException Malformed(string path, string what) =>
        new(AgentPlaneErrorCodes.ProviderConfigurationMalformed, $"{path}: {what}");

    /// <summary>
    /// What the file says about one engine. <b>Both members extend §14.2</b> — see the type's remarks.
    /// </summary>
    private sealed record EngineChoice(string EngineId, string Model, string? Account);
}
