using System.Text;
using AiDe.Core.Dispatch;
using AiDe.Core.Terminal;

namespace AiDe.Core.Tests;

/// <summary>
/// `P2-TERM-06` and `P2-TERM-07` — the terminal-process → runtime trust boundary, attacked.
/// </summary>
/// <remarks>
/// <para>The child process in a terminal is <b>untrusted</b>. It is frequently the very thing under
/// investigation, and every byte it emits is attacker-controlled in the cases that matter. OSC
/// sequences are therefore claims, not facts, and this suite is written as misuse cases: each one
/// states what the child gets if the control is absent.</para>
///
/// <para><b>Why a nonce at all.</b> Without one, any process that can print can announce that it is
/// back at a prompt. The design makes OSC state advisory precisely so that a forged claim cannot
/// mean acceptance (ADR-0007) — but "advisory" still drives what the user sees, and a session that
/// reports <c>Ready</c> while a command is mid-flight is a lie the UI will faithfully render. The
/// nonce is what separates the shell integration <i>we</i> injected from anything else that learned
/// to print the same bytes.</para>
///
/// <para><b>Why 52 and 8 are refused rather than sanitised.</b> Sanitising presumes we can tell a
/// safe clipboard write from a hostile one. We cannot: the whole payload is chosen by the child.
/// The control is that the host action does not exist and the parser has no path to one.</para>
/// </remarks>
public sealed class OscParserTests
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";

    private static OscParser Parser(string nonce = Nonce) => new(nonce);

    /// <summary>An OSC sequence with the 7-bit introducer and the standard ST terminator.</summary>
    private static byte[] Osc(string payload) => Encoding.ASCII.GetBytes($"]{payload}\\");

    private static (SessionActivity? Claim, List<OscEvent> Events) Feed(OscParser parser, params byte[][] chunks)
    {
        var events = new List<OscEvent>();
        SessionActivity? claim = null;

        foreach (var chunk in chunks)
        {
            var result = parser.Consume(chunk, events);
            if (result is not null)
            {
                claim = result;
            }
        }

        return (claim, events);
    }

    // ---- OSC 133 with a valid nonce is honoured ----------------------------

    [Fact]
    public void CommandFinished_WithTheSessionNonce_ClaimsReady()
    {
        var (claim, events) = Feed(Parser(), Osc($"133;D;0;nonce={Nonce}"));

        Assert.Equal(SessionActivity.Ready, claim);
        Assert.Equal(new OscEvent(OscKind.CommandFinished, OscDisposition.Honoured), Assert.Single(events));
    }

    [Fact]
    public void CommandExecuted_WithTheSessionNonce_ClaimsBusy()
    {
        var (claim, events) = Feed(Parser(), Osc($"133;C;nonce={Nonce}"));

        Assert.Equal(SessionActivity.Busy, claim);
        Assert.Equal(new OscEvent(OscKind.CommandExecuted, OscDisposition.Honoured), Assert.Single(events));
    }

    [Fact]
    public void PromptStart_WithTheSessionNonce_ClaimsReady()
    {
        // A prompt being drawn means the shell is waiting for input, which is exactly Ready.
        var (claim, _) = Feed(Parser(), Osc($"133;A;nonce={Nonce}"));

        Assert.Equal(SessionActivity.Ready, claim);
    }

    [Fact]
    public void CommandStart_WithTheSessionNonce_ClaimsReady()
    {
        // B marks the end of the prompt and the start of user typing: still waiting on the user.
        var (claim, _) = Feed(Parser(), Osc($"133;B;nonce={Nonce}"));

        Assert.Equal(SessionActivity.Ready, claim);
    }

    // ---- P2-TERM-06: the forged claim --------------------------------------

    [Fact]
    public void CommandFinished_WithNoNonce_IsRefused_AndClaimsNothing()
    {
        // Absent this control: any process that can print `ESC ] 133 ; D ST` — which is a documented,
        // widely-copied sequence — reports itself idle while it keeps running.
        var (claim, events) = Feed(Parser(), Osc("133;D;0"));

        Assert.Null(claim);
        Assert.Equal(
            new OscEvent(OscKind.CommandFinished, OscDisposition.RefusedUnauthenticated),
            Assert.Single(events));
    }

    [Fact]
    public void CommandFinished_WithAWrongNonce_IsRefused_AndClaimsNothing()
    {
        var (claim, events) = Feed(Parser(), Osc("133;D;0;nonce=deadbeefdeadbeefdeadbeefdeadbeef"));

        Assert.Null(claim);
        Assert.Equal(
            new OscEvent(OscKind.CommandFinished, OscDisposition.RefusedUnauthenticated),
            Assert.Single(events));
    }

    [Fact]
    public void CommandFinished_WithAPrefixOfTheNonce_IsRefused()
    {
        // A length-unaware comparison would accept a prefix, which turns the nonce into a guessing
        // game the child can play one byte at a time.
        var (claim, _) = Feed(Parser(), Osc($"133;D;0;nonce={Nonce[..16]}"));

        Assert.Null(claim);
    }

    [Fact]
    public void CommandFinished_WithTheNonceAsAPrefixOfALongerValue_IsRefused()
    {
        var (claim, _) = Feed(Parser(), Osc($"133;D;0;nonce={Nonce}extra"));

        Assert.Null(claim);
    }

    [Fact]
    public void Osc633_ShellIntegration_IsNeverHonoured_EvenWithAValidNonce()
    {
        // 633 is VS Code's parallel shell-integration protocol and is named in the threat model
        // alongside 133. We do not speak it, so honouring it would mean trusting a sequence no
        // integration of ours ever emits.
        var (claim, events) = Feed(Parser(), Osc($"633;D;0;nonce={Nonce}"));

        Assert.Null(claim);
        Assert.Equal(new OscEvent(OscKind.Unrecognized, OscDisposition.Ignored), Assert.Single(events));
    }

    // ---- P2-TERM-07: host actions are disabled outright --------------------

    [Fact]
    public void Osc52_Clipboard_IsRefused_EvenWithAValidNonce()
    {
        // Absent this control: any process that can print writes the user's clipboard — an egress
        // channel out of the sandbox and into whatever they paste into next.
        var (claim, events) = Feed(Parser(), Osc($"52;c;aGVsbG8=;nonce={Nonce}"));

        Assert.Null(claim);
        Assert.Equal(
            new OscEvent(OscKind.Clipboard, OscDisposition.RefusedDisabled),
            Assert.Single(events));
    }

    [Fact]
    public void Osc8_Hyperlink_IsRefused_EvenWithAValidNonce()
    {
        var (claim, events) = Feed(Parser(), Osc($"8;nonce={Nonce};https://example.invalid/"));

        Assert.Null(claim);
        Assert.Equal(
            new OscEvent(OscKind.Hyperlink, OscDisposition.RefusedDisabled),
            Assert.Single(events));
    }

    // ---- framing: a hostile stream is not a well-formed one ----------------

    [Fact]
    public void ASequenceSplitAcrossChunks_IsStillHonoured()
    {
        // Chunk boundaries are set by the pipe, not by the child. A parser that only recognised
        // whole-chunk sequences would work in tests and fail against a 4 KiB read boundary.
        var whole = Osc($"133;D;0;nonce={Nonce}");
        var parser = Parser();

        var (claim, events) = Feed(parser, whole[..5], whole[5..12], whole[12..]);

        Assert.Equal(SessionActivity.Ready, claim);
        Assert.Equal(OscDisposition.Honoured, Assert.Single(events).Disposition);
    }

    [Fact]
    public void ABelTerminatedSequence_IsHonoured()
    {
        var bytes = Encoding.ASCII.GetBytes($"]133;D;0;nonce={Nonce}");

        var (claim, _) = Feed(Parser(), bytes);

        Assert.Equal(SessionActivity.Ready, claim);
    }

    [Fact]
    public void AnEightBitIntroducerAndTerminator_AreHonoured()
    {
        // C1 controls arrive from processes that were never told we are a 7-bit terminal.
        var bytes = new List<byte> { 0x9D };
        bytes.AddRange(Encoding.ASCII.GetBytes($"133;D;0;nonce={Nonce}"));
        bytes.Add(0x9C);

        var (claim, _) = Feed(Parser(), bytes.ToArray());

        Assert.Equal(SessionActivity.Ready, claim);
    }

    [Fact]
    public void AnUnterminatedSequence_IsBounded_AndDoesNotGrowWithoutLimit()
    {
        // Absent this control: `ESC ] ` followed by an endless stream costs one byte of ours per byte
        // of theirs, and the bound on our memory is whatever the child decides to stop at.
        var flood = new List<byte>(Encoding.ASCII.GetBytes("]133;"));
        flood.AddRange(Enumerable.Repeat((byte)'x', OscParser.MaxPayloadBytes * 4));
        var parser = Parser();

        var (claim, events) = Feed(parser, flood.ToArray());

        Assert.Null(claim);
        Assert.Contains(events, e => e.Disposition == OscDisposition.Overflowed);
        Assert.True(
            parser.PendingPayloadBytes <= OscParser.MaxPayloadBytes,
            $"retained {parser.PendingPayloadBytes} bytes, which is above the cap");
    }

    [Fact]
    public void AfterAnOverflow_TheParserResyncs_AndHonoursTheNextValidSequence()
    {
        // An abandoned sequence must not poison the stream: the discard has to end at the real
        // terminator, or every later sequence is read as payload and silently lost.
        var flood = new List<byte>(Encoding.ASCII.GetBytes("]133;"));
        flood.AddRange(Enumerable.Repeat((byte)'x', OscParser.MaxPayloadBytes * 2));
        flood.AddRange(Encoding.ASCII.GetBytes("\\"));
        var parser = Parser();

        var (claim, _) = Feed(parser, flood.ToArray(), Osc($"133;D;0;nonce={Nonce}"));

        Assert.Equal(SessionActivity.Ready, claim);
    }

    [Fact]
    public void OrdinaryOutputContainingNoSequences_ProducesNothing()
    {
        var (claim, events) = Feed(Parser(), Encoding.UTF8.GetBytes("build succeeded in 1.4s\r\n"));

        Assert.Null(claim);
        Assert.Empty(events);
        Assert.Equal(0, Parser().PendingPayloadBytes);
    }

    [Fact]
    public void TheParserRetainsNoPayloadOnceASequenceEnds()
    {
        // Privacy: the parser reads every byte the child writes, which makes anything it keeps a
        // copy of terminal text living outside the bounded, ephemeral output channel.
        var parser = Parser();

        Feed(parser, Osc($"133;D;0;nonce={Nonce}"), Osc("52;c;c2VjcmV0"));

        Assert.Equal(0, parser.PendingPayloadBytes);
    }

    // ---- the nonce itself --------------------------------------------------

    [Fact]
    public void NewNonce_IsUnpredictable_AndDistinctPerCall()
    {
        var nonces = Enumerable.Range(0, 64).Select(_ => OscParser.NewNonce()).ToArray();

        Assert.Equal(nonces.Length, nonces.Distinct(StringComparer.Ordinal).Count());
        Assert.All(nonces, n => Assert.Equal(32, n.Length));
    }

    [Fact]
    public void AParserWithAnEmptyNonce_HonoursNothing()
    {
        // A session that failed to generate a nonce must fail closed, not accept every claim.
        Assert.Throws<ArgumentException>(() => new OscParser(string.Empty));
    }
}
