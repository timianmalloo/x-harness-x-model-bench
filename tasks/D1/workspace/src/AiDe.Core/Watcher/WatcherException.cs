namespace AiDe.Core.Watcher;

/// <summary>
/// A watcher-core failure carrying a stable <see cref="Code"/> (Observability Standard O7). The
/// message is for humans and may change; the code is for machines and search and does not.
/// </summary>
public sealed class WatcherException : Exception
{
    public WatcherException(string code, string message) : base(message) => Code = code;

    /// <summary>A stable <see cref="WatcherErrorCodes"/> value.</summary>
    public string Code { get; }
}
