using AiDe.Core.Presentation.Composer;
using AiDe.Core.PromptCompilation;

namespace AiDe.Core.Tests.Compilation;

/// <summary>
/// Ruling 105 (2): a per-turn account choice is the Ruling 63/72 shape — an <c>account</c> row with
/// <c>source: operator</c> written by the pre-compile at Send, read back by the projection, and
/// shown on the decoration line beside the session's default; no choice writes no row, and the
/// line reads the default with <c>session default</c> beside it.
/// </summary>
public sealed class TheAccountChoiceIsAnOperatorRowTests
{
    private static PreCompileInput Input(ComposerDraft draft) =>
        new(draft, null, "s-105", "claude-code", AiDe.Core.Sessions.CompileModes.MechanicalOnly, AiDe.Core.Watcher.TaskClasses.FreeForm);

    [Fact]
    public void AChoiceIsAnOperatorRow_AndNoChoiceIsNoRow()
    {
        var chosen = new ComposerDraft();
        chosen.ChooseAccount("work");
        var rows = PreCompile.Open(Input(chosen), "e1");
        var row = Assert.Single(rows.OfType<Decorated>(), d => d.Name == DecorationNames.Account);
        Assert.Equal(DecorationSources.Operator, row.Source);
        Assert.Equal("work", row.ValueAsString);

        var silent = new ComposerDraft();
        Assert.DoesNotContain(PreCompile.Open(Input(silent), "e2").OfType<Decorated>(), d => d.Name == DecorationNames.Account);

        chosen.ChooseAccount(null);
        Assert.Null(chosen.AccountChoice);
    }

    [Fact]
    public void TheProjectionReadsTheChoice_AndTheDecorationLineShowsItOrTheDefault()
    {
        var chosen = new ComposerDraft();
        chosen.ChooseAccount("work");
        var projection = Projection.Project(PreCompile.Live(Input(chosen)), chosen);
        Assert.Equal("work", projection.AccountOverride);

        var line = ComposerCompiler.Decorations(chosen, AiDe.Core.Watcher.TaskClasses.FreeForm, engineId: "claude-code", sessionId: "s-105", defaultAccountLabel: "max");
        var account = Assert.Single(line, r => r.Name == "account");
        Assert.Equal("work", account.Value);
        Assert.Equal(DecorationSources.Operator, account.Source);
        Assert.Equal("chosen for this turn", account.Reason);

        var silent = new ComposerDraft();
        Assert.Null(Projection.Project(PreCompile.Live(Input(silent)), silent).AccountOverride);
        var defaulted = Assert.Single(ComposerCompiler.Decorations(silent, AiDe.Core.Watcher.TaskClasses.FreeForm, engineId: "claude-code", sessionId: "s-105", defaultAccountLabel: "max"), r => r.Name == "account");
        Assert.Equal("max", defaulted.Value);
        Assert.Equal(DecorationSources.SessionDefault, defaulted.Source);
        Assert.Equal("session default", defaulted.Reason);

        // Unbound: the value is honest, never a plausible label.
        Assert.Equal(Envelope.NotRecorded, Assert.Single(ComposerCompiler.Decorations(silent, AiDe.Core.Watcher.TaskClasses.FreeForm), r => r.Name == "account").Value);
    }
}
