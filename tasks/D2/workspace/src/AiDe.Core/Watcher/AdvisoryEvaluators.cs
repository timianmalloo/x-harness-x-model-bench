namespace AiDe.Core.Watcher;

/// <summary>
/// A presence-only check that a credential exists for a would-egress evaluator (ADR-0024 credential-backed-grading-egress). It never
/// exposes the secret itself - the watcher store holds non-secret facts only (architecture §4), so the
/// gate authorises on <b>presence</b>, and the secret is resolved elsewhere, at the call, by the
/// credential-backed transport. Absent by default.
/// </summary>
public interface IAdvisoryCredentialSource
{
    /// <summary>Whether a credential is available to authorise the egressing evaluator's call.</summary>
    bool HasCredential { get; }
}

/// <summary>A credential source that never has a credential - the safe default (local-only operation).</summary>
public sealed class NoCredential : IAdvisoryCredentialSource
{
    public bool HasCredential => false;
}

/// <summary>
/// The deterministic, <b>local-only</b> advisory evaluator - the safe default that lets the advisory
/// dimensions (Evidence discipline, Solution economy) be judged without any model call, credential, or
/// egress. It grounds only on the quarantined evidence string the caller composes from deterministic
/// signals (a token list like <c>"verification=executed; coverage=9/10; actions_after_done=0;
/// premature=false; reuse=high"</c>) and maps it to a 0-4 rubric by fixed rules - never a guess: an
/// absent token scores conservatively (low), never optimistically.
/// </summary>
/// <remarks>
/// <para>Because it is deterministic, its <see cref="EvaluatorStability"/> trivially passes (every repeat
/// is identical), but it still only folds into Weave points after the ADR-0019 advisory-evaluator-calibration calibration gates qualify
/// its <c>(version, taskClass, schemaVersion)</c> in the registry (slice 7) - the local heuristic is a
/// transparent proxy an operator can inspect, not a licence to score advisory dimensions unbounded.</para>
/// <para>It judges ONLY the two advisory dimensions; asked for any other it throws, because a deterministic
/// dimension is the deterministic scorer's job, never an evaluator's (spec rule 8).</para>
/// </remarks>
public sealed class LocalHeuristicAdvisoryEvaluator : IAdvisoryEvaluator
{
    public string EvaluatorVersion => "local-heuristic/1";

    public AdvisoryAssessment Evaluate(ScoreDimension dimension, WorkEpisode episode, string evidence)
    {
        ArgumentNullException.ThrowIfNull(episode);
        ArgumentNullException.ThrowIfNull(evidence);

        var tokens = EvidenceTokens.Parse(evidence);

        var (rubric, rationale) = dimension switch
        {
            ScoreDimension.EvidenceDiscipline => ScoreEvidenceDiscipline(tokens),
            ScoreDimension.SolutionEconomy => ScoreSolutionEconomy(tokens),
            _ => throw new WatcherException(
                WatcherErrorCodes.InvalidBinding,
                $"'{dimension}' is not an advisory dimension; the deterministic scorer owns it (rule 8)."),
        };

        return new AdvisoryAssessment(dimension, rubric, rationale, EvidencePointer: "local:signals", EvaluatorVersion);
    }

    /// <summary>Evidence discipline: were claims grounded in executed verification and real coverage?</summary>
    private static (int Rubric, string Rationale) ScoreEvidenceDiscipline(EvidenceTokens t)
    {
        var verification = t.Bool("verification") ? 2 : 0;      // executed vs not (absent => 0, conservative)
        var coverage = t.Ratio("coverage") switch
        {
            >= 0.9 => 2,
            >= 0.5 => 1,
            _ => 0,
        };
        var rubric = Math.Clamp(verification + coverage, 0, 4);
        return (rubric, $"verification={(verification > 0 ? "executed" : "absent")}, coverage band {coverage}/2");
    }

    /// <summary>Solution economy: was the solution lean - no wasted actions after the done condition?</summary>
    private static (int Rubric, string Rationale) ScoreSolutionEconomy(EvidenceTokens t)
    {
        var afterDone = t.Int("actions_after_done") switch
        {
            0 => 2,
            <= 2 => 1,
            _ => 0,
        };
        var notPremature = t.Bool("premature") ? 0 : 1;         // premature completion is a penalty
        var reuse = string.Equals(t.Text("reuse"), "high", StringComparison.OrdinalIgnoreCase) ? 1 : 0;
        var rubric = Math.Clamp(afterDone + notPremature + reuse, 0, 4);
        return (rubric, $"actions-after-done band {afterDone}/2, premature={(notPremature == 0 ? "yes" : "no")}, reuse={t.Text("reuse") ?? "n/a"}");
    }
}

/// <summary>
/// The <b>egress + credential guard</b> (ADR-0024 credential-backed-grading-egress) around any advisory evaluator that would call out to a
/// model over the network. Before delegating it enforces, in order: the <see cref="EgressGate"/> has an
/// explicit per-path opt-in for this evaluator's path (else <see cref="WatcherErrorCodes.EgressDenied"/>,
/// LK-0003 - default-deny), and a credential is present (else <see cref="WatcherErrorCodes.InvalidBinding"/>,
/// LK-0002). Only then does the inner evaluator run. This is the boundary a real cloud judge sits behind;
/// the <see cref="LocalHeuristicAdvisoryEvaluator"/> needs no guard because it never egresses.
/// </summary>
public sealed class EgressGuardedAdvisoryEvaluator(
    IAdvisoryEvaluator inner, EgressGate gate, string egressPathId, IAdvisoryCredentialSource credentials)
    : IAdvisoryEvaluator
{
    private readonly IAdvisoryEvaluator _inner = inner ?? throw new ArgumentNullException(nameof(inner));
    private readonly EgressGate _gate = gate ?? throw new ArgumentNullException(nameof(gate));
    private readonly IAdvisoryCredentialSource _credentials = credentials ?? throw new ArgumentNullException(nameof(credentials));
    private readonly string _egressPathId = !string.IsNullOrEmpty(egressPathId)
        ? egressPathId
        : throw new ArgumentException("An egress path id is required.", nameof(egressPathId));

    public string EvaluatorVersion => _inner.EvaluatorVersion;

    public AdvisoryAssessment Evaluate(ScoreDimension dimension, WorkEpisode episode, string evidence)
    {
        // Egress first: the network boundary is default-deny (ADR-0024 credential-backed-grading-egress). A blocked path never reaches the
        // credential check, so a missing opt-in cannot be masked by a present credential.
        if (_gate.Decide(_egressPathId) != EgressDecision.Allowed)
        {
            throw new WatcherException(
                WatcherErrorCodes.EgressDenied,
                $"Advisory egress path '{_egressPathId}' is not opted in; the model judge cannot run (LK-0003).");
        }

        if (!_credentials.HasCredential)
        {
            throw new WatcherException(
                WatcherErrorCodes.InvalidBinding,
                $"No credential is available to authorise the advisory model judge on '{_egressPathId}' (LK-0002).");
        }

        return _inner.Evaluate(dimension, episode, evidence);
    }
}

/// <summary>
/// A tiny deterministic parser for the quarantined evidence token list the local evaluator grounds on.
/// Tokens are <c>key=value</c> separated by <c>;</c>. An absent or malformed token yields a conservative
/// default (false / 0 / null), never a guess - so a missing signal can only lower a score, never raise it.
/// </summary>
internal sealed class EvidenceTokens
{
    private readonly Dictionary<string, string> _tokens;

    private EvidenceTokens(Dictionary<string, string> tokens) => _tokens = tokens;

    public static EvidenceTokens Parse(string evidence)
    {
        var map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var part in evidence.Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            var eq = part.IndexOf('=');
            if (eq > 0)
            {
                map[part[..eq].Trim()] = part[(eq + 1)..].Trim();
            }
        }

        return new EvidenceTokens(map);
    }

    public string? Text(string key) => _tokens.TryGetValue(key, out var v) ? v : null;

    public bool Bool(string key)
    {
        var v = Text(key);
        // "executed"/"true"/"yes" are true; everything else (incl. absent) is false - conservative.
        return string.Equals(v, "executed", StringComparison.OrdinalIgnoreCase)
            || string.Equals(v, "true", StringComparison.OrdinalIgnoreCase)
            || string.Equals(v, "yes", StringComparison.OrdinalIgnoreCase);
    }

    public int Int(string key) => int.TryParse(Text(key), out var n) ? n : 0;

    /// <summary>Parses an "observed/required" ratio (e.g. "9/10"); absent or malformed => 0.0.</summary>
    public double Ratio(string key)
    {
        var v = Text(key);
        if (v is null)
        {
            return 0.0;
        }

        var slash = v.IndexOf('/');
        if (slash > 0
            && int.TryParse(v[..slash], out var observed)
            && int.TryParse(v[(slash + 1)..], out var required)
            && required > 0)
        {
            return (double)observed / required;
        }

        return 0.0;
    }
}
