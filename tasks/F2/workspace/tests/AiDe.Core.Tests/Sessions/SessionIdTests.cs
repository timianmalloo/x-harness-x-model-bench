using System.Text.RegularExpressions;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Sessions;

/// <summary>
/// F0 (docs/plans/conductor-front-door.md) — the session id shape. It appears in a directory name
/// under <c>.aide/sessions/</c>, so it must be filesystem-safe, and it is the primary key of a
/// brand-new object, so it must be collision-resistant on its own rather than a lossy truncation of
/// something else (see the remarks on <see cref="SessionId"/> for why
/// <c>AgentWorktree.ShortId</c> was read and not reused here).
/// </summary>
public sealed class SessionIdTests
{
    private static readonly Regex FilesystemSafe = new(@"^[A-Za-z0-9._-]+$", RegexOptions.Compiled);

    [Fact]
    public void New_ProducesAFilesystemSafeToken()
    {
        var id = SessionId.New();

        Assert.Matches(FilesystemSafe, id);
        Assert.DoesNotContain("..", id);
    }

    [Fact]
    public void New_IsSortableByCreationTime()
    {
        var earlier = SessionId.New(new DateTimeOffset(2026, 1, 1, 0, 0, 0, TimeSpan.Zero));
        var later = SessionId.New(new DateTimeOffset(2026, 1, 2, 0, 0, 0, TimeSpan.Zero));

        Assert.True(string.CompareOrdinal(earlier, later) < 0);
    }

    [Fact]
    public void New_TwoCallsAtTheSameInstantDoNotCollide()
    {
        var now = DateTimeOffset.UtcNow;

        var a = SessionId.New(now);
        var b = SessionId.New(now);

        Assert.NotEqual(a, b);
    }

    [Fact]
    public void New_RoundTripsThroughIsValid()
    {
        var id = SessionId.New();

        Assert.True(SessionId.IsValid(id));
    }

    [Theory]
    [InlineData("../../escape")]
    [InlineData("")]
    [InlineData("not a valid id")]
    [InlineData("con")]
    public void IsValid_RejectsHostileOrMalformedInput(string candidate)
    {
        Assert.False(SessionId.IsValid(candidate));
    }
}
