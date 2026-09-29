namespace AiDe.Core.Extraction;

/// <summary>
/// The Python standard library's top-level module names.
/// </summary>
/// <remarks>
/// <para><b>Why this exists.</b> An import that names something the repository does not contain was
/// counted as unresolved and disclosed as such. On a real workspace that produced
/// <c>python-imports-not-resolved (246 import(s) name something this scope does not contain)</c> —
/// which reads like a coverage hole and was treated as one, until the targets were measured:
/// <b>all 246, across all 32 distinct names, were the standard library</b> — sys, pathlib, json,
/// argparse, os, subprocess, urllib.</para>
///
/// <para>Nothing was wrong with the resolution. The number was arithmetically right and said
/// something false, which is the shape this codebase keeps meeting. <c>import sys</c> resolving to
/// nothing in the repository is not a gap in the graph any more than a C# file using
/// <c>System.String</c> is — the C# extractor already declines to draw the BCL for the same reason.</para>
///
/// <para><b>Generated, not remembered.</b> Taken verbatim from <c>sys.stdlib_module_names</c> on
/// CPython 3.12.10 — the interpreter's own answer. A hand-written list would be a guess about a set
/// the runtime publishes.</para>
///
/// <para>Single-underscore internals (<c>_socket</c>, <c>_ast</c>) are dropped because nothing
/// imports them by that name. <c>__future__</c> is KEPT — dropping it cost <b>26 false unknowns</b>
/// on a real workspace, because the filter was written as "private names" and <c>__future__</c> is
/// the one module in the set that looks private and is imported constantly.</para>
///
/// <para><b>It is a floor, not a promise.</b> A module added in a later Python is missing here and
/// falls back to being reported as unresolved, which is the safe direction: over-claiming would hide
/// a real unknown import inside a name nobody checked.</para>
/// </remarks>
public static class PythonStandardLibrary
{
    private static readonly HashSet<string> Modules = new(StringComparer.Ordinal)
    {
        "__future__", "abc", "aifc", "antigravity", "argparse", "array", "ast", "asyncio", "atexit",
        "audioop", "base64", "bdb", "binascii", "bisect", "builtins", "bz2", "cProfile", "calendar",
        "cgi", "cgitb", "chunk", "cmath", "cmd", "code", "codecs", "codeop", "collections", "colorsys",
        "compileall", "concurrent", "configparser", "contextlib", "contextvars", "copy", "copyreg",
        "crypt", "csv", "ctypes", "curses", "dataclasses", "datetime", "dbm", "decimal", "difflib",
        "dis", "doctest", "email", "encodings", "ensurepip", "enum", "errno", "faulthandler", "fcntl",
        "filecmp", "fileinput", "fnmatch", "fractions", "ftplib", "functools", "gc", "genericpath",
        "getopt", "getpass", "gettext", "glob", "graphlib", "grp", "gzip", "hashlib", "heapq", "hmac",
        "html", "http", "idlelib", "imaplib", "imghdr", "importlib", "inspect", "io", "ipaddress",
        "itertools", "json", "keyword", "lib2to3", "linecache", "locale", "logging", "lzma", "mailbox",
        "mailcap", "marshal", "math", "mimetypes", "mmap", "modulefinder", "msilib", "msvcrt",
        "multiprocessing", "netrc", "nis", "nntplib", "nt", "ntpath", "nturl2path", "numbers", "opcode",
        "operator", "optparse", "os", "ossaudiodev", "pathlib", "pdb", "pickle", "pickletools", "pipes",
        "pkgutil", "platform", "plistlib", "poplib", "posix", "posixpath", "pprint", "profile",
        "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc", "pydoc_data", "pyexpat", "queue",
        "quopri", "random", "re", "readline", "reprlib", "resource", "rlcompleter", "runpy", "sched",
        "secrets", "select", "selectors", "shelve", "shlex", "shutil", "signal", "site", "smtplib",
        "sndhdr", "socket", "socketserver", "spwd", "sqlite3", "sre_compile", "sre_constants",
        "sre_parse", "ssl", "stat", "statistics", "string", "stringprep", "struct", "subprocess",
        "sunau", "symtable", "sys", "sysconfig", "syslog", "tabnanny", "tarfile", "telnetlib",
        "tempfile", "termios", "textwrap", "this", "threading", "time", "timeit", "tkinter", "token",
        "tokenize", "tomllib", "trace", "traceback", "tracemalloc", "tty", "turtle", "turtledemo",
        "types", "typing", "unicodedata", "unittest", "urllib", "uu", "uuid", "venv", "warnings",
        "wave", "weakref", "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib", "xml", "xmlrpc",
        "zipapp", "zipfile", "zipimport", "zlib", "zoneinfo"
    };

    /// <summary>
    /// Whether an import target names the standard library.
    /// </summary>
    /// <remarks>
    /// Matched on the TOP-LEVEL package only, because <c>urllib.request</c> and
    /// <c>importlib.util</c> are the standard library exactly as much as <c>urllib</c> is, and a set
    /// of every submodule would be a set that goes stale one Python release at a time.
    /// </remarks>
    public static bool Contains(string importTarget)
    {
        if (string.IsNullOrEmpty(importTarget)) return false;

        var dot = importTarget.IndexOf('.', StringComparison.Ordinal);
        var root = dot < 0 ? importTarget : importTarget[..dot];

        return Modules.Contains(root);
    }
}
