namespace AiDe.Core.AgentPlane;

/// <summary>The per-run budget a goal block declares (§14.3 <c>budget: { requests, tokens }</c>).</summary>
/// <remarks>
/// A budget with no convergence condition is a timer, so the numbers live beside the done-condition
/// rather than alone. Both must be positive: a zero budget is not a small budget, it is a spawn that
/// can never do anything, which is a typo rather than an intent.
/// </remarks>
public sealed record RunBudget(int Requests, long Tokens)
{
    /// <summary>
    /// The declared value for "no cap chosen — bounded by the subscription instead" (Ruling 72;
    /// ADR-0033 §3), never a required number.
    /// </summary>
    /// <remarks>
    /// <para><b>A maximal, positive value rather than a nullable <see cref="RunBudget"/> or a second
    /// contract shape.</b> <see cref="SpawnContract.Validate"/>'s six fields are tier-blind and
    /// budget is one of them; making it optional there would be a contract change (ADR-0033's
    /// "Alternatives considered"). A declared maximal value keeps <see cref="SpawnContract.Validate"/>
    /// byte-identical and turns "no cap" into a value <see cref="IsSubscriptionBounded"/> can read,
    /// rather than an absence a caller must guess at.</para>
    ///
    /// <para><b>A one-way door.</b> This value crosses JSON into persisted run and result files
    /// (<c>ConductorEntry.cs</c>); every file ever written with <c>2147483647</c> /
    /// <c>9223372036854775807</c> must read as subscription-bounded forever, so
    /// <see cref="IsSubscriptionBounded"/> is a reader that can never be removed.</para>
    /// </remarks>
    public static readonly RunBudget SubscriptionBounded = new(Requests: int.MaxValue, Tokens: long.MaxValue);

    /// <summary>
    /// Whether this is the declared <see cref="SubscriptionBounded"/> value, by field equality.
    /// </summary>
    /// <remarks>
    /// <b>Value equality, not reference equality.</b> <see cref="RunBudget"/> crosses JSON (a request
    /// or result file deserializes a brand-new instance), so a caller checking
    /// <c>ReferenceEquals(budget, SubscriptionBounded)</c> would silently stop working the moment the
    /// value was read back from disk. Records already compare by value, so equality against the
    /// constant is exactly this predicate.
    /// </remarks>
    public bool IsSubscriptionBounded => this == SubscriptionBounded;

    /// <summary>
    /// How the absent cap reads wherever it is shown — Ruling 72 condition (1)'s words: the
    /// subscription's own limit is not readable by the product, so the state never reads as a
    /// number. One constant for the compiled block and the sheet (DM7).
    /// </summary>
    public const string SubscriptionBoundedDisplay = "bounded by your subscription — not measured here";
}

/// <summary>
/// The six fields spec §14.3 names, by their wire names. The error a caller sees uses these, so the
/// message and the schema are the same vocabulary.
/// </summary>
public static class GoalBlockFields
{
    // THE `Key` SUFFIX IS NOT DECORATION. These are the wire FIELD NAMES §14.3 lists, not the values
    // they carry: `FanOutCap` and `Budget` without it are names that claim to be limits, and
    // `verify-bounds-are-enforced.py` reads them as bounds that are declared and never compared —
    // correctly, on the name alone. The real bounds are `GoalBlock.FanOutCap` and `GoalBlock.Budget`,
    // and Phase 1 VALIDATES them without ENFORCING them: nothing counts requests or tokens against
    // the budget, and the plane spawns no sub-lane for a cap to bound. That gap is recorded in the
    // Proof Pack rather than hidden behind a name that reads as though it were closed.

    public const string GoalKey = "goal";
    public const string DoneWhenKey = "done_when";
    public const string NotInScopeKey = "not_in_scope";
    public const string TierKey = "tier";
    public const string FanOutCapKey = "fan_out_cap";
    public const string BudgetKey = "budget";

    /// <summary>All six, in the order §14.3 lists them.</summary>
    public static readonly IReadOnlyList<string> All = [GoalKey, DoneWhenKey, NotInScopeKey, TierKey, FanOutCapKey, BudgetKey];
}

/// <summary>
/// CT19's goal state as a spawn precondition — spec R2 and §14.3.
/// </summary>
/// <remarks>
/// <para><b>Every field is nullable, deliberately.</b> A required constructor parameter would move
/// the check to the compiler for a value that arrives from a tool call at runtime, and the caller
/// would then be forced to pass <i>something</i> — which is how a placeholder goal gets written. The
/// type carries what was declared; <see cref="SpawnContract.Validate"/> decides whether that is a
/// goal block. It also makes "omitted" expressible, which is what a field-level error needs.</para>
///
/// <para><b><see cref="FanOutCap"/> is <c>int?</c> rather than <c>int</c> for one specific reason:</b>
/// zero is the ordinary value — it is what "do not fan out" says — so presence cannot be tested by
/// truthiness. Defaulting it to zero would silently supply the most common answer and make the field
/// unforgettable in exactly the wrong way.</para>
/// </remarks>
public sealed record GoalBlock(
    string? Goal,
    string? DoneWhen,
    string? NotInScope,
    string? Tier,
    int? FanOutCap,
    RunBudget? Budget);

/// <summary>One field-level goal-block error. The field is a member, not a substring of prose.</summary>
/// <param name="Field">A <see cref="GoalBlockFields"/> name.</param>
/// <param name="Message">Why the spawn cannot proceed on it. Names the field too, for a log line read alone.</param>
public sealed record GoalBlockError(string Field, string Message);

/// <summary>
/// What the ACP adapter reported about how it is authenticated — the <c>_auth/status_update</c>
/// extension frame, observed live in the spike.
/// </summary>
/// <remarks>
/// <para><b>A measurement, not a configuration reading.</b> The spike found that
/// <c>ANTHROPIC_API_KEY</c>, an <c>apiKeyHelper</c> or a managed key <i>outrank</i> the stored
/// subscription inside the adapter, so a lane can believe it is on a subscription and be billed to
/// the API — with no direct-API spawn to reject. What the adapter says about itself is the only
/// version-robust evidence of where the requests will actually bill.</para>
///
/// <para><b>Absence is representable only as <c>null</c> at the call site.</b> The frame is an
/// <c>_</c>-prefixed extension and may not arrive at all; there is no "unknown" member here, because
/// the caller's <c>null</c> already says it and <see cref="SpawnContract"/> refuses on it.</para>
/// </remarks>
/// <param name="Kind">The observed <c>authStatus.kind</c>, verbatim.</param>
/// <param name="Plan">The observed plan, when the status carried one.</param>
/// <param name="Label">The adapter's display label — e.g. "Claude Max".</param>
public sealed record ObservedAuthStatus(string Kind, string? Plan, string? Label)
{
    /// <summary>The observed <c>kind</c> that means a subscription account, as captured in the spike.</summary>
    public const string AccountKind = "account";

    /// <summary>Whether the adapter says it is on a subscription account.</summary>
    public bool IsSubscription => string.Equals(Kind, AccountKind, StringComparison.Ordinal);
}

/// <summary>Everything a spawn attempt states about itself.</summary>
/// <param name="Goal">The goal block. Nullable so "no block at all" is a case rather than a crash.</param>
/// <param name="EngineId">The requested engine, which may be one no launch path implements.</param>
/// <param name="Model">The requested model.</param>
/// <param name="AccountLabel">The requested account.</param>
/// <param name="ObservedAuth">What the adapter reported, or <c>null</c> when nothing was observed.</param>
/// <param name="ReadOnly">
/// Ruling 73's read-only shape: the lane will hold no write-capable tool and no lease, so R2's
/// goal-block precondition — a rule about lanes that can write — is not applied; the identity
/// gates are. False by default, so every caller that existed before the ruling keeps R2 without
/// saying so. The host derives it from the request's missing lease — the same fact that picks the
/// lane's pin — never from a claim.
/// </param>
public sealed record SpawnRequest(
    GoalBlock? Goal,
    string EngineId,
    string Model,
    string AccountLabel,
    ObservedAuthStatus? ObservedAuth,
    bool ReadOnly = false);

/// <summary>
/// An authorized spawn: a resolved binding, an observed subscription, and — for a write, always;
/// for a read-only turn, when the turn had one — the goal block.
/// </summary>
/// <param name="Goal">Complete for a write. <c>null</c> only for a read-only Message (Ruling 73).</param>
public sealed record Spawn(GoalBlock? Goal, LaneBinding Binding, ObservedAuthStatus ObservedAuth);

/// <summary>
/// An authorized identity with no goal block: the resolved binding and the observed subscription —
/// what <see cref="SpawnContract.AuthorizeBinding"/> returns to a compile call (ADR-0035 rule 1).
/// </summary>
public sealed record BoundIdentity(LaneBinding Binding, ObservedAuthStatus ObservedAuth);

/// <summary>
/// The spawn precondition — spec R2 ("no block, no spawn"), §4.2's terms-of-service prohibition, and
/// the observed-auth gate.
/// </summary>
public static class SpawnContract
{
    /// <summary>
    /// Every reason this goal block is not one, each naming its own field. Empty means valid.
    /// </summary>
    /// <remarks>
    /// <para><b>All errors at once, not the first.</b> One-at-a-time validation turns a six-field
    /// omission into six round trips, and a conductor retrying a tool call six times looks like a
    /// loop rather than a caller who forgot the schema.</para>
    ///
    /// <para><b>A blank string is an unwritten field.</b> A goal of <c>"   "</c> and a goal of
    /// <c>null</c> want the same answer — the episode would be scored against nothing either way —
    /// and this matches how the coordination contract already reads an attribute. <c>not_in_scope</c>
    /// is included in that rule on purpose: CT19 requires the boundary to be <i>written</i>, and a
    /// lane with genuinely nothing out of scope can write so.</para>
    /// </remarks>
    public static IReadOnlyList<GoalBlockError> Validate(GoalBlock? block)
    {
        var errors = new List<GoalBlockError>();

        Text(errors, GoalBlockFields.GoalKey, block?.Goal, "what this lane is to achieve");
        Text(errors, GoalBlockFields.DoneWhenKey, block?.DoneWhen, "the terminal condition the outcome is judged against");
        Text(errors, GoalBlockFields.NotInScopeKey, block?.NotInScope, "the boundary the lane may not cross");
        Text(errors, GoalBlockFields.TierKey, block?.Tier, "the ceremony tier the run is held to");

        if (block?.FanOutCap is not { } cap)
        {
            errors.Add(Missing(GoalBlockFields.FanOutCapKey, "how many sub-lanes this lane may spawn (0 is a valid answer)"));
        }
        else if (cap < 0)
        {
            errors.Add(new GoalBlockError(
                GoalBlockFields.FanOutCapKey,
                $"the goal block field '{GoalBlockFields.FanOutCapKey}' is {cap}; a cap is a bound, and a negative bound is not one"));
        }

        if (block?.Budget is not { } budget)
        {
            errors.Add(Missing(GoalBlockFields.BudgetKey, "the request and token ceiling this run may not exceed"));
        }
        else if (budget.Requests <= 0 || budget.Tokens <= 0)
        {
            errors.Add(new GoalBlockError(
                GoalBlockFields.BudgetKey,
                $"the goal block field '{GoalBlockFields.BudgetKey}' allows {budget.Requests} requests and "
                + $"{budget.Tokens} tokens; a spawn that can do nothing is a typo, not a budget"));
        }

        return errors;
    }

    /// <summary>
    /// Decides whether this spawn may proceed, and returns what it is bound to.
    /// </summary>
    /// <remarks>
    /// <para><b>The order is the substance.</b> The terms-of-service prohibition is checked
    /// <i>first</i>, before the goal block and before any binding, so it cannot be masked by another
    /// error. If validation ran first, an operator would fix six fields and only then learn the
    /// spawn was never permitted — and a reader would have to prove the prohibition unreachable-by-
    /// accident rather than read it.</para>
    ///
    /// <para><b>The observed-auth gate fails closed.</b> A subscription-configured account with no
    /// observed status is refused, never assumed.</para>
    ///
    /// <para><b>The goal-block precondition is the write shape's</b> (Ruling 73). A
    /// <see cref="SpawnRequest.ReadOnly"/> request opens a lane that cannot write, so R2's "no
    /// block, no spawn" has nothing to protect there and is not applied; everything else — the
    /// order, the identity gates, the binding — is the same for both shapes.</para>
    ///
    /// <para><b>And the observed account is checked, when there is something to check it against.</b>
    /// The observed label is a display string the adapter chooses ("Claude Max"); the configured
    /// label is an operator's own name for a login ("max-personal"). Neither determines the other, so
    /// the correspondence is <i>declared</i> — <see cref="ProviderAccount.ObservedAuthLabel"/> — and
    /// enforced only where it was declared. Where it was not, the check is the auth <i>kind</i>
    /// alone, which is "not recorded" rather than a guessed mapping (IO12). What the declared form
    /// buys is real: an operator with two subscription logins who switches the local CLI between them
    /// gets a refusal instead of a lane that bills and ranks against the wrong account.</para>
    /// </remarks>
    /// <exception cref="AgentPlaneException">
    /// <see cref="AgentPlaneErrorCodes.DirectApiRefusedByToS"/>,
    /// <see cref="AgentPlaneErrorCodes.GoalBlockIncomplete"/>,
    /// <see cref="AgentPlaneErrorCodes.ObservedAuthNotRecorded"/>,
    /// <see cref="AgentPlaneErrorCodes.ObservedAuthNotSubscription"/>, or any refusal
    /// <see cref="ProviderRegistry.Bind"/> raises.
    /// </exception>
    public static Spawn Authorize(SpawnRequest request, ProviderRegistry registry)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(registry);

        RefuseDirectApiUnderASubscription(request.EngineId, registry);

        if (!request.ReadOnly)
        {
            RequireGoalBlock(request.Goal);
        }

        var bound = BindObserved(request.EngineId, request.Model, request.AccountLabel, request.ObservedAuth, registry);

        return new Spawn(request.Goal, bound.Binding, bound.ObservedAuth);
    }

    /// <summary>
    /// The <b>identity half</b> of <see cref="Authorize"/> — the terms-of-service refusal, the
    /// binding, the observed-subscription gate and the label match — with no goal-block
    /// precondition (ADR-0035 rule 1).
    /// </summary>
    /// <remarks>
    /// <para><b>For the compile call, which exists to fill the goal block</b> (§A9 R0/R1). A compile
    /// cannot take <see cref="Authorize"/> as written: it refuses a block missing <c>goal</c> /
    /// <c>done_when</c>, and the placeholder block an implementer would reach for is a spoofed
    /// precondition on the auth gate. So the identity gate is one function both entry points call —
    /// the same <c>AP-0009</c>–<c>AP-0013</c> refusals, by construction rather than by copy — and a
    /// compile can never bill an API key while a subscription is configured.</para>
    ///
    /// <para><b><see cref="Authorize"/>'s order is unchanged</b> (US-D12): it still checks the terms
    /// first, the goal block second and the binding last; this method is the terms check plus the
    /// binding, and nothing in between.</para>
    /// </remarks>
    /// <exception cref="AgentPlaneException">
    /// <see cref="AgentPlaneErrorCodes.DirectApiRefusedByToS"/>,
    /// <see cref="AgentPlaneErrorCodes.ObservedAuthNotRecorded"/>,
    /// <see cref="AgentPlaneErrorCodes.ObservedAuthNotSubscription"/>,
    /// <see cref="AgentPlaneErrorCodes.ObservedAuthAccountMismatch"/>, or any refusal
    /// <see cref="ProviderRegistry.Bind"/> raises.
    /// </exception>
    public static BoundIdentity AuthorizeBinding(
        string engineId, string model, string accountLabel, ObservedAuthStatus? observed, ProviderRegistry registry)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(engineId);
        ArgumentNullException.ThrowIfNull(registry);

        RefuseDirectApiUnderASubscription(engineId, registry);
        return BindObserved(engineId, model, accountLabel, observed, registry);
    }

    /// <summary>
    /// §4.2's terms-of-service prohibition, checked <i>first</i> from both entry points so it cannot
    /// be masked by another error.
    /// </summary>
    private static void RefuseDirectApiUnderASubscription(string engineId, ProviderRegistry registry)
    {
        if (string.Equals(engineId, ProviderRegistry.DirectApiEngineId, StringComparison.Ordinal)
            && registry.HasSubscriptionAccount(ProviderRegistry.AnthropicProviderId))
        {
            throw new AgentPlaneException(
                AgentPlaneErrorCodes.DirectApiRefusedByToS,
                "refused by Anthropic's terms of service: a subscription account is configured, and the "
                + "terms forbid third-party tools from using a Pro/Max subscription, so every "
                + "Anthropic-bound request must originate inside a Claude Code process. Spawn the "
                + "'claude-code' engine instead; there is no direct-api entry while the subscription stands");
        }
    }

    /// <summary>The binding and the observed-auth gate — the tail both entry points share.</summary>
    private static BoundIdentity BindObserved(
        string engineId, string model, string accountLabel, ObservedAuthStatus? observedAuth, ProviderRegistry registry)
    {
        var binding = registry.Bind(engineId, model, accountLabel);

        if (binding.Provider.Auth != ProviderAuth.Subscription)
        {
            // An API-key provider has nothing for the observed-subscription gate to check. It is
            // disabled by default and reaches here only where an operator turned it on deliberately.
            return new BoundIdentity(binding, observedAuth ?? new ObservedAuthStatus("apiKey", null, null));
        }

        if (observedAuth is not { } observed)
        {
            throw new AgentPlaneException(
                AgentPlaneErrorCodes.ObservedAuthNotRecorded,
                $"the adapter's auth status for account '{binding.Account.Label}' is not recorded, so where "
                + "this lane would bill is unknown; the spawn is refused rather than assumed to be on the "
                + "subscription, because an environment API key outranks it inside the adapter and bills silently");
        }

        if (!observed.IsSubscription)
        {
            throw new AgentPlaneException(
                AgentPlaneErrorCodes.ObservedAuthNotSubscription,
                $"account '{binding.Account.Label}' is configured as a subscription, but the adapter reports "
                + $"auth kind '{observed.Kind}'; an API key or an unauthenticated adapter bills somewhere the "
                + "subscription does not, so the spawn is refused");
        }

        if (binding.Account.ObservedAuthLabel is { } recorded
            && !string.Equals(recorded, observed.Label, StringComparison.Ordinal))
        {
            throw new AgentPlaneException(
                AgentPlaneErrorCodes.ObservedAuthAccountMismatch,
                $"account '{binding.Account.Label}' was recorded as the one the adapter calls '{recorded}', but "
                + $"the adapter reports '{observed.Label ?? "not recorded"}'; the engine is logged into a "
                + "different account than the lane was bound to, and the work would bill and rank against that one");
        }

        return new BoundIdentity(binding, observed);
    }

    /// <summary>Throws a single refusal naming every field the block is missing.</summary>
    private static void RequireGoalBlock(GoalBlock? block)
    {
        var errors = Validate(block);
        if (errors.Count == 0)
        {
            return;
        }

        throw new AgentPlaneException(
            AgentPlaneErrorCodes.GoalBlockIncomplete,
            "the goal block is not a spawn precondition yet — "
            + string.Join("; ", errors.Select(e => e.Message)));
    }

    private static void Text(List<GoalBlockError> errors, string field, string? value, string what)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            errors.Add(Missing(field, what));
        }
    }

    private static GoalBlockError Missing(string field, string what)
        => new(field, $"the goal block field '{field}' is required: it states {what}");
}
