using AiDe.Core.AgentPlane;
using AiDe.Core.Tests.Sessions;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// <c>~/.aide/providers.json</c> — the reader spec §14.2's <c>providers.yaml</c> never had, and the
/// binding that turns it into the <c>(engine, model, account)</c> triple a run needs.
/// </summary>
/// <remarks>
/// <para><b>The clause these tests exist to falsify:</b> "no run-side value reaches
/// <c>GovernedRunRequest</c> from a code default". The dangerous shape is not a crash — it is a
/// reader that answers a file with no <c>model</c> by picking one, or a provider row carrying two
/// accounts by taking the first. Both produce a run that works, bills the wrong account, and ranks
/// in the wrong standings cohort, which is DC-110: a defaulted value is indistinguishable from a
/// chosen one afterwards.</para>
///
/// <para><b>Missing and malformed are different facts and must stay different.</b> A missing file is
/// an operator who has not configured a backend yet; a malformed one is an operator who tried and
/// got it wrong. Collapsing the second into the first — an empty registry — is the silently-empty
/// state Ruling 47 (b) refuses, because it renders as "no agent backend is configured", which is a
/// wrong claim about a file that exists.</para>
/// </remarks>
public sealed class ProviderConfigurationTests
{
    /// <summary>§14.2's example rows, transcribed to JSON, with the two extensions this node adds.</summary>
    private const string Section142AsJson = """
        {
          "adapterInstallRoot": "C:/adapters",
          "providers": {
            "anthropic": { "auth": "subscription", "engine": "claude-code", "acp": "adapter",
              "accounts": [ { "label": "max-personal", "health": "ready", "observedAuthLabel": "Claude Max" } ] },
            "openai": { "auth": "subscription", "engine": "codex", "acp": "adapter",
              "accounts": [ { "label": "chatgpt-personal", "health": "needs-login" } ] }
          },
          "engines": {
            "claude-code": { "model": "claude-sonnet-4-6" }
          }
        }
        """;

    private static string Write(string json)
    {
        var path = Path.Combine(
            Path.GetTempPath(), "aide-providers", Guid.NewGuid().ToString("N"), "providers.json");

        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, json);
        return path;
    }

    private static AgentPlaneException Malformed(string json)
        => Assert.Throws<AgentPlaneException>(() => ProviderConfiguration.Read(Write(json)));

    // ---------------------------------------------------------------------------------------
    // (b) — missing is an absence; malformed is an error naming file and field.
    // ---------------------------------------------------------------------------------------

    /// <summary>A file that is not there is an absence, and absence is not an error.</summary>
    /// <remarks>
    /// This is the state <c>MainWindow</c> renders as "no agent backend is configured". It has to be
    /// distinguishable from every refusal below by TYPE rather than by reading a message, because a
    /// caller that told them apart by string would stop doing so the first time a message changed.
    /// </remarks>
    [Fact]
    public void AMissingFileIsAnAbsenceRatherThanARefusal()
    {
        var path = Path.Combine(Path.GetTempPath(), "aide-providers", Guid.NewGuid().ToString("N"), "providers.json");

        Assert.Null(ProviderConfiguration.ReadIfPresent(path));
    }

    /// <summary>Every malformed shape names the file and the field, and none of them yields a registry.</summary>
    [Theory]
    // A top-level field the schema requires.
    // Ruling 104 (2): an ABSENT adapterInstallRoot is the default root, not a refusal — see
    // SessionAccountsTests.AdapterInstallRoot_AbsentIsTheAdaptersDirectoryBesideTheFile_PresentOverrides;
    // a blank one is still refused by name, because "" is not a directory and not an absence.
    [InlineData("""{ "adapterInstallRoot": "", "providers": {} }""", "adapterInstallRoot")]
    [InlineData("""{ "adapterInstallRoot": "C:/a" }""", "providers")]
    // A key nobody declared — a typo, refused rather than ignored into an empty provider.
    [InlineData("""{ "adapterInstallRoot": "C:/a", "providers": {}, "provders": {} }""", "provders")]
    [InlineData("""{ "adapterInstallRoot": "C:/a", "providers": { "anthropic": { "auth": "subscription", "acounts": [] } } }""", "acounts")]
    // A value outside the closed set §4.3 declares.
    [InlineData("""{ "adapterInstallRoot": "C:/a", "providers": { "anthropic": { "auth": "oauth", "accounts": [] } } }""", "auth")]
    [InlineData("""{ "adapterInstallRoot": "C:/a", "providers": { "anthropic": { "auth": "subscription", "accounts": [ { "label": "x", "health": "fine" } ] } } }""", "health")]
    // Health is RECORDED, never defaulted: an account without one is not an account that is ready.
    [InlineData("""{ "adapterInstallRoot": "C:/a", "providers": { "anthropic": { "auth": "subscription", "accounts": [ { "label": "x" } ] } } }""", "health")]
    [InlineData("""{ "adapterInstallRoot": "C:/a", "providers": { "anthropic": { "auth": "subscription", "accounts": [ { "health": "ready" } ] } } }""", "label")]
    // An engines entry for an engine the catalog does not carry.
    [InlineData("""{ "adapterInstallRoot": "C:/a", "providers": {}, "engines": { "clawed-code": { "model": "m" } } }""", "clawed-code")]
    // Not JSON at all, and not an object.
    [InlineData("""[ "not an object" ]""", "providers.json")]
    [InlineData("""{ "adapterInstallRoot": """, "providers.json")]
    public void AMalformedFileIsRefusedByNameRatherThanReadAsEmpty(string json, string named)
    {
        var error = Malformed(json);

        Assert.Equal(AgentPlaneErrorCodes.ProviderConfigurationMalformed, error.Code);
        Assert.Contains(named, error.Message, StringComparison.Ordinal);
        Assert.Contains("providers.json", error.Message, StringComparison.Ordinal);
    }

    // ---------------------------------------------------------------------------------------
    // The transcription, and the facets that are NOT read.
    // ---------------------------------------------------------------------------------------

    /// <summary>§14.2's map becomes the registry's rows, with the accounts §4.3 makes first-class.</summary>
    [Fact]
    public void Section142TranscribedToJsonBecomesTheRegistry()
    {
        var config = ProviderConfiguration.Read(Write(Section142AsJson));

        Assert.Equal("C:/adapters", config.AdapterInstallRoot);
        Assert.Equal(["anthropic", "openai"], config.Registry.Rows.Select(r => r.ProviderId));

        var anthropic = config.Registry.Find("anthropic");
        Assert.Equal(ProviderAuth.Subscription, anthropic.Auth);

        var account = Assert.Single(anthropic.Accounts);
        Assert.Equal("max-personal", account.Label);
        Assert.Equal(AccountHealth.Ready, account.Health);
        Assert.Equal("Claude Max", account.ObservedAuthLabel);

        // needs-login survives as itself. The registry is what treats it as absent (§4.3); a reader
        // that dropped the account would make "configured but not logged in" unreportable.
        Assert.Equal(AccountHealth.NeedsLogin, Assert.Single(config.Registry.Find("openai").Accounts).Health);
    }

    /// <summary>
    /// The §14.2 facets this node cuts are accepted and not read — never refused, and never acted on.
    /// </summary>
    /// <remarks>
    /// <c>engine:</c> is the one that matters. <see cref="ProviderRow"/> deliberately carries no
    /// engine id because <see cref="EngineRow.Provider"/> already states that mapping, and two
    /// definitions of one mapping is a defect signature (DM7). So a file may carry §14.2's
    /// <c>engine:</c> — a transcription should not have to delete it — and nothing here reads it.
    /// </remarks>
    [Fact]
    public void TheCutFacetsOfSection142AreAcceptedAndNotRead()
    {
        var config = ProviderConfiguration.Read(Write("""
            {
              "adapterInstallRoot": "C:/adapters",
              "providers": {
                "github": { "auth": "subscription", "engine": "copilot", "acp": "native",
                  "metered": "credits", "accounts": [ { "label": "enterprise-org", "health": "ready" } ] }
              },
              "routing": { "default_mode": "pinned-per-role" },
              "engines": { "copilot": { "model": "gpt-5" } }
            }
            """));

        var row = config.Registry.Find("github");
        Assert.Equal("enterprise-org", Assert.Single(row.Accounts).Label);

        // Nothing from `engine:`, `acp:`, `metered:` or `routing:` reached the row: the record has
        // no member that could hold one.
        Assert.Equal(3, typeof(ProviderRow).GetProperties().Length);
    }

    // ---------------------------------------------------------------------------------------
    // (a) — no code default, and an ambiguous binding is a field-level refusal naming the field.
    // ---------------------------------------------------------------------------------------

    /// <summary>One configured account is a binding; the file chose it by carrying exactly one.</summary>
    [Fact]
    public void OneConfiguredAccountBindsWithoutASelection()
    {
        var config = ProviderConfiguration.Read(Write(Section142AsJson));

        var binding = config.Bind("claude-code", out var refusal);

        Assert.Null(refusal);
        Assert.NotNull(binding);
        Assert.Equal("claude-code", binding!.EngineId);
        Assert.Equal("claude-sonnet-4-6", binding.Model);
        Assert.Equal("max-personal", binding.Account.Label);
        Assert.Equal("anthropic", binding.Provider.ProviderId);
    }

    /// <summary>
    /// <b>Condition (a), the whole of it:</b> two accounts and no selection is a refusal that names
    /// the field, never the first row.
    /// </summary>
    /// <remarks>
    /// A reader that took <c>accounts[0]</c> here would be correct in the single-account case, which
    /// is every case anyone tests by hand, and wrong in exactly the case that costs money. The
    /// refusal names <c>accountLabel</c> because that is the field the operator must fill in, and it
    /// names both candidates so the fix does not require re-reading the file.
    /// </remarks>
    [Fact]
    public void TwoAccountsAndNoSelectionIsAFieldLevelRefusalNamingTheField()
    {
        var config = ProviderConfiguration.Read(Write("""
            {
              "adapterInstallRoot": "C:/adapters",
              "providers": {
                "anthropic": { "auth": "subscription", "accounts": [
                  { "label": "max-personal", "health": "ready" },
                  { "label": "max-work", "health": "ready" } ] }
              },
              "engines": { "claude-code": { "model": "claude-sonnet-4-6" } }
            }
            """));

        var binding = config.Bind("claude-code", out var refusal);

        Assert.Null(binding);
        Assert.NotNull(refusal);
        Assert.Equal("accountLabel", refusal!.Field);
        Assert.Contains("max-personal", refusal.Message, StringComparison.Ordinal);
        Assert.Contains("max-work", refusal.Message, StringComparison.Ordinal);
        Assert.Contains("providers.json", refusal.Message, StringComparison.Ordinal);
    }

    /// <summary>The selection resolves it — and it is the operator's, from the file.</summary>
    [Fact]
    public void AnAccountSelectionResolvesTheAmbiguity()
    {
        var config = ProviderConfiguration.Read(Write("""
            {
              "adapterInstallRoot": "C:/adapters",
              "providers": {
                "anthropic": { "auth": "subscription", "accounts": [
                  { "label": "max-personal", "health": "ready" },
                  { "label": "max-work", "health": "ready" } ] }
              },
              "engines": { "claude-code": { "model": "opus", "account": "max-work" } }
            }
            """));

        var binding = config.Bind("claude-code", out var refusal);

        Assert.Null(refusal);
        Assert.Equal("max-work", binding!.Account.Label);
        Assert.Equal("opus", binding.Model);
    }

    /// <summary>A selection the provider does not carry is refused by the registry's own rule.</summary>
    [Fact]
    public void ASelectedAccountTheProviderDoesNotCarryIsRefusedNamingIt()
    {
        var config = ProviderConfiguration.Read(Write("""
            {
              "adapterInstallRoot": "C:/adapters",
              "providers": { "anthropic": { "auth": "subscription", "accounts": [
                { "label": "max-personal", "health": "ready" } ] } },
              "engines": { "claude-code": { "model": "opus", "account": "max-typo" } }
            }
            """));

        var binding = config.Bind("claude-code", out var refusal);

        Assert.Null(binding);
        Assert.Equal("accountLabel", refusal!.Field);
        Assert.Contains("max-typo", refusal.Message, StringComparison.Ordinal);
    }

    /// <summary>No model in the file is no model anywhere. There is nothing to fall back to.</summary>
    [Fact]
    public void AnEngineWithNoModelIsAFieldLevelRefusalNamingModel()
    {
        var config = ProviderConfiguration.Read(Write("""
            {
              "adapterInstallRoot": "C:/adapters",
              "providers": { "anthropic": { "auth": "subscription", "accounts": [
                { "label": "max-personal", "health": "ready" } ] } }
            }
            """));

        var binding = config.Bind("claude-code", out var refusal);

        Assert.Null(binding);
        Assert.Equal("model", refusal!.Field);
        Assert.Contains("claude-code", refusal.Message, StringComparison.Ordinal);
        Assert.Contains("providers.json", refusal.Message, StringComparison.Ordinal);
    }

    /// <summary>An engines entry with a key but no model is malformed, not an absent model.</summary>
    [Fact]
    public void AnEnginesEntryWithNoModelMemberIsMalformed()
    {
        var error = Malformed("""
            { "adapterInstallRoot": "C:/a", "providers": {}, "engines": { "claude-code": { } } }
            """);

        Assert.Contains("model", error.Message, StringComparison.Ordinal);
    }

    /// <summary>An engine whose provider is not in the file refuses, and says which provider.</summary>
    [Fact]
    public void AnEngineWhoseProviderIsNotConfiguredIsRefusedNamingTheProvider()
    {
        var config = ProviderConfiguration.Read(Write("""
            {
              "adapterInstallRoot": "C:/adapters",
              "providers": { "anthropic": { "auth": "subscription", "accounts": [
                { "label": "max-personal", "health": "ready" } ] } },
              "engines": { "codex": { "model": "gpt-5" } }
            }
            """));

        var binding = config.Bind("codex", out var refusal);

        Assert.Null(binding);
        Assert.Equal("providers", refusal!.Field);
        Assert.Contains("openai", refusal.Message, StringComparison.Ordinal);
    }

    /// <summary>
    /// needs-login stays an absence at the binding too — the registry's rule, not a second opinion.
    /// </summary>
    [Fact]
    public void ANeedsLoginAccountDoesNotBind()
    {
        var config = ProviderConfiguration.Read(Write("""
            {
              "adapterInstallRoot": "C:/adapters",
              "providers": { "anthropic": { "auth": "subscription", "accounts": [
                { "label": "max-personal", "health": "needs-login" } ] } },
              "engines": { "claude-code": { "model": "opus" } }
            }
            """));

        var binding = config.Bind("claude-code", out var refusal);

        Assert.Null(binding);
        Assert.Equal("accountLabel", refusal!.Field);
        Assert.Contains("needs-login", refusal.Message, StringComparison.Ordinal);
    }

    /// <summary>
    /// The structural half of "no code default": the source declares no fallback for either field.
    /// </summary>
    /// <remarks>
    /// The behavioural cases above each prove one path. This proves there is no OTHER path — a
    /// <c>??</c> or a <c>= "sonnet"</c> added later by someone making a test pass would go red here
    /// rather than in a standings cohort six weeks on. CI6: a rule that is only prose is a memoir.
    /// </remarks>
    [Fact]
    public void TheReaderDeclaresNoFallbackForAModelOrAnAccount()
    {
        var source = RepoFiles.SourceFile("src", "AiDe.Core", "AgentPlane", "ProviderConfiguration.cs");

        foreach (var fallback in new[]
                 {
                     "Model ??", "model ??", "Account ??", "account ??",
                     "FirstOrDefault()", "?? \"", "Accounts[0]",
                 })
        {
            Assert.DoesNotContain(fallback, source, StringComparison.Ordinal);
        }
    }

    /// <summary>The path is <c>~/.aide/providers.json</c>, as §4.3 says and with §14.2's name corrected.</summary>
    [Fact]
    public void TheDefaultPathIsUnderTheUsersAideDirectory()
    {
        var path = ProviderConfiguration.DefaultPath;

        Assert.EndsWith(Path.Combine(".aide", "providers.json"), path, StringComparison.Ordinal);
        Assert.True(Path.IsPathRooted(path));
    }
}
