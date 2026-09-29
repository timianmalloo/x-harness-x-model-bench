using System.Diagnostics;
using AiDe.Core.Presentation.Composer;

namespace AiDe.Core.Tests.Composer;

/// <summary>A reader that counts, so "zero bytes were read" is an observation rather than a claim.</summary>
internal sealed class CountingFileReader : IAttachmentFileReader
{
    private readonly AttachmentFileReader _real = new();

    public long ReadCount => _real.ReadCount;

    public long MetadataCount { get; private set; }

    public long Length(string resolvedPath)
    {
        MetadataCount++;
        return _real.Length(resolvedPath);
    }

    public byte[] ReadAllBytes(string resolvedPath) => _real.ReadAllBytes(resolvedPath);
}

/// <summary>An affirmation that records what it was asked, and answers as the test instructs.</summary>
internal sealed class ScriptedAffirmation(bool answer) : IAttachmentAffirmation
{
    public List<OutsideWorkspaceAffirmation> Asked { get; } = [];

    /// <summary>The reader's count at the moment each question was asked — C14(e)(iii)'s observable.</summary>
    public List<long> ReadCountWhenAsked { get; } = [];

    public IAttachmentFileReader? Reader { get; set; }

    public bool Confirm(OutsideWorkspaceAffirmation affirmation)
    {
        Asked.Add(affirmation);
        ReadCountWhenAsked.Add(Reader?.ReadCount ?? -1);
        return answer;
    }
}

/// <summary>A workspace root and an outside directory, both real, both cleaned up.</summary>
internal sealed class AttachmentFixture : IDisposable
{
    private readonly string _base;

    public AttachmentFixture()
    {
        _base = Path.Combine(Path.GetTempPath(), "aide-composer", Guid.NewGuid().ToString("N"));
        WorkspaceRoot = Path.Combine(_base, "workspace");
        Outside = Path.Combine(_base, "outside");
        Directory.CreateDirectory(WorkspaceRoot);
        Directory.CreateDirectory(Outside);

        Reader = new CountingFileReader();
        Affirmation = new ScriptedAffirmation(answer: true) { Reader = Reader };
    }

    public string WorkspaceRoot { get; }

    public string Outside { get; }

    public CountingFileReader Reader { get; }

    public ScriptedAffirmation Affirmation { get; set; }

    public AttachmentGate Gate() =>
        new(WorkspaceRoot, Reader, Affirmation, "Anthropic (Claude Code)", "max-personal");

    public string WriteInside(string relativePath, string content)
    {
        var path = Path.Combine(WorkspaceRoot, relativePath);
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, content);
        return path;
    }

    public string WriteOutside(string name, string content)
    {
        var path = Path.Combine(Outside, name);
        File.WriteAllText(path, content);
        return path;
    }

    /// <summary>
    /// Links a directory, with a real reparse point on both platforms.
    /// </summary>
    /// <remarks>
    /// <b>A symbolic link where the platform allows one, a junction where it does not.</b> Windows
    /// refuses <c>CreateSymbolicLink</c> without a privilege that a developer machine does not have
    /// by default, and a test that quietly did nothing there would be the exact defect this clause is
    /// about. A junction is a real reparse point and exercises the same resolution path, so the
    /// assertion below is identical either way — and if NEITHER can be created the test fails rather
    /// than passes with no link at all.
    /// </remarks>
    public static string LinkDirectory(string link, string target)
    {
        try
        {
            Directory.CreateSymbolicLink(link, target);
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        {
            if (!OperatingSystem.IsWindows())
            {
                throw;
            }

            using var process = Process.Start(new ProcessStartInfo("cmd.exe", $"/c mklink /J \"{link}\" \"{target}\"")
            {
                CreateNoWindow = true,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            })!;

            process.WaitForExit();
        }

        Assert.True(Directory.Exists(link), $"no reparse point could be created at {link}");
        Assert.NotNull(new DirectoryInfo(link).ResolveLinkTarget(returnFinalTarget: true));
        return link;
    }

    public void Dispose()
    {
        try
        {
            Directory.Delete(_base, recursive: true);
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        {
            // A leaked temp directory is not a test failure.
        }
    }
}
