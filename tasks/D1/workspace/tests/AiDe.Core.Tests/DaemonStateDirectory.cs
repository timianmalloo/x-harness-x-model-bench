namespace AiDe.Core.Tests;

/// <summary>
/// Where a daemon launched BY A TEST keeps its state.
/// </summary>
/// <remarks>
/// <para>Beside the temp workspace, never the machine-wide default. The daemon used to derive its
/// own directory under LocalAppData with no way for a caller to say otherwise, so every test that
/// launched one wrote into the user's real profile. MEASURED: one run of this suite left <b>12</b>
/// workspace directories there, and <b>2,674</b> had accumulated over four days — all but one of
/// them an empty store belonging to a test that had long since finished.</para>
///
/// <para>Nothing failed, which is the point. A test suite that leaves state outside its own temp
/// directory is not isolated, and the only symptom is a folder somebody eventually notices.</para>
/// </remarks>
internal static class DaemonStateDirectory
{
    /// <summary>The state directory for a test workspace, removed with it.</summary>
    public static string For(string workspace) => Path.Combine(workspace, ".aide-data");

    /// <summary>The `--data` argument pair, for a launcher that takes extra arguments.</summary>
    public static string[] ArgumentsFor(string workspace) => ["--data", For(workspace)];
}
