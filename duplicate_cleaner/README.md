# D: Drive Duplicate Cleaner Agent

A safe, production-grade Python script for finding and removing duplicate files on Windows systems. Uses content-based (SHA-256 hash) comparison and smart decision rules to determine which duplicates to keep.

## Features

✅ **Safe by Default**: Dry-run mode enabled by default  
✅ **Smart Keep Logic**: Prioritizes files in project folders and user content directories  
✅ **Quarantine Mode**: Move duplicates instead of deleting (with restore script)  
✅ **Performance**: Multi-threaded hashing with partial hash optimization  
✅ **Detailed Reports**: CSV and JSON reports with full audit trail  
✅ **Flexible Filtering**: Exclude paths, glob patterns, file extensions, size limits  
✅ **Long Path Support**: Handles Windows long paths gracefully  

## Requirements

- Python 3.11+
- Windows 10/11
- No external dependencies (uses only standard library)

## Installation

```powershell
# No installation needed - just run the script
python duplicate_cleaner.py --help
```

## Usage Examples

### 1. Dry Run (Safe Scan)
Just scan and see what would be removed:
```powershell
python duplicate_cleaner.py --root "D:\"
```

### 2. Quarantine Mode (Recommended)
Move duplicates to quarantine folder with restore script:
```powershell
python duplicate_cleaner.py --root "D:\" --apply --mode quarantine
```

After running, check:
- `D:\_DUPLICATE_QUARANTINE\` - quarantined files
- `D:\_DUPLICATE_QUARANTINE\restore.ps1` - restoration script

To restore everything:
```powershell
cd D:\_DUPLICATE_QUARANTINE
.\restore.ps1
```

### 3. Report Only
Generate reports without any file operations:
```powershell
python duplicate_cleaner.py --root "D:\" --apply --mode report
```

### 4. Delete Mode (Use with Caution)
Permanently delete duplicates (requires `--confirm`):
```powershell
python duplicate_cleaner.py --root "D:\" --apply --mode delete --confirm
```

### 5. Advanced Filtering

Exclude specific directories:
```powershell
python duplicate_cleaner.py --root "D:\" --exclude "D:\Games" "D:\VMs" "D:\Backups"
```

Skip file types:
```powershell
python duplicate_cleaner.py --root "D:\" --skip-ext ".iso" ".vhdx" ".vmdk" ".tmp"
```

Filter by size:
```powershell
# Only files between 1MB and 100MB
python duplicate_cleaner.py --root "D:\" --min-size 1048576 --max-size 104857600
```

Use glob patterns:
```powershell
python duplicate_cleaner.py --root "D:\" --exclude-glob "*.log" "*.tmp" "node_modules"
```

### 6. Performance Tuning

Adjust worker threads:
```powershell
python duplicate_cleaner.py --root "D:\" --workers 8
```

Enable verbose logging:
```powershell
python duplicate_cleaner.py --root "D:\" --verbose
```

## How It Works

### Phase 1: Size Grouping
- Scans all files in root directory
- Groups files by size (only files with same size are potential duplicates)
- Applies exclusions and filters

### Phase 2: Hash Computation
1. **Partial Hash**: Quickly hashes beginning, middle, and end of files
2. **Full Hash**: Only computes full SHA-256 for files with matching partial hashes
3. Groups files by full hash to find true duplicates

### Phase 3: Keep Decision
For each group of duplicates, chooses which file to keep based on:

1. **Folder Importance Score** (higher is better):
   - +50 points: Project indicators (package.json, pom.xml, .sln, etc.)
   - +30 points: Project folders (src, node_modules, .git, etc.)
   - +40 points: User content folders (Documents, Photos, Videos, etc.)
   - +20 points: Organized folders (10+ sibling files)
   - -100 points: Temp/cache folders
   - -2 points per folder depth

2. **Age** (if folder score ties):
   - Keeps older file (earliest of creation/modification time)

3. **Path Length** (if still tied):
   - Keeps shorter path (closer to root)

### Phase 4: Action & Report
- Performs action based on mode (report/quarantine/delete)
- Generates CSV and JSON reports
- Creates restore script (quarantine mode)

## Output Files

All outputs are saved to `<root>/_DUPLICATE_LOGS/` by default:

- `duplicate_report_YYYYMMDD_HHMMSS.csv` - Detailed CSV report
- `duplicate_report_YYYYMMDD_HHMMSS.json` - JSON report
- `summary_YYYYMMDD_HHMMSS.txt` - Human-readable summary
- `duplicate_cleaner_YYYYMMDD_HHMMSS.log` - Execution log

### CSV/JSON Report Fields:
- `hash` - SHA-256 hash of file content
- `size` - File size in bytes
- `kept_path` - Path of file that was kept
- `removed_path` - Path of file that was removed/quarantined
- `reason` - Explanation for keep decision
- `kept_ctime`, `kept_mtime` - Timestamps of kept file
- `removed_ctime`, `removed_mtime` - Timestamps of removed file
- `action` - Action taken (dry-run, move, delete, report-only)
- `error` - Error message if operation failed
- `timestamp` - When action was recorded

## Safety Features

### Default Exclusions
Automatically excludes:
- `C:\Windows`
- `C:\Program Files`
- `C:\Program Files (x86)`
- `C:\ProgramData`

### Safety Checks
- Dry-run is default (use `--apply` to execute)
- Delete mode requires both `--apply` and `--confirm`
- Handles permission errors gracefully
- Does not follow symlinks/junctions
- Long path support

### Undo Operations
- **Quarantine mode**: Use generated `restore.ps1` script
- **Delete mode**: NO UNDO - files are permanently deleted

## Adjusting Keep Rules

The keep decision logic is in the `DecisionEngine` class. You can modify:

### Add Project Indicators
```python
PROJECT_INDICATORS = {
    'package.json', 'pom.xml', '.sln',
    'your-special-file.txt'  # Add your own
}
```

### Add Project Folders
```python
PROJECT_FOLDERS = {
    'src', 'node_modules', '.git',
    'my-source-folder'  # Add your own
}
```

### Adjust Scoring Weights
In `compute_folder_score()`:
```python
# Current weights:
# Project indicators: +50
# Project folders: +30
# User content: +40
# Many siblings: +20
# Temp folders: -100
# Path depth: -2 per level
```

## Command-Line Reference

```
--root PATH              Root directory to scan (required)
--apply                  Execute actions (disables dry-run)
--mode MODE              Action mode: report|quarantine|delete (default: quarantine)
--exclude PATH [PATH...] Directories to exclude (absolute paths)
--exclude-glob PATTERN   Glob patterns to exclude
--skip-ext EXT [EXT...]  File extensions to skip
--min-size BYTES         Minimum file size (default: 0)
--max-size BYTES         Maximum file size (default: 1TB)
--workers N              Worker threads for hashing (default: 4)
--log-dir PATH           Log directory (default: <root>/_DUPLICATE_LOGS)
--confirm                Required for delete mode
--verbose                Enable verbose logging
--dry-run                Explicit dry-run flag (default: True)
```

## Testing

Run the unit tests:
```powershell
pytest test_duplicate_cleaner.py -v
```

## Performance Tips

1. **Use exclusions** to skip large directories you don't want to scan
2. **Adjust --workers** based on your CPU (typically 4-8)
3. **Use --min-size** to skip small files (e.g., 100KB minimum)
4. **Skip known large files** with --skip-ext (e.g., .iso, .vhdx)

## Troubleshooting

### "Permission denied" errors
- Run with admin privileges if needed
- Check log file for detailed error messages

### "Path too long" errors
- Script handles long paths automatically
- If issues persist, exclude deeply nested folders

### Slow performance
- Increase `--workers` for faster hashing
- Use `--min-size` to skip small files
- Use `--exclude` for large folders you don't need to scan

## License

This script is provided as-is for personal use. Modify as needed.

## Warning

⚠️ **ALWAYS do a dry-run first** before using `--apply`  
⚠️ **Prefer quarantine mode** over delete mode  
⚠️ **Review reports** before restoring or permanently deleting  
⚠️ **Backup important data** before running any cleanup operation
