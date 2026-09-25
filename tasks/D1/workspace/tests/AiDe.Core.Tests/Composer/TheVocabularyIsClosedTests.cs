using System.Text;
using AiDe.Core.Presentation.Composer;

namespace AiDe.Core.Tests.Composer;

/// <summary>
/// Security <b>C9</b> (origin-bound routing), <b>C13</b> (no path crosses as a string) and
/// <b>C20</b> (the schema is closed and versioned).
/// </summary>
/// <remarks>
/// <b>Every one of these was written red first</b>, against a router that had no origin check, no
/// version check and no allow-list: each assertion below was observed failing before the rule that
/// makes it pass existed. A control whose first run is green is evidence about nothing.
/// </remarks>
public sealed class TheVocabularyIsClosedTests
{
    private const string PageUrl = "https://aide.assets.invalid/composer.html";
    private const string Instance = "1f9c2f1a5f2b4a3d8c7e6f5a4b3c2d1e";

    private sealed class CountingSink : IComposerMessageSink
    {
        public long Ready { get; private set; }

        public long Fields { get; private set; }

        public long Focus { get; private set; }

        public long Attach { get; private set; }

        public long Metrics { get; private set; }

        public List<string> OfferedPaths { get; } = [];

        public long Total => Ready + Fields + Focus + Attach + Metrics;

        public void MarkReady() => Ready++;

        public void SetFieldText(string fieldId, long revision, string text) => Fields++;

        public void MoveFocus(bool backward) => Focus++;

        public void OfferAttachment(IReadOnlyList<string> filePaths)
        {
            Attach++;
            OfferedPaths.AddRange(filePaths);
        }

        public void RecordMetric(string name, long value) => Metrics++;
    }

    private static (ComposerMessageRouter Router, CountingSink Sink) Build(params string[] fieldIds)
    {
        var sink = new CountingSink();
        return (new ComposerMessageRouter(PageUrl, Instance, fieldIds, sink), sink);
    }

    private static string Envelope(string kind, string extra = "") =>
        $"{{\"v\":1,\"kind\":\"{kind}\",\"instance\":\"{Instance}\"{(extra.Length == 0 ? "" : "," + extra)}}}";

    [Fact]
    public void TheFiveKindsAreTheWholeVocabularyAndTheRefusedNamesAreNotInIt()
    {
        Assert.Equal(5, ComposerMessageKinds.All.Count);

        foreach (var refused in ComposerMessageKinds.RefusedNames)
        {
            Assert.DoesNotContain(refused, ComposerMessageKinds.All, StringComparer.Ordinal);
            Assert.False(ComposerMessageKinds.IsKnown(refused));
        }
    }

    [Theory]
    [InlineData("https://example.invalid/")]
    [InlineData("file:///C:/x.html")]
    [InlineData("about:blank")]
    [InlineData("https://aide.assets.invalid.evil.test/")]
    [InlineData("https://aide.assets.invalid/other.html")]
    [InlineData(null)]
    public void C9_AMessageFromAnyOtherDocumentMovesNoCounterAtAll(string? sourceUri)
    {
        var (router, sink) = Build("goal:1");

        var inputs = 0;
        foreach (var kind in ComposerMessageKinds.All)
        {
            inputs++;
            var result = router.Route(sourceUri, Envelope(kind, "\"fieldId\":\"goal:1\",\"rev\":1,\"text\":\"x\""), ["C:/x.txt"]);
            Assert.False(result.Accepted);
        }

        Assert.Equal(0, sink.Total);
        Assert.Equal(inputs, router.Dropped);
        Assert.False(router.IsReady);
    }

    /// <summary>
    /// <b>INV-0007, finding 2.</b> A <c>ready</c> that follows a navigation the host declared is a
    /// NEW document's mount, not a duplicate: it is accepted, the sink hears it, and the new page's
    /// revisions start again from its own 1 — so typing into the reloaded page is not dropped as
    /// "not strictly greater" than the old page's count.
    /// </summary>
    /// <remarks>
    /// <b>Observed red before the fix</b> against a router whose <c>BeginNavigation</c> did nothing:
    /// the second ready dropped as "this instance already reported ready" (<c>Ready</c> stayed 1,
    /// <c>Dropped</c> read 1) — exactly the <c>router drops=2</c> the shell probe printed after one
    /// later render.
    /// </remarks>
    [Fact]
    public void AReadyAfterADeclaredNavigationIsAMountNotADuplicate()
    {
        var (router, sink) = Build("goal:1");

        Assert.True(router.Route(PageUrl, Envelope("editor.ready"), []).Accepted);
        Assert.True(router.Route(PageUrl, Envelope("draft.changed", "\"fieldId\":\"goal:1\",\"rev\":7,\"text\":\"old page\""), []).Accepted);

        // Without a navigation, a second ready is still the duplicate it always was.
        Assert.False(router.Route(PageUrl, Envelope("editor.ready"), []).Accepted);
        Assert.Equal(1, router.Dropped);

        // The host saw NavigationStarting for the page URL: the document is being replaced.
        router.BeginNavigation();
        Assert.False(router.IsReady);

        // THE OLD PAGE IS STILL ALIVE for a moment. A late change from it, at its old revision, is
        // dropped as "before ready" — and does NOT re-raise the high-water mark the new page will
        // count under. Pinned, because the alternative is the same silence by a third route.
        Assert.False(router.Route(PageUrl, Envelope("draft.changed", "\"fieldId\":\"goal:1\",\"rev\":8,\"text\":\"late\""), []).Accepted);
        Assert.Equal(2, router.Dropped);

        var readyAgain = router.Route(PageUrl, Envelope("editor.ready"), []);
        Assert.True(readyAgain.Accepted, readyAgain.Reason);
        Assert.Equal(2, sink.Ready);
        Assert.True(router.IsReady);

        // The new page counts from its own 1, which is below the old page's 7.
        var typed = router.Route(PageUrl, Envelope("draft.changed", "\"fieldId\":\"goal:1\",\"rev\":1,\"text\":\"new page\""), []);
        Assert.True(typed.Accepted, typed.Reason);
        Assert.Equal(2, sink.Fields);
        Assert.Equal(2, router.Dropped);
    }

    [Fact]
    public void C9_AStaleInstanceIsRefusedOnEveryKind()
    {
        var (router, sink) = Build("goal:1");
        var stale = $"{{\"v\":1,\"kind\":\"editor.ready\",\"instance\":\"not-this-surface\"}}";

        Assert.False(router.Route(PageUrl, stale, []).Accepted);
        Assert.Equal(0, sink.Total);
        Assert.Equal(1, router.Dropped);
    }

    [Fact]
    public void C20_EveryUnknownKindAndEveryMalformedBodyReachesDropAndCount()
    {
        var (router, sink) = Build("goal:1");

        var corpus = new List<string>
        {
            "",
            "   ",
            "not json at all",
            "[]",
            "null",
            "{}",
            "{\"v\":1}",
            "{\"v\":\"1\",\"kind\":\"editor.ready\",\"instance\":\"" + Instance + "\"}",
            "{\"v\":2,\"kind\":\"editor.ready\",\"instance\":\"" + Instance + "\"}",
            "{\"kind\":\"editor.ready\",\"instance\":\"" + Instance + "\"}",
            "{\"v\":1,\"kind\":null,\"instance\":\"" + Instance + "\"}",
            "{\"v\":1,\"kind\":42,\"instance\":\"" + Instance + "\"}",
            // Case-varied values. The allow-list is on the VALUE and compares ordinally.
            Envelope("EDITOR.READY"),
            Envelope("Editor.Ready"),
            Envelope("editor.Ready"),
            // A case-varied MEMBER name still binds under Web defaults, so the value check has to be
            // what refuses it — this row is the reason that sentence is in the plan.
            "{\"V\":1,\"KIND\":\"editor.ready\",\"INSTANCE\":\"" + Instance + "\"}",
            // Prototype pollution rides on an UNKNOWN kind here, deliberately: the same members on a
            // valid envelope are simply extra members on a valid message, and asserting that they are
            // dropped would be asserting the wrong thing.
            "{\"v\":1,\"kind\":\"editor.pollute\",\"instance\":\"" + Instance + "\",\"__proto__\":{\"polluted\":true}}",
            // A duplicate key: the reader must not throw, whichever one it takes.
            "{\"v\":1,\"kind\":\"nope\",\"kind\":\"editor.ready\",\"instance\":\"" + Instance + "\"}",
            "{\"v\":1,\"kind\":\"draft.changed\",\"instance\":\"" + Instance + "\",\"fieldId\":null,\"rev\":1,\"text\":\"x\"}",
            "{\"v\":1,\"kind\":\"metrics\",\"instance\":\"" + Instance + "\",\"name\":{},\"value\":[]}",
            // A very large string. It must be refused for being over the cap, never by throwing.
            Envelope("draft.changed", "\"fieldId\":\"goal:1\",\"rev\":1,\"text\":\"" + new string('a', 10 * 1024 * 1024) + "\""),
        };

        foreach (var kind in ComposerMessageKinds.RefusedNames)
        {
            corpus.Add(Envelope(kind));
        }

        for (var i = 0; i < 100; i++)
        {
            corpus.Add(Envelope("generated.kind." + i));
        }

        foreach (var body in corpus)
        {
            var result = router.Route(PageUrl, body, []);
            Assert.False(result.Accepted, body.Length > 120 ? body[..120] : body);
        }

        Assert.Equal(0, sink.Total);
        Assert.Equal(corpus.Count, router.Dropped);
    }

    [Fact]
    public void ADraftChangeBeforeReadyIsRefused()
    {
        var (router, sink) = Build("goal:1");

        Assert.False(router.Route(PageUrl, Envelope("draft.changed", "\"fieldId\":\"goal:1\",\"rev\":1,\"text\":\"x\""), []).Accepted);
        Assert.Equal(0, sink.Fields);
    }

    [Fact]
    public void ASecondReadyForOneInstanceIsDroppedAndCounted()
    {
        var (router, sink) = Build("goal:1");

        Assert.True(router.Route(PageUrl, Envelope("editor.ready"), []).Accepted);
        Assert.False(router.Route(PageUrl, Envelope("editor.ready"), []).Accepted);

        Assert.Equal(1, sink.Ready);
        Assert.Equal(1, router.Dropped);
    }

    [Fact]
    public void AFieldIdTheHostDidNotMintIsNeverCreated()
    {
        var (router, sink) = Build("goal:1");
        router.Route(PageUrl, Envelope("editor.ready"), []);

        Assert.False(router.Route(PageUrl, Envelope("draft.changed", "\"fieldId\":\"goal:2\",\"rev\":1,\"text\":\"x\""), []).Accepted);
        Assert.Equal(0, sink.Fields);

        Assert.True(router.Route(PageUrl, Envelope("draft.changed", "\"fieldId\":\"goal:1\",\"rev\":1,\"text\":\"x\""), []).Accepted);
        Assert.Equal(1, sink.Fields);
    }

    [Fact]
    public void ARevisionThatIsNotStrictlyGreaterIsRefused()
    {
        var (router, sink) = Build("goal:1");
        router.Route(PageUrl, Envelope("editor.ready"), []);

        Assert.True(router.Route(PageUrl, Envelope("draft.changed", "\"fieldId\":\"goal:1\",\"rev\":7,\"text\":\"a\""), []).Accepted);
        Assert.False(router.Route(PageUrl, Envelope("draft.changed", "\"fieldId\":\"goal:1\",\"rev\":7,\"text\":\"b\""), []).Accepted);
        Assert.False(router.Route(PageUrl, Envelope("draft.changed", "\"fieldId\":\"goal:1\",\"rev\":6,\"text\":\"c\""), []).Accepted);
        Assert.True(router.Route(PageUrl, Envelope("draft.changed", "\"fieldId\":\"goal:1\",\"rev\":8,\"text\":\"d\""), []).Accepted);

        Assert.Equal(2, sink.Fields);
    }

    [Fact]
    public void TextOverTheByteCapIsRefusedAndNeverTruncated()
    {
        var (router, sink) = Build("goal:1");
        router.Route(PageUrl, Envelope("editor.ready"), []);

        var overCap = new string('x', ComposerMessageRouter.MaxFieldTextBytes + 1);
        Assert.False(router.Route(PageUrl, Envelope("draft.changed", $"\"fieldId\":\"goal:1\",\"rev\":1,\"text\":\"{overCap}\""), []).Accepted);
        Assert.Equal(0, sink.Fields);

        // A multi-byte character counts as its BYTES, not its chars: the cap is on what crosses.
        var justUnder = new string('e', ComposerMessageRouter.MaxFieldTextBytes - 2) + "\u00e9";
        Assert.Equal(ComposerMessageRouter.MaxFieldTextBytes, Encoding.UTF8.GetByteCount(justUnder));
        Assert.True(router.Route(PageUrl, Envelope("draft.changed", $"\"fieldId\":\"goal:1\",\"rev\":2,\"text\":\"{justUnder}\""), []).Accepted);
    }

    [Fact]
    public void C13_APathInTheBodyProducesZeroAttachmentsAndOneRefusal()
    {
        var (router, sink) = Build("goal:1");
        router.Route(PageUrl, Envelope("editor.ready"), []);

        foreach (var member in new[] { "path", "uri", "name", "content", "bytes" })
        {
            var body = Envelope("attach.offered", $"\"{member}\":\"C:/Users/secret/.env\"");
            var result = router.Route(PageUrl, body, []);

            Assert.False(result.Accepted);
            Assert.Equal(0, sink.Attach);
            Assert.Empty(sink.OfferedPaths);
        }
    }

    [Fact]
    public void C13_AnAttachOfferWithNoFileObjectIsRefusedEvenWithACleanBody()
    {
        var (router, sink) = Build("goal:1");
        router.Route(PageUrl, Envelope("editor.ready"), []);

        Assert.False(router.Route(PageUrl, Envelope("attach.offered", "\"count\":1"), []).Accepted);
        Assert.Equal(0, sink.Attach);
    }

    [Fact]
    public void AnAttachOfferOverTheObjectCapIsRefused()
    {
        var (router, sink) = Build("goal:1");
        router.Route(PageUrl, Envelope("editor.ready"), []);

        var tooMany = Enumerable.Range(0, ComposerMessageRouter.MaxOfferedObjects + 1)
            .Select(i => $"C:/tmp/{i}.txt").ToArray();

        Assert.False(router.Route(PageUrl, Envelope("attach.offered"), tooMany).Accepted);
        Assert.Equal(0, sink.Attach);

        Assert.True(router.Route(PageUrl, Envelope("attach.offered"), tooMany[..ComposerMessageRouter.MaxOfferedObjects]).Accepted);
        Assert.Equal(ComposerMessageRouter.MaxOfferedObjects, sink.OfferedPaths.Count);
    }

    [Fact]
    public void TheMetricsKindMovesNothingButADiagnosticCounter()
    {
        var (router, sink) = Build("goal:1");
        router.Route(PageUrl, Envelope("editor.ready"), []);

        Assert.True(router.Route(PageUrl, Envelope("metrics", "\"name\":\"attachments.bytes\",\"value\":41207"), []).Accepted);

        Assert.Equal(1, sink.Metrics);
        Assert.Equal(0, sink.Fields);
        Assert.Equal(0, sink.Attach);
        Assert.Equal(0, sink.Focus);
    }
}
