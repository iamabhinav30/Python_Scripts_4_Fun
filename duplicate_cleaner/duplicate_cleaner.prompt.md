You are a senior Windows automation engineer. Write a SAFE, production-grade Python 3.11 “duplicate cleaner agent” for Windows that scans my D: drive and removes duplicates carefully.

GOAL
- Find and remove duplicate files under D:\ based on CONTENT (hash), not just name.
- When duplicates are found, decide which copy to KEEP using these rules:
  1) Prefer keeping the file that is “more likely in-use in its folder”:
     - If a file lives in a “project-like” folder or in the same folder as other related files, do NOT delete it blindly.
     - Implement a “folder importance scoring” heuristic:
       * Keep files in folders that contain many sibling files with same base name prefix, or contain config/source folders (e.g., src, node_modules, .git, package.json, *.sln, *.csproj, *.py, *.ts, *.java, pom.xml, build.gradle, angular.json).
       * Keep files in user-content folders like Photos/Videos/Documents/Music over random temp/download/cache folders.
  2) If folder score ties, keep the OLDEST created file (or if Windows creation time is unreliable, use earliest of (ctime, mtime)).
  3) If still tie, keep the shortest path (closer to root) and delete others.

SAFETY REQUIREMENTS (STRICT)
- MUST support DRY RUN (default) which only prints and logs what would be deleted.
- MUST support “quarantine mode”:
  - Instead of deleting, move duplicates to D:\_DUPLICATE_QUARANTINE\ preserving directory structure.
  - Also write a restore script (restore.ps1) that can put everything back.
- MUST create a detailed CSV + JSON report containing:
  - hash, size, kept_path, removed_path, reason, timestamps, action (move/delete), errors
- MUST never touch:
  - Windows system folders if present
  - Program Files, ProgramData
  - Any folder I list in an EXCLUDE list
- MUST support include/exclude patterns (glob) and max file size limit and skip file extensions list.
- MUST handle long paths and permission errors gracefully.
- MUST not follow directory junctions/symlinks by default.

PERFORMANCE REQUIREMENTS
- Two-phase scan:
  1) Group by file size (skip unique sizes).
  2) For same-size candidates, compute hash.
- Hashing must be streaming (chunked) and use SHA-256.
- Optional: use a fast partial-hash first (first+middle+last chunks) to reduce hashing, then confirm with full hash before deletion/move.
- Use multithreading for hashing (ThreadPoolExecutor) but keep memory bounded.
- Show progress (files scanned, candidate groups, duplicates found).

CLI INTERFACE
Provide a CLI using argparse with these options:
- --root "D:\"
- --dry-run (default true)
- --apply (actually perform action)
- --mode [report|quarantine|delete] (default quarantine)
- --exclude "D:\Games" "D:\VMs" ...
- --exclude-glob "*.tmp" "*.log"
- --skip-ext ".iso" ".vhdx" ...
- --min-size, --max-size
- --workers N
- --log-dir "D:\_DUPLICATE_LOGS\"
- --confirm (extra safety flag required for delete mode)

OUTPUT
- Give me:
  1) The complete Python script in one file (duplicate_cleaner.py)
  2) Example commands for dry-run and apply
  3) Explanation of the “keep decision” rules and how to adjust them
  4) Unit-test stubs (pytest) for hashing, grouping, keep decision, and quarantine restore mapping

CRITICAL
- Do NOT delete anything unless --apply is passed.
- In delete mode, require BOTH --apply and --confirm.
- Always print a final summary.

ASSUME
- Windows 10/11
- Python 3.11+
- I will run from terminal with admin only if needed.

Now write the code with clean structure: main(), Scanner, Hasher, DecisionEngine, Reporter, QuarantineManager.
