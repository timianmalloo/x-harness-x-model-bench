namespace AiDe.Core.Extraction;

/// <summary>
/// How a module-shaped scope names its files, so that two scopes cannot name the same node.
/// </summary>
/// <remarks>
/// <para><b>The defect this closes.</b> Both the Python and TypeScript extractors named a module by
/// its path RELATIVE TO ITS OWN SCOPE, and a scope is one directory. Every Python package has an
/// <c>__init__.py</c>, so a repository with five packages produced five scopes each declaring a
/// module called <c>__init__</c> — which is ONE node in the graph, carrying the merged edges of five
/// unrelated files. The same holds for <c>index.ts</c>, <c>main</c>, <c>setup</c> and
/// <c>conftest</c>. Nothing failed; the graph was simply wrong in a way no count could show.</para>
///
/// <para><b>The id is the repository-relative path, without its extension.</b> Unique by
/// construction, readable, and the same string a person would type to open the file. It is also
/// what makes cross-scope resolution possible: an import naming a sibling package is a path from the
/// repository root, and now so is every module id.</para>
/// </remarks>
public static class ModuleNaming
{
    /// <summary>
    /// The scope's own directory, relative to the repository root, from its id.
    /// </summary>
    /// <remarks>
    /// Discovery builds these ids as <c>python:&lt;relative path&gt;</c>, so the prefix is already
    /// carried; deriving it here avoids threading the repository root through a contract that four
    /// other extractors do not need.
    /// </remarks>
    public static string ScopePrefix(string scopeId)
    {
        var cut = scopeId.IndexOf(':', StringComparison.Ordinal);
        var relative = cut < 0 ? scopeId : scopeId[(cut + 1)..];

        // Discovery writes "." for a scope that IS the repository root.
        return relative is "." or "" ? string.Empty : relative.Trim('/');
    }

    /// <summary>The globally unique id of a module, from its path within the scope.</summary>
    public static string Qualify(string scopePrefix, string moduleWithinScope) =>
        scopePrefix.Length == 0 ? moduleWithinScope : scopePrefix + "/" + moduleWithinScope;
}
