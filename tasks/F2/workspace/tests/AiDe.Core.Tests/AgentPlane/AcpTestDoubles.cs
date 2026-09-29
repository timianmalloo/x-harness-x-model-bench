using System.Text;
using System.Threading.Channels;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// A <see cref="TextReader"/> the test pushes bytes into, one chunk at a time, and closes to signal
/// end of stream.
/// </summary>
/// <remarks>
/// <b>Chunking is the point.</b> A child process's stdout arrives in arbitrary pieces, so the frame
/// splitter has to be correct across a chunk boundary that falls inside a frame, and across a chunk
/// that carries several frames. A reader built over a fixed string cannot pose either question.
/// </remarks>
internal sealed class PushTextReader : TextReader
{
    private readonly Channel<string> _chunks = Channel.CreateUnbounded<string>();
    private string _current = string.Empty;
    private int _offset;

    /// <summary>Makes <paramref name="text"/> available to the next read. Never adds a newline.</summary>
    public void Push(string text) => _chunks.Writer.TryWrite(text);

    /// <summary>End of stream — what a child process exiting looks like to its parent.</summary>
    public void EndOfStream() => _chunks.Writer.TryComplete();

    public override async ValueTask<int> ReadAsync(Memory<char> buffer, CancellationToken cancellationToken = default)
    {
        while (_offset >= _current.Length)
        {
            if (!await _chunks.Reader.WaitToReadAsync(cancellationToken).ConfigureAwait(false))
            {
                return 0;
            }

            if (_chunks.Reader.TryRead(out var next))
            {
                _current = next;
                _offset = 0;
            }
        }

        var count = Math.Min(buffer.Length, _current.Length - _offset);
        _current.AsSpan(_offset, count).CopyTo(buffer.Span);
        _offset += count;
        return count;
    }
}

/// <summary>
/// Records every newline-terminated frame written, and — at the moment it is written — a snapshot of
/// a caller-supplied counter.
/// </summary>
/// <remarks>
/// <b>The snapshot is what makes the ordinal assertion possible.</b> "The run event was observable
/// before the response went out" is a statement about two moments, and a writer that only keeps the
/// text can testify to one of them. Sampling the published-event count at write time puts both on
/// one timeline without a clock and without a sleep.
/// </remarks>
internal sealed class RecordingTextWriter(Func<long>? snapshot = null) : TextWriter
{
    private readonly StringBuilder _pending = new();

    public List<(string Line, long Snapshot)> Lines { get; } = [];

    public override Encoding Encoding => Encoding.UTF8;

    public override void Write(char value)
    {
        if (value != '\n')
        {
            _pending.Append(value);
            return;
        }

        Lines.Add((_pending.ToString(), snapshot?.Invoke() ?? 0));
        _pending.Clear();
    }

    public override void Write(string? value)
    {
        foreach (var character in value ?? string.Empty)
        {
            Write(character);
        }
    }
}

/// <summary>
/// Locates the captured ACP frame corpus, wherever the runner's working directory happens to be.
/// </summary>
/// <remarks>
/// One locator for every test that reads the corpus. Two copies of "where is the evidence" is the
/// shape that lets one of them go on finding a directory the other no longer looks in.
/// </remarks>
internal static class AcpCorpus
{
    /// <summary>The directory holding <c>*.jsonl</c> and <c>PROVENANCE.md</c>.</summary>
    /// <exception cref="InvalidOperationException">
    /// Thrown loudly rather than skipped: a test that passes because it could not find its subject
    /// is an absence rendered as success (DC-025).
    /// </exception>
    public static string Directory()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null)
        {
            var candidate = Path.Combine(dir.FullName, "spikes", "acp-subscription-lane", "frames");
            if (File.Exists(Path.Combine(candidate, "PROVENANCE.md")))
            {
                return candidate;
            }

            dir = dir.Parent;
        }

        throw new InvalidOperationException(
            "could not locate spikes/acp-subscription-lane/frames from " + AppContext.BaseDirectory);
    }

    /// <summary>Every non-blank line of one corpus file, verbatim.</summary>
    public static IReadOnlyList<string> Lines(string fileName)
        => [.. File.ReadAllLines(Path.Combine(Directory(), fileName)).Where(l => !string.IsNullOrWhiteSpace(l))];
}
