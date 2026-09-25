using System.Reflection;
using System.Text;
using System.Text.Json.Nodes;
using AiDe.Core.PromptCompilation;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.PromptCompilation;

/// <summary>
/// ADR-0034's falsifying tests 1–3 and 6 (the store half): the store's public surface is
/// <c>Append</c> and a reader; the chain refuses a torn or flipped file; two writers see one refusal;
/// the walk is schema-agnostic; the lifetime is the caller's handle.
/// </summary>
/// <remarks>
/// <b>Red first (recorded in the Proof Pack):</b> no <c>AiDe.Core.PromptCompilation</c> namespace existed
/// when these were written — the first run of this file is a compile failure of the test project,
/// which is the red for a type that does not exist.
/// </remarks>
public sealed class TheEnvelopeStoreIsAppendOnlyTests : IDisposable
{
    private readonly string _workspace = Path.Combine(Path.GetTempPath(), "aide-envelope-" + Guid.NewGuid().ToString("n")[..8]);
    private const string SessionA = "20260912T100000Z-0000aaaa";

    public TheEnvelopeStoreIsAppendOnlyTests() => Directory.CreateDirectory(SessionPaths.SessionDirectory(_workspace, SessionA));

    public void Dispose()
    {
        try { Directory.Delete(_workspace, recursive: true); } catch (IOException) { }
        GC.SuppressFinalize(this);
    }

    private string SessionDir => SessionPaths.SessionDirectory(_workspace, SessionA);
    private string FilePath => Path.Combine(SessionDir, EnvelopeStore.FileName);

    private static Opened OpenedRow(string envelopeId, string sessionId = SessionA, string text = "Refactor @src/A/") =>
        new(envelopeId, text, sessionId, "claude-code", CompileModes.MechanicalOnly, null, PreCompile.ConstantsFor(PreCompile.ProjectorVersion));

    // ── test 1: the surface ──

    /// <summary>ADR-0034 test 1: reflection over the store finds <c>Append</c> and a reader only — no update, delete or rewrite member.</summary>
    [Fact]
    public void ThePublicSurfaceIsAppendAndAReaderOnly()
    {
        var members = typeof(EnvelopeStore)
            .GetMembers(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly)
            .Where(m => m.MemberType is MemberTypes.Method or MemberTypes.Property or MemberTypes.Constructor or MemberTypes.Field)
            .Where(m => m is not MethodInfo { IsSpecialName: true })   // property accessors are listed by their property
            .Select(m => m.Name)
            .Order(StringComparer.Ordinal)
            .ToList();

        // NAMED, not counted: the exact surface. A `Rewrite`, `Delete`, `Update`, `Truncate` or
        // `Remove` member appears here by name and fails the equality.
        Assert.Equal(
            new[]
            {
                nameof(EnvelopeStore.Append),
                nameof(EnvelopeStore.BrokenAt),
                nameof(EnvelopeStore.Dispose),
                nameof(EnvelopeStore.FileName),
                nameof(EnvelopeStore.Open),
                nameof(EnvelopeStore.OpenReport),
                nameof(EnvelopeStore.Path),
                nameof(EnvelopeStore.Read),
                nameof(EnvelopeStore.ReadFile),
                nameof(EnvelopeStore.Schema),
                nameof(EnvelopeStore.SessionId),
            }.Order(StringComparer.Ordinal),
            members);

        Assert.DoesNotContain(members, m =>
            m.Contains("Update", StringComparison.OrdinalIgnoreCase)
            || m.Contains("Delete", StringComparison.OrdinalIgnoreCase)
            || m.Contains("Rewrite", StringComparison.OrdinalIgnoreCase)
            || m.Contains("Remove", StringComparison.OrdinalIgnoreCase)
            || m.Contains("Truncate", StringComparison.OrdinalIgnoreCase)
            || m.Contains("Clear", StringComparison.OrdinalIgnoreCase));

        // AND THE NON-PUBLIC, NON-PRIVATE SURFACE IS EXACTLY THE FAULT SEAM: an `internal` writer
        // would be invisible to the public census above and visible to this test project.
        var nonPublic = typeof(EnvelopeStore)
            .GetMembers(BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly)
            .Where(m => m is MethodInfo { IsAssembly: true } or MethodInfo { IsFamilyOrAssembly: true } or FieldInfo { IsAssembly: true } or PropertyInfo)
            .Where(m => m is not PropertyInfo p || (p.GetMethod?.IsAssembly ?? false))
            .Select(m => m.Name)
            .ToList();
        Assert.Equal(["OpenWith"], nonPublic);
    }

    /// <summary>ADR-0034 rule 3: an append that throws after a good open latches the store — nothing is appended until a reopen walks the real tail (the D&amp;P lens's condition).</summary>
    [Fact]
    public void AnAppendThatThrowsAfterOpenLatchesTheStoreUntilItIsReopened()
    {
        using (var seed = EnvelopeStore.Open(SessionDir))
        {
            seed.Append(OpenedRow("e1"));
        }

        var faulting = new FaultingStream();
        using (var store = EnvelopeStore.OpenWith(SessionDir, inner => faulting.Over(inner)))
        {
            store.Append(new Decorated("e1", "goal", JsonValue.Create("g"), DecorationSources.Operator));   // a good append first

            faulting.FailAfterBytes = 20;   // the next write lands a prefix, then throws — disk full mid-row
            var refused = Assert.Throws<EnvelopeStoreException>(() =>
                store.Append(new Decorated("e1", "done_when", JsonValue.Create("d"), DecorationSources.Operator)));
            Assert.Equal(EnvelopeStoreErrorCodes.AppendFailed, refused.Code);

            // LATCHED: a later append is refused with the earlier failure named — it does not glue a
            // row to the partial prefix.
            faulting.FailAfterBytes = null;
            var latched = Assert.Throws<EnvelopeStoreException>(() =>
                store.Append(new Consumed("e1", "r", null, "Completed", ConsumedReasons.Completed)));
            Assert.Equal(EnvelopeStoreErrorCodes.AppendFailed, latched.Code);
            Assert.Contains("until the store is reopened", latched.Message, StringComparison.Ordinal);
        }

        // A reopen walks the real tail: the partial row is a torn last line (counted), the chain is
        // whole up to it, the next seq is unique, and the appended row chains over the torn bytes.
        using var reopened = EnvelopeStore.Open(SessionDir);
        Assert.Null(reopened.BrokenAt);
        Assert.Equal(1, reopened.Read().SkippedTorn);
        var next = reopened.Append(new Decorated("e1", "done_when", JsonValue.Create("d"), DecorationSources.Operator));
        Assert.Equal(3, next.Seq);
        reopened.Dispose();
        Assert.Null(EnvelopeStore.ReadFile(FilePath).BrokenAt);
    }

    /// <summary>A stream that lands a prefix of one write and then throws — the disk-full shape.</summary>
    private sealed class FaultingStream
    {
        public int? FailAfterBytes { get; set; }

        public Stream Over(Stream inner) => new Wrapper(inner, this);

        private sealed class Wrapper(Stream inner, FaultingStream owner) : Stream
        {
            public override bool CanRead => inner.CanRead;
            public override bool CanSeek => inner.CanSeek;
            public override bool CanWrite => inner.CanWrite;
            public override long Length => inner.Length;
            public override long Position { get => inner.Position; set => inner.Position = value; }
            public override void Flush() => inner.Flush();
            public override int Read(byte[] buffer, int offset, int count) => inner.Read(buffer, offset, count);
            public override long Seek(long offset, SeekOrigin origin) => inner.Seek(offset, origin);
            public override void SetLength(long value) => inner.SetLength(value);
            public override void Write(byte[] buffer, int offset, int count) => Write(buffer.AsSpan(offset, count));
            public override void Write(ReadOnlySpan<byte> buffer)
            {
                if (owner.FailAfterBytes is { } n && buffer.Length > n)
                {
                    inner.Write(buffer[..n]);
                    inner.Flush();
                    throw new IOException("There is not enough space on the disk.");
                }

                inner.Write(buffer);
            }

            protected override void Dispose(bool disposing)
            {
                if (disposing) inner.Dispose();
                base.Dispose(disposing);
            }
        }
    }

    [Fact]
    public void AnAppendedSeqAtOrBelowTheLastIsRefused()
    {
        using var store = EnvelopeStore.Open(SessionDir);
        var opened = store.Append(OpenedRow("e1"));
        Assert.Equal(1, opened.Seq);
        var second = store.Append(new Decorated("e1", "task_class", JsonValue.Create("free-form"), DecorationSources.SessionDefault));
        Assert.Equal(2, second.Seq);

        var refused = Assert.Throws<EnvelopeStoreException>(() =>
            store.Append(new Decorated("e1", "goal", JsonValue.Create("g"), DecorationSources.Operator) { Seq = 2 }));
        Assert.Equal(EnvelopeStoreErrorCodes.SeqNotIncreasing, refused.Code);

        // Nothing landed: the file holds exactly the two rows.
        Assert.Equal(2, store.Read().Rows);
    }

    [Fact]
    public void ADecoratedAfterAnAcceptedSubmittedIsRefused()
    {
        using var store = EnvelopeStore.Open(SessionDir);
        store.Append(OpenedRow("e1"));
        store.Append(new Submitted("e1", Accepted: true, Refusal: null, TextSha256: "t", ProjectionSha: "p", ProjectorVersion: "1"));

        var refused = Assert.Throws<EnvelopeStoreException>(() =>
            store.Append(new Decorated("e1", "goal", JsonValue.Create("late"), DecorationSources.Operator)));
        Assert.Equal(EnvelopeStoreErrorCodes.DecoratedAfterSubmitted, refused.Code);

        // A REFUSED submitted does not close the envelope: a later decorated and a later accepted
        // submitted are both admitted (US-D6/US-D7: exactly one ACCEPTED submitted).
        store.Append(OpenedRow("e2"));
        store.Append(new Submitted("e2", Accepted: false, Refusal: "stale", TextSha256: "t", ProjectionSha: "p", ProjectorVersion: "1"));
        store.Append(new Decorated("e2", "goal", JsonValue.Create("g"), DecorationSources.Operator));
        store.Append(new Submitted("e2", Accepted: true, Refusal: null, TextSha256: "t", ProjectionSha: "p", ProjectorVersion: "1"));
        Assert.Throws<EnvelopeStoreException>(() =>
            store.Append(new Submitted("e2", Accepted: true, Refusal: null, TextSha256: "t", ProjectionSha: "p", ProjectorVersion: "1")));
    }

    [Fact]
    public void ABodyMemberOnAnAttachmentValueIsRefused()
    {
        using var store = EnvelopeStore.Open(SessionDir);
        store.Append(OpenedRow("e1"));

        var withBody = new JsonArray(new JsonObject { ["path"] = "src/x.cs", ["sha256"] = "abc", ["bytes"] = 3, ["body"] = "class X {}" });
        var refused = Assert.Throws<EnvelopeStoreException>(() =>
            store.Append(new Decorated("e1", DecorationNames.Attachments, withBody, DecorationSources.Mechanical)));
        Assert.Equal(EnvelopeStoreErrorCodes.AttachmentBodyRefused, refused.Code);

        var byReference = new JsonArray(new JsonObject { ["path"] = "src/x.cs", ["sha256"] = "abc", ["bytes"] = 3, ["outside_workspace"] = false });
        store.Append(new Decorated("e1", DecorationNames.Attachments, byReference, DecorationSources.Mechanical));
    }

    /// <summary>US-D1: no decoration is ever named <c>lease</c> (DM-A), in any case.</summary>
    [Theory]
    [InlineData("lease")]
    [InlineData("Lease")]
    [InlineData("LEASE")]
    public void ADecorationNamedLeaseIsRefused(string name)
    {
        using var store = EnvelopeStore.Open(SessionDir);
        store.Append(OpenedRow("e1"));
        var refused = Assert.Throws<EnvelopeStoreException>(() =>
            store.Append(new Decorated("e1", name, JsonValue.Create("src/**"), DecorationSources.Operator)));
        Assert.Equal(EnvelopeStoreErrorCodes.DecorationNameRefused, refused.Code);
    }

    /// <summary>US-D1: an <c>operator</c> row may never carry a settings name — the ceilings have one home.</summary>
    [Theory]
    [InlineData("ceilings")]
    [InlineData("fan_out_effective")]
    [InlineData("budget")]
    [InlineData("shape")]
    public void AnOperatorRowNamedASettingOrAProjectionIsRefused(string name)
    {
        using var store = EnvelopeStore.Open(SessionDir);
        store.Append(OpenedRow("e1"));
        var refused = Assert.Throws<EnvelopeStoreException>(() =>
            store.Append(new Decorated("e1", name, JsonValue.Create(3), DecorationSources.Operator)));
        Assert.Equal(EnvelopeStoreErrorCodes.DecorationNameRefused, refused.Code);
    }

    /// <summary>§A9 input (14) at the store: a tier row outside {T0, T1, T2} is refused and the prior row stands.</summary>
    [Fact]
    public void ATierRowOutsideTheThreeTiersIsRefusedAtTheStore()
    {
        using var store = EnvelopeStore.Open(SessionDir);
        store.Append(OpenedRow("e1"));
        store.Append(new Decorated("e1", DecorationNames.Tier, JsonValue.Create("T2"), DecorationSources.Operator));

        var refused = Assert.Throws<EnvelopeStoreException>(() =>
            store.Append(new Decorated("e1", DecorationNames.Tier, JsonValue.Create("T9"), DecorationSources.Operator)));
        Assert.Equal(EnvelopeStoreErrorCodes.TierRefused, refused.Code);
        Assert.Equal("T2", store.Read().Envelopes.Single().Current(DecorationNames.Tier)!.ValueAsString);
    }

    /// <summary>A setting, a ref or a projection has one mechanical writer: a derived row named like one is refused too (C5), not only an operator row.</summary>
    [Theory]
    [InlineData("ceilings", DecorationSources.Derived)]
    [InlineData("attachments", DecorationSources.Derived)]
    [InlineData("shape", DecorationSources.Derived)]
    [InlineData("fan_out_effective", DecorationSources.SessionDefault)]
    public void ANonMechanicalRowNamedASettingARefOrAProjectionIsRefused(string name, string source)
    {
        using var store = EnvelopeStore.Open(SessionDir);
        store.Append(OpenedRow("e1"));
        var refused = Assert.Throws<EnvelopeStoreException>(() =>
            store.Append(new Decorated("e1", name, JsonValue.Create("x"), source)));
        Assert.Equal(EnvelopeStoreErrorCodes.DecorationNameRefused, refused.Code);
    }

    /// <summary>The attachment refs are an allow-list of four scalars, so a nested, re-cased or extra member is refused as a body would be.</summary>
    [Theory]
    [InlineData("{\"path\":\"x\",\"sha256\":\"a\",\"bytes\":1,\"outside_workspace\":false,\"meta\":{\"body\":\"hidden\"}}")]
    [InlineData("{\"path\":\"x\",\"sha256\":\"a\",\"bytes\":1,\"outside_workspace\":false,\"Body\":\"re-cased\"}")]
    [InlineData("{\"path\":\"x\",\"sha256\":\"a\",\"bytes\":1,\"outside_workspace\":false,\"content\":\"x\"}")]
    [InlineData("{\"path\":{\"nested\":true},\"sha256\":\"a\",\"bytes\":1,\"outside_workspace\":false}")]
    [InlineData("{\"path\":\"x\",\"sha256\":\"a\",\"bytes\":1}")]
    public void AnAttachmentValueOutsideTheFourScalarsIsRefused(string element)
    {
        using var store = EnvelopeStore.Open(SessionDir);
        store.Append(OpenedRow("e1"));
        var refused = Assert.Throws<EnvelopeStoreException>(() =>
            store.Append(new Decorated("e1", DecorationNames.Attachments, new JsonArray(JsonNode.Parse(element)), DecorationSources.Mechanical)));
        Assert.Equal(EnvelopeStoreErrorCodes.AttachmentBodyRefused, refused.Code);
    }

    /// <summary>Two readers may fold at once (FileShare.Read); a writer refuses them and they it.</summary>
    [Fact]
    public void TwoReadersMayFoldAtOnceAndAReaderRefusesAWriter()
    {
        using (var seed = EnvelopeStore.Open(SessionDir))
        {
            seed.Append(OpenedRow("e1"));
        }

        using var reader = new FileStream(FilePath, FileMode.Open, FileAccess.Read, FileShare.Read);
        Assert.Single(EnvelopeStore.ReadFile(FilePath).Envelopes);   // a second reader beside the first
        var refused = Assert.Throws<EnvelopeStoreException>(() => EnvelopeStore.Open(SessionDir));   // a writer while a reader holds it
        Assert.Equal(EnvelopeStoreErrorCodes.HeldByAnotherWriter, refused.Code);
    }

    [Fact]
    public void AnOpenedRowWhoseSessionIdDiffersFromTheDirectorySegmentIsRefused()
    {
        using var store = EnvelopeStore.Open(SessionDir);
        var refused = Assert.Throws<EnvelopeStoreException>(() => store.Append(OpenedRow("e1", sessionId: "20260912T100000Z-0000bbbb")));
        Assert.Equal(EnvelopeStoreErrorCodes.SessionIdMismatch, refused.Code);
        Assert.Equal(0, store.Read().Rows);
    }

    // ── test 2: two writers ──

    [Fact]
    public void TwoWritersOnOneFileSeeExactlyOneRefusal_AndAReaderWhileAWriterHoldsItIsRefusedVisibly()
    {
        using var first = EnvelopeStore.Open(SessionDir);
        first.Append(OpenedRow("e1"));

        var refused = Assert.Throws<EnvelopeStoreException>(() => EnvelopeStore.Open(SessionDir));
        Assert.Equal(EnvelopeStoreErrorCodes.HeldByAnotherWriter, refused.Code);
        Assert.Contains("another AI-DE has this session's compile history open", refused.Message, StringComparison.Ordinal);

        // A reader is refused the same way — never a partial fold.
        var reader = Assert.Throws<EnvelopeStoreException>(() => EnvelopeStore.ReadFile(FilePath));
        Assert.Equal(EnvelopeStoreErrorCodes.HeldByAnotherWriter, reader.Code);
    }

    /// <summary>ADR-0034 test 6 (the handle half): closing releases the handle, and a second open succeeds afterwards.</summary>
    [Fact]
    public void ClosingTheStoreReleasesTheHandleSoASecondOpenSucceeds()
    {
        var first = EnvelopeStore.Open(SessionDir);
        first.Append(OpenedRow("e1"));
        first.Dispose();

        using var second = EnvelopeStore.Open(SessionDir);
        var row = second.Append(new Decorated("e1", "goal", JsonValue.Create("g"), DecorationSources.Operator));
        Assert.Equal(2, row.Seq);   // the key map survived the reopen: seq continues, never restarts
    }

    // ── test 3: chain and fold ──

    [Fact]
    public void OneFlippedByteMidFileReportsRecordBrokenAtLineNAndYieldsNoEnvelopePastN()
    {
        using (var store = EnvelopeStore.Open(SessionDir))
        {
            store.Append(OpenedRow("e0"));                                                   // line 1
            store.Append(new Submitted("e0", true, null, "t", "p", "1"));                    // line 2 — e0 is whole before the break
            store.Append(OpenedRow("e1"));                                                   // line 3
            store.Append(new Decorated("e1", "goal", JsonValue.Create("keep the store small"), DecorationSources.Operator));   // line 4 — flipped
            store.Append(new Submitted("e1", true, null, "t", "p", "1"));                    // line 5
            store.Append(OpenedRow("e2"));                                                   // line 6
            store.Append(new Decorated("e2", "goal", JsonValue.Create("second"), DecorationSources.Operator));
        }

        // Flip one byte INSIDE a JSON string of line 4 — still valid JSON, a plausible fold without the chain.
        var lines = File.ReadAllText(FilePath, Encoding.UTF8).Split('\n');
        Assert.Equal("", lines[^1]);
        lines[3] = lines[3].Replace("keep the store small", "keep the store SMALL", StringComparison.Ordinal);
        File.WriteAllText(FilePath, string.Join('\n', lines), new UTF8Encoding(false));

        var fold = EnvelopeStore.ReadFile(FilePath);

        Assert.Equal(4, fold.BrokenAt);
        Assert.Contains("record broken at line 4", fold.Report, StringComparison.Ordinal);

        // e0 lies wholly before the break and folds; e1 spans it and e2 is past it — no envelope past N.
        var only = Assert.Single(fold.Envelopes);
        Assert.Equal("e0", only.EnvelopeId);
        Assert.False(only.IsAbandoned);
    }

    [Fact]
    public void ReopeningOnABrokenFileRefusesAppendLeavesTheBytesUnchangedAndNeverDuplicatesAKey()
    {
        using (var store = EnvelopeStore.Open(SessionDir))
        {
            store.Append(OpenedRow("e1"));
            store.Append(new Decorated("e1", "goal", JsonValue.Create("keep"), DecorationSources.Operator));
            store.Append(new Decorated("e1", "done_when", JsonValue.Create("kept"), DecorationSources.Operator));
        }

        var lines = File.ReadAllText(FilePath, Encoding.UTF8).Split('\n');
        lines[1] = lines[1].Replace("keep", "KEEP", StringComparison.Ordinal);
        File.WriteAllText(FilePath, string.Join('\n', lines), new UTF8Encoding(false));
        var bytesBefore = File.ReadAllBytes(FilePath);

        var reopened = EnvelopeStore.Open(SessionDir);
        Assert.Equal(2, reopened.BrokenAt);

        var refused = Assert.Throws<EnvelopeStoreException>(() =>
            reopened.Append(new Decorated("e1", "not_in_scope", JsonValue.Create("n"), DecorationSources.Operator)));
        Assert.Equal(EnvelopeStoreErrorCodes.StoreBroken, refused.Code);
        Assert.Contains("purge it to start again", refused.Message, StringComparison.Ordinal);

        // The handle is exclusive (FileShare.None) — the file is read after the store releases it.
        reopened.Dispose();
        Assert.Equal(bytesBefore, File.ReadAllBytes(FilePath));

        // The key map read every line regardless of the break: no (envelope_id, seq) is duplicated.
        var keys = File.ReadAllLines(FilePath)
            .Where(l => l.Length > 0)
            .Select(l => JsonNode.Parse(l)!.AsObject())
            .Select(o => (o["envelope_id"]!.GetValue<string>(), o["seq"]!.GetValue<int>()))
            .ToList();
        Assert.Equal(keys.Count, keys.Distinct().Count());
    }

    [Fact]
    public void ATornLastLineAndAnUnknownSchemaAreSkippedAndCounted_AndTheNextAppendNewlineTerminates()
    {
        using (var store = EnvelopeStore.Open(SessionDir))
        {
            store.Append(OpenedRow("e1"));
        }

        // A /2 row (unknown schema, a known key) and then a torn last line — a crash mid-write.
        var last = File.ReadAllLines(FilePath).Last(l => l.Length > 0);
        var v2 = JsonNode.Parse(last)!.AsObject();
        v2["schema"] = "compiled-envelope/2";
        v2["seq"] = 2;
        v2["kind"] = "decorated";
        v2["prev_sha"] = EnvelopeHash.Sha256Hex(last);
        var v2Line = v2.ToJsonString();
        File.AppendAllText(FilePath, v2Line + "\n", new UTF8Encoding(false));
        File.AppendAllText(FilePath, "{\"schema\":\"compiled-envelope/1\",\"envelope_id\":\"e1\",\"seq\":3,\"kind\":\"decor", new UTF8Encoding(false));

        using var reopened = EnvelopeStore.Open(SessionDir);
        var fold = reopened.Read();
        Assert.Equal(1, fold.SkippedUnknownSchema);
        Assert.Equal(1, fold.SkippedTorn);
        Assert.Null(fold.BrokenAt);
        Assert.Single(fold.Envelopes);

        // A /1 writer after a /2 row: a unique, HIGHER seq (the walk read the /2 key), and the torn
        // line was newline-terminated before the append so the chain stays unbroken.
        var row = reopened.Append(new Decorated("e1", "goal", JsonValue.Create("g"), DecorationSources.Operator));
        Assert.Equal(3, row.Seq);
        reopened.Dispose();

        var after = EnvelopeStore.ReadFile(FilePath);
        Assert.Null(after.BrokenAt);
        Assert.Equal(1, after.SkippedTorn);
        Assert.Equal(1, after.SkippedUnknownSchema);
        var e1 = Assert.Single(after.Envelopes);
        Assert.Equal("g", e1.Current("goal")?.Value?.GetValue<string>());
    }

    [Fact]
    public void AnAcceptedSubmittedWithNoConsumedReadsOutcomeNotRecorded_AndASecondConsumedIsRefused()
    {
        using var store = EnvelopeStore.Open(SessionDir);
        store.Append(OpenedRow("e1"));
        store.Append(new Submitted("e1", true, null, "t", "p", "1"));

        var open = Assert.Single(store.Read().Envelopes);
        Assert.Equal(Envelope.NotRecorded, open.Outcome);
        Assert.False(open.IsAbandoned);

        store.Append(new Consumed("e1", "r-1", "ep-1", "Completed", ConsumedReasons.Completed));
        Assert.Equal("Completed", Assert.Single(store.Read().Envelopes).Outcome);

        var refused = Assert.Throws<EnvelopeStoreException>(() => store.Append(new Consumed("e1", "r-1", "ep-1", "Completed", ConsumedReasons.Completed)));
        Assert.Equal(EnvelopeStoreErrorCodes.ConsumedTwice, refused.Code);

        // An envelope with no submitted at all is abandoned: a stable read, because no writer holds the file.
        store.Append(OpenedRow("e2"));
        Assert.True(store.Read().Envelopes.Single(e => e.EnvelopeId == "e2").IsAbandoned);
        Assert.Null(store.Read().Envelopes.Single(e => e.EnvelopeId == "e2").Outcome);
    }

    [Fact]
    public void TheOpenReportCarriesBytesRowsEnvelopesBrokenAtAndWalkMs()
    {
        using (var store = EnvelopeStore.Open(SessionDir))
        {
            store.Append(OpenedRow("e1"));
            store.Append(OpenedRow("e2"));
        }

        using var reopened = EnvelopeStore.Open(SessionDir);
        var report = reopened.OpenReport;
        Assert.Equal(new FileInfo(FilePath).Length, report.Bytes);
        Assert.Equal(2, report.Rows);
        Assert.Equal(2, report.Envelopes);
        Assert.Null(report.BrokenAt);
        Assert.True(report.WalkMs >= 0);
    }

    [Fact]
    public void AppendAssignsSeqPerEnvelopeAndPrevShaOverTheRawPreviousLineAnyEnvelope()
    {
        using (var store = EnvelopeStore.Open(SessionDir))
        {
            store.Append(OpenedRow("e1"));
            store.Append(OpenedRow("e2"));
            store.Append(new Decorated("e1", "goal", JsonValue.Create("g"), DecorationSources.Operator));
        }

        var lines = File.ReadAllLines(FilePath).Where(l => l.Length > 0).Select(l => JsonNode.Parse(l)!.AsObject()).ToList();
        Assert.Equal(["e1", "e2", "e1"], lines.Select(l => l["envelope_id"]!.GetValue<string>()));
        Assert.Equal([1, 1, 2], lines.Select(l => l["seq"]!.GetValue<int>()));
        Assert.Equal("", lines[0]["prev_sha"]!.GetValue<string>());

        var raw = File.ReadAllLines(FilePath).Where(l => l.Length > 0).ToList();
        Assert.Equal(EnvelopeHash.Sha256Hex(raw[0]), lines[1]["prev_sha"]!.GetValue<string>());
        Assert.Equal(EnvelopeHash.Sha256Hex(raw[1]), lines[2]["prev_sha"]!.GetValue<string>());
        Assert.All(lines, l => Assert.Equal(EnvelopeStore.Schema, l["schema"]!.GetValue<string>()));
    }

    [Fact]
    public void AMissingSessionDirectoryIsRefusedNeverCreated()
    {
        var absent = SessionPaths.SessionDirectory(_workspace, "20260912T100000Z-0000cccc");
        var refused = Assert.Throws<EnvelopeStoreException>(() => EnvelopeStore.Open(absent));
        Assert.Equal(EnvelopeStoreErrorCodes.NoSessionDirectory, refused.Code);
        Assert.False(Directory.Exists(absent));
    }
}
