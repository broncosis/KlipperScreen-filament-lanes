# Project Rules

## Open Source Attribution & License Compatibility

### Determine the Project License First

Before any commit or GitHub push, identify this project's license from the LICENSE file in the repo root. All rules below apply relative to that license.

### Required: Credit All Third-Party Code

Whenever code, macros, configs, or logic is copied, adapted, or heavily inspired by an external open-source project:

- Add a comment near the borrowed code in the file:  
    
  \# Based on work by \[Author/Project\] (\[URL\])  
    
  \# Original license: \[License Name\]  
    
- Add the project to CREDITS.md in the repo root (create it if it doesn't exist):  
  - Project name  
  - Author or organization  
  - Source URL  
  - License

### Required: License Compatibility Check

All third-party code incorporated into this project must be compatible with the project's own license:

- If the third-party license is **more restrictive** than the project license (e.g. incorporating GPL v3 code into an MIT-licensed project), flag it and do not proceed — the licenses are incompatible and require human decision.  
- If the third-party license is **the same or more permissive**, it is safe to proceed.  
- If the third-party license is **unknown**, flag it for human review. Do not assume it is free to use.  
- If only *referencing or calling* a project (not copying code), license compatibility is usually not an issue — but flag for human review if uncertain.

### Required: GitHub Push Checklist

Before suggesting a `git push` or PR, confirm:

1. The project LICENSE file exists and is correct.  
2. All borrowed or adapted code has attribution comments in-file.  
3. CREDITS.md is up to date.  
4. No third-party code with an incompatible license has been incorporated.  
5. When in doubt, flag for human review rather than proceeding.

### Context: Common Projects in This Codebase

- **Klipper, Moonraker, Mainsail, Fluidd** — GPL v3.  
- Other 3D printer firmware and toolchanger community projects (KTC, Happy Hare, Klicky, etc.) — assume GPL v3 unless confirmed otherwise.  
- Bobcat3d / e-commerce related projects — verify LICENSE file, likely MIT.

