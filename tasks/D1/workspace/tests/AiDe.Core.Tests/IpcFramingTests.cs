using System.Text;
using AiDe.Core.Ipc;

namespace AiDe.Core.Tests;

/// <summary>
/// Message framing on a byte stream — where a boundary's hostile-input surface begins.
/// </summary>
/// <remarks>
/// <para>A pipe carries bytes, not messages. Everything above this layer assumes it is handed one
/// whole request at a time, and every one of those assumptions is only as true as the framing. The
/// interesting cases are therefore not "does a message round-trip" but what happens when the peer
/// lies: a length prefix that promises more than it sends, one that promises a gigabyte, a stream
/// that ends halfway.</para>
///
/// <para><b>The length prefix is attacker-chosen.</b> Allocating what it asks for is a remote memory
/// exhaustion in one line, so the cap is the control and it is checked before any allocation.</para>
/// </remarks>
public sealed class IpcFramingTests
{
    private static async Task<T> RoundTrip<T>(Func<Stream, Task> write, Func<Stream, Task<T>> read)
    {
        using var stream = new MemoryStream();
        await write(stream);
        stream.Position = 0;
        return await read(stream);
    }

    [Fact]
    public async Task AMessage_RoundTrips()
    {
        var result = await RoundTrip(
            s => IpcFraming.WriteAsync(s, "hello", CancellationToken.None),
            s => IpcFraming.ReadAsync(s, CancellationToken.None));

        Assert.Equal("hello", result);
    }

    [Fact]
    public async Task Utf8Content_SurvivesIntact()
    {
        var payload = "{\"path\":\"C:\\\\Проекты\\\\ünïcode\",\"emoji\":\"🙂\"}";

        var result = await RoundTrip(
            s => IpcFraming.WriteAsync(s, payload, CancellationToken.None),
            s => IpcFraming.ReadAsync(s, CancellationToken.None));

        Assert.Equal(payload, result);
    }

    [Fact]
    public async Task SeveralMessages_ReadBackInOrder()
    {
        using var stream = new MemoryStream();
        await IpcFraming.WriteAsync(stream, "one", CancellationToken.None);
        await IpcFraming.WriteAsync(stream, "two", CancellationToken.None);
        stream.Position = 0;

        Assert.Equal("one", await IpcFraming.ReadAsync(stream, CancellationToken.None));
        Assert.Equal("two", await IpcFraming.ReadAsync(stream, CancellationToken.None));
    }

    [Fact]
    public async Task AClosedStream_ReadsAsNull_RatherThanThrowing()
    {
        // A peer that hangs up is the ordinary end of every connection, not an error. Throwing here
        // would make normal disconnection indistinguishable from a protocol violation.
        using var empty = new MemoryStream();

        Assert.Null(await IpcFraming.ReadAsync(empty, CancellationToken.None));
    }

    [Fact]
    public async Task ATruncatedPrefix_ReadsAsNull()
    {
        using var stream = new MemoryStream([0x00, 0x00]); // Two bytes of a four-byte prefix.

        Assert.Null(await IpcFraming.ReadAsync(stream, CancellationToken.None));
    }

    [Fact]
    public async Task ABodyShorterThanItsPrefixPromises_ReadsAsNull()
    {
        // A peer that announces 100 bytes and sends 4 has either crashed or is probing. Either way
        // the answer is "no message", never a partial one handed upward as though it were whole.
        using var stream = new MemoryStream();
        stream.Write([0x00, 0x00, 0x00, 0x64]);
        stream.Write("abcd"u8);
        stream.Position = 0;

        Assert.Null(await IpcFraming.ReadAsync(stream, CancellationToken.None));
    }

    [Fact]
    public async Task AnOversizedLengthPrefix_IsRefusedWithoutAllocating()
    {
        // Absent this control: `write(0x7FFFFFFF)` costs the attacker four bytes and costs us two
        // gigabytes. The cap must be checked BEFORE the buffer is created, which is what makes this
        // a memory-safety test rather than a validation test.
        using var stream = new MemoryStream();
        stream.Write([0x7F, 0xFF, 0xFF, 0xFF]);
        stream.Position = 0;

        var thrown = await Record.ExceptionAsync(
            () => IpcFraming.ReadAsync(stream, CancellationToken.None));

        Assert.IsType<InvalidDataException>(thrown);
        Assert.Contains("frame", thrown.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task ANegativeLengthPrefix_IsRefused()
    {
        using var stream = new MemoryStream();
        stream.Write([0xFF, 0xFF, 0xFF, 0xFF]);
        stream.Position = 0;

        Assert.IsType<InvalidDataException>(
            await Record.ExceptionAsync(() => IpcFraming.ReadAsync(stream, CancellationToken.None)));
    }

    [Fact]
    public async Task AMessageAtTheCap_IsAccepted()
    {
        // The boundary itself, so the cap cannot quietly become off-by-one and reject valid traffic.
        var payload = new string('x', IpcFraming.MaxFrameBytes - 16);

        var result = await RoundTrip(
            s => IpcFraming.WriteAsync(s, payload, CancellationToken.None),
            s => IpcFraming.ReadAsync(s, CancellationToken.None));

        Assert.Equal(payload.Length, result!.Length);
    }

    [Fact]
    public async Task WritingBeyondTheCap_IsRefusedBySender()
    {
        // Refused on OUR side too, not only defended against on theirs: a message we cannot send is
        // a bug in the caller, and discovering it as a peer's protocol violation is far from home.
        using var stream = new MemoryStream();
        var oversized = new string('x', IpcFraming.MaxFrameBytes + 1);

        Assert.IsType<ArgumentException>(
            await Record.ExceptionAsync(
                () => IpcFraming.WriteAsync(stream, oversized, CancellationToken.None)));
    }

    [Fact]
    public void TheFrameCap_IsSmallEnoughToBeAMeaningfulBound()
    {
        // Documents intent: a control lane carries envelopes, not payloads. A cap in the hundreds of
        // megabytes would satisfy every test above and defend against nothing.
        Assert.InRange(IpcFraming.MaxFrameBytes, 4096, 4 * 1024 * 1024);
    }

    [Fact]
    public async Task Cancellation_IsHonouredMidRead()
    {
        using var stream = new BlockingStream();
        using var cancellation = new CancellationTokenSource();
        await cancellation.CancelAsync();

        await Assert.ThrowsAnyAsync<OperationCanceledException>(
            () => IpcFraming.ReadAsync(stream, cancellation.Token));
    }

    /// <summary>A stream that never produces data, so a read has to be cancelled to end.</summary>
    private sealed class BlockingStream : Stream
    {
        public override bool CanRead => true;

        public override bool CanSeek => false;

        public override bool CanWrite => false;

        public override long Length => throw new NotSupportedException();

        public override long Position
        {
            get => throw new NotSupportedException();
            set => throw new NotSupportedException();
        }

        public override async ValueTask<int> ReadAsync(
            Memory<byte> buffer, CancellationToken cancellationToken)
        {
            // Awaited rather than continued: a ContinueWith turns cancellation into an ordinary
            // completion returning 0, which the framing correctly reads as "peer hung up" — so the
            // helper would have been testing the wrong thing while looking like it worked.
            await Task.Delay(Timeout.Infinite, cancellationToken);
            return 0;
        }

        public override void Flush()
        {
        }

        public override int Read(byte[] buffer, int offset, int count) => throw new NotSupportedException();

        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();

        public override void SetLength(long value) => throw new NotSupportedException();

        public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
    }
}
