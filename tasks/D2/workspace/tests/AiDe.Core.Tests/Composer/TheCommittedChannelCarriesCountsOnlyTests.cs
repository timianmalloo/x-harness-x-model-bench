using AiDe.Core.Presentation.Composer;
using AiDe.Core.Tests.Sessions;

namespace AiDe.Core.Tests.Composer;

/// <summary>
/// The audit trail's two channels, and refusal <b>(h)</b>: nothing about a composed send's content
/// ever reaches the committed, cloned, append-only record.
/// </summary>
/// <remarks>
/// <b>Both halves are red-first, and the falsifier is the half that makes the other one mean
/// anything.</b> The Audit Mandate's prompt field is for the human's instruction to an agent, and it
/// is verbatim, committed, cloned and append-only. Routing the composer's send through it would
/// convert a transient egress into a permanent, shared, unretractable one.
/// </remarks>
public sealed class TheCommittedChannelCarriesCountsOnlyTests
{
    private static IReadOnlyList<string> CommittedChannels() =>
    [
        Path.Combine(RepoFiles.Root(), "docs", "audit"),
        Path.Combine(RepoFiles.Root(), ".agents", "log"),
    ];

    [Fact]
    public void TheCommittedRecordCarriesTheCountsPrivacyRequiredAndNothingElse()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        draft.SetFreeFormText("compose something\n");

        fixture.Gate().Offer(
            draft,
            [
                fixture.WriteInside("a.md", "inside one\n"),
                fixture.WriteInside("b.md", "inside two\n"),
                fixture.WriteOutside("c.md", "outside one\n"),
            ],
            attachEnabled: true);

        var compiled = ComposerCompiler.Compile(draft);
        var record = ComposerSendRecord.Committed(attachEnabled: true, compiled, blockedByAttachSetting: 0);

        Assert.Equal(["attach_enabled", "attachments"], record.Select(p => p.Key));

        var attachments = record["attachments"]!.AsObject();
        Assert.Equal(
            ["count", "bytes_total", "inside_workspace", "outside_workspace", "blocked_by_setting"],
            attachments.Select(p => p.Key));

        Assert.Equal(3, attachments["count"]!.GetValue<int>());
        Assert.Equal(2, attachments["inside_workspace"]!.GetValue<int>());
        Assert.Equal(1, attachments["outside_workspace"]!.GetValue<int>());
        Assert.Equal(34, attachments["bytes_total"]!.GetValue<int>());
    }

    [Fact]
    public void TheCommittedRecordNeverCarriesAPathABasenameAHashOrTheComposedText()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        draft.SetFreeFormText("compose something secret\n");

        var outside = fixture.WriteOutside("DISTINCTIVE-BASENAME.md", "outside content\n");
        fixture.Gate().Offer(draft, [outside], attachEnabled: true);

        var compiled = ComposerCompiler.Compile(draft);
        var json = ComposerSendRecord
            .Committed(attachEnabled: true, compiled, blockedByAttachSetting: 0)
            .ToJsonString();

        Assert.DoesNotContain("DISTINCTIVE-BASENAME", json, StringComparison.Ordinal);
        Assert.DoesNotContain(outside, json, StringComparison.Ordinal);
        Assert.DoesNotContain(Path.GetDirectoryName(outside)!, json, StringComparison.Ordinal);
        Assert.DoesNotContain(draft.Attachments[0].Sha256, json, StringComparison.Ordinal);
        Assert.DoesNotContain("compose something secret", json, StringComparison.Ordinal);
        Assert.DoesNotContain("outside content", json, StringComparison.Ordinal);
    }

    [Fact]
    public void RefusalH_ARealSendLeavesNoCanaryInAnyCommittedChannel()
    {
        var canary = "PRIVACY-CANARY-" + Guid.NewGuid().ToString("N");

        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        draft.SetFreeFormText($"please look at this: {canary}\n");

        var file = fixture.WriteInside($"{canary}.md", $"the attachment body carries {canary} too\n");
        fixture.Gate().Offer(draft, [file], attachEnabled: true);

        var compiled = ComposerCompiler.Compile(draft);
        Assert.Contains(canary, compiled.Text, StringComparison.Ordinal);

        // The send's record is written to both channels, exactly as the product writes them.
        ComposerSendRecord.AppendChannelB(
            fixture.WorkspaceRoot, draft.Attachments, blockedByAttachSetting: 0, DateTimeOffset.UnixEpoch);
        var committed = ComposerSendRecord
            .Committed(attachEnabled: true, compiled, blockedByAttachSetting: 0)
            .ToJsonString();

        Assert.DoesNotContain(canary, committed, StringComparison.Ordinal);
        Assert.Empty(ComposerCanarySweep.Hits(CommittedChannels(), canary));
        Assert.Empty(ComposerCanarySweep.Hits(CommittedChannels(), AttachmentPolicy.RealPath(file)));
    }

    [Fact]
    public void RefusalH_TheSweepFindsTheCanaryWhenItIsDeliberatelyWrittenIntoACommittedChannel()
    {
        // THE FALSIFIER, and it runs against the SAME sweep the clause test uses — a scratch file is
        // written inside the real committed-channel tree, found, and removed.
        var canary = "PRIVACY-CANARY-" + Guid.NewGuid().ToString("N");
        var probe = Path.Combine(RepoFiles.Root(), "docs", "audit", $"canary-falsifier-{canary}.tmp");

        try
        {
            Assert.Empty(ComposerCanarySweep.Hits(CommittedChannels(), canary));

            File.WriteAllText(probe, $"{{\"prompt\":\"{canary}\"}}\n");

            var hits = ComposerCanarySweep.Hits(CommittedChannels(), canary);
            Assert.Single(hits);
            Assert.Equal(probe, hits[0]);
        }
        finally
        {
            if (File.Exists(probe))
            {
                File.Delete(probe);
            }
        }
    }

    [Fact]
    public void ChannelBCarriesTheReviewableRecordAndLivesInsideTheIgnoredSidecar()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        var outside = fixture.WriteOutside("brief.md", "outside content\n");

        fixture.Gate().Offer(draft, [outside], attachEnabled: true);
        ComposerSendRecord.AppendChannelB(
            fixture.WorkspaceRoot, draft.Attachments, blockedByAttachSetting: 0, DateTimeOffset.UnixEpoch);

        var file = ComposerSendRecord.ChannelBFile(fixture.WorkspaceRoot);
        Assert.Equal(
            Path.Combine(fixture.WorkspaceRoot, ".aide", "attachments.jsonl"),
            file);

        var line = Assert.Single(File.ReadAllLines(file));
        Assert.Contains(draft.Attachments[0].ResolvedPath.Replace("\\", "\\\\", StringComparison.Ordinal), line, StringComparison.Ordinal);
        Assert.Contains(draft.Attachments[0].Sha256, line, StringComparison.Ordinal);
        Assert.Contains("\"outside_workspace\":true", line, StringComparison.Ordinal);

        // Its erasure path is "delete .aide/", which is statable and testable.
        Directory.Delete(Path.Combine(fixture.WorkspaceRoot, ".aide"), recursive: true);
        Assert.False(File.Exists(file));
    }

    [Fact]
    public void TheSidecarDirectoryIsGitIgnoredSoChannelBCannotBecomeChannelA()
    {
        var gitignore = File.ReadAllText(Path.Combine(RepoFiles.Root(), ".gitignore"));
        Assert.Contains(".aide/", gitignore, StringComparison.Ordinal);
    }
}
