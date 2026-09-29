using AiDe.Core.Ipc;

namespace AiDe.Core.Tests;

/// <summary>
/// `P2-SEC-*` — the first cross-process trust boundary in the product, attacked.
/// </summary>
/// <remarks>
/// <para>Phase 1 had no boundary here: the shell called the core directly, so
/// <c>CallerPrincipal</c> was simply true. Phase 2 makes it a claim arriving over a pipe, and every
/// test below is a misuse case for a control the design named — not a happy path with a negative
/// assertion bolted on.</para>
///
/// <para>Each case states what an attacker gets if the control is absent, because a security test
/// whose failure mode is unstated tends to be "fixed" by loosening the assertion.</para>
/// </remarks>
public sealed class IpcBoundaryTests
{
    private const string Workspace = "ws-1";
    private const long Epoch = 42;

    private static (DaemonEndpoint Endpoint, CapabilityRegistry Registry) Daemon(long epoch = Epoch)
    {
        var registry = new CapabilityRegistry();
        var endpoint = new DaemonEndpoint(Workspace, registry, _ => epoch);
        endpoint.Register("describe", (_, _) => IpcResponse.Success(IpcPayloadTestExtensions.Json("described")));
        return (endpoint, registry);
    }

    /// <summary>The capability from a handshake response.</summary>
    /// <remarks>
    /// The handshake returns <see cref="IpcOpenResult"/> rather than a bare token, because the epoch
    /// has to travel with it: a freshly connected shell cannot ask for the epoch, since asking is a
    /// command and every command is judged against the epoch it claims.
    /// </remarks>
    private static string? Capability(IpcResponse response) =>
        response.Payload is null
            ? null
            : response.Payload.As<IpcOpenResult>()!.Capability;

    private static IpcPeer Peer(int processId = 1234, string connection = "conn-a") =>
        new("S-1-5-21-owner", processId, connection);

    private static IpcRequest Request(
        string? capability,
        int version = IpcVersion.Current,
        string workspace = Workspace,
        long epoch = Epoch,
        string operation = "describe",
        string commandId = "cmd-1") =>
        new(version, operation, commandId, workspace, epoch, capability, null);

    // ---- handshake ---------------------------------------------------------

    [Fact]
    public void OpenWorkspace_WithACurrentVersion_IssuesACapability()
    {
        var (endpoint, registry) = Daemon();

        var response = endpoint.OpenWorkspace(Request(null), Peer());

        Assert.True(response.Ok);
        Assert.False(string.IsNullOrWhiteSpace(Capability(response)));
        Assert.Equal(1, registry.Count);
    }

    [Fact]
    public void OpenWorkspace_WithThePreviousMajor_IsStillAccepted()
    {
        var (endpoint, _) = Daemon();

        var response = endpoint.OpenWorkspace(Request(null, version: IpcVersion.Previous), Peer());

        // Without this, every upgrade becomes a synchronised restart of shell and daemon — which is
        // exactly what the rollback path cannot depend on.
        Assert.True(response.Ok);
    }

    [Fact]
    public void OpenWorkspace_WithAnUnsupportedMajor_IsRejectedAndNeverNegotiatedDown()
    {
        var (endpoint, registry) = Daemon();

        var response = endpoint.OpenWorkspace(Request(null, version: 99), Peer());

        Assert.False(response.Ok);
        Assert.Equal(IpcErrorCodes.UnsupportedVersion, response.ErrorCode);
        // The reply says what this build DOES speak, so the bootstrap can decide rather than guess.
        Assert.Equal(IpcVersion.Supported, response.SupportedVersions);
        // Absent this, a peer speaking an unknown protocol would hold authority on the daemon.
        Assert.Equal(0, registry.Count);
    }

    [Fact]
    public void OpenWorkspace_ForAnotherWorkspace_IsRejectedBeforeAnyCapabilityExists()
    {
        var (endpoint, registry) = Daemon();

        var response = endpoint.OpenWorkspace(Request(null, workspace: "ws-other"), Peer());

        Assert.False(response.Ok);
        Assert.Equal(IpcErrorCodes.WorkspaceMismatch, response.ErrorCode);
        Assert.Equal(0, registry.Count);
    }

    // ---- capability binding ------------------------------------------------

    [Fact]
    public void Invoke_WithTheIssuedCapability_Succeeds()
    {
        var (endpoint, _) = Daemon();
        var peer = Peer();
        var token = Capability(endpoint.OpenWorkspace(Request(null), peer));

        var response = endpoint.Invoke(Request(token), peer);

        Assert.True(response.Ok);
        Assert.Equal("described", response.Payload.AsText());
    }

    [Fact]
    public void Invoke_WithNoCapability_IsDenied()
    {
        var (endpoint, _) = Daemon();

        var response = endpoint.Invoke(Request(null), Peer());

        Assert.False(response.Ok);
        Assert.Equal(IpcErrorCodes.NotAuthorized, response.ErrorCode);
    }

    [Fact]
    public void Invoke_WithAForgedCapability_IsDenied()
    {
        var (endpoint, _) = Daemon();
        var peer = Peer();
        endpoint.OpenWorkspace(Request(null), peer);

        // A well-formed token of the right shape that this daemon never issued.
        var response = endpoint.Invoke(Request("Zm9yZ2VkLXRva2VuLXdpdGgtdGhlLXJpZ2h0LXNoYXBl"), peer);

        Assert.False(response.Ok);
        Assert.Equal(IpcErrorCodes.CapabilityUnknown, response.ErrorCode);
    }

    [Fact]
    public void Invoke_ReplayingACapabilityOnAnotherConnection_IsDenied()
    {
        var (endpoint, _) = Daemon();
        var original = Peer(connection: "conn-a");
        var token = Capability(endpoint.OpenWorkspace(Request(null), original));

        var thief = Peer(connection: "conn-b");
        var response = endpoint.Invoke(Request(token), thief);

        // Without the connection binding the token is a bearer secret: anyone who observes it owns
        // the workspace for as long as the daemon lives.
        Assert.False(response.Ok);
        Assert.Equal(IpcErrorCodes.CapabilityWrongConnection, response.ErrorCode);
    }

    [Fact]
    public void Invoke_FromADifferentProcessOnTheSameConnection_IsDenied()
    {
        var (endpoint, _) = Daemon();
        var original = Peer(processId: 1234);
        var token = Capability(endpoint.OpenWorkspace(Request(null), original));

        var impostor = Peer(processId: 5678);
        var response = endpoint.Invoke(Request(token), impostor);

        Assert.False(response.Ok);
        Assert.Equal(IpcErrorCodes.CapabilityWrongProcess, response.ErrorCode);
    }

    [Fact]
    public void Invoke_NamingAnotherWorkspace_IsDeniedEvenWithAValidCapability()
    {
        var (endpoint, _) = Daemon();
        var peer = Peer();
        var token = Capability(endpoint.OpenWorkspace(Request(null), peer));

        var response = endpoint.Invoke(Request(token, workspace: "ws-other"), peer);

        Assert.False(response.Ok);
        Assert.Equal(IpcErrorCodes.WorkspaceMismatch, response.ErrorCode);
    }

    // ---- revocation --------------------------------------------------------

    [Fact]
    public void Invoke_AfterTheCapabilityIsRevoked_IsDenied()
    {
        var (endpoint, registry) = Daemon();
        var peer = Peer();
        var token = Capability(endpoint.OpenWorkspace(Request(null), peer))!;

        Assert.True(registry.Revoke(token));

        var response = endpoint.Invoke(Request(token), peer);
        Assert.False(response.Ok);
        Assert.Equal(IpcErrorCodes.CapabilityUnknown, response.ErrorCode);
    }

    [Fact]
    public void RevokingAConnection_RevokesEveryCapabilityItHolds()
    {
        var (endpoint, registry) = Daemon();
        var peer = Peer(connection: "conn-a");
        endpoint.OpenWorkspace(Request(null), peer);
        endpoint.OpenWorkspace(Request(null), peer);
        endpoint.OpenWorkspace(Request(null), Peer(processId: 999, connection: "conn-b"));

        var revoked = registry.RevokeConnection("conn-a");

        // A disconnect must not leave authority behind for a reconnecting process to inherit.
        Assert.Equal(2, revoked);
        Assert.Equal(1, registry.Count);
    }

    [Fact]
    public void Revoke_IsIdempotent()
    {
        var (endpoint, registry) = Daemon();
        var token = Capability(endpoint.OpenWorkspace(Request(null), Peer()))!;

        Assert.True(registry.Revoke(token));
        Assert.False(registry.Revoke(token));
    }

    // ---- epoch fence -------------------------------------------------------

    [Fact]
    public void Invoke_WithAStaleEpochInTheCommand_IsDenied()
    {
        var (endpoint, _) = Daemon();
        var peer = Peer();
        var token = Capability(endpoint.OpenWorkspace(Request(null), peer));

        var response = endpoint.Invoke(Request(token, epoch: Epoch - 1), peer);

        // The command was authored against state that has since been replaced. Running it would
        // apply an intention formed about a workspace that no longer exists.
        Assert.False(response.Ok);
        Assert.Equal(IpcErrorCodes.EpochStale, response.ErrorCode);
    }

    [Fact]
    public void Invoke_WithACapabilityFromABeforeTheEpochAdvanced_IsDenied()
    {
        var registry = new CapabilityRegistry();
        var epoch = Epoch;
        var endpoint = new DaemonEndpoint(Workspace, registry, _ => epoch);
        endpoint.Register("describe", (_, _) => IpcResponse.Success(IpcPayloadTestExtensions.Json("described")));

        var peer = Peer();
        var token = Capability(endpoint.OpenWorkspace(Request(null), peer));

        epoch++;   // the core restarted underneath the holder

        var response = endpoint.Invoke(Request(token, epoch: epoch), peer);

        Assert.False(response.Ok);
        Assert.Equal(IpcErrorCodes.EpochStale, response.ErrorCode);
    }

    // ---- envelope ----------------------------------------------------------

    [Theory]
    [InlineData("", "cmd-1")]
    [InlineData("describe", "")]
    [InlineData("   ", "cmd-1")]
    public void Invoke_WithAMalformedEnvelope_IsDenied(string operation, string commandId)
    {
        var (endpoint, _) = Daemon();
        var peer = Peer();
        var token = Capability(endpoint.OpenWorkspace(Request(null), peer));

        var response = endpoint.Invoke(
            Request(token, operation: operation, commandId: commandId), peer);

        Assert.False(response.Ok);
        Assert.Equal(IpcErrorCodes.MalformedEnvelope, response.ErrorCode);
    }

    [Fact]
    public void Invoke_WithAnUnknownOperation_IsDeniedRatherThanGuessedAt()
    {
        var (endpoint, _) = Daemon();
        var peer = Peer();
        var token = Capability(endpoint.OpenWorkspace(Request(null), peer));

        var response = endpoint.Invoke(Request(token, operation: "drop-everything"), peer);

        Assert.False(response.Ok);
        Assert.Equal(IpcErrorCodes.MalformedEnvelope, response.ErrorCode);
    }

    // ---- ordering ----------------------------------------------------------

    [Fact]
    public void VersionIsCheckedBeforeAuthorization()
    {
        var (endpoint, _) = Daemon();

        var response = endpoint.Invoke(Request(capability: null, version: 99), Peer());

        // Not NotAuthorized: a peer we cannot understand is turned away before we reason about its
        // authority at all.
        Assert.Equal(IpcErrorCodes.UnsupportedVersion, response.ErrorCode);
    }

    [Fact]
    public void WorkspaceIsCheckedBeforeTheCapability()
    {
        var (endpoint, _) = Daemon();

        var response = endpoint.Invoke(
            Request("some-token-we-never-issued", workspace: "ws-other"), Peer());

        // Validating the capability first would tell an unauthorized caller whether a token is live
        // on a workspace it has no business naming.
        Assert.Equal(IpcErrorCodes.WorkspaceMismatch, response.ErrorCode);
    }

    // ---- the registry on its own ------------------------------------------
    //
    // These exist because MUTATION TESTING found a gap the endpoint tests hid. Disabling the
    // registry's workspace binding failed nothing: `DaemonEndpoint.Invoke` checks the workspace
    // before it validates a capability, so the registry's own check was never what rejected.
    //
    // The registry is the component that decides what a capability means, and it is defence in
    // depth behind the endpoint — but an untested control is not a control, and its documentation
    // claims four bindings. So each is asserted here at its own level, where the endpoint's earlier
    // gate cannot stand in for it.

    [Fact]
    public void Registry_RejectsACapabilityIssuedForAnotherWorkspace()
    {
        var registry = new CapabilityRegistry();
        var peer = Peer();
        var capability = registry.Issue(peer, "ws-issued-for", Epoch);

        var check = registry.Validate(capability.Token, peer, "ws-presented-to", Epoch);

        Assert.False(check.Ok);
        Assert.Equal(IpcErrorCodes.WorkspaceMismatch, check.ErrorCode);
    }

    [Fact]
    public void Registry_RejectsAWrongConnectionWrongProcessAndStaleEpoch_Independently()
    {
        var registry = new CapabilityRegistry();
        var peer = Peer(processId: 1234, connection: "conn-a");
        var token = registry.Issue(peer, Workspace, Epoch).Token;

        Assert.Equal(
            IpcErrorCodes.CapabilityWrongConnection,
            registry.Validate(token, Peer(1234, "conn-b"), Workspace, Epoch).ErrorCode);

        Assert.Equal(
            IpcErrorCodes.CapabilityWrongProcess,
            registry.Validate(token, Peer(5678, "conn-a"), Workspace, Epoch).ErrorCode);

        Assert.Equal(
            IpcErrorCodes.EpochStale,
            registry.Validate(token, peer, Workspace, Epoch + 1).ErrorCode);

        Assert.True(registry.Validate(token, peer, Workspace, Epoch).Ok);
    }

    [Fact]
    public void Registry_RejectsAnEmptyOrMissingToken()
    {
        var registry = new CapabilityRegistry();

        Assert.Equal(
            IpcErrorCodes.NotAuthorized,
            registry.Validate(null, Peer(), Workspace, Epoch).ErrorCode);
        Assert.Equal(
            IpcErrorCodes.NotAuthorized,
            registry.Validate(string.Empty, Peer(), Workspace, Epoch).ErrorCode);
    }

    [Fact]
    public void IssuedTokensAreUniqueAndNotGuessable()
    {
        var (endpoint, _) = Daemon();
        var peer = Peer();

        var tokens = Enumerable.Range(0, 64)
            .Select(_ => Capability(endpoint.OpenWorkspace(Request(null), peer))!)
            .ToList();

        Assert.Equal(64, tokens.Distinct(StringComparer.Ordinal).Count());
        Assert.All(tokens, t => Assert.True(t.Length >= 40, $"token too short to resist guessing: {t.Length}"));
    }
}
