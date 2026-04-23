# Versioned Documentation Skill

## Description
Manage versioned documentation files. When making improvements to specification documents, create new version files instead of overwriting existing ones.

## Versioning Convention

### File Naming
```
<NAME>_v<MAJOR>.<MINOR>.md
```

Examples:
- `PROTOCOL_v0.1.md` - Initial version
- `PROTOCOL_v0.2.md` - Minor improvements
- `PROTOCOL_v1.0.md` - Major revision

### Version Incrementing Rules

1. **Patch changes** (typos, formatting): Edit in place, no new version
2. **Minor changes** (clarifications, additions, non-breaking): Increment minor version (v0.1 → v0.2)
3. **Major changes** (breaking changes, architectural shifts): Increment major version (v0.2 → v1.0)

## Workflow

### Creating a New Version

1. Copy the current version to a new file:
   ```bash
   cp PROTOCOL_v0.1.md PROTOCOL_v0.2.md
   ```

2. Update the version number in the new file's header

3. Add a changelog entry at the top of the new version:
   ```markdown
   ## Changelog (v0.2)
   - Added X feature
   - Clarified Y section
   - Fixed Z inconsistency
   ```

4. Keep a `PROTOCOL.md` symlink or copy pointing to the latest version for easy access

### Maintaining Latest Link

After creating a new version:
```bash
cp PROTOCOL_v0.2.md PROTOCOL.md
```

Or use a symlink:
```bash
ln -sf PROTOCOL_v0.2.md PROTOCOL.md
```

### Directory Structure

```
/project
├── PROTOCOL.md           # Always latest version (copy or symlink)
├── PROTOCOL_v0.1.md      # Initial version
├── PROTOCOL_v0.2.md      # Second version
├── PROTOCOL_v1.0.md      # First major release
└── versions/             # Optional: archive old versions
    └── ...
```

## Commands

### List All Versions
```bash
ls -la *_v*.md | sort -V
```

### Compare Versions
```bash
diff PROTOCOL_v0.1.md PROTOCOL_v0.2.md
```

### Get Latest Version Number
```bash
ls PROTOCOL_v*.md 2>/dev/null | sort -V | tail -1 | sed 's/.*_v\([0-9.]*\)\.md/\1/'
```

### Create Next Minor Version
```bash
LATEST=$(ls PROTOCOL_v*.md 2>/dev/null | sort -V | tail -1)
CURRENT_VER=$(echo $LATEST | sed 's/.*_v\([0-9]*\)\.\([0-9]*\)\.md/\1.\2/')
MAJOR=$(echo $CURRENT_VER | cut -d. -f1)
MINOR=$(echo $CURRENT_VER | cut -d. -f2)
NEW_VER="v${MAJOR}.$((MINOR + 1))"
cp "$LATEST" "PROTOCOL_${NEW_VER}.md"
echo "Created PROTOCOL_${NEW_VER}.md"
```

## Git Commit Convention

When committing version changes:
```
docs(protocol): bump to v0.2

Changes:
- Added X
- Clarified Y
- Fixed Z
```

## Notes

- Never delete old versions (they serve as historical record)
- Always update PROTOCOL.md to point to latest
- Include changelog in each versioned file
- Tag git releases to match major versions: `git tag v1.0`
