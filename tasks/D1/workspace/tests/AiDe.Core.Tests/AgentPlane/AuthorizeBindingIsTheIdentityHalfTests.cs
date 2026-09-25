using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// ADR-0035 rule 1: <c>SpawnContract.AuthorizeBinding</c> is the identity half of
/// <see cref="SpawnContract.Authorize"/> factored out — the direct-api refusal, <c>Bind</c>, the
/// observed-subscription check and the label match — so a compile, which exists to <i>fill</i> the
/// goal block (§A9 R0), takes the same <c>AP-0009</c>–<c>AP-0013</c> gate a lane takes without
/// spoofing a placeholder block into <c>Authorize</c>.
/// </summary>
/// <remarks>
/// <b>The same refusal from both entry points, by code.</b> Each case below drives one input through
/// <c>AuthorizeBinding</c> and through <c>Authorize</c> (with a complete block) and asserts the two
/// codes are equal — a gate that was factored but drifted would fail here, not in production.
/// </remarks>
public sealed class AuthorizeBindingIsTheIdentityHalfTests
{
    private static GoalBlock Complete() => new("g", "d", "n", "T1", 0, new RunBudget(1, 1));

    private static ProviderRegistry Registry(string? recordedLabel = null)
        => new([new ProviderRow("anthropic", ProviderAuth.Subscription, [new ProviderAccount("max-personal", AccountHealth.Ready, recordedLabel)])]);

    private static ObservedAuthStatus Subscription(string label = "Claude Max")
        => new(ObservedAuthStatus.AccountKind, Plan: "max", Label: label);

    /// <summary>R0: a compile has no goal block yet, and the binding gate does not ask for one.</summary>
    [Fact]
    public void AnEmptyStructureIsNotRefusedByTheBindingGate()
    {
        var binding = SpawnContract.AuthorizeBinding("claude-code", "sonnet", "max-personal", Subscription(), Registry());

        Assert.Equal("claude-code", binding.Binding.EngineId);
        Assert.Equal("sonnet", binding.Binding.Model);
        Assert.Equal("max-personal", binding.Binding.Account.Label);
        Assert.True(binding.ObservedAuth.IsSubscription);
    }

    public static TheoryData<string, string, string?, ObservedAuthStatus?, string> Refusals => new()
    {
        // engineId, accountLabel, recorded label, observed, expected code
        { ProviderRegistry.DirectApiEngineId, "max-personal", null, Subscription(), AgentPlaneErrorCodes.DirectApiRefusedByToS },
        { "claude-code", "max-personal", null, null, AgentPlaneErrorCodes.ObservedAuthNotRecorded },
        { "claude-code", "max-personal", null, new ObservedAuthStatus("apiKey", null, null), AgentPlaneErrorCodes.ObservedAuthNotSubscription },
        { "claude-code", "max-personal", "Claude Max", Subscription("Claude Team"), AgentPlaneErrorCodes.ObservedAuthAccountMismatch },
        { "claude-code", "no-such-account", null, Subscription(), AgentPlaneErrorCodes.UnknownAccount },
    };

    /// <summary>The AP-0009–AP-0013 refusals (and Bind's own) are the same code from both entry points.</summary>
    [Theory]
    [MemberData(nameof(Refusals))]
    public void TheSameRefusalComesFromBothEntryPoints(string engineId, string accountLabel, string? recordedLabel, ObservedAuthStatus? observed, string expectedCode)
    {
        var registry = Registry(recordedLabel);

        var fromBinding = Assert.Throws<AgentPlaneException>(
            () => SpawnContract.AuthorizeBinding(engineId, "sonnet", accountLabel, observed, registry));
        var fromAuthorize = Assert.Throws<AgentPlaneException>(
            () => SpawnContract.Authorize(new SpawnRequest(Complete(), engineId, "sonnet", accountLabel, observed), registry));

        Assert.Equal(expectedCode, fromBinding.Code);
        Assert.Equal(fromBinding.Code, fromAuthorize.Code);
    }

    /// <summary>
    /// <c>Authorize</c> is unchanged in order (US-D12): the ToS refusal still precedes the goal
    /// block, and an incomplete block is still refused before the binding is looked up — so a
    /// block-incomplete request against an unknown account reads <c>AP-0008</c>, as before.
    /// </summary>
    [Fact]
    public void AuthorizeStillRefusesTheGoalBlockBeforeTheBinding()
    {
        var error = Assert.Throws<AgentPlaneException>(
            () => SpawnContract.Authorize(new SpawnRequest(null, "claude-code", "sonnet", "no-such-account", Subscription()), Registry()));

        Assert.Equal(AgentPlaneErrorCodes.GoalBlockIncomplete, error.Code);
    }

    /// <summary>A read-only spawn and a binding-only authorization agree on the binding they return.</summary>
    [Fact]
    public void AuthorizeReturnsTheBindingAuthorizeBindingReturns()
    {
        var registry = Registry("Claude Max");

        var spawn = SpawnContract.Authorize(new SpawnRequest(null, "claude-code", "sonnet", "max-personal", Subscription(), ReadOnly: true), registry);
        var binding = SpawnContract.AuthorizeBinding("claude-code", "sonnet", "max-personal", Subscription(), registry);

        Assert.Equal(spawn.Binding, binding.Binding);
        Assert.Equal(spawn.ObservedAuth, binding.ObservedAuth);
    }
}
