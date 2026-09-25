using System.Text.Json;
using System.Text.RegularExpressions;

namespace AiDe.Core.Terminal;

/// <summary>One agent's readiness marker, and where it came from.</summary>
/// <param name="Origin">
/// Which source supplied the pattern. Kept because a user-tuned marker and a built-in default carry
/// different weight when a dispatch is later refused, and "why did it refuse" is unanswerable if the
/// answer is "some pattern".
/// </param>
/// <param name="AttentionPattern">
/// A screen that is waiting on a PERSON — a trust gate, an auth prompt. Null when nothing is known
/// to need answering. Separate from <paramref name="Pattern"/> because "waiting for you" and "busy"
/// are different situations with different correct responses, and collapsing them leaves a pane that
/// refuses without ever saying why.
/// </param>
/// <param name="HarnessId">
/// The harness this executable is, as <c>service.name</c> on the session's coordination record —
/// <c>claude-code</c>, <c>github-copilot</c>. Null when unknown, and then the session registers with
/// no harness rather than a guessed one.
/// </param>
/// <param name="DisplayName">
/// The menu label, e.g. <c>Claude Code</c>. A profile with a display name AND a gesture gets its own
/// <c>New … session</c> entry; one without gets none. **The menu is derived from this set rather than
/// listed beside it** — a second hand-maintained list is the defect shape this repository has hit
/// repeatedly (a list kept in step by memory).
/// </param>
/// <param name="Gesture">
/// The keyboard chord for that entry. Required alongside <paramref name="DisplayName"/> because
/// every command must declare one (<c>WorkbenchCommandTests</c>) and every rendered menu item must
/// show one (<c>MainMenuTests</c>) — so a derived command with no gesture would fail both. It cannot
/// be generated: chords are a finite, human-chosen space, and an invented one would collide.
/// </param>
public sealed record AgentReadinessProfile(
    string Agent, string Pattern, string Origin, string? AttentionPattern = null,
    string? HarnessId = null, string? DisplayName = null, string? Gesture = null)
{
    /// <summary>Whether this profile can offer its own "New … session" command.</summary>
    public bool Launchable => !string.IsNullOrWhiteSpace(DisplayName) && !string.IsNullOrWhiteSpace(Gesture);

    /// <summary>The command id for this harness's session, derived from the executable name.</summary>
    public string CommandId => CommandIdFor(Agent);

    /// <summary>The one place the id is spelled, so the catalog, the menu and the controller agree.</summary>
    public static string CommandIdFor(string agent) => "terminal.new." + agent.ToLowerInvariant();
}

/// <summary>
/// Per-agent readiness markers, built in and user-supplied.
/// </summary>
/// <remarks>
/// <para><b>Why this exists.</b> The built-in markers are a guess about what an agent's prompt looks
/// like, and a guess that does not match means the agent is refused forever — a correct refusal that
/// is also a dead end. Nothing shipped could change that without a rebuild, so the honest fix is to
/// let the marker be configured where the agent actually runs.</para>
///
/// <para><b>A bad pattern fails loudly, never open.</b> A regex that does not compile is reported and
/// the agent keeps its built-in marker; it never degrades to "assume ready", because the one thing
/// worse than refusing a ready agent is dispatching into an unready one — the failure
/// <c>spikes/agent-dispatch</c> measured.</para>
///
/// <para><b>Tuning is measurement, not guesswork.</b> <see cref="AgentReadinessWatcher.LastJudged"/>
/// exposes the tail the watcher actually tested, so a user fixing a pattern reads what the agent
/// printed rather than reasoning about what it probably prints.</para>
/// </remarks>
public sealed class AgentReadinessProfiles
{
    public const string FileName = "agent-readiness.json";

    private readonly Dictionary<string, AgentReadinessProfile> _byAgent =
        new(StringComparer.OrdinalIgnoreCase);

    private AgentReadinessProfiles(IEnumerable<AgentReadinessProfile> profiles, IReadOnlyList<string> problems)
    {
        foreach (var profile in profiles)
        {
            _byAgent[profile.Agent] = profile;
        }

        Problems = problems;
    }

    /// <summary>Patterns that were rejected, and why. Surfaced rather than absorbed.</summary>
    public IReadOnlyList<string> Problems { get; }

    public IReadOnlyCollection<AgentReadinessProfile> All => _byAgent.Values;

    /// <summary>The built-in markers, with no file involved.</summary>
    /// <summary>
    /// Harness identity and launch affordance per known executable.
    /// </summary>
    /// <remarks>
    /// Beside <see cref="AgentReadinessWatcher.KnownAgents"/> rather than inside it because that map
    /// answers "how do I know this agent is ready", which is a different question with a different
    /// lifetime — a readiness pattern is tuned against a rendered screen, a harness id is a fixed
    /// fact about the product. Keyed by the same executable name, so the two cannot drift apart in
    /// membership even though they are separate maps: a profile is only built for a key present in
    /// <see cref="AgentReadinessWatcher.KnownAgents"/>.
    /// </remarks>
    private static readonly IReadOnlyDictionary<string, (string HarnessId, string Display, string Gesture)> KnownHarness =
        new Dictionary<string, (string, string, string)>(StringComparer.OrdinalIgnoreCase)
        {
            // Ctrl+K, A is inherited from the removed `terminal.newAgent`, so the chord a user has
            // in their fingers still opens an agent session — it now opens a NAMED one.
            ["claude"] = ("claude-code", "Claude Code", "Ctrl+K, A"),
            ["copilot"] = ("github-copilot", "GitHub Copilot", "Ctrl+K, G"),
        };

    public static AgentReadinessProfiles BuiltIn { get; } = new(
        AgentReadinessWatcher.KnownAgents.Select(kv =>
        {
            var harness = KnownHarness.TryGetValue(kv.Key, out var h) ? h : default;
            return new AgentReadinessProfile(
                kv.Key, kv.Value, "built-in",
                AgentReadinessWatcher.KnownAttention.GetValueOrDefault(kv.Key),
                HarnessId: harness.HarnessId,
                DisplayName: harness.Display,
                Gesture: harness.Gesture);
        }),
        []);

    /// <summary>Loads the overrides beside the built-ins. A missing file is the ordinary case.</summary>
    public static AgentReadinessProfiles Load(string? stateDirectory)
    {
        if (string.IsNullOrEmpty(stateDirectory))
        {
            return BuiltIn;
        }

        var path = Path.Combine(stateDirectory, FileName);
        if (!File.Exists(path))
        {
            return BuiltIn;
        }

        Dictionary<string, string>? overrides;
        try
        {
            overrides = JsonSerializer.Deserialize<Dictionary<string, string>>(
                File.ReadAllText(path),
                new JsonSerializerOptions { ReadCommentHandling = JsonCommentHandling.Skip });
        }
        catch (Exception ex) when (ex is JsonException or IOException)
        {
            return new AgentReadinessProfiles(
                BuiltIn.All,
                [$"{FileName} could not be read ({ex.GetType().Name}); the built-in markers are in use."]);
        }

        if (overrides is null)
        {
            return BuiltIn;
        }

        var profiles = BuiltIn.All.ToDictionary(p => p.Agent, StringComparer.OrdinalIgnoreCase);
        var problems = new List<string>();

        foreach (var (agent, pattern) in overrides)
        {
            if (string.IsNullOrWhiteSpace(agent))
            {
                continue;
            }

            if (string.IsNullOrWhiteSpace(pattern))
            {
                // An explicit empty marker means "this agent has none", which is a legitimate thing
                // to say: it makes the refusal deliberate rather than an unmatched pattern.
                profiles.Remove(agent);
                continue;
            }

            if (!Compiles(pattern, out var reason))
            {
                problems.Add($"the readiness marker for '{agent}' is not a usable pattern ({reason}); " +
                             "the built-in marker is in use for it.");
                continue;
            }

            // The attention pattern is kept from the built-in. Overriding the READY marker is
            // routine tuning; silently dropping the dialog detector with it would turn a tuned
            // profile into one that cannot tell a prompt from a trust gate.
            profiles[agent] = new AgentReadinessProfile(
                agent, pattern, FileName,
                profiles.GetValueOrDefault(agent)?.AttentionPattern
                    ?? AgentReadinessWatcher.KnownAttention.GetValueOrDefault(agent));
        }

        return new AgentReadinessProfiles(profiles.Values, problems);
    }

    /// <summary>The marker for an agent, or null when nothing reports readiness for it.</summary>
    public AgentReadinessProfile? For(string agent) =>
        string.IsNullOrWhiteSpace(agent) ? null : _byAgent.GetValueOrDefault(agent);

    /// <summary>A watcher for an agent, or null — the caller must treat null as "cannot establish".</summary>
    public AgentReadinessWatcher? WatcherFor(string agent) =>
        For(agent) is { } profile
            ? new AgentReadinessWatcher(profile.Pattern, profile.AttentionPattern)
            : null;

    /// <summary>Writes the current markers as a starting point for the user to edit.</summary>
    public static string WriteTemplate(string stateDirectory)
    {
        Directory.CreateDirectory(stateDirectory);
        var path = Path.Combine(stateDirectory, FileName);

        // Never overwritten: the file exists to hold a marker the user tuned, and regenerating it
        // over their edit would destroy the only copy of the thing this feature is for.
        if (!File.Exists(path))
        {
            File.WriteAllText(path, JsonSerializer.Serialize(
                BuiltIn.All.ToDictionary(p => p.Agent, p => p.Pattern),
                new JsonSerializerOptions { WriteIndented = true }));
        }

        return path;
    }

    private static bool Compiles(string pattern, out string reason)
    {
        try
        {
            // Constructed exactly as the watcher constructs it, timeout included: a pattern that
            // validated here and timed out there would be accepted and then silently fail closed.
            _ = new Regex(pattern, RegexOptions.Compiled | RegexOptions.CultureInvariant,
                TimeSpan.FromMilliseconds(250));
            reason = string.Empty;
            return true;
        }
        catch (ArgumentException ex)
        {
            reason = ex.Message.Split('\n')[0].Trim();
            return false;
        }
    }
}
