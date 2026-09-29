using System.Text;
using AiDe.Core.Presentation.Composer;

namespace AiDe.Core.Tests.Composer;

/// <summary>
/// Security <b>C14</b> (bounded, visible, literal) and Privacy <b>C14(e)(i)–(vi)</b>.
/// </summary>
/// <remarks>
/// <b>Every clause here has its own test, and each was observed red first</b> — against a gate that
/// attached anything it was handed. The caps, the refusal set, the resolved-path label, the pre-read
/// affirmation and the legibility rule were each added to turn one red assertion green.
/// </remarks>
public sealed class AttachmentsAreBoundedVisibleAndLiteralTests
{
    [Fact]
    public void C14_AFileOverThePerFileCapIsRefusedByNameAndSizeAndNeverTruncated()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        var big = fixture.WriteInside("big.md", new string('x', AttachmentPolicy.MaxAttachmentBytes + 1));

        var outcome = fixture.Gate().Offer(draft, [big], attachEnabled: true);

        Assert.Empty(outcome.Attached);
        Assert.Empty(draft.Attachments);
        var refusal = Assert.Single(outcome.Refusals);
        Assert.Contains("big.md", refusal, StringComparison.Ordinal);
        Assert.Contains((AttachmentPolicy.MaxAttachmentBytes + 1).ToString(), refusal, StringComparison.Ordinal);
        Assert.Contains("refused, not truncated", refusal, StringComparison.Ordinal);
    }

    [Fact]
    public void C14_AFileExactlyAtThePerFileCapIsAccepted()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        var atCap = fixture.WriteInside("at-cap.md", new string('x', AttachmentPolicy.MaxAttachmentBytes));

        var outcome = fixture.Gate().Offer(draft, [atCap], attachEnabled: true);

        Assert.Single(outcome.Attached);
        Assert.Equal(AttachmentPolicy.MaxAttachmentBytes, outcome.Attached[0].Bytes);
    }

    [Fact]
    public void C14_ThePerSendByteCapIsEnforcedAcrossFilesAndNamesTheTotal()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        var gate = fixture.Gate();

        var each = AttachmentPolicy.MaxAttachmentBytes;
        var files = Enumerable.Range(0, 5)
            .Select(i => fixture.WriteInside($"f{i}.md", new string('x', each)))
            .ToArray();

        var outcome = gate.Offer(draft, files, attachEnabled: true);

        // 4 x 32 KiB = 128 KiB, so the fifth crosses the per-send cap.
        Assert.Equal(4, outcome.Attached.Count);
        Assert.Equal(AttachmentPolicy.MaxSendAttachmentBytes, draft.Attachments.Sum(a => a.Bytes));
        var refusal = Assert.Single(outcome.Refusals);
        Assert.Contains(AttachmentPolicy.MaxSendAttachmentBytes.ToString(), refusal, StringComparison.Ordinal);
    }

    [Fact]
    public void C14_ThePerSendFileCountCapIsEnforced()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        var gate = fixture.Gate();

        var files = Enumerable.Range(0, AttachmentPolicy.MaxAttachmentsPerSend + 1)
            .Select(i => fixture.WriteInside($"s{i}.md", "one line\n"))
            .ToArray();

        var outcome = gate.Offer(draft, files, attachEnabled: true);

        Assert.Equal(AttachmentPolicy.MaxAttachmentsPerSend, outcome.Attached.Count);
        Assert.Contains(
            outcome.Refusals,
            r => r.Contains(AttachmentPolicy.MaxAttachmentsPerSend.ToString(), StringComparison.Ordinal));
    }

    [Fact]
    public void C14_AnAttachmentIsHeldAsTextAndIsNeverReReadAtSendTime()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        var file = fixture.WriteInside("note.md", "the original bytes\n");

        fixture.Gate().Offer(draft, [file], attachEnabled: true);
        var readsAfterAttach = fixture.Reader.ReadCount;

        // The file changes underneath. What was affirmed is what is sent.
        File.WriteAllText(file, "SOMETHING ELSE ENTIRELY\n");

        var compiled = ComposerCompiler.Compile(draft);

        Assert.Equal(readsAfterAttach, fixture.Reader.ReadCount);
        Assert.Contains("the original bytes", compiled.Text, StringComparison.Ordinal);
        Assert.DoesNotContain("SOMETHING ELSE", compiled.Text, StringComparison.Ordinal);
    }

    [Fact]
    public void C14_ANonUtf8FileIsRefusedAndTheRefusalNamesTheDetectedEncoding()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();

        var utf16 = Path.Combine(fixture.WorkspaceRoot, "windows-notes.md");
        File.WriteAllBytes(utf16, Encoding.Unicode.GetPreamble().Concat(Encoding.Unicode.GetBytes("hello")).ToArray());

        var outcome = fixture.Gate().Offer(draft, [utf16], attachEnabled: true);

        Assert.Empty(outcome.Attached);
        var refusal = Assert.Single(outcome.Refusals);
        Assert.Contains("UTF-16LE", refusal, StringComparison.Ordinal);
    }

    [Fact]
    public void C14_InvalidUtf8IsRefusedRatherThanDecodedLossily()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();

        var broken = Path.Combine(fixture.WorkspaceRoot, "broken.md");
        File.WriteAllBytes(broken, [0x68, 0x69, 0xC3, 0x28, 0x0A]);

        var outcome = fixture.Gate().Offer(draft, [broken], attachEnabled: true);

        Assert.Empty(outcome.Attached);
        Assert.Contains(outcome.Refusals, r => r.Contains("not valid UTF-8", StringComparison.Ordinal));
    }

    [Fact]
    public void C14_TheFenceHeaderNamesTheSourceItsByteCountAndWhereItCameFrom()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        var inside = fixture.WriteInside("src/Note.cs", "class Note { }\n");
        var outside = fixture.WriteOutside("spec.md", "outside content\n");

        fixture.Gate().Offer(draft, [inside, outside], attachEnabled: true);
        var text = ComposerCompiler.Compile(draft).Text;

        Assert.Contains("source=src/Note.cs", text, StringComparison.Ordinal);
        Assert.Contains("bytes=15", text, StringComparison.Ordinal);
        Assert.Contains("location=inside the workspace root", text, StringComparison.Ordinal);
        Assert.Contains($"source={outside}", text, StringComparison.Ordinal);
        Assert.Contains("location=OUTSIDE the workspace root", text, StringComparison.Ordinal);
    }

    [Fact]
    public void C14_AnAttachmentCarryingItsOwnFenceIsStillFullyEnclosed()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        var file = fixture.WriteInside("readme.md", "```\nnested\n```\ntail\n");

        fixture.Gate().Offer(draft, [file], attachEnabled: true);
        var text = ComposerCompiler.Compile(draft).Text;

        Assert.Contains("````" + ComposerCompiler.AttachmentFenceTag, text, StringComparison.Ordinal);
        Assert.Contains("tail", text, StringComparison.Ordinal);
    }

    [Fact]
    public void C14e_i_ADirectoryAndAnArchiveEachProduceZeroAttachmentsAndOneVisibleRefusal()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();

        var directory = Path.Combine(fixture.WorkspaceRoot, "docs");
        Directory.CreateDirectory(directory);
        fixture.WriteInside("docs/a.md", "a\n");
        fixture.WriteInside("docs/b.md", "b\n");

        var archive = fixture.WriteInside("bundle.zip", "not really a zip, and it never gets that far\n");

        var directoryOutcome = fixture.Gate().Offer(draft, [directory], attachEnabled: true);
        Assert.Empty(directoryOutcome.Attached);
        Assert.Single(directoryOutcome.Refusals);
        Assert.Contains("directory", directoryOutcome.Refusals[0], StringComparison.Ordinal);

        var archiveOutcome = fixture.Gate().Offer(draft, [archive], attachEnabled: true);
        Assert.Empty(archiveOutcome.Attached);
        Assert.Single(archiveOutcome.Refusals);
        Assert.Contains("archive", archiveOutcome.Refusals[0], StringComparison.Ordinal);

        Assert.Empty(draft.Attachments);
    }

    [Fact]
    public void C14e_i_AMultiSelectOfThreeProducesThreeSeparatelyAffirmedAttachments()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();

        var files = Enumerable.Range(0, 3)
            .Select(i => fixture.WriteOutside($"pick{i}.md", $"pick {i}\n"))
            .ToArray();

        var outcome = fixture.Gate().Offer(draft, files, attachEnabled: true);

        Assert.Equal(3, outcome.Attached.Count);
        Assert.Equal(3, fixture.Affirmation.Asked.Count);
        Assert.Equal(
            files.Select(AttachmentPolicy.RealPath),
            fixture.Affirmation.Asked.Select(a => a.AbsolutePath));
    }

    [Fact]
    public void C14e_ii_TheLabelFollowsARealLinkRatherThanThePick()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();

        fixture.WriteOutside("secret-notes.md", "outside content\n");
        var link = AttachmentFixture.LinkDirectory(
            Path.Combine(fixture.WorkspaceRoot, "linked"), fixture.Outside);

        var picked = Path.Combine(link, "secret-notes.md");
        var outcome = fixture.Gate().Offer(draft, [picked], attachEnabled: true);

        var attachment = Assert.Single(outcome.Attached);
        Assert.True(
            attachment.IsOutsideWorkspace,
            "a link inside the workspace pointing outside it was labelled INSIDE — the bypass with nobody lying");
        Assert.Single(fixture.Affirmation.Asked);
        Assert.Contains("location=OUTSIDE", ComposerCompiler.Compile(draft).Text, StringComparison.Ordinal);
    }

    [Fact]
    public void C14e_ii_TheRefusalSetIsAppliedToTheResolvedPathToo()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();

        var secrets = Path.Combine(fixture.Outside, ".ssh");
        Directory.CreateDirectory(secrets);
        File.WriteAllText(Path.Combine(secrets, "config"), "Host example\n");

        var link = AttachmentFixture.LinkDirectory(Path.Combine(fixture.WorkspaceRoot, "innocent"), secrets);
        var outcome = fixture.Gate().Offer(draft, [Path.Combine(link, "config")], attachEnabled: true);

        Assert.Empty(outcome.Attached);
        Assert.Contains(outcome.Refusals, r => r.Contains(".ssh", StringComparison.Ordinal));
    }

    [Fact]
    public void C14e_iii_NotOneByteIsReadWhileTheAffirmationIsPending()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        var outside = fixture.WriteOutside("brief.md", "the brief\n");

        fixture.Gate().Offer(draft, [outside], attachEnabled: true);

        Assert.Single(fixture.Affirmation.ReadCountWhenAsked);
        Assert.Equal(0, fixture.Affirmation.ReadCountWhenAsked[0]);
        Assert.Equal(1, fixture.Reader.ReadCount);
    }

    [Fact]
    public void C14e_iii_TheAffirmationNamesThePathTheByteCountTheProviderAndTheAccount()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        var outside = fixture.WriteOutside("brief.md", "the brief\n");

        fixture.Gate().Offer(draft, [outside], attachEnabled: true);

        var asked = Assert.Single(fixture.Affirmation.Asked);
        Assert.Equal(AttachmentPolicy.RealPath(outside), asked.AbsolutePath);
        Assert.Equal(10, asked.Bytes);
        Assert.Contains("Anthropic", asked.Prompt, StringComparison.Ordinal);
        Assert.Contains("max-personal", asked.Prompt, StringComparison.Ordinal);
        Assert.Contains(asked.AbsolutePath, asked.Prompt, StringComparison.Ordinal);
    }

    [Fact]
    public void C14e_iii_DecliningLeavesTheDraftByteUnchanged()
    {
        using var fixture = new AttachmentFixture
        {
            Affirmation = new ScriptedAffirmation(answer: false),
        };
        fixture.Affirmation.Reader = fixture.Reader;

        var draft = new ComposerDraft();
        draft.SetFreeFormText("the prompt as typed\n");
        var before = ComposerCompiler.Compile(draft).Text;

        var outside = fixture.WriteOutside("brief.md", "the brief\n");
        var outcome = fixture.Gate().Offer(draft, [outside], attachEnabled: true);

        Assert.Empty(outcome.Attached);
        Assert.Equal(0, fixture.Reader.ReadCount);
        Assert.Equal(before, ComposerCompiler.Compile(draft).Text);
    }

    [Fact]
    public void C14e_iii_AnInsideWorkspaceFileIsNeverAffirmed()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        var inside = fixture.WriteInside("src/Note.cs", "class Note { }\n");

        var outcome = fixture.Gate().Offer(draft, [inside], attachEnabled: true);

        Assert.Single(outcome.Attached);
        Assert.Empty(fixture.Affirmation.Asked);
    }

    [Theory]
    // The original organising idea: well-known secret filenames.
    [InlineData(".env")]
    [InlineData(".env.local")]
    [InlineData("server.pem")]
    [InlineData("private.key")]
    [InlineData("cert.p12")]
    [InlineData("cert.pfx")]
    [InlineData("id_rsa")]
    [InlineData("id_rsa.pub")]
    [InlineData("id_ed25519")]
    [InlineData(".npmrc")]
    [InlineData(".netrc")]
    [InlineData(".git-credentials")]
    [InlineData("credentials")]
    [InlineData("vault.kdbx")]
    // The SECOND CLASS: an in-repo config file carrying a third party's credentials in an env or
    // settings block. `.mcp.json` is why the list grew by a class rather than by a name.
    [InlineData(".mcp.json")]
    [InlineData(".mcp.json.tmp")]
    [InlineData("docker-compose.yml")]
    [InlineData("docker-compose.override.yml")]
    [InlineData("prod.tfvars")]
    [InlineData("local.settings.json")]
    [InlineData("appsettings.Production.json")]
    public void C14e_iv_TheCategoricalRefusalSetRefusesByNameWhateverTheHumanPicked(string name)
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        var file = fixture.WriteInside(name, "ANTHROPIC_API_KEY=sk-not-a-real-key\n");

        var outcome = fixture.Gate().Offer(draft, [file], attachEnabled: true);

        Assert.Empty(outcome.Attached);
        var refusal = Assert.Single(outcome.Refusals);
        Assert.Contains("categorical refusal set", refusal, StringComparison.Ordinal);
    }

    [Theory]
    [InlineData(".git/config")]
    [InlineData(".ssh/known_hosts")]
    [InlineData(".aws/config")]
    [InlineData(".azure/profile.json")]
    [InlineData(".gnupg/gpg.conf")]
    [InlineData(".kube/config.txt")]
    [InlineData(".config/gh/hosts.txt")]
    [InlineData(".vscode/mcp.json")]
    [InlineData(".cursor/mcp.json")]
    [InlineData(".devcontainer/devcontainer.json")]
    [InlineData("User Data/Default/profile.txt")]
    public void C14e_iv_TheRefusalSetAlsoRefusesByDirectory(string relativePath)
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        var file = fixture.WriteInside(relativePath, "secret\n");

        var outcome = fixture.Gate().Offer(draft, [file], attachEnabled: true);

        Assert.Empty(outcome.Attached);
        Assert.Contains(outcome.Refusals, r => r.Contains("categorical refusal set", StringComparison.Ordinal));
    }

    [Theory]
    // A deny-list that also denies the neighbours is a different defect.
    [InlineData("env.md")]
    [InlineData("keynote.md")]
    [InlineData("environment.md")]
    [InlineData("mcp.json")]
    [InlineData("appsettings.json")]
    [InlineData("credentials-policy.md")]
    [InlineData("compose.md")]
    public void C14e_iv_ANearMissIsStillAttached(string name)
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        var file = fixture.WriteInside(name, "ordinary content\n");

        var outcome = fixture.Gate().Offer(draft, [file], attachEnabled: true);

        Assert.Empty(outcome.Refusals);
        Assert.Single(outcome.Attached);
    }

    [Fact]
    public void C14e_v_TheCompiledViewRendersEveryByteThatWillBeSent()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();

        var body = string.Join("\n", Enumerable.Range(0, 800).Select(i => $"line {i} of the attachment"));
        var file = fixture.WriteInside("long.md", body);

        fixture.Gate().Offer(draft, [file], attachEnabled: true);
        var compiled = ComposerCompiler.Compile(draft);

        // The VIEW is this string. Nothing truncates, elides or virtualizes it, so the rendered
        // length and the sent length are one number.
        Assert.Contains("line 799 of the attachment", compiled.Text, StringComparison.Ordinal);
        Assert.Equal(body.Length, draft.Attachments[0].Bytes);
        Assert.Equal(body, draft.Attachments[0].Text);
        Assert.Contains(body, compiled.Text, StringComparison.Ordinal);
    }

    [Fact]
    public void C14e_vi_TheRunningTotalAndTheCapAreBothNamedWhenASendIsRefused()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();
        var gate = fixture.Gate();

        // 4 x 30,000 = 120,000, which is under the 131,072 cap; a 20,000-byte fifth crosses it. The
        // two numbers in the refusal are therefore DIFFERENT, which is what makes "names the current
        // total AND the cap" a real assertion rather than one number read twice.
        foreach (var name in new[] { "a.md", "b.md", "c.md", "d.md" })
        {
            gate.Offer(draft, [fixture.WriteInside(name, new string('x', 30_000))], attachEnabled: true);
        }

        Assert.Equal(120_000, draft.Attachments.Sum(a => a.Bytes));

        var outcome = gate.Offer(
            draft, [fixture.WriteInside("e.md", new string('x', 20_000))], attachEnabled: true);

        var refusal = Assert.Single(outcome.Refusals);
        Assert.Contains("120000", refusal, StringComparison.Ordinal);
        Assert.Contains(AttachmentPolicy.MaxSendAttachmentBytes.ToString(), refusal, StringComparison.Ordinal);
        Assert.Contains("already carries", refusal, StringComparison.Ordinal);
    }

    [Fact]
    [Trait("Platform", "Windows")]
    public void C14e_ii_ADirectoryJunctionInThePathPrefixIsResolvedBeforeTheInsideOutsideTest()
    {
        using var fixture = new AttachmentFixture();
        var draft = new ComposerDraft();

        var deep = Path.Combine(fixture.Outside, "nested", "deeper");
        Directory.CreateDirectory(deep);
        File.WriteAllText(Path.Combine(deep, "brief.md"), "from outside\n");

        var junction = AttachmentFixture.LinkDirectory(
            Path.Combine(fixture.WorkspaceRoot, "vendor"), Path.Combine(fixture.Outside, "nested"));

        var picked = Path.Combine(junction, "deeper", "brief.md");
        var outcome = fixture.Gate().Offer(draft, [picked], attachEnabled: true);

        var attachment = Assert.Single(outcome.Attached);
        Assert.True(attachment.IsOutsideWorkspace, "a junction in the PREFIX was not resolved before the label was computed");
        Assert.StartsWith(AttachmentPolicy.RealPath(fixture.Outside), attachment.ResolvedPath, StringComparison.Ordinal);
    }
}
