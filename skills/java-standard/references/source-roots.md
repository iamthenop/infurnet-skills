# Java standard — source roots

Canonical source-root lookup for Java projects.
`java-standard/SKILL.md` governs Java source placement rules;
this file carries the root definitions.

The listed roots are established repository conventions. Do not add,
rename, merge, or reinterpret source roots without authority.

## Source roots

| Root | Contains |
| --- | --- |
| `src/main/java` | production Java source |
| `src/main/resources` | production classpath resources |
| `src/test/java` | isolated unit and package tests |
| `src/it/java` | live integration and contract tests |
