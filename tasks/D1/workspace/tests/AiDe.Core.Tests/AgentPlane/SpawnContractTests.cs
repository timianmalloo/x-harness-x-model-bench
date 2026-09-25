using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// The goal block as a spawn precondition (spec R2, §14.3) and the two refusals that gate an
/// Anthropic spawn (spec §4.2 + the observed-auth ruling).
/// </summary>
/// <remarks>
/// <para><b>Why the field test is parameterized over all six.</b> R2 says "<c>spawn_agent</c> without
/// <i>any</i> of Goal / Done when / Not in scope / Tier / Fan-out cap / Budget fails with a
/// field-level error". A single omit-one-field test satisfies that sentence while five of the six
/// fields go unchecked, and the field most likely to be forgotten is <b>Budget</b> — it appears only
/// in §14.3's schema excerpt and in no prose bullet. So the theory enumerates the six by name, and
/// <see cref="TheSpecNamesExactlySixFields"/> fails the day someone adds a seventh without adding a
/// case for it.</para>
///
/// <para><b>Why the error must name the field.</b> "The goal block is incomplete" sends the caller
/// back to compare six values by eye. A field-level error is the difference between a message and a
/// fix.</para>
/// </remarks>
public sealed class SpawnContractTests
{
    private static GoalBlock Complete() => new(
        Goal: "Move PaymentAggregate and handlers into Payments.Domain",
        DoneWhen: "Payments.Domain builds; its tests green; no references from Ordering",
        NotInScope: "IPaymentGateway contract edits (serial spine)",
        Tier: "T1",
        FanOutCap: 0,
        Budget: new RunBudget(Requests: 250, Tokens: 600_000));

    /// <summary>The complete block with exactly one field removed.</summary>
    private static GoalBlock Without(string field) => field switch
    {
        GoalBlockFields.GoalKey => Complete() with { Goal = null },
        GoalBlockFields.DoneWhenKey => Complete() with { DoneWhen = null },
        GoalBlockFields.NotInScopeKey => Complete() with { NotInScope = null },
        GoalBlockFields.TierKey => Complete() with { Tier = null },
        GoalBlockFields.FanOutCapKey => Complete() with { FanOutCap = null },
        GoalBlockFields.BudgetKey => Complete() with { Budget = null },
        _ => throw new ArgumentOutOfRangeException(nameof(field), field, "unknown goal-block field"),
    };

    private static ProviderRegistry SubscriptionRegistry(AccountHealth health = AccountHealth.Ready)
        => new([new ProviderRow("anthropic", ProviderAuth.Subscription, [new ProviderAccount("max-personal", health)])]);

    private static ObservedAuthStatus Subscription()
        => new(ObservedAuthStatus.AccountKind, Plan: "max", Label: "Claude Max");

    private static SpawnRequest Request(
        GoalBlock? goal = null, string engineId = "claude-code", ObservedAuthStatus? auth = null)
        => new(goal ?? Complete(), engineId, Model: "sonnet", AccountLabel: "max-personal", ObservedAuth: auth);

    /// <summary>The theory below must enumerate every field the spec names; this fails if one appears.</summary>
    [Fact]
    public void TheSpecNamesExactlySixFields()
    {
        Assert.Equal(6, GoalBlockFields.All.Count);
        Assert.Equal(
            new[] { "goal", "done_when", "not_in_scope", "tier", "fan_out_cap", "budget" },
            GoalBlockFields.All);
    }

    /// <summary>Omitting any one of the six yields exactly one error, and it names that field.</summary>
    [Theory]
    [InlineData(GoalBlockFields.GoalKey)]
    [InlineData(GoalBlockFields.DoneWhenKey)]
    [InlineData(GoalBlockFields.NotInScopeKey)]
    [InlineData(GoalBlockFields.TierKey)]
    [InlineData(GoalBlockFields.FanOutCapKey)]
    [InlineData(GoalBlockFields.BudgetKey)]
    public void OmittingAnyOneFieldFailsWithAnErrorNamingThatField(string field)
    {
        var error = Assert.Single(SpawnContract.Validate(Without(field)));

        Assert.Equal(field, error.Field);
        Assert.Contains(field, error.Message, StringComparison.Ordinal);
    }

    /// <summary>And the refusal a caller actually sees at spawn names it too, not merely the result object.</summary>
    [Theory]
    [InlineData(GoalBlockFields.GoalKey)]
    [InlineData(GoalBlockFields.DoneWhenKey)]
    [InlineData(GoalBlockFields.NotInScopeKey)]
    [InlineData(GoalBlockFields.TierKey)]
    [InlineData(GoalBlockFields.FanOutCapKey)]
    [InlineData(GoalBlockFields.BudgetKey)]
    public void TheSpawnRefusalNamesTheOmittedField(string field)
    {
        var error = Assert.Throws<AgentPlaneException>(
            () => SpawnContract.Authorize(Request(Without(field), auth: Subscription()), SubscriptionRegistry()));

        Assert.Equal(AgentPlaneErrorCodes.GoalBlockIncomplete, error.Code);
        Assert.Contains(field, error.Message, StringComparison.Ordinal);
    }

    [Fact]
    public void ACompleteGoalBlockValidates() => Assert.Empty(SpawnContract.Validate(Complete()));

    /// <summary>
    /// A fan-out cap of zero is a declaration, not an omission.
    /// </summary>
    /// <remarks>
    /// Zero is the most common real value — it is what "do not fan out" says — so a validator that
    /// tested truthiness rather than presence would reject exactly the ordinary case. This is why the
    /// field is nullable rather than defaulted.
    /// </remarks>
    [Fact]
    public void AFanOutCapOfZeroIsPresent()
        => Assert.Empty(SpawnContract.Validate(Complete() with { FanOutCap = 0 }));

    /// <summary>A blank string is an unwritten field, not a written empty one.</summary>
    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public void ABlankFieldIsTreatedAsMissing(string blank)
    {
        var error = Assert.Single(SpawnContract.Validate(Complete() with { NotInScope = blank }));

        Assert.Equal(GoalBlockFields.NotInScopeKey, error.Field);
    }

    /// <summary>A negative cap and an empty budget are named against their own field, not a generic error.</summary>
    [Fact]
    public void AnOutOfRangeValueIsReportedAgainstItsOwnField()
    {
        Assert.Equal(
            GoalBlockFields.FanOutCapKey,
            Assert.Single(SpawnContract.Validate(Complete() with { FanOutCap = -1 })).Field);

        Assert.Equal(
            GoalBlockFields.BudgetKey,
            Assert.Single(SpawnContract.Validate(Complete() with { Budget = new RunBudget(0, 0) })).Field);
    }

    /// <summary>Every missing field is reported at once, not one per round trip.</summary>
    [Fact]
    public void AnEmptyGoalBlockNamesAllSixFields()
    {
        var errors = SpawnContract.Validate(new GoalBlock(null, null, null, null, null, null));

        Assert.Equal(GoalBlockFields.All, [.. errors.Select(e => e.Field)]);
    }

    // ---- The ToS invariant (spec §4.2, line 354; ToS ruling clause 1) ----

    /// <summary>
    /// An Anthropic direct-api spawn is rejected with the ToS reason while a subscription is configured.
    /// </summary>
    /// <remarks>
    /// Spec §4.2 states the prohibition and says it is "enforced in code": Anthropic forbids
    /// third-party tools from using Pro/Max subscriptions, so every Anthropic-bound request must
    /// originate inside a Claude Code process. A refusal that said only "unknown engine" would be
    /// true and useless — the operator would add the engine.
    /// </remarks>
    [Fact]
    public void AnAnthropicDirectApiSpawnIsRejectedWithTheToSReason()
    {
        var error = Assert.Throws<AgentPlaneException>(
            () => SpawnContract.Authorize(
                Request(engineId: ProviderRegistry.DirectApiEngineId, auth: Subscription()),
                SubscriptionRegistry()));

        Assert.Equal(AgentPlaneErrorCodes.DirectApiRefusedByToS, error.Code);
        Assert.Contains("subscription", error.Message, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("terms of service", error.Message, StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>
    /// The ToS refusal is checked first, so an incomplete goal block cannot mask it.
    /// </summary>
    /// <remarks>
    /// Ordering is the whole substance here. If validation ran first, the operator would fix six
    /// fields and only then learn the spawn was never permitted — and a reader of the code would
    /// have to prove the prohibition is unreachable-by-accident rather than read it.
    /// </remarks>
    [Fact]
    public void TheToSRefusalIsNotMaskedByAnIncompleteGoalBlock()
    {
        var error = Assert.Throws<AgentPlaneException>(
            () => SpawnContract.Authorize(
                Request(new GoalBlock(null, null, null, null, null, null), ProviderRegistry.DirectApiEngineId),
                SubscriptionRegistry()));

        Assert.Equal(AgentPlaneErrorCodes.DirectApiRefusedByToS, error.Code);
    }

    // ---- The observed-auth gate (ToS ruling clause 2) — fail closed ----

    /// <summary>
    /// An absent observed auth status REFUSES. It never assumes subscription.
    /// </summary>
    /// <remarks>
    /// The spike found that <c>ANTHROPIC_API_KEY</c>, an <c>apiKeyHelper</c> or a managed key
    /// outranks the stored subscription inside the adapter, so a lane can believe it is on the
    /// subscription and be silently billed to the API — with no direct-api spawn to reject. The
    /// status frame is an <c>_</c>-prefixed extension and may simply not arrive; when it does not,
    /// the honest state is "not recorded", and a "not recorded" that proceeds is a guess with a bill
    /// attached.
    /// </remarks>
    [Fact]
    public void AnAbsentObservedAuthStatusRefusesTheSpawn()
    {
        var error = Assert.Throws<AgentPlaneException>(
            () => SpawnContract.Authorize(Request(auth: null), SubscriptionRegistry()));

        Assert.Equal(AgentPlaneErrorCodes.ObservedAuthNotRecorded, error.Code);
        Assert.Contains("not recorded", error.Message, StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>An observed status that is not a subscription refuses, naming what was observed.</summary>
    [Theory]
    [InlineData("apiKey")]
    [InlineData("unauthenticated")]
    [InlineData("")]
    public void AnObservedNonSubscriptionAuthStatusRefusesTheSpawn(string kind)
    {
        var error = Assert.Throws<AgentPlaneException>(
            () => SpawnContract.Authorize(
                Request(auth: new ObservedAuthStatus(kind, Plan: null, Label: null)),
                SubscriptionRegistry()));

        Assert.Equal(AgentPlaneErrorCodes.ObservedAuthNotSubscription, error.Code);
    }

    /// <summary>The positive control: an observed subscription authorizes, and the spawn carries the triple.</summary>
    [Fact]
    public void AnObservedSubscriptionAuthorizesTheSpawn()
    {
        var spawn = SpawnContract.Authorize(Request(auth: Subscription()), SubscriptionRegistry());

        Assert.Equal("claude-code", spawn.Binding.EngineId);
        Assert.Equal("sonnet", spawn.Binding.Model);
        Assert.Equal("max-personal", spawn.Binding.Account.Label);
        Assert.Equal("Claude Max", spawn.ObservedAuth.Label);
        Assert.Equal("T1", spawn.Goal?.Tier);
    }

    /// <summary>A quota-degraded account still spawns; the pressure travels with the binding.</summary>
    [Fact]
    public void AQuotaDegradedAccountStillSpawnsAndSaysSo()
    {
        var spawn = SpawnContract.Authorize(
            Request(auth: Subscription()), SubscriptionRegistry(AccountHealth.QuotaDegraded));

        Assert.Equal(AccountHealth.QuotaDegraded, spawn.Binding.Account.Health);
    }

    // ------------------------------------------------------------ the auth-label correspondence

    /// <summary>
    /// The gap N3 named, closed: when the operator has recorded what the adapter calls this account,
    /// the observed label is checked against it, and a mismatch refuses.
    /// </summary>
    /// <remarks>
    /// <para><b>Why the correspondence has to be declared and cannot be derived.</b> The configured
    /// label is an operator's own name for a login (<c>max-personal</c>); the observed label is the
    /// adapter's name for a <i>plan tier</i> (<c>Claude Max</c>). Nothing in either value determines
    /// the other, and the adapter reads the local <c>claude</c> CLI credential store — which holds
    /// exactly one login — so it can never report which of several configured accounts the operator
    /// meant. Inventing a mapping inside a control that exists because guessing is expensive is how
    /// the control starts lying.</para>
    ///
    /// <para><b>What the check therefore buys.</b> An operator who has two subscription logins and
    /// switches the CLI between them gets a refusal instead of a lane that bills, ranks and reports
    /// against the wrong account.</para>
    /// </remarks>
    [Fact]
    public void AnObservedLabelThatContradictsTheRecordedOneRefusesTheSpawn()
    {
        var registry = new ProviderRegistry([
            new ProviderRow(
                "anthropic",
                ProviderAuth.Subscription,
                [new ProviderAccount("max-personal", AccountHealth.Ready, ObservedAuthLabel: "Claude Max")]),
        ]);

        var error = Assert.Throws<AgentPlaneException>(
            () => SpawnContract.Authorize(
                Request(auth: new ObservedAuthStatus(ObservedAuthStatus.AccountKind, "team", "Claude Team")),
                registry));

        Assert.Equal(AgentPlaneErrorCodes.ObservedAuthAccountMismatch, error.Code);
        Assert.Contains("Claude Max", error.Message, StringComparison.Ordinal);
        Assert.Contains("Claude Team", error.Message, StringComparison.Ordinal);
    }

    // ------------------------------------------------------------ S2: RunBudget.SubscriptionBounded

    /// <summary>The sentinel's exact declared value (ADR-0033 §3): maximal, and positive on both fields.</summary>
    [Fact]
    public void SubscriptionBoundedIsTheDeclaredMaximalValue()
    {
        Assert.Equal(int.MaxValue, RunBudget.SubscriptionBounded.Requests);
        Assert.Equal(long.MaxValue, RunBudget.SubscriptionBounded.Tokens);
    }

    /// <summary>
    /// A goal block carrying the sentinel validates with no error — <c>Validate</c> is tier-blind and
    /// stays byte-identical (ADR-0033's "Alternatives considered"): the sentinel is accepted because
    /// it is a positive value like any other, not because of a special case in the validator.
    /// </summary>
    [Fact]
    public void AGoalBlockCarryingSubscriptionBoundedValidatesWithNoError()
        => Assert.Empty(SpawnContract.Validate(Complete() with { Budget = RunBudget.SubscriptionBounded }));

    /// <summary>The same block authorizes a spawn, carrying the sentinel through untouched.</summary>
    [Fact]
    public void AGoalBlockCarryingSubscriptionBoundedAuthorizesASpawn()
    {
        var spawn = SpawnContract.Authorize(
            Request(Complete() with { Budget = RunBudget.SubscriptionBounded }, auth: Subscription()),
            SubscriptionRegistry());

        Assert.NotNull(spawn.Goal);
        Assert.True(spawn.Goal.Budget!.IsSubscriptionBounded);
    }

    /// <summary>
    /// <see cref="RunBudget.IsSubscriptionBounded"/> is value equality, not reference equality — the
    /// case that matters once the record has crossed JSON and come back as a new instance (ADR-0033
    /// §3: "a <c>RunBudget(int.MaxValue, long.MaxValue)</c> read from a request file satisfies the
    /// predicate").
    /// </summary>
    [Fact]
    public void IsSubscriptionBoundedIsValueEqualityNotReferenceEquality()
    {
        var separatelyConstructed = new RunBudget(int.MaxValue, long.MaxValue);

        Assert.NotSame(RunBudget.SubscriptionBounded, separatelyConstructed);
        Assert.True(separatelyConstructed.IsSubscriptionBounded);
    }

    /// <summary>An ordinary, finite budget is not mistaken for the sentinel.</summary>
    [Fact]
    public void AnOrdinaryBudgetIsNotSubscriptionBounded()
        => Assert.False(new RunBudget(250, 600_000).IsSubscriptionBounded);

    /// <summary>The matching case authorizes — the check is a correspondence, not a second refusal.</summary>
    [Fact]
    public void AnObservedLabelThatMatchesTheRecordedOneAuthorizes()
    {
        var registry = new ProviderRegistry([
            new ProviderRow(
                "anthropic",
                ProviderAuth.Subscription,
                [new ProviderAccount("max-personal", AccountHealth.Ready, ObservedAuthLabel: "Claude Max")]),
        ]);

        var spawn = SpawnContract.Authorize(Request(auth: Subscription()), registry);

        Assert.Equal("Claude Max", spawn.ObservedAuth.Label);
    }

    /// <summary>
    /// With nothing recorded the check degrades to <c>kind</c> alone — <b>"not recorded", never a
    /// guessed correspondence</b> (IO12) — and the account says so about itself.
    /// </summary>
    [Fact]
    public void WithNoRecordedLabelTheCheckIsKindAloneAndTheAccountSaysSo()
    {
        var account = new ProviderAccount("max-personal", AccountHealth.Ready);
        Assert.Null(account.ObservedAuthLabel);

        var spawn = SpawnContract.Authorize(
            Request(auth: new ObservedAuthStatus(ObservedAuthStatus.AccountKind, "max", "Anything At All")),
            new ProviderRegistry([new ProviderRow("anthropic", ProviderAuth.Subscription, [account])]));

        Assert.Equal("Anything At All", spawn.ObservedAuth.Label);
    }

    // ------------------------------------------------------------ the read-only shape (Ruling 73)

    /// <summary>
    /// Ruling 73: a Message carries no goal block, and a read-only spawn — every write-capable tool
    /// disallowed on its lane — is authorized without one. R2's "no block, no spawn" is a rule about
    /// lanes that can write.
    /// </summary>
    [Fact]
    public void AReadOnlySpawnWithNoGoalBlockIsAuthorized()
    {
        var spawn = SpawnContract.Authorize(
            new SpawnRequest(null, "claude-code", "sonnet", "max-personal", Subscription(), ReadOnly: true),
            SubscriptionRegistry());

        Assert.Null(spawn.Goal);
        Assert.Equal("claude-code", spawn.Binding.EngineId);
        Assert.Equal("Claude Max", spawn.ObservedAuth.Label);
    }

    /// <summary>A scopeless goal block runs read-only too, and its block travels on the spawn.</summary>
    [Fact]
    public void AReadOnlySpawnWithAGoalBlockCarriesIt()
    {
        var spawn = SpawnContract.Authorize(
            new SpawnRequest(Complete(), "claude-code", "sonnet", "max-personal", Subscription(), ReadOnly: true),
            SubscriptionRegistry());

        Assert.Equal("T1", spawn.Goal?.Tier);
    }

    /// <summary>
    /// The control against over-narrowing: the write shape is the default, and it still requires the
    /// block — an absent block on a write-shaped spawn is R2's refusal, unchanged.
    /// </summary>
    [Fact]
    public void AWriteSpawnWithNoGoalBlockIsStillRefusedByField()
    {
        var error = Assert.Throws<AgentPlaneException>(
            () => SpawnContract.Authorize(
                new SpawnRequest(null, "claude-code", "sonnet", "max-personal", Subscription()),
                SubscriptionRegistry()));

        Assert.Equal(AgentPlaneErrorCodes.GoalBlockIncomplete, error.Code);
        Assert.False(new SpawnRequest(null, "e", "m", "a", null).ReadOnly);
    }

    /// <summary>
    /// The identity half is not waived by the shape: the ToS refusal and the observed-auth gate
    /// fire for a read-only spawn exactly as for a write.
    /// </summary>
    [Fact]
    public void TheIdentityGatesStillFireForAReadOnlySpawn()
    {
        var tos = Assert.Throws<AgentPlaneException>(
            () => SpawnContract.Authorize(
                new SpawnRequest(null, ProviderRegistry.DirectApiEngineId, "sonnet", "max-personal", Subscription(), ReadOnly: true),
                SubscriptionRegistry()));
        Assert.Equal(AgentPlaneErrorCodes.DirectApiRefusedByToS, tos.Code);

        var unrecorded = Assert.Throws<AgentPlaneException>(
            () => SpawnContract.Authorize(
                new SpawnRequest(null, "claude-code", "sonnet", "max-personal", null, ReadOnly: true),
                SubscriptionRegistry()));
        Assert.Equal(AgentPlaneErrorCodes.ObservedAuthNotRecorded, unrecorded.Code);

        var apiKey = Assert.Throws<AgentPlaneException>(
            () => SpawnContract.Authorize(
                new SpawnRequest(null, "claude-code", "sonnet", "max-personal", new ObservedAuthStatus("apiKey", null, null), ReadOnly: true),
                SubscriptionRegistry()));
        Assert.Equal(AgentPlaneErrorCodes.ObservedAuthNotSubscription, apiKey.Code);
    }
}
