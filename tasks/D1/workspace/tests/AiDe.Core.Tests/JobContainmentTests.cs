using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.Versioning;
using AiDe.Core.Terminal;

namespace AiDe.Core.Tests;

/// <summary>
/// A Job Object assignment that does not happen must say so.
/// </summary>
/// <remarks>
/// <para><b>Red-first, and the red was that nothing happened.</b> Before this control,
/// <see cref="ConPtyTerminalSession.StartAsync"/> and
/// <c>TerminalHostLauncher.RunInNewConsoleAsync</c> both called <c>AssignProcessToJobObject</c>
/// and discarded the boolean. Reproduced against a job whose object
/// had been closed, the call returned <c>false</c>, set <c>ERROR_INVALID_HANDLE</c> (6), raised
/// nothing, and left the child running outside the job - and the test asserting all of that
/// PASSED. That is the shape the whole defect takes: the job exists, the process is not in it, and
/// every signal a reviewer reads is green.</para>
///
/// <para><b>The structural half of the fix is not in this file.</b> The raw import is now
/// <c>private</c>, so <see cref="ConPtyInterop.AssignProcessToJob"/> is the only way to reach it
/// from anywhere - including this assembly, since <c>InternalsVisibleTo</c> does not extend to
/// private members. A future call site cannot discard the answer, because the answer is no longer
/// offered. This test is the proof that the one remaining way fires.</para>
/// </remarks>
[Trait("Platform", "Windows")]
[SupportedOSPlatform("windows")]
public sealed class JobContainmentTests
{
    [Fact]
    public void AnAssignThatCannotHappenIsNotSilent()
    {
        // Taken BEFORE the job handle closes, so nothing allocates a handle in between and the
        // closed value cannot be re-issued to something else under us. It could not be re-issued to
        // a JOB in any case - nothing here creates one - so the assign cannot accidentally succeed
        // and put the test host in a kill-on-close job.
        using var self = Process.GetCurrentProcess();
        var handle = self.Handle;

        // A job whose last handle has closed: the object is gone, which is the cheapest genuine
        // failure and exactly the shape a real one takes.
        var job = ConPtyInterop.CreateKillOnCloseJob();
        ConPtyInterop.CloseHandle(job);

        var error = Assert.Throws<Win32Exception>(() => ConPtyInterop.AssignProcessToJob(job, handle));

        // The native code is asserted so a throw for some OTHER reason cannot pass for this one:
        // 6 is ERROR_INVALID_HANDLE, the operating system agreeing the job was gone.
        Assert.Equal(6, error.NativeErrorCode);
        Assert.Contains("AssignProcessToJobObject", error.Message, StringComparison.Ordinal);
    }
}
