using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// The provider registry — spec §4.3. An unknown provider is refused, a lane binds to
/// <c>(engine, model, account)</c>, and an account carries one of three observed health states.
/// </summary>
/// <remarks>
/// <para><b>The clause these tests exist to falsify:</b> "an unknown provider id is refused, not
/// defaulted". The dangerous shape is not a crash — it is a registry that quietly answers with the
/// one provider that happens to be configured, so a lane bound to a typo runs on somebody else's
/// account and the bill is the first thing that notices.</para>
///
/// <para><b>Accounts are first-class</b> (§4.3): "a lane binds to (engine, model, account), never
/// just a provider. Quota pressure, standings cohorts, and the profiler all key on the account." A
/// binding that carried only a provider would make every one of those three read the wrong row.</para>
/// </remarks>
public sealed class ProviderRegistryTests
{
    private static ProviderRow Anthropic(AccountHealth health = AccountHealth.Ready)
        => new("anthropic", ProviderAuth.Subscription, [new ProviderAccount("max-personal", health)]);

    private static ProviderRegistry Registry(params ProviderRow[] rows) => new(rows);

    /// <summary>The headline refusal: an id the registry does not carry never resolves to one it does.</summary>
    [Fact]
    public void AnUnknownProviderIdIsRefused()
    {
        var error = Assert.Throws<AgentPlaneException>(() => Registry(Anthropic()).Find("anthropik"));

        Assert.Equal(AgentPlaneErrorCodes.UnknownProvider, error.Code);
        Assert.Contains("anthropik", error.Message, StringComparison.Ordinal);
    }

    /// <summary>
    /// The other half of "refused, not defaulted", asserted where a default would be most tempting.
    /// </summary>
    /// <remarks>
    /// With exactly one provider configured, a lenient lookup ("there is only one, they must have
    /// meant that") is both plausible to write and impossible to notice. This test is the reason the
    /// registry may not become lenient later.
    /// </remarks>
    [Fact]
    public void ASingleConfiguredProviderIsNotSubstitutedForAnUnknownOne()
    {
        var registry = Registry(Anthropic());

        Assert.Throws<AgentPlaneException>(() => registry.Find("openai"));
        Assert.Equal("anthropic", Assert.Single(registry.Rows).ProviderId);
    }

    /// <summary>A lane binds to the triple, not to a provider.</summary>
    [Fact]
    public void ALaneBindsToEngineModelAndAccount()
    {
        var binding = Registry(Anthropic()).Bind("claude-code", "sonnet", "max-personal");

        Assert.Equal("claude-code", binding.EngineId);
        Assert.Equal("sonnet", binding.Model);
        Assert.Equal("max-personal", binding.Account.Label);
        Assert.Equal("anthropic", binding.Provider.ProviderId);
    }

    /// <summary>An account label nobody logged into is refused rather than resolved to the first one.</summary>
    [Fact]
    public void AnUnknownAccountLabelIsRefused()
    {
        var error = Assert.Throws<AgentPlaneException>(
            () => Registry(Anthropic()).Bind("claude-code", "sonnet", "max-work"));

        Assert.Equal(AgentPlaneErrorCodes.UnknownAccount, error.Code);
        Assert.Contains("max-work", error.Message, StringComparison.Ordinal);
    }

    /// <summary>
    /// The three states of §4.3's health probe, and the one rule the spec states about them: "the
    /// router treats <c>needs-login</c> as absent".
    /// </summary>
    /// <remarks>
    /// <c>quota-degraded</c> deliberately still binds. It is a pressure signal, not an absence — an
    /// account under quota pressure can still run a lane, and refusing it would turn a soft signal
    /// into an outage. The binding carries the health so a caller can see the degradation instead of
    /// inferring it.
    /// </remarks>
    [Theory]
    [InlineData(AccountHealth.Ready, true)]
    [InlineData(AccountHealth.QuotaDegraded, true)]
    [InlineData(AccountHealth.NeedsLogin, false)]
    public void NeedsLoginIsTreatedAsAbsentAndTheOtherTwoBind(AccountHealth health, bool bindable)
    {
        var registry = Registry(Anthropic(health));

        if (bindable)
        {
            Assert.Equal(health, registry.Bind("claude-code", "sonnet", "max-personal").Account.Health);
            return;
        }

        var error = Assert.Throws<AgentPlaneException>(() => registry.Bind("claude-code", "sonnet", "max-personal"));
        Assert.Equal(AgentPlaneErrorCodes.AccountNotReady, error.Code);
        Assert.Contains("needs-login", error.Message, StringComparison.Ordinal);
    }

    /// <summary>
    /// The engine → provider mapping is the catalog's, so an unknown engine is refused with the
    /// catalog's own code rather than re-decided here.
    /// </summary>
    /// <remarks>
    /// Two definitions of one mapping is a defect signature (DM7). <see cref="EngineCatalog"/>
    /// already carries <c>Provider</c> per row, so <see cref="ProviderRow"/> deliberately does not.
    /// </remarks>
    [Fact]
    public void AnEngineTheCatalogDoesNotCarryIsRefusedWithTheCatalogsCode()
    {
        var error = Assert.Throws<AgentPlaneException>(
            () => Registry(Anthropic()).Bind("claude-kode", "sonnet", "max-personal"));

        Assert.Equal(AgentPlaneErrorCodes.UnknownEngine, error.Code);
    }

    /// <summary>A catalogued engine whose provider is not configured is refused, never defaulted.</summary>
    [Fact]
    public void ACataloguedEngineWithNoConfiguredProviderIsRefused()
    {
        var error = Assert.Throws<AgentPlaneException>(
            () => Registry(Anthropic()).Bind("codex", "gpt-5", "chatgpt-personal"));

        Assert.Equal(AgentPlaneErrorCodes.UnknownProvider, error.Code);
        Assert.Contains("openai", error.Message, StringComparison.Ordinal);
    }

    /// <summary>Two rows for one provider id is a configuration error, refused at construction.</summary>
    [Fact]
    public void ADuplicateProviderIdIsRefusedAtConstruction()
        => Assert.Throws<AgentPlaneException>(() => Registry(Anthropic(), Anthropic()));
}
