using System.Diagnostics;
using AiDe.Core.PromptCompilation;

namespace AiDe.Core.Tests.Compilation;

/// <summary>
/// <c>compile.mode.changed{from, to, trigger}</c> (ADR-0036; CV-4) — the compile-mode ladder's
/// transition history, one event per real transition, for each of the four trigger words.
/// </summary>
public sealed class TheCompileModeChangedEventTests
{
    /// <summary>The trigger vocabulary is exactly the four named words, in the order the plan names them.</summary>
    [Fact]
    public void TheTriggerVocabularyIsExactlyFourWords()
    {
        Assert.Equal(
            [CompileModeChangeTriggers.Operator, CompileModeChangeTriggers.Gate, CompileModeChangeTriggers.Ring, CompileModeChangeTriggers.Drift],
            CompileModeChangeTriggers.All);
        Assert.Equal(["operator", "gate", "ring", "drift"], CompileModeChangeTriggers.All);
    }

    /// <summary>Each trigger word produces its own <c>compile.mode.changed</c> row carrying <c>from</c>/<c>to</c>/<c>trigger</c> — the reds list's "rows with each trigger".</summary>
    [Theory]
    [InlineData(CompileModeChangeTriggers.Operator)]
    [InlineData(CompileModeChangeTriggers.Gate)]
    [InlineData(CompileModeChangeTriggers.Ring)]
    [InlineData(CompileModeChangeTriggers.Drift)]
    public void ModeChangedEmitsFromToAndTrigger(string trigger)
    {
        using var capture = ActivityCapture.Open(CompileSignal.SourceName, CompileEventKinds.ModeChanged);

        CompileSignal.ModeChanged("agentic", "agentic-advisory", trigger);

        var activity = Assert.Single(capture.Activities);
        Assert.Equal("agentic", activity.GetTagItem("from"));
        Assert.Equal("agentic-advisory", activity.GetTagItem("to"));
        Assert.Equal(trigger, activity.GetTagItem("trigger"));
    }

    /// <summary>Listens for named activities on one source and keeps every one started while open — the pattern <c>ComposeCounter</c> uses, generalised to inspect tags.</summary>
    private sealed class ActivityCapture : IDisposable
    {
        private readonly ActivityListener _listener;
        private readonly List<Activity> _activities = [];

        private ActivityCapture(string sourceName, string operationName)
        {
            _listener = new ActivityListener
            {
                ShouldListenTo = source => source.Name == sourceName,
                Sample = (ref ActivityCreationOptions<ActivityContext> _) => ActivitySamplingResult.AllDataAndRecorded,
                ActivityStarted = activity =>
                {
                    if (activity.OperationName == operationName)
                    {
                        lock (_activities)
                        {
                            _activities.Add(activity);
                        }
                    }
                },
            };
            ActivitySource.AddActivityListener(_listener);
        }

        public IReadOnlyList<Activity> Activities
        {
            get
            {
                lock (_activities)
                {
                    return [.. _activities];
                }
            }
        }

        public static ActivityCapture Open(string sourceName, string operationName) => new(sourceName, operationName);

        public void Dispose() => _listener.Dispose();
    }
}
