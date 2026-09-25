namespace AiDe.Core.Sessions;

/// <summary>
/// The on-disk path contract for a session (Addendum A3; Ruling 23; F0 clauses 1-2).
/// </summary>
/// <remarks>
/// <para><b><c>session.json</c>, not <c>.yaml</c> (Ruling 23, recorded as an A3 erratum).</b> A3's
/// prose named <c>session.yaml</c>; at the time of Ruling 23, no YAML parser existed in any
/// <c>.csproj</c> in this repository, <c>System.Text.Json</c> was already used in 38 files, and the
/// sibling run-log path is <c>.jsonl</c>. Choosing YAML for this one file would have made it the
/// only YAML reader in the product for a format with no reader anywhere else — that was the actual
/// reasoning, and it still holds for THIS path today: <see cref="SessionFile"/> reads and writes
/// <c>System.Text.Json</c> only, via <c>SessionConfigStore</c>.</para>
///
/// <para><b>Update (Ruling 35 / Ruling 36): a YAML-reading package now exists in this project.</b>
/// <c>AiDe.Core.csproj</c> takes a YAML library, scoped to the template loader
/// (<see cref="TemplateFrontmatterReader"/> / <c>TemplateSchema.cs</c>) for template
/// frontmatter — an unrelated format, an unrelated path. This does not reopen Ruling 23: Ruling 36
/// confirmed the two rulings do not conflict, because Ruling 23's subject was always the
/// session-config path specifically, never a claim that the *project* would forever contain no
/// YAML parser. Nothing under this type takes a YAML dependency; see
/// <c>SessionPathContractTests.SessionConfigSource_ContainsNoYamlToken</c>, which asserts that
/// directly against source rather than repeating a repo-wide claim in prose. (Deliberately not
/// naming the package here by its literal token:
/// <c>TemplateFrontmatterParserTests.TheDependencyIsScopedToTheTemplateLoader</c> asserts that
/// exactly one file in <c>src/</c> contains it, and this paragraph would otherwise be a second.)</para>
///
/// <para><b><c>runs/&lt;run-id&gt;.jsonl</c> is RESERVED, not built.</b> <c>RunLogStore</c> is Phase
/// 3. This type only computes the path so the contract is fixed now and the directory shape never
/// has to change later; nothing in this slice ever calls <see cref="RunLogFile"/> to write —
/// asserted by <c>SessionPathContractTests</c> and <c>SessionConfigStoreTests</c> in
/// <c>AiDe.Core.Tests.Sessions</c>.</para>
/// </remarks>
public static class SessionPaths
{
    public const string SessionFileName = "session.json";
    public const string EventsFileName = "session-events.jsonl";
    public const string RunsDirectoryName = "runs";

    /// <summary><c>&lt;workspaceRoot&gt;/.aide/sessions</c> — every session's parent.</summary>
    public static string SessionsRoot(string workspaceRoot) =>
        Path.Combine(workspaceRoot, ".aide", "sessions");

    /// <summary><c>&lt;workspaceRoot&gt;/.aide/sessions/&lt;session-id&gt;</c>.</summary>
    public static string SessionDirectory(string workspaceRoot, string sessionId) =>
        Path.Combine(SessionsRoot(workspaceRoot), sessionId);

    /// <summary>The session's config file — see the remarks on YAML vs. JSON.</summary>
    public static string SessionFile(string workspaceRoot, string sessionId) =>
        Path.Combine(SessionDirectory(workspaceRoot, sessionId), SessionFileName);

    /// <summary>
    /// The session's own append-only event log (<c>session.open</c> / <c>session.config</c> —
    /// clauses 3-4). Deliberately a SIBLING of <c>runs/</c>, never inside it: this is session-scoped
    /// state, not a run's record, and clause 2 forbids anything writing under the reserved subtree.
    /// </summary>
    public static string EventsFile(string workspaceRoot, string sessionId) =>
        Path.Combine(SessionDirectory(workspaceRoot, sessionId), EventsFileName);

    /// <summary>
    /// <c>&lt;workspaceRoot&gt;/.aide/sessions/&lt;session-id&gt;/runs</c> — RESERVED for Phase 3's
    /// <c>RunLogStore</c>. Computed, never created or written to, by this slice.
    /// </summary>
    public static string RunsDirectory(string workspaceRoot, string sessionId) =>
        Path.Combine(SessionDirectory(workspaceRoot, sessionId), RunsDirectoryName);

    /// <summary>
    /// <c>&lt;workspaceRoot&gt;/.aide/sessions/&lt;session-id&gt;/runs/&lt;run-id&gt;.jsonl</c> —
    /// RESERVED for Phase 3's <c>RunLogStore</c>. F0 fixes the path so the shape never has to move;
    /// it must not be used to write here (clause 2, asserted by test).
    /// </summary>
    public static string RunLogFile(string workspaceRoot, string sessionId, string runId) =>
        Path.Combine(RunsDirectory(workspaceRoot, sessionId), $"{runId}.jsonl");
}
