namespace AiDe.Core.Projections;

/// <summary>One line of a workspace file that contains the term.</summary>
/// <param name="NodeId">
/// The node this file belongs to, so a hit is something the surface can navigate to rather than a
/// path the client would have to resolve itself.
/// </param>
/// <param name="Line">1-based line number.</param>
/// <param name="Text">The matching line, trimmed and bounded.</param>
public sealed record ContentMatch(string NodeId, string RelativePath, int Line, string Text);

/// <summary>What a corpus content search found, and what it did not look at.</summary>
/// <param name="FilesSearched">How many files were actually read.</param>
/// <param name="FilesSkipped">
/// Files the search did not read — too large, unreadable, or not text. Reported rather than
/// silently dropped: a search that quietly skipped half the corpus and said nothing would be a
/// coverage claim nobody could check (DC-025).
/// </param>
public sealed record ContentSearchResult(
    IReadOnlyList<ContentMatch> Matches,
    int FilesSearched,
    int FilesSkipped,
    bool Truncated,
    ResultBounds Bounds,
    string SourceRevision);
