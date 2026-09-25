using AiDe.Core.PromptCompilation;

namespace AiDe.Core.Sessions;

/// <summary>Why a compile mode is not selectable: a stable code and the reason in voice.</summary>
public sealed record CompileModeRefusal(string Code, string Reason);

/// <summary>
/// Which of the three compile modes this machine may select right now, and why not for the rest —
/// the settings model's reading of the deployment gates (ADR-0036 rule 1; US-D11).
/// </summary>
/// <param name="Refusals">One entry per mode that is not selectable.</param>
/// <param name="Recount">The recount over the frame log, when one could be read.</param>
/// <param name="ArtifactPath">Where the gate-1 artifact was looked for.</param>
public sealed record CompileModeAvailability(
    IReadOnlyDictionary<string, CompileModeRefusal> Refusals,
    FrameRecount? Recount,
    string ArtifactPath)
{
    /// <summary>Whether <paramref name="mode"/> may be selected. An unknown word is never selectable.</summary>
    public bool IsSelectable(string mode) =>
        CompileModeGate.Modes.Contains(mode, StringComparer.Ordinal) && !Refusals.ContainsKey(mode);

    /// <summary>The refusal for <paramref name="mode"/>, or null when it is selectable.</summary>
    public CompileModeRefusal? RefusalFor(string mode) => Refusals.TryGetValue(mode, out var refusal) ? refusal : null;
}

/// <summary>
/// The compile-mode ladder as deployment gates the product evaluates (ADR-0036 rule 1; Ruling 68):
/// <c>mechanical-only</c> always; <c>agentic-advisory</c> only when the pin-spike artifact exists,
/// its recorded triple equals the <b>installed</b> triple, and a recount of tool-call frames over
/// the frame log it names reads zero; <c>agentic</c> only after Gate 2's admission report — whose
/// reader is CV-4's — so it is refused here naming Gate 2.
/// </summary>
/// <remarks>
/// <para><b>Presence alone is spoofable (Ruling 68), so nothing here trusts a field the artifact
/// wrote about itself.</b> The triple is recomputed from the install root's bytes and compared;
/// the frame log's sha is recomputed and compared; the count is recounted. What this does not
/// close, recorded: an artifact <i>and</i> frame log fabricated together by the machine's own user
/// (ADR-0036 accepts it for the operator's own machine — the recount raises the forgery's cost from
/// one field to a consistent frame log).</para>
///
/// <para><b>Evaluated at every read, stored nowhere</b> — a demotion is computed, never remembered
/// (the drift detector's watermark is Gate 2's, CV-4).</para>
/// </remarks>
public static class CompileModeGate
{
    /// <summary>The three modes, in ladder order.</summary>
    public static readonly IReadOnlyList<string> Modes = [CompileModes.MechanicalOnly, CompileModes.AgenticAdvisory, CompileModes.Agentic];

    /// <summary>Evaluates the gates against the artifacts under <see cref="CompilePinArtifact.DefaultDirectory"/>.</summary>
    public static CompileModeAvailability Evaluate(string adapterInstallRoot) =>
        Evaluate(adapterInstallRoot, CompilePinArtifact.DefaultDirectory);

    /// <summary>Evaluates the gates against the artifacts under <paramref name="proofDirectory"/>.</summary>
    public static CompileModeAvailability Evaluate(string adapterInstallRoot, string proofDirectory)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(adapterInstallRoot);
        ArgumentException.ThrowIfNullOrWhiteSpace(proofDirectory);

        var artifactPath = Path.Combine(proofDirectory, CompilePinArtifact.FileName);
        var refusals = new Dictionary<string, CompileModeRefusal>(StringComparer.Ordinal);
        FrameRecount? recount = null;

        var gateOne = GateOne(adapterInstallRoot, artifactPath, out recount);
        if (gateOne is { } refused)
        {
            refusals[CompileModes.AgenticAdvisory] = refused;
            refusals[CompileModes.Agentic] = refused;
        }
        else
        {
            // Gate 2 (ADR-0036): the admission report over 50 scored + 50 holdout envelopes, its
            // floors recomputed from the report's own numerator/denominator pairs — never a
            // verdict field. `agentic` is refused by name until CompileAdmissionGate admits it.
            if (CompileAdmissionGate.Evaluate(proofDirectory) is { } gateTwoRefusal)
            {
                refusals[CompileModes.Agentic] = gateTwoRefusal;
            }
        }

        return new CompileModeAvailability(refusals, recount, artifactPath);
    }

    /// <summary>The pin's identity: the sent <c>_meta</c> as canonical JSON with the per-session <c>model</c> removed.</summary>
    private static string? PinIdentity(System.Text.Json.Nodes.JsonObject? meta)
    {
        if (meta is null)
        {
            return null;
        }

        var clone = meta.DeepClone().AsObject();
        if (clone["claudeCode"]?["options"] is System.Text.Json.Nodes.JsonObject options)
        {
            options.Remove("model");
        }

        return clone.ToJsonString();
    }

    /// <summary>Gate 1: the pin artifact, a staleness gate. Null when it admits.</summary>
    private static CompileModeRefusal? GateOne(string adapterInstallRoot, string artifactPath, out FrameRecount? recount)
    {
        recount = null;

        var artifact = CompilePinArtifact.Read(artifactPath, out var problem);
        if (artifact is null)
        {
            return new CompileModeRefusal(
                EnvelopeStoreErrorCodes.PinArtifactMissing,
                $"the compile-pin-spike artifact was not found at {artifactPath}" + (problem is null ? string.Empty : $" ({problem})")
                + "; run spikes/compile-session-pin-wire/Run-PinSpike.ps1 (PD-5) — a failed spike is a hard stop, never a fallback (Ruling 68)");
        }

        // THE RUN ENDED (PD-5's second run: an aborted summary with a zero count and a valid frame
        // log would otherwise admit): only a full run with every prompt answered is a measurement.
        if (!string.Equals(artifact.Mode, "full", StringComparison.Ordinal) || artifact.PromptsUnanswered > 0)
        {
            return new CompileModeRefusal(
                EnvelopeStoreErrorCodes.PinRunNotEnded,
                $"the compile-pin-spike artifact records a run that did not end (mode {artifact.Mode ?? Envelope.NotRecorded}, {artifact.PromptsUnanswered} prompt(s) without a result); an aborted or timed-out spike admits nothing — re-run PD-5 to completion");
        }

        // THE PIN THAT WAS MEASURED IS THE PIN THIS BUILD SENDS: a pin widened since the run (a new
        // denied name, strictMcpConfig) re-runs PD-5 by construction. The model is per session and
        // is not part of the pin's identity.
        var expected = PinIdentity(AgentPlane.LaneSessionOptions.Compile.ToMeta());
        var recorded = PinIdentity(artifact.SentMeta);
        if (!string.Equals(expected, recorded, StringComparison.Ordinal))
        {
            return new CompileModeRefusal(
                EnvelopeStoreErrorCodes.PinIdentityMismatch,
                $"the compile-pin-spike artifact measured another pin than this build sends: recorded {recorded ?? Envelope.NotRecorded}; this build sends {expected}; re-run PD-5 under the current pin");
        }

        var installed = CompilePin.Installed(adapterInstallRoot);
        if (CompilePin.Mismatch(installed, artifact.Triple) is { } mismatch)
        {
            return new CompileModeRefusal(
                EnvelopeStoreErrorCodes.PinTripleMismatch,
                $"the compile-pin-spike artifact was recorded against another adapter/SDK/CLI build than the one installed under {adapterInstallRoot}: {mismatch}; re-run PD-5 on this build");
        }

        var frameLogPath = Path.Combine(Path.GetDirectoryName(artifactPath)!, CompilePinArtifact.FrameLogFileName);
        if (artifact.FrameLogSha256 is null || !File.Exists(frameLogPath))
        {
            return new CompileModeRefusal(
                EnvelopeStoreErrorCodes.PinFrameLogUnverifiable,
                $"the compile-pin-spike artifact's tool_call count cannot be recounted: {(artifact.FrameLogSha256 is null ? "the artifact names no frame log" : $"the frame log {frameLogPath} is missing")}; the count is never trusted as written");
        }

        var bytes = File.ReadAllBytes(frameLogPath);
        var sha = Convert.ToHexStringLower(System.Security.Cryptography.SHA256.HashData(bytes));
        if (!string.Equals(sha, artifact.FrameLogSha256, StringComparison.Ordinal))
        {
            return new CompileModeRefusal(
                EnvelopeStoreErrorCodes.PinFrameLogUnverifiable,
                $"the frame log {frameLogPath} does not hash to the sha the compile-pin-spike artifact recorded; the recount would be over other frames");
        }

        recount = CompilePin.Recount(bytes);
        if (recount.ToolCalls != 0)
        {
            return new CompileModeRefusal(
                EnvelopeStoreErrorCodes.PinRecountNotZero,
                $"the recount over the compile-pin-spike frame log reads {recount.ToolCalls} tool_call frame(s) ({string.Join(", ", recount.ToolNames)}) where the artifact claims {artifact.RecordedToolCalls?.ToString(System.Globalization.CultureInfo.InvariantCulture) ?? Envelope.NotRecorded}; the pin did not hold");
        }

        return null;
    }
}
