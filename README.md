# Agent Skills

Public, installable snapshots of selected Skills maintained in a private source repository.

## Install

Install one Skill with the pinned installer version:

```powershell
npx skills@1.5.21 add luck-gh/agent-skills --skill new-skills
```

Repeat `--skill` to install more than one Skill. Install `new-skills` to receive the repository's unified update checks and guarded upgrade flow.

## Published Skills

The authoritative list, file hashes, directory hashes, and current snapshot ID are in [`skills-manifest.json`](skills-manifest.json). This repository is a generated public mirror. Public contributions are reviewed here, manually applied to the private source of truth, and then returned through the normal snapshot publication flow.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
