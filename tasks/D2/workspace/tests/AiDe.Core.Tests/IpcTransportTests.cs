using System.IO.Pipes;
using System.Runtime.Versioning;
using System.Security.AccessControl;
using System.Security.Principal;
using AiDe.Core.Ipc;

namespace AiDe.Core.Tests;

/// <summary>
/// `P2-IPC-03..07` and `P2-SEC-*` over a <b>real named pipe</b>.
/// </summary>
/// <remarks>
/// <para><see cref="IpcBoundaryTests"/> attacks the authorization decisions without a socket, which
/// is what made them testable at all. This suite covers what only a connection can answer: whether
/// the ACL is what we believe, whether identity is derived from the kernel rather than a claim,
/// whether a flood is refused instead of queued, and whether the daemon actually goes away when
/// nobody needs it.</para>
///
/// <para><b>The gap these close.</b> Everything above the transport was proven months of commits
/// before the transport existed; a boundary that is correct in every decision and wrong about who is
/// connected is wrong about everything.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class IpcTransportTests
{
    private const string Workspace = "ws-transport";
    private const long Epoch = 7;

    /// <summary>A unique pipe name per test, so a leftover server cannot serve the next one.</summary>
    private static string FreshPipeName() => $"aide.test.{Guid.NewGuid():N}";

    private static DaemonEndpoint Endpoint(long epoch = Epoch)
    {
        var endpoint = new DaemonEndpoint(Workspace, new CapabilityRegistry(), _ => epoch);
        endpoint.Register("describe", (request, _) => IpcResponse.Success(IpcPayloadTestExtensions.Json($"described:{request.Payload.AsText()}")));
        endpoint.Register("slow", (_, _) =>
        {
            Thread.Sleep(400);
            return IpcResponse.Success(IpcPayloadTestExtensions.Json("slow-done"));
        });
        return endpoint;
    }

    /// <summary>Runs a server for the body's duration and shuts it down afterwards.</summary>
    private static async Task WithServer(
        IpcServer server, string pipeName, Func<string, IpcServer, Task> body)
    {
        using var life = new CancellationTokenSource(TimeSpan.FromSeconds(60));
        var running = server.RunAsync(life.Token);

        try
        {
            await body(pipeName, server);
        }
        finally
        {
            await life.CancelAsync();
            try
            {
                await running;
            }
            catch (OperationCanceledException)
            {
            }
        }
    }

    private static async Task<IpcClient> ConnectAsync(string pipeName) =>
        await IpcClient.ConnectAsync(pipeName, TimeSpan.FromSeconds(15), CancellationToken.None);

    // ---- the happy path exists, and only over a real pipe ------------------------

    [Fact]
    public async Task AClient_OpensAWorkspace_AndInvokesAnOperation()
    {
        var pipeName = FreshPipeName();
        var server = new IpcServer(pipeName, Endpoint());

        await WithServer(server, pipeName, async (name, _) =>
        {
            await using var client = await ConnectAsync(name);

            var opened = await client.OpenWorkspaceAsync(Workspace, Epoch, CancellationToken.None);
            Assert.True(opened.Ok, opened.Reason);
            Assert.True(client.IsOpen);

            var response = await client.InvokeAsync(
                "describe", "cmd-1", Workspace, Epoch, IpcPayloadTestExtensions.Json("payload"), CancellationToken.None);

            Assert.True(response.Ok, response.Reason);
            Assert.Equal("described:payload", response.Payload.AsText());
        });
    }

    [Fact]
    public async Task AnInvokeWithoutOpening_IsRejected()
    {
        // The capability is the whole authorization story; a connection that skipped the handshake
        // has none, and must not be served on the strength of having connected.
        //
        // NotAuthorized rather than CapabilityUnknown, and the distinction is deliberate upstream:
        // "carried no capability" is a different fact from "carried one I do not recognise", and
        // only the second tells an attacker anything about which tokens are live.
        var pipeName = FreshPipeName();
        var server = new IpcServer(pipeName, Endpoint());

        await WithServer(server, pipeName, async (name, _) =>
        {
            await using var client = await ConnectAsync(name);

            var response = await client.InvokeAsync(
                "describe", "cmd-1", Workspace, Epoch, null, CancellationToken.None);

            Assert.False(response.Ok);
            Assert.Equal(IpcErrorCodes.NotAuthorized, response.ErrorCode);
        });
    }

    [Fact]
    public async Task AnUnsupportedVersion_IsRejectedWithTheSupportedSet_OverTheWire()
    {
        // The version rejection carries what we DO speak so a bootstrap can act rather than guess.
        // That the field survives serialisation is a wire concern, invisible to the endpoint tests.
        var pipeName = FreshPipeName();
        var server = new IpcServer(pipeName, Endpoint());

        await WithServer(server, pipeName, async (name, _) =>
        {
            await using var client = await ConnectAsync(name);

            var response = await client.SendAsync(
                new IpcMessage(
                    IpcMessage.Open,
                    new IpcRequest(999, "open", "cmd-1", Workspace, Epoch, null, null)),
                CancellationToken.None);

            Assert.False(response.Ok);
            Assert.Equal(IpcErrorCodes.UnsupportedVersion, response.ErrorCode);
            Assert.NotNull(response.SupportedVersions);
            Assert.Contains(IpcVersion.Current, response.SupportedVersions!);
        });
    }

    [Fact]
    public async Task AWorkspaceMismatch_IsRejected_BeforeAnyCapabilityExists()
    {
        var pipeName = FreshPipeName();
        var server = new IpcServer(pipeName, Endpoint());

        await WithServer(server, pipeName, async (name, _) =>
        {
            await using var client = await ConnectAsync(name);

            var response = await client.OpenWorkspaceAsync(
                "some-other-workspace", Epoch, CancellationToken.None);

            Assert.False(response.Ok);
            Assert.Equal(IpcErrorCodes.WorkspaceMismatch, response.ErrorCode);
            Assert.False(client.IsOpen);
        });
    }

    // ---- P2-SEC: identity comes from the kernel ---------------------------------

    [Fact]
    public void ThePipeAcl_AdmitsOnlyTheOwner()
    {
        // Read back what was actually created rather than trusting the call that created it. Absent
        // this control, a pipe carrying a workspace's whole command surface could be reachable by
        // every process on the machine and nothing would say so.
        var pipeName = FreshPipeName();
        using var pipe = IpcPipeFactory.CreateServer(pipeName, 1);

        var security = pipe.GetAccessControl();
        var rules = security
            .GetAccessRules(true, true, typeof(SecurityIdentifier))
            .Cast<PipeAccessRule>()
            .ToList();

        var owner = WindowsIdentity.GetCurrent().User!.Value;

        Assert.NotEmpty(rules);
        Assert.All(rules, rule => Assert.Equal(AccessControlType.Allow, rule.AccessControlType));
        Assert.All(rules, rule => Assert.Equal(owner, rule.IdentityReference.Value));
    }

    [Fact]
    public async Task ThePeersIdentity_IsDerivedFromTheConnection_NotFromThePayload()
    {
        // A peer that could state its own identity could state someone else's. The SID and process
        // id must match this process because that is who actually connected.
        var pipeName = FreshPipeName();
        IpcPeer? observed = null;

        var endpoint = new DaemonEndpoint(Workspace, new CapabilityRegistry(), _ => Epoch);
        endpoint.Register("whoami", (_, peer) =>
        {
            observed = peer;
            return IpcResponse.Success(IpcPayloadTestExtensions.Json("ok"));
        });

        var server = new IpcServer(pipeName, endpoint);

        await WithServer(server, pipeName, async (name, _) =>
        {
            await using var client = await ConnectAsync(name);
            await client.OpenWorkspaceAsync(Workspace, Epoch, CancellationToken.None);
            await client.InvokeAsync("whoami", "cmd-1", Workspace, Epoch, null, CancellationToken.None);
        });

        Assert.NotNull(observed);
        Assert.Equal(WindowsIdentity.GetCurrent().User!.Value, observed!.OwnerSid);
        Assert.Equal(Environment.ProcessId, observed.ProcessId);
    }

    [Fact]
    public async Task APeerWhoseSidIsNotTheOwners_IsRefused()
    {
        // The check exists because "the ACL made it impossible" is an assumption about a system
        // call's behaviour, and this is what would notice if it stopped being true.
        //
        // It cannot fire against a real foreign peer here — the ACL admits only this user, so every
        // client a test can create is already the right one. A mutation run proved the consequence:
        // the check could be deleted and nothing failed. Varying what the server EXPECTS tests the
        // decision without needing a second account.
        var pipeName = FreshPipeName();
        var server = new IpcServer(
            pipeName,
            Endpoint(),
            new IpcServerOptions(StartupGrace: TimeSpan.FromSeconds(20)),
            expectedOwnerSid: "S-1-5-21-0-0-0-1234");

        await WithServer(server, pipeName, async (name, running) =>
        {
            await using var client = await ConnectAsync(name);

            var response = await client.OpenWorkspaceAsync(Workspace, Epoch, CancellationToken.None);

            Assert.False(response.Ok);
            Assert.Equal(IpcErrorCodes.NotAuthorized, response.ErrorCode);
            Assert.Equal(1, running.IdentityRefusals);
            Assert.False(client.IsOpen);
        });
    }

    // ---- P2-IPC-07: what actually bounds a flood ---------------------------------

    [Fact]
    public async Task AFloodOfPipelinedRequests_IsServedSerially_WithoutUnboundedWork()
    {
        // The bound is serial service per connection, not a refusal.
        //
        // An earlier revision of this suite expected a `Busy` rejection, guarded by a per-connection
        // in-flight semaphore. That control could never fire: the serve loop reads, answers, and only
        // then reads again, so in-flight is one by construction. Rather than introduce concurrency
        // purely to make a limit reachable, the limit was removed and this test was rewritten to
        // assert the property that is actually true — every request answered, in order, with the
        // daemon doing one request's worth of work at a time.
        var pipeName = FreshPipeName();
        var server = new IpcServer(pipeName, Endpoint(), new IpcServerOptions(MaxConnections: 2));

        await WithServer(server, pipeName, async (name, _) =>
        {
            using var raw = IpcPipeFactory.CreateClient(name);
            await raw.ConnectAsync(15_000, CancellationToken.None);

            await Send(raw, IpcMessage.Open, "open", null);
            var opened = await Receive(raw);
            Assert.True(opened.Ok, opened.Reason);
            var capability = Capability(opened);

            // Written and read CONCURRENTLY, which is what a real pipelining client does and what
            // this had to become: with the writes done first, the responses fill the pipe's buffer,
            // the daemon blocks writing one, stops reading, and both ends deadlock. That deadlock is
            // a genuine property of a serial server, and it is why the response write now has a
            // timeout — see AClientThatNeverReads_IsDisconnected.
            const int Flood = 50;

            var writing = Task.Run(async () =>
            {
                for (var i = 0; i < Flood; i++)
                {
                    await Send(raw, IpcMessage.Invoke, "describe", capability);
                }
            });

            for (var i = 0; i < Flood; i++)
            {
                var response = await Receive(raw);
                Assert.True(response.Ok, $"request {i} was not served: {response.ErrorCode} {response.Reason}");
            }

            await writing;
        });
    }

    [Fact]
    public async Task OneBusyConnection_DoesNotStopAnotherClientBeingServed()
    {
        // The property that matters for a flood: containment. One connection working hard must not
        // make the daemon unavailable to a second shell, which is what "bounded lane" is protecting.
        var pipeName = FreshPipeName();
        var server = new IpcServer(pipeName, Endpoint(), new IpcServerOptions(MaxConnections: 4));

        await WithServer(server, pipeName, async (name, _) =>
        {
            await using var busy = await ConnectAsync(name);
            await busy.OpenWorkspaceAsync(Workspace, Epoch, CancellationToken.None);

            // "slow" sleeps inside the handler, so this connection is occupied while it runs.
            var occupied = busy.InvokeAsync(
                "slow", "cmd-slow", Workspace, Epoch, null, CancellationToken.None);

            await using var other = await ConnectAsync(name);
            var opened = await other.OpenWorkspaceAsync(Workspace, Epoch, CancellationToken.None);
            var served = await other.InvokeAsync(
                "describe", "cmd-other", Workspace, Epoch, IpcPayloadTestExtensions.Json("second"), CancellationToken.None);

            Assert.True(opened.Ok, opened.Reason);
            Assert.True(served.Ok, "a second client could not be served while the first was busy");
            Assert.Equal("described:second", served.Payload.AsText());

            Assert.True((await occupied).Ok);
        });
    }

    [Fact]
    public async Task AFrameAboveTheCap_IsRefused_BeforeTheDaemonAllocatesForIt()
    {
        // The other half of the flood story: one connection cannot make the daemon allocate an
        // arbitrary amount by claiming a large frame.
        var pipeName = FreshPipeName();
        var server = new IpcServer(pipeName, Endpoint());

        await WithServer(server, pipeName, async (name, _) =>
        {
            using (var hostile = IpcPipeFactory.CreateClient(name))
            {
                await hostile.ConnectAsync(15_000, CancellationToken.None);
                await hostile.WriteAsync(new byte[] { 0x40, 0x00, 0x00, 0x00 }, CancellationToken.None);
                await hostile.FlushAsync(CancellationToken.None);
                await Task.Delay(300);
            }

            await using var honest = await ConnectAsync(name);
            Assert.True((await honest.OpenWorkspaceAsync(Workspace, Epoch, CancellationToken.None)).Ok);
        });
    }

    [Fact]
    public async Task AClientThatNeverReads_IsDisconnected_SoItCannotHoldAListener()
    {
        // The failure this closes was found by the flood test above deadlocking. A client that
        // pipelines and never drains its responses fills the pipe buffer; the daemon blocks on the
        // write, stops reading, and holds that listener for as long as the client likes. With a
        // fixed listener pool, enough such clients make the daemon unreachable to honest shells.
        //
        // Same-user only, so this is not a trust-boundary crossing — but "a buggy client can make
        // the product stop responding" is a defect whoever wrote the client.
        var pipeName = FreshPipeName();
        var server = new IpcServer(
            pipeName,
            Endpoint(),
            new IpcServerOptions(
                MaxConnections: 1,
                StartupGrace: TimeSpan.FromSeconds(20),
                ResponseTimeout: TimeSpan.FromMilliseconds(400)));

        await WithServer(server, pipeName, async (name, running) =>
        {
            using (var deaf = IpcPipeFactory.CreateClient(name))
            {
                await deaf.ConnectAsync(15_000, CancellationToken.None);

                // Written and never read back. The writes are expected to FAIL partway: once the
                // daemon gives up and drops the connection, this end's pipe breaks — which is the
                // control firing, not a flaw in the test.
                try
                {
                    for (var i = 0; i < 400; i++)
                    {
                        await Send(deaf, IpcMessage.Open, "open", null);
                    }
                }
                catch (IOException)
                {
                }

                // Long enough for the daemon's response buffer to fill and the write to time out.
                await Task.Delay(TimeSpan.FromSeconds(3));

                Assert.True(
                    running.StalledConnections >= 1,
                    "the daemon was still blocked writing to a client that never reads");
            }

            // The single listener is free again, so an honest shell can be served.
            await using var honest = await ConnectAsync(name);
            var opened = await honest.OpenWorkspaceAsync(Workspace, Epoch, CancellationToken.None);

            Assert.True(opened.Ok, "the only listener was still held by the stalled connection");
        });
    }

    // ---- P2-IPC-05: the daemon goes away when nobody needs it ---------------------

    [Fact]
    public async Task WithNoClient_TheServerExitsAfterItsStartupGrace()
    {
        // An orphaned daemon holds a workspace lock the user cannot see or reason about. Exiting is
        // the behaviour; the grace is what stops an ordinary shell restart from killing it.
        var pipeName = FreshPipeName();
        var server = new IpcServer(
            pipeName,
            Endpoint(),
            new IpcServerOptions(StartupGrace: TimeSpan.FromMilliseconds(300)));

        using var life = new CancellationTokenSource(TimeSpan.FromSeconds(20));

        await server.RunAsync(life.Token);

        Assert.False(life.IsCancellationRequested, "the server had to be cancelled rather than exiting");
        Assert.Equal(0, server.ServedConnections);
    }

    [Fact]
    public async Task AfterItsLastClientLeaves_TheServerExitsOnTheIdleGrace()
    {
        var pipeName = FreshPipeName();
        var server = new IpcServer(
            pipeName,
            Endpoint(),
            new IpcServerOptions(
                StartupGrace: TimeSpan.FromSeconds(10),
                IdleGrace: TimeSpan.FromMilliseconds(300)));

        using var life = new CancellationTokenSource(TimeSpan.FromSeconds(25));
        var running = server.RunAsync(life.Token);

        await using (var client = await ConnectAsync(pipeName))
        {
            var opened = await client.OpenWorkspaceAsync(Workspace, Epoch, CancellationToken.None);
            Assert.True(opened.Ok, opened.Reason);
        }

        await running;

        Assert.False(life.IsCancellationRequested, "the server had to be cancelled rather than exiting");
        Assert.Equal(1, server.ServedConnections);
    }

    [Fact]
    public async Task WhileAClientIsAttached_TheServerDoesNotExit()
    {
        // The grace must be refreshed by presence, not merely started once. Without that, a daemon
        // would exit out from under a shell that is quietly connected between commands.
        var pipeName = FreshPipeName();
        var server = new IpcServer(
            pipeName,
            Endpoint(),
            new IpcServerOptions(
                StartupGrace: TimeSpan.FromSeconds(10),
                IdleGrace: TimeSpan.FromMilliseconds(200)));

        await WithServer(server, pipeName, async (name, running) =>
        {
            await using var client = await ConnectAsync(name);
            await client.OpenWorkspaceAsync(Workspace, Epoch, CancellationToken.None);

            await Task.Delay(TimeSpan.FromMilliseconds(900));

            var response = await client.InvokeAsync(
                "describe", "cmd-late", Workspace, Epoch, IpcPayloadTestExtensions.Json("still-here"), CancellationToken.None);

            Assert.True(response.Ok, "the daemon exited while a client was still attached");
            Assert.Equal(1, running.ActiveConnections);
        });
    }

    // ---- malformed traffic ends the connection, never the daemon -------------------

    [Fact]
    public async Task AMalformedFrame_EndsThatConnectionAndLeavesTheDaemonServing()
    {
        // A peer can always send nonsense. What it must not be able to do is take the daemon with
        // it: one poisoned connection ending is containment, the daemon ending is a denial of
        // service reachable by four bytes.
        var pipeName = FreshPipeName();
        var server = new IpcServer(pipeName, Endpoint());

        await WithServer(server, pipeName, async (name, _) =>
        {
            using (var hostile = IpcPipeFactory.CreateClient(name))
            {
                await hostile.ConnectAsync(15_000, CancellationToken.None);

                // A length prefix promising 2 GiB.
                await hostile.WriteAsync(new byte[] { 0x7F, 0xFF, 0xFF, 0xFF }, CancellationToken.None);
                await hostile.FlushAsync(CancellationToken.None);
                await Task.Delay(300);
            }

            await using var honest = await ConnectAsync(name);
            var opened = await honest.OpenWorkspaceAsync(Workspace, Epoch, CancellationToken.None);

            Assert.True(opened.Ok, "the daemon stopped serving after one malformed frame");
        });
    }

    [Fact]
    public async Task AnUnknownMessageKind_IsRejectedWithoutClosingTheConnection()
    {
        var pipeName = FreshPipeName();
        var server = new IpcServer(pipeName, Endpoint());

        await WithServer(server, pipeName, async (name, _) =>
        {
            await using var client = await ConnectAsync(name);

            var rejected = await client.SendAsync(
                new IpcMessage("smuggle", new IpcRequest(
                    IpcVersion.Current, "describe", "cmd-1", Workspace, Epoch, null, null)),
                CancellationToken.None);

            Assert.False(rejected.Ok);
            Assert.Equal(IpcErrorCodes.MalformedEnvelope, rejected.ErrorCode);

            // Still usable: a rejected message is not a protocol desynchronisation.
            var opened = await client.OpenWorkspaceAsync(Workspace, Epoch, CancellationToken.None);
            Assert.True(opened.Ok, opened.Reason);
        });
    }

    // ---- helpers for the raw-frame cases ------------------------------------------

    /// <summary>The capability out of a handshake response, which now carries the epoch too.</summary>
    private static string Capability(IpcResponse opened) =>
        opened.Payload.As<IpcOpenResult>()!.Capability;

    private static Task Send(Stream pipe, string kind, string operation, string? capability) =>
        IpcFraming.WriteAsync(
            pipe,
            System.Text.Json.JsonSerializer.Serialize(
                new IpcMessage(kind, new IpcRequest(
                    IpcVersion.Current, operation, Guid.NewGuid().ToString("N"),
                    Workspace, Epoch, capability, null)),
                new System.Text.Json.JsonSerializerOptions(System.Text.Json.JsonSerializerDefaults.Web)),
            CancellationToken.None);

    private static async Task<IpcResponse> Receive(Stream pipe)
    {
        var raw = await IpcFraming.ReadAsync(pipe, CancellationToken.None);
        Assert.NotNull(raw);

        return System.Text.Json.JsonSerializer.Deserialize<IpcResponse>(
            raw!, new System.Text.Json.JsonSerializerOptions(System.Text.Json.JsonSerializerDefaults.Web))!;
    }
}
