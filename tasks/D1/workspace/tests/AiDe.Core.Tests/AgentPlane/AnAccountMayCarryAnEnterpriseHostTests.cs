using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// The enterprise host is a field on the <b>account</b> in <c>providers.json</c> — never on the
/// engine row (Ruling 97 condition 3; Ruling 105 (1): <c>Account = (provider, label, health, host?)</c>).
/// </summary>
/// <remarks>
/// <para><b>Red-first.</b> Before <c>host</c> was a known member the reader refused the whole file
/// with "carries \"host\", which this reader does not know" — the right refusal for a typo, the
/// wrong one for the field the ruling names.</para>
///
/// <para><b>Extends §14.2, and is marked as such</b> beside <c>observedAuthLabel</c> in the reader;
/// the errata note records it. The value is passed to the copilot CLI verbatim as
/// <c>COPILOT_GH_HOST</c> (hostname form, per <c>copilot help environment</c>:
/// <c>spikes/engine-backends/copilot/copilot-help-environment.txt:51</c>); whether the ACP server
/// reads it at session time was <b>not observable</b> without a tenant (spike §1, "Not recorded").</para>
/// </remarks>
public sealed class AnAccountMayCarryAnEnterpriseHostTests
{
    private static string Write(string json)
    {
        var path = Path.Combine(
            Path.GetTempPath(), "aide-providers", Guid.NewGuid().ToString("N"), "providers.json");

        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, json);
        return path;
    }

    /// <summary>An account's <c>host</c> is read onto <see cref="ProviderAccount.Host"/>; an account without one reads <c>null</c>.</summary>
    [Fact]
    public void AHostOnAnAccountIsReadAndAnAbsentOneIsNull()
    {
        var config = ProviderConfiguration.Read(Write("""
            {
              "adapterInstallRoot": "C:/adapters",
              "providers": {
                "github": { "auth": "subscription", "accounts": [
                  { "label": "work", "health": "ready", "host": "mycompany.ghe.com" },
                  { "label": "personal", "health": "ready" }
                ] }
              }
            }
            """));

        var accounts = config.Registry.Find("github").Accounts;
        Assert.Equal("mycompany.ghe.com", accounts[0].Host);
        Assert.Null(accounts[1].Host);
    }

    /// <summary>A <c>host</c> that is present and not a string is a refusal naming the field, like every other typed member.</summary>
    [Fact]
    public void AHostThatIsNotAStringIsRefused()
    {
        var error = Assert.Throws<AgentPlaneException>(() => ProviderConfiguration.Read(Write("""
            {
              "adapterInstallRoot": "C:/adapters",
              "providers": {
                "github": { "auth": "subscription", "accounts": [ { "label": "work", "health": "ready", "host": 42 } ] }
              }
            }
            """)));

        Assert.Equal(AgentPlaneErrorCodes.ProviderConfigurationMalformed, error.Code);
        Assert.Contains("host", error.Message, StringComparison.Ordinal);
    }

    /// <summary>A blank <c>host</c> is refused: it looks configured and configures nothing.</summary>
    [Fact]
    public void ABlankHostIsRefused()
    {
        var error = Assert.Throws<AgentPlaneException>(() => ProviderConfiguration.Read(Write("""
            {
              "adapterInstallRoot": "C:/adapters",
              "providers": {
                "github": { "auth": "subscription", "accounts": [ { "label": "work", "health": "ready", "host": "  " } ] }
              }
            }
            """)));

        Assert.Equal(AgentPlaneErrorCodes.ProviderConfigurationMalformed, error.Code);
        Assert.Contains("host", error.Message, StringComparison.Ordinal);
    }

    /// <summary>
    /// The host travels on the binding — <c>LaneBinding.Account.Host</c> — so the launch can read
    /// it from the account the run bills against, never from a second field.
    /// </summary>
    [Fact]
    public void TheHostTravelsOnTheBindingsAccount()
    {
        var config = ProviderConfiguration.Read(Write("""
            {
              "adapterInstallRoot": "C:/adapters",
              "providers": {
                "github": { "auth": "subscription", "accounts": [ { "label": "work", "health": "ready", "host": "mycompany.ghe.com" } ] }
              },
              "engines": { "copilot": { "model": "claude-sonnet-5" } }
            }
            """));

        var binding = config.Bind("copilot", out var refusal);

        Assert.Null(refusal);
        Assert.Equal("mycompany.ghe.com", binding!.Account.Host);
        Assert.Equal("mycompany.ghe.com", Assert.Single(EngineCatalog.LaunchEnvironment(EngineCatalog.Find(binding.EngineId), binding.Account)).Value);
    }
}
