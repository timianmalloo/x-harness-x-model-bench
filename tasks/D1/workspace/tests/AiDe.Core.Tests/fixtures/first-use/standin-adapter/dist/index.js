// Stand-in entry module for the fresh-machine oracle. It is never launched: the test asserts
// EngineCatalog.ResolveLaunch resolves to this file on disk after the product ran npm install.
process.stdout.write("stand-in adapter; not the real one\n");
