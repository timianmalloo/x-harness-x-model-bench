using System.Security.Cryptography;

namespace AiDe.Core.Presentation.Composer;

/// <summary>Reads a file's bytes, and counts that it did.</summary>
/// <remarks>
/// <b>The counter is the observable three separate clauses rest on.</b> C21(a) asserts it reads 0
/// with attach off; C14(e)(iii) asserts it reads 0 while an affirmation is pending; C15 asserts it
/// reads 0 between the compiled view rendering and the prompt reaching the run host.
/// </remarks>
public interface IAttachmentFileReader
{
    /// <summary>How many times file CONTENT has been read. Metadata is not a read.</summary>
    long ReadCount { get; }

    /// <summary>The file's size, from metadata. Deliberately not a content read.</summary>
    long Length(string resolvedPath);

    /// <summary>Reads the whole file, and increments <see cref="ReadCount"/>.</summary>
    byte[] ReadAllBytes(string resolvedPath);
}

/// <summary>The real reader. Every content read in the composer goes through this one type.</summary>
public sealed class AttachmentFileReader : IAttachmentFileReader
{
    private long _reads;

    /// <inheritdoc/>
    public long ReadCount => Interlocked.Read(ref _reads);

    /// <inheritdoc/>
    public long Length(string resolvedPath) => new FileInfo(resolvedPath).Length;

    /// <inheritdoc/>
    public byte[] ReadAllBytes(string resolvedPath)
    {
        Interlocked.Increment(ref _reads);
        return File.ReadAllBytes(resolvedPath);
    }
}

/// <summary>
/// What the operator is asked, before a single byte of an outside-workspace file is read.
/// </summary>
/// <param name="AbsolutePath">The resolved path, named in full.</param>
/// <param name="Bytes">Its size, from metadata.</param>
/// <param name="ProviderName">Where the content goes.</param>
/// <param name="AccountLabel">The account the run bills to.</param>
public sealed record OutsideWorkspaceAffirmation(
    string AbsolutePath, long Bytes, string ProviderName, string AccountLabel)
{
    /// <summary>
    /// The sentence the operator reads. It must name provider and account: the decision is about
    /// where the bytes go, and an affirmation that does not say so is not informed.
    /// </summary>
    public string Prompt =>
        $"Attach '{AbsolutePath}' ({Bytes} bytes)? It is OUTSIDE this workspace. Its contents will be "
        + $"sent to {ProviderName} on the account '{AccountLabel}'. Once sent, nothing is retractable.";
}

/// <summary>Asks the operator, per outside-workspace file, before anything is read.</summary>
public interface IAttachmentAffirmation
{
    /// <summary>True when the operator affirmed this exact file.</summary>
    bool Confirm(OutsideWorkspaceAffirmation affirmation);
}

/// <summary>What one attach gesture produced.</summary>
/// <param name="Attached">The attachments, in affirmation order.</param>
/// <param name="Refusals">
/// Visible, operator-facing refusals. <b>Never written to any channel</b> — the committed record and
/// Channel B carry counts, and for a blocked attach a count is all that exists anywhere.
/// </param>
/// <param name="BlockedByAttachSetting">
/// How many files were not attached because the session's attach setting is off. A COUNT, never a
/// name (C21(d)).
/// </param>
public sealed record AttachOutcome(
    IReadOnlyList<ComposerAttachment> Attached,
    IReadOnlyList<string> Refusals,
    int BlockedByAttachSetting);

/// <summary>
/// The attach path: operator-enabled, bounded, visible, literal, and host-owned.
/// </summary>
/// <remarks>
/// <para><b>The setting stops the READ, not the insert (C21(a)).</b> With attach off this type
/// returns before it touches the file system at all — it does not resolve, stat, or open anything.
/// A gate that blocks the insert but still reads the file has already done the thing.</para>
///
/// <para><b>A blocked attach records a COUNT ONLY (C21(d)).</b> The refusal string names no path, no
/// basename and no extension, because the setting exists to stop that content being recorded, and a
/// control that logs what it refused is the breach it prevents wearing a compliance hat.</para>
///
/// <para><b>One human act, one named file (C14(e)(i)).</b> A directory and an archive each produce
/// zero attachments and one visible refusal; a multi-select of N files produces N separately
/// affirmed attachments, never one bulk insert.</para>
///
/// <para><b>Whole-file attach is not minimized, and that is recorded rather than implied.</b> Paste
/// is the minimizing path — a selection rather than a whole file — and attach is the maximal one.
/// The caps here ceiling the attach path only.</para>
/// </remarks>
public sealed class AttachmentGate
{
    private readonly IAttachmentFileReader _reader;
    private readonly IAttachmentAffirmation _affirmation;
    private readonly string _workspaceRoot;
    private readonly string _providerName;
    private readonly string _accountLabel;

    /// <param name="workspaceRoot">The session's workspace root. Resolved once, here.</param>
    /// <param name="reader">The one type that reads attachment bytes.</param>
    /// <param name="affirmation">Who is asked about an outside-workspace file.</param>
    /// <param name="providerName">Where content goes — named in the affirmation.</param>
    /// <param name="accountLabel">The account the run bills to — named in the affirmation.</param>
    public AttachmentGate(
        string workspaceRoot,
        IAttachmentFileReader reader,
        IAttachmentAffirmation affirmation,
        string providerName,
        string accountLabel)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(workspaceRoot);
        ArgumentNullException.ThrowIfNull(reader);
        ArgumentNullException.ThrowIfNull(affirmation);
        ArgumentException.ThrowIfNullOrWhiteSpace(providerName);
        ArgumentException.ThrowIfNullOrWhiteSpace(accountLabel);

        _workspaceRoot = AttachmentPolicy.RealPath(workspaceRoot);
        _reader = reader;
        _affirmation = affirmation;
        _providerName = providerName;
        _accountLabel = accountLabel;
    }

    /// <summary>
    /// Offers files to a draft. Nothing here mutates <paramref name="draft"/> unless a file survives
    /// every rule.
    /// </summary>
    /// <param name="draft">The draft the attachments would land in.</param>
    /// <param name="pickedPaths">What one human act named — a drop, a dialog, or a multi-select.</param>
    /// <param name="attachEnabled">The session's persisted setting. Default false (C21).</param>
    public AttachOutcome Offer(
        ComposerDraft draft, IReadOnlyList<string> pickedPaths, bool attachEnabled)
    {
        ArgumentNullException.ThrowIfNull(draft);
        ArgumentNullException.ThrowIfNull(pickedPaths);

        if (!attachEnabled)
        {
            // BEFORE THE FILE SYSTEM IS TOUCHED AT ALL. Not resolved, not stat'ed, not opened — and
            // the message below names nothing about what was picked.
            return new AttachOutcome(
                [],
                pickedPaths.Count == 0
                    ? []
                    : ["Attaching files is off for this session. Turn on Attach files in the session settings to enable it."],
                pickedPaths.Count);
        }

        var attached = new List<ComposerAttachment>();
        var refusals = new List<string>();

        var countSoFar = draft.Attachments.Count;
        var bytesSoFar = draft.Attachments.Sum(a => a.Bytes);

        foreach (var picked in pickedPaths)
        {
            if (countSoFar + 1 > AttachmentPolicy.MaxAttachmentsPerSend)
            {
                refusals.Add(
                    $"'{Path.GetFileName(picked)}' was not attached: a send carries at most "
                    + $"{AttachmentPolicy.MaxAttachmentsPerSend} files, and this send already has {countSoFar}.");
                continue;
            }

            var resolved = AttachmentPolicy.RealPath(picked);

            if (Directory.Exists(resolved))
            {
                refusals.Add(
                    $"'{picked}' is a directory. One human act attaches one named file — no directory, "
                    + "glob, archive expansion or recursive walk.");
                continue;
            }

            if (AttachmentPolicy.IsArchive(resolved))
            {
                refusals.Add(
                    $"'{Path.GetFileName(resolved)}' is an archive. One human act attaches one named "
                    + "file; an archive is not expanded.");
                continue;
            }

            if (!File.Exists(resolved))
            {
                refusals.Add($"'{picked}' is not a file that can be read.");
                continue;
            }

            if (AttachmentPolicy.RefusalFor(resolved) is { } refusal)
            {
                refusals.Add($"'{Path.GetFileName(resolved)}' was refused by {refusal}.");
                continue;
            }

            // THE LABEL IS COMPUTED FROM THE RESOLVED PATH (C14(e)(ii)), never from the pick.
            var outside = !AttachmentPolicy.IsInsideWorkspace(resolved, _workspaceRoot);
            var length = _reader.Length(resolved);

            if (length > AttachmentPolicy.MaxAttachmentBytes)
            {
                refusals.Add(
                    $"'{Path.GetFileName(resolved)}' is {length} bytes, over the {AttachmentPolicy.MaxAttachmentBytes}-byte "
                    + "per-file cap. It is refused, not truncated.");
                continue;
            }

            if (bytesSoFar + length > AttachmentPolicy.MaxSendAttachmentBytes)
            {
                refusals.Add(
                    $"'{Path.GetFileName(resolved)}' is {length} bytes and this send already carries "
                    + $"{bytesSoFar}; the per-send cap is {AttachmentPolicy.MaxSendAttachmentBytes} bytes.");
                continue;
            }

            if (outside)
            {
                // ASKED BEFORE THE BYTES ARE READ. Declining leaves the draft byte-unchanged.
                var asked = new OutsideWorkspaceAffirmation(resolved, length, _providerName, _accountLabel);
                if (!_affirmation.Confirm(asked))
                {
                    refusals.Add($"'{resolved}' was not attached: the outside-workspace prompt was declined.");
                    continue;
                }
            }

            var bytes = _reader.ReadAllBytes(resolved);

            if (!AttachmentPolicy.TryDecodeUtf8(bytes, out var text, out var encoding))
            {
                refusals.Add(
                    $"'{Path.GetFileName(resolved)}' is not UTF-8 text — it reads as {encoding}. Only "
                    + "UTF-8 text is attachable.");
                continue;
            }

            var attachment = new ComposerAttachment(
                DisplayPath: outside ? resolved : RepositoryRelative(resolved),
                ResolvedPath: resolved,
                Bytes: bytes.Length,
                Text: text,
                IsOutsideWorkspace: outside,
                Sha256: Convert.ToHexStringLower(SHA256.HashData(bytes)));

            draft.Add(attachment);
            attached.Add(attachment);
            countSoFar++;
            bytesSoFar += attachment.Bytes;
        }

        return new AttachOutcome(attached, refusals, 0);
    }

    private string RepositoryRelative(string resolved) =>
        Path.GetRelativePath(_workspaceRoot, resolved).Replace('\\', '/');
}
