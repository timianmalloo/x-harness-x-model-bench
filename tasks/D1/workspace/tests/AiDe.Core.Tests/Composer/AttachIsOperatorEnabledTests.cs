using System.Text.Json;
using AiDe.Core.Presentation.Composer;
using AiDe.Core.Sessions;
using AiDe.Core.Tests.Sessions;

namespace AiDe.Core.Tests.Composer;

/// <summary>
/// <b>C21</b> — attach is operator-enabled, off by default, and host-owned — with the audit-channel
/// rules the committed log and the machine-local record are both bound by.
/// </summary>
/// <remarks>
/// <b>Red first, and the first assertion to go red was the one that matters:</b> a gate that blocked
/// the insert while still reading the file passed everything except
/// <see cref="C21a_WithAttachOffNotOneByteOfAPickedFileIsRead"/>, which is the whole point of the
/// clause — a gate that blocks the insert but still reads the file has already done the thing.
/// </remarks>
public sealed class AttachIsOperatorEnabledTests : IDisposable
{
    private readonly string _workspaceRoot;
    private readonly SessionConfigStore _store;

    public AttachIsOperatorEnabledTests()
    {
        _workspaceRoot = Path.Combine(Path.GetTempPath(), "aide-c21", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_workspaceRoot);
        _store = new SessionConfigStore(_workspaceRoot, "s-0001");
    }

    public void Dispose()
    {
        try
        {
            Directory.Delete(_workspaceRoot, recursive: true);
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        {
        }
    }

    [Fact]
    public void C21_TheShippedDefaultIsOff()
    {
        var config = _store.Create("first", "w-1", [new AccountRef("anthropic", "max")], new AccountRef("anthropic", "max"), DateTimeOffset.UnixEpoch);

        Assert.False(config.AttachEnabled);
        Assert.False(_store.Load().AttachEnabled);
    }

    [Fact]
    public void C21_ASessionFileWrittenBeforeThisFieldExistedStillReadsAndReadsFalse()
    {
        // The exact bytes an earlier build wrote: no attachEnabled member anywhere.
        var legacy = """
        {
          "SessionId": "s-0001",
          "Name": "first",
          "WorkspaceId": "w-1",
          "CreatedAt": "1970-01-01T00:00:00+00:00",
          "EnabledBackends": ["claude-code"]
        }
        """;

        Directory.CreateDirectory(SessionPaths.SessionDirectory(_workspaceRoot, "s-0001"));
        File.WriteAllText(SessionPaths.SessionFile(_workspaceRoot, "s-0001"), legacy);

        Assert.False(_store.Load().AttachEnabled);
    }

    [Fact]
    public void C21a_WithAttachOffNotOneByteOfAPickedFileIsRead()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        draft.SetFreeFormText("the prompt as typed\n");
        var before = ComposerCompiler.Compile(draft).Text;

        var inside = fixture.WriteInside("src/Note.cs", "class Note { }\n");
        var outside = fixture.WriteOutside("brief.md", "the brief\n");

        var outcome = fixture.Gate().Offer(draft, [inside, outside, inside], attachEnabled: false);

        Assert.Empty(outcome.Attached);
        Assert.Empty(draft.Attachments);
        Assert.Equal(before, ComposerCompiler.Compile(draft).Text);
        Assert.Equal(0, fixture.Reader.ReadCount);

        // Not even metadata: with the setting off, the file system is not touched at all.
        Assert.Equal(0, fixture.Reader.MetadataCount);
        Assert.Empty(fixture.Affirmation.Asked);
        Assert.Equal(3, outcome.BlockedByAttachSetting);

        // And the same gestures attach once the setting is on.
        var enabled = fixture.Gate().Offer(draft, [inside], attachEnabled: true);
        Assert.Single(enabled.Attached);
        Assert.Equal(1, fixture.Reader.ReadCount);
    }

    [Fact]
    public void C21d_ABlockedAttachRecordsACountAndNeverAName()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();

        const string CanaryBasename = "PRIVACY-CANARY-4d1f8e2a.md";
        var canaryPath = fixture.WriteOutside(CanaryBasename, "PRIVACY-CANARY-4d1f8e2a body\n");

        var outcome = fixture.Gate().Offer(draft, [canaryPath], attachEnabled: false);

        // The operator-facing refusal itself names nothing about the pick.
        var refusal = Assert.Single(outcome.Refusals);
        Assert.DoesNotContain(CanaryBasename, refusal, StringComparison.Ordinal);
        Assert.DoesNotContain(canaryPath, refusal, StringComparison.Ordinal);
        Assert.DoesNotContain("PRIVACY-CANARY", refusal, StringComparison.Ordinal);
        Assert.Contains("session", refusal, StringComparison.OrdinalIgnoreCase);

        // Channel B, which is the MORE permissive channel, is still a count and never a name.
        ComposerSendRecord.AppendChannelB(
            fixture.WorkspaceRoot, outcome.Attached, outcome.BlockedByAttachSetting, DateTimeOffset.UnixEpoch);

        var channelB = File.ReadAllText(ComposerSendRecord.ChannelBFile(fixture.WorkspaceRoot));
        Assert.Contains("\"blocked_by_setting\":1", channelB, StringComparison.Ordinal);
        Assert.DoesNotContain("PRIVACY-CANARY", channelB, StringComparison.Ordinal);
        Assert.DoesNotContain(canaryPath, channelB, StringComparison.Ordinal);

        // And the committed channel.
        var committed = ComposerSendRecord
            .Committed(attachEnabled: false, ComposerCompiler.Compile(draft), outcome.BlockedByAttachSetting)
            .ToJsonString();
        Assert.DoesNotContain("PRIVACY-CANARY", committed, StringComparison.Ordinal);
        Assert.Contains("\"blocked_by_setting\":1", committed, StringComparison.Ordinal);
    }

    [Fact]
    public void C21d_TheCanarySweepCanActuallyFindTheCanaryWhenItIsDeliberatelyWritten()
    {
        // THE FALSIFIER. A grep that greps nothing passes forever, so this run writes the canary into
        // the same swept tree and requires the same sweep to FIND it.
        using var fixture = new AttachmentFixture();

        const string Canary = "PRIVACY-CANARY-4d1f8e2a";
        Assert.Empty(ComposerCanarySweep.Hits(fixture.WorkspaceRoot, Canary));

        Directory.CreateDirectory(Path.Combine(fixture.WorkspaceRoot, ".aide"));
        File.WriteAllText(
            Path.Combine(fixture.WorkspaceRoot, ".aide", "deliberate.jsonl"),
            $"{{\"leaked\":\"{Canary}\"}}\n");

        var hits = ComposerCanarySweep.Hits(fixture.WorkspaceRoot, Canary);
        Assert.Single(hits);
        Assert.Contains("deliberate.jsonl", hits[0], StringComparison.Ordinal);
    }

    [Fact]
    public void C21b_TheDisabledReasonNamesTheSettingThatGovernsIt()
    {
        using var fixture = new AttachmentFixture();
        var outcome = fixture.Gate().Offer(new ComposerDraft(), ["C:/anything.md"], attachEnabled: false);

        var refusal = Assert.Single(outcome.Refusals);
        Assert.Contains("Attach files", refusal, StringComparison.Ordinal);
        Assert.Contains("off for this session", refusal, StringComparison.Ordinal);
    }

    [Fact]
    public void C21c_OffIsDistinguishableFromNeverAskedByTheExistingEventLogAlone()
    {
        _store.Create("first", "w-1", [new AccountRef("anthropic", "max")], new AccountRef("anthropic", "max"), DateTimeOffset.UnixEpoch);

        // A never-toggled session's log carries no config event at all.
        Assert.DoesNotContain(_store.ReadEvents(), e => e.Kind == SessionEventKinds.Config);

        var eventsFile = SessionPaths.EventsFile(_workspaceRoot, "s-0001");

        _store.SetAttachEnabled(true, DateTimeOffset.UnixEpoch.AddMinutes(1));
        var afterFirst = File.ReadAllLines(eventsFile);

        _store.SetAttachEnabled(false, DateTimeOffset.UnixEpoch.AddMinutes(2));
        var afterSecond = File.ReadAllLines(eventsFile);

        var configEvents = _store.ReadEvents().Where(e => e.Kind == SessionEventKinds.Config).ToList();
        Assert.Equal(2, configEvents.Count);
        Assert.True(configEvents[0].Body["attachEnabled"]!.GetValue<bool>());
        Assert.False(configEvents[1].Body["attachEnabled"]!.GetValue<bool>());

        // Earlier lines are byte-unchanged: the record of the first decision is not rewritten by the
        // second one.
        Assert.Equal(afterFirst, afterSecond[..afterFirst.Length]);
    }

    [Fact]
    public void C21c_NoProvenanceFieldIsAddedToTheSessionConfig()
    {
        var config = _store.Create("first", "w-1", [new AccountRef("anthropic", "max")], new AccountRef("anthropic", "max"), DateTimeOffset.UnixEpoch);
        var members = JsonDocument.Parse(JsonSerializer.Serialize(config)).RootElement
            .EnumerateObject().Select(p => p.Name).ToList();

        // The append-only log is already the record. Two definitions of one fact is a defect
        // signature, so these names must not appear here.
        foreach (var forbidden in new[] { "source", "decidedAt", "attachEnabledSource", "attachEnabledDecidedAt" })
        {
            Assert.DoesNotContain(forbidden, members, StringComparer.OrdinalIgnoreCase);
        }

        Assert.Contains("AttachEnabled", members, StringComparer.Ordinal);
    }

    [Fact]
    public void C21e_TheSettingIsUnreachableFromThePageVocabulary()
    {
        foreach (var spelling in new[]
                 {
                     "attach.enabled", "attachEnabled", "attach_enabled", "AttachEnabled",
                     "setting.attach", "config.attach",
                 })
        {
            Assert.False(ComposerMessageKinds.IsKnown(spelling));
        }

        // And the sink — the only surface the router can reach — declares nothing that could write it.
        var members = typeof(IComposerMessageSink).GetMethods().Select(m => m.Name).ToList();
        Assert.DoesNotContain(members, m => m.Contains("Attach", StringComparison.Ordinal) && m != "OfferAttachment");
        Assert.DoesNotContain(members, m => m.Contains("Enable", StringComparison.Ordinal));
        Assert.DoesNotContain(members, m => m.Contains("Send", StringComparison.Ordinal));
    }

    [Fact]
    public void C21f_NothingInTheProductDescribesTheSettingAsPreventingAttachForADeployment()
    {
        // The honest limit is that this is a per-session, operator-writable DEFAULT. A comment
        // claiming it prevents or restricts attach for a deployment would be the security-shaped lie
        // the clause names, so the source is read rather than trusted.
        var config = RepoFiles.SourceFile("src", "AiDe.Core", "Sessions", "SessionConfig.cs");

        Assert.Contains("enforceable policy", config, StringComparison.Ordinal);
        Assert.Contains("non-session-overridable", config, StringComparison.Ordinal);

        // And nothing ANYWHERE in the composer or the session config claims the opposite. The clause
        // says "described anywhere", so the sweep is over every file that could carry the claim
        // rather than over the one that carries its correction.
        var swept = Directory
            .EnumerateFiles(
                Path.Combine(RepoFiles.Root(), "src", "AiDe.Core", "Presentation", "Composer"), "*.cs")
            .Concat(Directory.EnumerateFiles(
                Path.Combine(RepoFiles.Root(), "src", "AiDe.App", "Workbench", "Composer"), "*.cs"))
            .Append(Path.Combine(RepoFiles.Root(), "src", "AiDe.Core", "Sessions", "SessionConfig.cs"))
            .Append(Path.Combine(RepoFiles.Root(), "src", "AiDe.App", "Web", "composer.mjs"))
            .ToList();

        Assert.NotEmpty(swept);

        foreach (var path in swept)
        {
            var text = File.ReadAllText(path);
            foreach (var claim in new[] { "prevents attach", "restricts attach", "prevent attach", "restrict attach" })
            {
                Assert.DoesNotContain(claim, text, StringComparison.OrdinalIgnoreCase);
            }
        }
    }
}
