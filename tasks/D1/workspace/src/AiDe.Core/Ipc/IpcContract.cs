using AiDe.Core.Facts;

namespace AiDe.Core.Ipc;

/// <summary>Stable, catalogued failure codes for the IPC boundary.</summary>
/// <remarks>
/// Stable strings rather than an enum's numbers because they cross a process boundary and appear in
/// operator-facing output. A renumbered enum silently changes what a log line means; a renamed
/// string breaks a test.
/// </remarks>
public static class IpcErrorCodes
{
    public const string UnsupportedVersion = "ipc.unsupported_version";
    public const string MalformedEnvelope = "ipc.malformed_envelope";
    public const string CapabilityUnknown = "ipc.capability_unknown";
    public const string CapabilityRevoked = "ipc.capability_revoked";
    public const string CapabilityWrongConnection = "ipc.capability_wrong_connection";
    public const string CapabilityWrongProcess = "ipc.capability_wrong_process";
    public const string WorkspaceMismatch = "ipc.workspace_mismatch";
    public const string EpochStale = "ipc.epoch_stale";
    public const string NotAuthorized = "ipc.not_authorized";

    /// <summary>Another daemon already serves this workspace.</summary>
    public const string WorkspaceLocked = "ipc.workspace_locked";

    /// <summary>
    /// The daemon went away without answering. A transport fact, deliberately NOT an authorization
    /// one: reporting a vanished daemon as "not authorized" sends every investigation to the wrong
    /// place, and it briefly did exactly that here.
    /// </summary>
    public const string TransportClosed = "ipc.transport_closed";

    /// <summary>
    /// The response is larger than one frame can carry.
    /// </summary>
    /// <remarks>
    /// INV-0003. Without this code an oversized response threw out of the write path, the serve loop
    /// did not catch that exception type, and the connection closed with no reply — which the client
    /// can only report as <see cref="TransportClosed"/>. "The daemon vanished" and "the answer is too
    /// big to send" need different things from a user, and rendering the second as the first sends
    /// them to look at the daemon.
    /// </remarks>
    public const string PayloadTooLarge = "ipc.payload_too_large";

    /// <summary>
    /// This daemon has no record of the command being asked about.
    /// </summary>
    /// <remarks>
    /// Distinct from a failure of the command itself: "I never started that, or no longer remember
    /// it" is information a caller acts on differently from "it ran and did not work".
    /// </remarks>
    public const string CommandUnknown = "ipc.command_unknown";
}

/// <summary>
/// Which IPC majors this build speaks.
/// </summary>
/// <remarks>
/// <para>Two majors, never one. During an upgrade a new shell may meet an old daemon or the reverse,
/// and a single-version boundary makes every upgrade a synchronised restart of both — which is
/// exactly what the rollback path cannot rely on.</para>
///
/// <para><b>Never negotiated down silently.</b> An unsupported version is rejected with
/// <see cref="IpcErrorCodes.UnsupportedVersion"/>. Silent downgrade is how a peer ends up speaking a
/// protocol neither side chose, and the failure appears far from its cause.</para>
/// </remarks>
public static class IpcVersion
{
    /// <remarks>
    /// <b>3 carries the payload as JSON, not as a string containing JSON.</b> Through 2 a payload was
    /// serialised and the resulting TEXT was placed in a string field, so the transport re-escaped
    /// every quote in it — MEASURED at 1.56-1.57x, which is how a 727,244-byte graph became 1,137,104
    /// bytes on the wire and was refused (DC-047). A peer speaking 2 is still understood, because
    /// <see cref="IpcPayload"/> reads either form.
    /// </remarks>
    public const int Current = 3;

    /// <summary>The one previous major still accepted, so an upgrade need not be simultaneous.</summary>
    public const int Previous = 2;

    public static bool IsSupported(int major) => major == Current || major == Previous;

    public static IReadOnlyList<int> Supported => [Current, Previous];
}

/// <summary>
/// Reading a payload, in either encoding a peer might have sent.
/// </summary>
/// <remarks>
/// <para>From version 3 a payload IS JSON: the envelope carries the value itself, so nothing is
/// escaped twice and the bytes measured are the bytes sent. Through version 2 the payload was a
/// string holding JSON text, which the envelope then re-escaped — the encoding that made a graph
/// inside its byte budget too large for the frame it was budgeted against (DC-047).</para>
///
/// <para><b>Read tolerantly, write one way.</b> A JSON string where a value is expected is a version-2
/// peer, and its text is parsed rather than rejected — that is what keeps <see cref="IpcVersion.Previous"/>
/// a real guarantee instead of a comment. Writing only ever produces the new form: two encodings on
/// the write side is how a wire format ends up with no single answer to "what does this look like".</para>
/// </remarks>
public static class IpcPayload
{
    /// <summary>The payload as <typeparamref name="T"/>, or default when there is none.</summary>
    /// <exception cref="System.Text.Json.JsonException">The payload is not valid JSON for T.</exception>
    public static T? Read<T>(System.Text.Json.JsonElement? payload, System.Text.Json.JsonSerializerOptions options)
    {
        if (payload is not { } element) return default;

        // A version-2 peer sent JSON *text*. Deserialising it as T would bind the string to T and
        // fail with a message about the type rather than about the version.
        if (element.ValueKind == System.Text.Json.JsonValueKind.String && typeof(T) != typeof(string))
        {
            var text = element.GetString();

            return string.IsNullOrEmpty(text)
                ? default
                : System.Text.Json.JsonSerializer.Deserialize<T>(text, options);
        }

        return System.Text.Json.JsonSerializer.Deserialize<T>(element, options);
    }

    /// <summary>A value as a payload. Always the current encoding.</summary>
    public static System.Text.Json.JsonElement From<T>(T value, System.Text.Json.JsonSerializerOptions options) =>
        System.Text.Json.JsonSerializer.SerializeToElement(value, options);
}

/// <summary>One request across the boundary.</summary>
/// <remarks>
/// <paramref name="CommandId"/> carries the architecture's idempotency semantics unchanged — the
/// same id is the same command, and a retry after an unknown outcome must return the existing
/// receipt rather than acting twice. Phase 1 simply had a shorter path to the same contract.
/// </remarks>
public sealed record IpcRequest(
    int Version,
    string Operation,
    string CommandId,
    string WorkspaceId,
    long WorkspaceEpoch,
    string? Capability,
    System.Text.Json.JsonElement? Payload);

/// <summary>One reply. Either <paramref name="Ok"/> with a payload, or an error code and reason.</summary>
public sealed record IpcResponse(
    bool Ok,
    System.Text.Json.JsonElement? Payload,
    string? ErrorCode,
    string? Reason,
    IReadOnlyList<int>? SupportedVersions = null)
{
    public static IpcResponse Success(System.Text.Json.JsonElement? payload = null) =>
        new(true, payload, null, null);

    /// <summary>The common case: a result object, carried as JSON rather than as text about JSON.</summary>
    public static IpcResponse Success<T>(T result, System.Text.Json.JsonSerializerOptions options) =>
        new(true, System.Text.Json.JsonSerializer.SerializeToElement(result, options), null, null);

    public static IpcResponse Error(string code, string reason) => new(false, null, code, reason);

    /// <summary>
    /// A version rejection, which uniquely carries what this build DOES speak.
    /// </summary>
    /// <remarks>
    /// Returning the supported set turns "we disagree" into something a peer can act on: the
    /// bootstrap can decide to upgrade, roll back, or stop. A bare rejection leaves it guessing, and
    /// guessing across a version boundary is how a downgrade loop starts.
    /// </remarks>
    public static IpcResponse UnsupportedVersion(int requested) => new(
        false, null, IpcErrorCodes.UnsupportedVersion,
        $"IPC major {requested} is not supported by this build", IpcVersion.Supported);
}

/// <summary>What a successful handshake returns.</summary>
/// <remarks>
/// <para><b>The epoch is here because there is nowhere else it can come from.</b> Every command
/// states the epoch it was authored against and the daemon rejects a mismatch — which leaves a shell
/// that has just connected unable to ask for the epoch, because asking is itself a command subject
/// to the fence. Returning it from the handshake is the only ordering that terminates.</para>
///
/// <para>The alternative — exempting an <c>epoch</c> operation from the fence — would put a hole in
/// the check to work around an ordering problem, and holes in fences are how the next thing gets
/// exempted too.</para>
/// </remarks>
public sealed record IpcOpenResult(string Capability, long Epoch);

/// <summary>Who is on the other end of a connection, as established by the transport.</summary>
/// <remarks>
/// Built by the transport from the authenticated connection, never from anything the caller sends.
/// A peer that could name its own identity could name someone else's, which is the whole point of
/// binding a capability to the connection rather than to a claim.
/// </remarks>
public sealed record IpcPeer(string OwnerSid, int ProcessId, string ConnectionId)
{
    public CallerPrincipal ToPrincipal() => new($"shell:{ProcessId}", CallerKind.Shell);
}
