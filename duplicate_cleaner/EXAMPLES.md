# Example Usage Commands for Duplicate Cleaner

## Basic Commands

### 1. Dry Run (Safe - Just Scan)
```powershell
python duplicate_cleaner.py --root "D:\"
```

### 2. Dry Run with Verbose Output
```powershell
python duplicate_cleaner.py --root "D:\" --verbose
```

### 3. Scan a Specific Folder
```powershell
python duplicate_cleaner.py --root "D:\MyDocuments"
```

---

## Quarantine Mode (Recommended)

### 4. Move Duplicates to Quarantine
```powershell
python duplicate_cleaner.py --root "D:\" --apply --mode quarantine
```

### 5. Review and Restore from Quarantine
```powershell
# After quarantine, check the quarantine folder
cd D:\_DUPLICATE_QUARANTINE

# Review quarantined files
explorer .

# Restore everything
.\restore.ps1
```

---

## Report Mode

### 6. Generate Reports Only (No File Operations)
```powershell
python duplicate_cleaner.py --root "D:\" --apply --mode report
```

---

## Delete Mode (Use with Extreme Caution)

### 7. Permanently Delete Duplicates
```powershell
# Requires BOTH --apply and --confirm
python duplicate_cleaner.py --root "D:\" --apply --mode delete --confirm
```

---

## Advanced Filtering

### 8. Exclude Specific Directories
```powershell
python duplicate_cleaner.py --root "D:\" --exclude "D:\Games" "D:\VirtualMachines" "D:\ISOs"
```

### 9. Skip Large Media Files
```powershell
python duplicate_cleaner.py --root "D:\" --skip-ext ".iso" ".vhdx" ".vmdk" ".ova"
```

### 10. Exclude Patterns
```powershell
python duplicate_cleaner.py --root "D:\" --exclude-glob "*.tmp" "*.log" "*.cache" "node_modules"
```

### 11. Filter by File Size
```powershell
# Only files between 1MB and 100MB
python duplicate_cleaner.py --root "D:\" --min-size 1048576 --max-size 104857600
```

### 12. Only Large Files (10MB+)
```powershell
python duplicate_cleaner.py --root "D:\" --min-size 10485760
```

---

## Performance Optimization

### 13. Use More Workers for Faster Processing
```powershell
# Use 8 threads instead of default 4
python duplicate_cleaner.py --root "D:\" --workers 8
```

### 14. Custom Log Directory
```powershell
python duplicate_cleaner.py --root "D:\" --log-dir "C:\Logs\DuplicateCleaner"
```

---

## Combined Examples

### 15. Production Run with Multiple Filters
```powershell
python duplicate_cleaner.py `
    --root "D:\" `
    --apply `
    --mode quarantine `
    --exclude "D:\Games" "D:\VMs" `
    --skip-ext ".iso" ".vhdx" ".tmp" `
    --min-size 1048576 `
    --workers 8 `
    --verbose
```

### 16. Safe Scan of User Directories
```powershell
python duplicate_cleaner.py `
    --root "C:\Users\YourName\Documents" `
    --exclude "C:\Users\YourName\Documents\Work" `
    --min-size 100000 `
    --verbose
```

### 17. Clean Downloads Folder
```powershell
python duplicate_cleaner.py `
    --root "C:\Users\YourName\Downloads" `
    --apply `
    --mode quarantine `
    --skip-ext ".exe" ".msi" `
    --verbose
```

---

## Step-by-Step Workflow

### Recommended Safe Workflow:

#### Step 1: Dry Run to See What Would Be Removed
```powershell
python duplicate_cleaner.py --root "D:\" --verbose
```

#### Step 2: Review the Reports
```powershell
# Check the logs directory
cd D:\_DUPLICATE_LOGS
notepad summary_*.txt
```

#### Step 3: Run in Quarantine Mode
```powershell
python duplicate_cleaner.py --root "D:\" --apply --mode quarantine
```

#### Step 4: Verify Quarantined Files
```powershell
cd D:\_DUPLICATE_QUARANTINE
dir /s
```

#### Step 5: If Everything Looks Good, Delete Quarantine
```powershell
# Only after you're sure!
Remove-Item -Path "D:\_DUPLICATE_QUARANTINE" -Recurse -Force
```

#### Step 6: If Something Went Wrong, Restore
```powershell
cd D:\_DUPLICATE_QUARANTINE
.\restore.ps1
```

---

## Testing on a Small Directory First

### 18. Test on a Small Folder
```powershell
# Create a test folder structure
mkdir D:\DuplicateTest
echo "content" > D:\DuplicateTest\file1.txt
echo "content" > D:\DuplicateTest\file2.txt
echo "unique" > D:\DuplicateTest\file3.txt

# Run cleaner on test folder
python duplicate_cleaner.py --root "D:\DuplicateTest" --apply --mode quarantine --verbose
```

---

## Troubleshooting Commands

### 19. Check Python Version
```powershell
python --version
# Should be 3.11 or higher
```

### 20. View Help
```powershell
python duplicate_cleaner.py --help
```

### 21. Test Import (Check for Errors)
```powershell
python -c "import duplicate_cleaner; print('Import successful')"
```

---

## Real-World Examples

### 22. Clean Photo Library
```powershell
python duplicate_cleaner.py `
    --root "D:\Photos" `
    --apply `
    --mode quarantine `
    --skip-ext ".db" ".ini" `
    --min-size 50000 `
    --verbose
```

### 23. Clean Development Projects
```powershell
python duplicate_cleaner.py `
    --root "D:\Projects" `
    --exclude-glob "node_modules" "dist" "build" ".git" `
    --min-size 10000 `
    --verbose
```

### 24. Clean Download Archives
```powershell
python duplicate_cleaner.py `
    --root "D:\Archives" `
    --skip-ext ".zip" ".rar" ".7z" `
    --apply `
    --mode quarantine
```

---

## Notes

- Always start with a **dry run** (no --apply flag)
- Use **quarantine mode** first, not delete mode
- Review the **CSV/JSON reports** before making final decisions
- Keep the **restore script** until you're sure everything is correct
- **Backup important data** before running any cleanup operation
