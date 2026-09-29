# New import-origin rule in Extraction/

Add one pure rule in `src/AiDe.Core/Extraction/` that classifies a single import or require
specifier, as discovered by a language reader, as builtin, workspace-local, or external. Use the
existing `AiDe.Core.Extraction.PythonStandardLibrary` and `AiDe.Core.Extraction.NodeBuiltinModules`
types. Keep this a pure classification rule: no file I/O, no changes to any existing extractor.

Provide these public types in `AiDe.Core.Extraction`:

- `ImportOrigin` — an enum with exactly three members, in this order: `Builtin`, `Workspace`,
  `External`.
- `ImportOriginRule.Classify(string language, string specifier, IReadOnlySet<string> workspaceModuleIds)`
  returning `ImportOrigin`.

`language` is exactly `"python"` or `"node"` (ordinal, case-sensitive); any other value throws
`ArgumentException`. Reject a null `language`, `specifier`, or `workspaceModuleIds` with
`ArgumentNullException` naming that parameter. An empty `specifier` throws `ArgumentException`.

Classification is evaluated top to bottom; the first rule that matches wins:

1. Relative-path shape. For `"python"`, a `specifier` starting with one or more `.` characters is
   `Workspace`. For `"node"`, a `specifier` starting with `./`, `../`, or `/` is `Workspace`. (Both
   languages resolve a relative or path-shaped specifier within the same codebase by construction;
   it is never the standard library, the runtime, or an external package.)
2. Builtin. For `"python"`, `PythonStandardLibrary.Contains(specifier)` is `Builtin`. For `"node"`,
   `NodeBuiltinModules.Contains(specifier)` is `Builtin`.
3. Workspace membership. `workspaceModuleIds.Contains(specifier)` (ordinal, exact text match — this
   rule does no normalization between a specifier's text and a module id's text) is `Workspace`.
4. Otherwise `External`.

Add focused tests for the new rule. The task is scoped to this rule and its tests within the
45-minute budget.
