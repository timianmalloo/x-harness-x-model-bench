using System.Text.Json;
using AiDe.Core.AgentPlane;
using AiDe.Core.Presentation.Sessions;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Sessions;

/// <summary>
/// F5 clause 1: <c>session.open</c> carries an <c>origin</c> field <b>set only on the
/// <c>Ctrl+N</c> / <c>MainMenuBuilder</c> command path</b> — with the companion that constructs a
/// session directly and shows <c>origin</c> reading the other value.
/// </summary>
/// <remarks>
/// <para><b>The companion is the whole test, and the positive half alone would be theatre.</b>
/// "The front door sets origin" is satisfied by a field that is always the same string, and a field
/// that is always the same string distinguishes nothing. <b>Asserted-about is what N7 was blocked
/// for.</b> So the load-bearing case here is
/// <see cref="ASessionConstructedDirectlyReadsTheOtherValue"/>: it takes the path the clause says is
/// NOT the front door and shows the field reading <c>direct</c>. Break that and the positive half
/// still passes while the claim is false.</para>
///
/// <para><b>Three cases, because the claim has three parts.</b> The sheet's created session reads
/// the front-door value; a directly constructed one reads the other; and <b>exactly one site in
/// <c>src/</c> can produce the front-door value</b>, which is what makes "only on that path" a
/// statement about the product rather than about this test's two examples.</para>
/// </remarks>
public sealed class TheSessionOriginIsSetOnlyOnTheCommandPathTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-f5-origin-" + Guid.NewGuid().ToString("N"));

    public TheSessionOriginIsSetOnlyOnTheCommandPathTests() => Directory.CreateDirectory(_root);

    public void Dispose()
    {
        try
        {
            Directory.Delete(_root, recursive: true);
        }
        catch (IOException)
        {
        }
    }

    /// <summary>Reads the <c>origin</c> a session's <c>session.open</c> line carries, or null.</summary>
    /// <remarks>
    /// Read back out of the persisted JSON body rather than from a return value: the clause is
    /// about what the <b>stream</b> carries, and the exit run reads it from the same file with the
    /// same key.
    /// </remarks>
    private static string? OriginOf(SessionConfigStore store)
    {
        var open = store.ReadEvents().Single(e => e.Kind == SessionEventKinds.Open);
        return open.Body["origin"]?.GetValue<string>();
    }

    [Fact]
    public void TheFrontDoorSheetStampsTheCommandPathOrigin()
    {
        var sheet = new NewSessionSheetViewModel(_root, _root, new ProviderRegistry([]), DateTimeOffset.UtcNow)
        {
            TaskClass = "feature",
        };

        var created = sheet.Create(DateTimeOffset.UtcNow);
        var store = new SessionConfigStore(_root, created.Config.SessionId);

        Assert.Equal(SessionOrigins.MainMenuNewSession, OriginOf(store));
    }

    /// <summary>
    /// THE COMPANION. A session constructed directly — no sheet, no command — reads the other value.
    /// </summary>
    /// <remarks>
    /// Without this, <c>origin</c> could be a constant and every assertion about it would still
    /// pass. This is the case that makes the field carry information.
    /// </remarks>
    [Fact]
    public void ASessionConstructedDirectlyReadsTheOtherValue()
    {
        var sessionId = SessionId.New();
        var store = new SessionConfigStore(_root, sessionId);

        store.Create("constructed directly", "workspace-1", [new AccountRef("anthropic", "max")], new AccountRef("anthropic", "max"), DateTimeOffset.UtcNow);

        Assert.Equal(SessionOrigins.Direct, OriginOf(store));
        Assert.NotEqual(SessionOrigins.MainMenuNewSession, OriginOf(store));
    }

    /// <summary>A config toggle carries no origin — the session was already open.</summary>
    [Fact]
    public void ASessionConfigEventCarriesNoOrigin()
    {
        var sessionId = SessionId.New();
        var store = new SessionConfigStore(_root, sessionId);

        store.Create("toggled", "workspace-1", [new AccountRef("anthropic", "max")], new AccountRef("anthropic", "max"), DateTimeOffset.UtcNow);
        store.SetDefaultAccount(null, DateTimeOffset.UtcNow);

        var config = store.ReadEvents().Single(e => e.Kind == SessionEventKinds.Config);
        Assert.Null(config.Body["origin"]);
    }

    /// <summary>
    /// "Only on the command path", as a property of <c>src/</c> rather than of this file's examples.
    /// </summary>
    /// <remarks>
    /// <b>The scan states its own shape</b> (DC-118 half (b), which has no lint): <b>root</b>
    /// <c>src/</c>; <b>recursion</b> all directories beneath it; <b>token set</b> the single literal
    /// <c>MainMenuNewSession</c>; <b>allowlist</b> <see cref="AllowlistedOriginStampSites"/> — the
    /// declaration, and the one caller the clause names. A file appearing here that is not in the
    /// allowlist means a second way to claim the front door, which is the failure the clause exists
    /// to prevent.
    /// </remarks>
    [Fact]
    public void ExactlyOneSiteInSrcCanStampTheFrontDoorOrigin()
    {
        var src = Path.Combine(RepoRoot(), "src");
        Assert.True(Directory.Exists(src), $"expected {src} to exist");

        var hits = Directory
            .EnumerateFiles(src, "*.cs", SearchOption.AllDirectories)
            .Where(path => File.ReadAllText(path).Contains(
                nameof(SessionOrigins.MainMenuNewSession), StringComparison.Ordinal))
            .Select(Path.GetFileName)
            .Order(StringComparer.Ordinal)
            .ToList();

        Assert.Equal(AllowlistedOriginStampSites.Order(StringComparer.Ordinal), hits);
    }

    /// <summary>
    /// The only files in <c>src/</c> that may name the front-door origin: where it is declared, and
    /// the single sheet that stamps it.
    /// </summary>
    /// <remarks>
    /// <para>A named constant rather than literals in the loop, for the reason
    /// <c>SessionPathContractTests.AllowlistedRunLogReservationFiles</c> is one: when a later phase
    /// legitimately adds a second front door, it extends this list citing its ruling, rather than
    /// the guard being weakened or deleted to let it through.</para>
    ///
    /// <para><b>That sentence has now been tested, and the answer is Ruling 49: this slice admits no
    /// second front door.</b> A headless entry point was proposed for the F5 exit run, to substitute
    /// for the operator's gesture. It would not have appeared in this list — it would have driven
    /// <c>NewSessionSheetViewModel.Create()</c> rather than naming the constant — so <b>this guard
    /// would have stayed green while the claim it protects became false</b>: the origin would no
    /// longer have distinguished the operator's route from a harness's. The plan's clause 1 says the
    /// origin is set <i>only</i> on the <c>Ctrl+N</c> / <c>MainMenuBuilder</c> path, and a second
    /// path reaching the same sheet falsifies that sentence without reddening anything here.</para>
    ///
    /// <para><b>So the list stays at two entries, and the guard is not the whole control.</b> What
    /// this test can see is who <i>names</i> the constant; what it cannot see is who <i>reaches</i>
    /// the sheet. A later phase adding a second front door cites its own ruling and must state which
    /// half it is changing.</para>
    /// </remarks>
    private static readonly IReadOnlyList<string> AllowlistedOriginStampSites =
        ["NewSessionSheetViewModel.cs", "SessionConfig.cs"];

    private static string RepoRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);

        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "AiDe.sln")))
        {
            directory = directory.Parent;
        }

        return directory?.FullName
            ?? throw new InvalidOperationException("could not locate the repository root from the test output directory");
    }
}
