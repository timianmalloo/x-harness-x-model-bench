namespace AiDe.Core.Extraction;

/// <summary>Where an import or require specifier resolves.</summary>
public enum ImportOrigin
{
    Builtin,
    Workspace,
    External,
}

/// <summary>
/// Classifies a raw import/require specifier by where it resolves, reusing the existing
/// per-runtime builtin lists (<see cref="PythonStandardLibrary"/>, <see cref="NodeBuiltinModules"/>)
/// and a caller-supplied set of workspace module ids. Pure: no file I/O, no extractor wiring.
/// </summary>
public static class ImportOriginRule
{
    public static ImportOrigin Classify(string language, string specifier, IReadOnlySet<string> workspaceModuleIds)
    {
        ArgumentNullException.ThrowIfNull(language);
        ArgumentNullException.ThrowIfNull(specifier);
        ArgumentNullException.ThrowIfNull(workspaceModuleIds);
        if (language is not ("python" or "node"))
        {
            throw new ArgumentException($"language must be \"python\" or \"node\", not \"{language}\".", nameof(language));
        }
        if (specifier.Length == 0)
        {
            throw new ArgumentException("specifier must not be empty.", nameof(specifier));
        }

        var isPython = language == "python";
        var isRelativePathShaped = isPython
            ? specifier.StartsWith('.')
            : specifier.StartsWith("./", StringComparison.Ordinal)
                || specifier.StartsWith("../", StringComparison.Ordinal)
                || specifier.StartsWith('/');
        if (isRelativePathShaped)
        {
            return ImportOrigin.Workspace;
        }

        var isBuiltin = isPython ? PythonStandardLibrary.Contains(specifier) : NodeBuiltinModules.Contains(specifier);
        if (isBuiltin)
        {
            return ImportOrigin.Builtin;
        }

        return workspaceModuleIds.Contains(specifier) ? ImportOrigin.Workspace : ImportOrigin.External;
    }
}
