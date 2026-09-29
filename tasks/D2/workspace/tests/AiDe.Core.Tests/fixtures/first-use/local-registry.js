// A minimal npm registry for ONE package, over HTTP on 127.0.0.1 — the fresh-machine oracle's
// "npm pointed at a local registry" (Ruling 104 condition 2). It answers the packument and serves one
// tarball; nothing else is reachable and no other host is contacted.
// A minimal npm registry over HTTP for one package: answers the packument and serves one tarball.
// Usage: node registry.js <package-name> <version> <tarball-path> [port]
// Prints "listening <port>" on stdout once bound; no network beyond 127.0.0.1.
const http = require("http");
const fs = require("fs");
const crypto = require("crypto");

const [name, version, tarballPath, portArg] = process.argv.slice(2);
const tarball = fs.readFileSync(tarballPath);
const shasum = crypto.createHash("sha1").update(tarball).digest("hex");
const integrity = "sha512-" + crypto.createHash("sha512").update(tarball).digest("base64");
const encoded = name.replace("/", "%2f");

const server = http.createServer((req, res) => {
  const url = decodeURIComponent(req.url);
  if (url === "/" + name || req.url === "/" + encoded || url.startsWith("/" + name + "?")) {
    const base = "http://127.0.0.1:" + server.address().port;
    const body = {
      name,
      "dist-tags": { latest: version },
      versions: {
        [version]: {
          name, version,
          dist: { tarball: base + "/tarball.tgz", shasum, integrity },
        },
      },
    };
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify(body));
    return;
  }
  if (req.url === "/tarball.tgz") {
    res.writeHead(200, { "content-type": "application/octet-stream" });
    res.end(tarball);
    return;
  }
  res.writeHead(404);
  res.end("not here: " + req.url);
});

server.listen(portArg ? Number(portArg) : 0, "127.0.0.1", () => {
  process.stdout.write("listening " + server.address().port + "\n");
});
