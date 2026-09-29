namespace AiDe.Core.Watcher;

/// <summary>
/// What could be established about one declared Proof Pack path.
/// </summary>
/// <remarks>
/// <b>Three states, not a bool</b>, because a bool is the defect this exists to fix.
/// <c>HasProofPack: false</c> was hardcoded on the agent scoring path, which collapsed
/// <i>we looked and there was none</i> — a fact about the episode — into
/// <i>there was nowhere to look</i>, a fact about the product. The scorecard then made a statement
/// about the agent when the true statement was about a missing channel. Reintroducing a bool here
/// would rebuild that collapse one layer down.
/// </remarks>
public enum ProofPackVerdict
{
    /// <summary>The declared path is a real committed Proof Pack inside the session's repository.</summary>
    Verified,

    /// <summary>We could look, and it is not there — or it is not a Proof Pack path at all.</summary>
    NotFound,

    /// <summary>We could not look. The repository is not reachable from here, so nothing is claimed.</summary>
    Unverifiable,
}

/// <summary>
/// Checks whether a path an agent declared is really a committed Proof Pack in its repository.
/// </summary>
/// <remarks>
/// <para><b>Why this makes agent-declared evidence admissible.</b> The owner's decision is that the
/// watcher <i>derives</i> — it observes rather than accepts testimony, which is why an
/// <c>episode-close</c> carrying its own <c>acceptance_met</c> stays refused. A declared path is
/// different in exactly the way that matters: <b>the agent names a file and the product checks
/// whether the file is there</b>. The agent cannot make the check pass by asserting harder. That is
/// an observation about a claim, not a claim accepted.</para>
///
/// <para><b>Why not simply scan the repository for Proof Packs.</b> Because nothing links one to an
/// episode, and crediting an episode with any <c>docs/proof/</c> file found in the tree would
/// fabricate <i>presence</i> — an agent scored for someone else's evidence. That is strictly worse
/// than the bug being fixed: today's value is an honest zero about the wrong subject, where that
/// would be a wrong number that looks like a right one.</para>
///
/// <para><b>The containment check is a security boundary, not tidiness.</b> The declared path
/// arrives from outside the product, verbatim and uninspected by the ingest half — absolute paths,
/// traversal, and escaping are all recorded exactly as sent, deliberately, so that this layer
/// decides what is true. A path escaping the repository would let a session point at another
/// repository's evidence, or at any file on the machine whose existence then becomes a score.</para>
///
/// <para><b>NO PRODUCTION CALLER ON THIS BRANCH.</b> Stated rather than left to be found (DC-089).
/// The caller is <see cref="ClosedEpisodeScoring"/>, which will read declared artifacts from the
/// store once the contract half lands, and it is deliberately not written yet because the store
/// method it needs does not exist here. This claim is a negative and negatives decay when someone
/// else acts (DC-094), so it is tied to something that fails: the day
/// <c>ClosedEpisodeScoring</c> calls this, <c>WhatDaydreamSeesInAnAgentEpisodeTests</c> goes red,
/// because an evidenced episode stops being unremarkable.</para>
/// </remarks>
public static class ProofPackVerifier
{
    /// <summary>The committed location a Proof Pack lives in, matching the audit-log convention.</summary>
    /// <remarks>
    /// The same substring <c>AuditLogEpisodeSource</c> looks for in an audit entry's artifacts, so
    /// the two evidence paths agree on what a Proof Pack IS. Two definitions of that would let an
    /// episode be evidenced on one path and unevidenced on the other.
    /// </remarks>
    public const string ProofDirectory = "docs/proof/";

    /// <summary>
    /// The verdict for one declared path across every checkout the session could have committed it
    /// in, and the method a caller holding a <c>SessionBinding</c> wants (DC-115).
    /// </summary>
    /// <remarks>
    /// <para><b>Why more than one root.</b> A repository has several working trees, and the one a
    /// lane commits its evidence in is its own linked worktree, on its own branch. Reading only the
    /// canonical repository path answers about the PARENT checkout — a different tree, on a
    /// different branch, which simply does not contain the file. That produced <c>Not Scored — no
    /// minimum verification path</c> for evidence that existed and was named: a false statement
    /// about the agent where the true statement was about where somebody looked.</para>
    ///
    /// <para><b>Verified wins, and the fold is therefore order-independent.</b> A verdict per root,
    /// combined so that <c>Verified</c> beats <c>NotFound</c> beats <c>Unverifiable</c>: finding it
    /// anywhere is finding it, "we looked in a real checkout and it is not there" outranks "we could
    /// not look", and an empty or wholly unreachable set stays <c>Unverifiable</c> rather than
    /// becoming an absence nobody observed. Nothing depends on which root is passed first, so a
    /// caller cannot get this wrong by ordering it wrong.</para>
    ///
    /// <para><b>Containment is unchanged, and per root.</b> Each candidate is checked whole against
    /// one root — the declared path must land inside THAT root's tree and under its
    /// <c>docs/proof/</c>. Several roots is several complete checks, never a widened one: a path
    /// escaping every root is still <c>NotFound</c>, and neighbouring-directory admission is still
    /// refused by the separator-terminated prefix test. <b>Which roots are legitimate is the
    /// caller's decision, not this method's</b> — see <see cref="ClosedEpisodeScoring"/>, which
    /// admits a second checkout only when the filesystem confirms it belongs to the bound
    /// repository.</para>
    /// </remarks>
    /// <param name="checkouts">
    /// The working trees to look in. Null and blank entries are tolerated and answer
    /// <c>Unverifiable</c> on their own, so a caller need not filter an absent worktree out.
    /// </param>
    /// <param name="declaredPath">The path exactly as the agent sent it, unmodified by the ingest.</param>
    public static ProofPackVerdict VerifyInCheckouts(IReadOnlyList<string?> checkouts, string? declaredPath)
    {
        ArgumentNullException.ThrowIfNull(checkouts);

        // Unverifiable is the honest start: nothing has been looked at yet.
        var best = ProofPackVerdict.Unverifiable;

        foreach (var checkout in checkouts)
        {
            var verdict = Verify(checkout, declaredPath);

            if (verdict is ProofPackVerdict.Verified)
            {
                return ProofPackVerdict.Verified;
            }

            if (verdict is ProofPackVerdict.NotFound)
            {
                best = ProofPackVerdict.NotFound;
            }
        }

        return best;
    }

    /// <summary>
    /// The verdict for one declared path, relative to ONE working tree.
    /// </summary>
    /// <param name="repositoryRoot">
    /// <para>The working tree to look in — a directory on this machine, not an identity.</para>
    ///
    /// <para><b>The canonical repository path is not sufficient on its own</b>, and the comment here
    /// used to say that it was: <i>"the corrected one, so a worktree-registered agent is checked
    /// against the repository its evidence is actually committed in"</i>. That holds only for a
    /// worktree sharing the parent's branch, and is false for every lane on its own — which is
    /// DC-115. It survived because a reasoned-through comment reads as though somebody had checked.
    /// A caller holding a session should use <see cref="VerifyInCheckouts"/>.</para>
    /// </param>
    /// <param name="declaredPath">The path exactly as the agent sent it, unmodified by the ingest.</param>
    public static ProofPackVerdict Verify(string? repositoryRoot, string? declaredPath)
    {
        // THE IDENTITY-TO-FILESYSTEM BOUNDARY, and it belongs here rather than in the caller.
        //
        // The repository root arrives as WatcherIdentity.Canonicalise's output, which normalises to a
        // BACKSLASH on every platform so that two spellings of one directory collapse to one
        // repository in the fleet map wherever they are read. That is right for an identity and wrong
        // for a path: on Linux it asks the OS about "\tmp\xyz", a single filename with no separators,
        // so Directory.Exists was false for every Linux repository and this returned Unverifiable
        // before looking at anything. A committed Proof Pack simply stopped counting as evidence, and
        // the verdict said "we could not look" rather than "it is not there" — which is the honest
        // answer to the wrong question (INV-0005).
        //
        // ONE definition of the conversion, shared with the locator's own boundary. It was two
        // copies and a rule in prose, and the prose is what the next boundary was written against.
        var reachable = RepositoryIdentity.ToFileSystemPath(repositoryRoot);

        // No repository we can reach means we cannot look. Saying NotFound here would be the
        // hardcoded false all over again, in the one case where the product is the thing at fault.
        if (string.IsNullOrWhiteSpace(reachable) || !Directory.Exists(reachable))
        {
            return ProofPackVerdict.Unverifiable;
        }

        repositoryRoot = reachable;

        if (string.IsNullOrWhiteSpace(declaredPath))
        {
            return ProofPackVerdict.NotFound;
        }

        try
        {
            var root = Path.TrimEndingDirectorySeparator(Path.GetFullPath(repositoryRoot));

            // Combine handles the relative case and RETURNS THE SECOND ARGUMENT UNCHANGED when it is
            // rooted — which is why containment is checked below rather than assumed from the join.
            // An absolute declared path lands wherever it points, and must then be rejected on its
            // own merits, not silently reinterpreted as relative.
            var full = Path.GetFullPath(Path.Combine(root, declaredPath));

            if (!IsInside(root, full))
            {
                return ProofPackVerdict.NotFound;
            }

            // Compared against the repository-relative portion, so a repository that merely happens
            // to live under a directory called docs/proof does not make every file in it evidence.
            var relative = full[root.Length..].TrimStart('\\', '/').Replace('\\', '/');

            // THE SAME RULE AS CONTAINMENT, and it was not. This read OrdinalIgnoreCase on every
            // platform while IsInside two members below already asked the platform - so the file
            // disagreed with itself, and on Linux "DOCS/PROOF/x.md" was admitted as a Proof Pack
            // path. That is not tidiness: this method decides Verified / NotFound / Unverifiable,
            // so a verifier that accepts a spelling nothing in the system would ever WRITE makes
            // "Verified" mean something slightly different from what every reader takes it to mean.
            if (!relative.StartsWith(ProofDirectory, PathComparison.ForThisFileSystem))
            {
                return ProofPackVerdict.NotFound;
            }

            // A directory is not a Proof Pack, and File.Exists is false for one, so this also rejects
            // a declaration pointing at the docs/proof folder itself.
            return File.Exists(full) ? ProofPackVerdict.Verified : ProofPackVerdict.NotFound;
        }
        catch (Exception ex) when (ex is ArgumentException or IOException
            or NotSupportedException or UnauthorizedAccessException or PathTooLongException)
        {
            // A path the filesystem refuses to even evaluate is not evidence, and it is not our
            // inability to look either — the agent sent something unusable.
            return ProofPackVerdict.NotFound;
        }
    }

    /// <summary>
    /// Whether <paramref name="candidate"/> is contained by <paramref name="root"/>.
    /// </summary>
    /// <remarks>
    /// <para>The separator is appended before comparing, because a plain prefix test says
    /// <c>C:\repos\app-other</c> is inside <c>C:\repos\app</c> — a neighbouring repository admitted
    /// as this one's evidence, which is the containment failure that matters most here.</para>
    ///
    /// <para>The case rule is <see cref="AiDe.Core.PathComparison.ForThisFileSystem"/>'s - the one
    /// platform-conditional rule every containment boundary in this assembly consults. It was
    /// written inline here and as a hardcoded <c>OrdinalIgnoreCase</c> in the directory match,
    /// which is how one member ended up POSIX-correct and the other did not; it is now a shared
    /// member because three further sites were carrying their own copy of the wrong half.</para>
    /// </remarks>
    private static bool IsInside(string root, string candidate)
    {
        if (string.Equals(root, candidate, PathComparison.ForThisFileSystem))
        {
            return false;
        }

        return candidate.StartsWith(root + Path.DirectorySeparatorChar, PathComparison.ForThisFileSystem);
    }

}
