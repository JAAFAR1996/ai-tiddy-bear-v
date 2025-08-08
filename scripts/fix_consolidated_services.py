#!/usr/bin/env python3
"""Fix consolidated services by properly merging implementations."""

import json
import shutil
from pathlib import Path
from datetime import datetime


def fix_consolidated_services():
    """Fix the circular imports in consolidated services."""
    
    project_root = Path("/mnt/c/Users/jaafa/Desktop/ai teddy bear")
    
    # Read consolidation log
    with open(project_root / "service_consolidation_log.json", "r") as f:
        consolidation_log = json.load(f)
    
    # Get the latest backup directory
    backup_dir = Path("/mnt/c/Users/jaafa/Desktop/ai teddy bear/backups/consolidation_20250728_165440")
    
    # Fix each consolidated service
    fixes = []
    
    # Fix AI Service
    print("Fixing AI Service...")
    original_ai_service = backup_dir / "src/services/ai_service.py"
    target_ai_service = project_root / "src/application/services/ai_service.py"
    
    if original_ai_service.exists():
        # Copy the actual implementation
        shutil.copy2(original_ai_service, target_ai_service)
        fixes.append({
            "service": "ai_service",
            "source": str(original_ai_service),
            "target": str(target_ai_service),
            "status": "fixed"
        })
        print(f"✓ Fixed AI service: {target_ai_service}")
    
    # Fix Audio Service
    print("Fixing Audio Service...")
    original_audio_service = backup_dir / "src/services/audio_service.py"
    target_audio_service = project_root / "src/application/services/audio_service.py"
    
    if original_audio_service.exists():
        # Copy the actual implementation
        shutil.copy2(original_audio_service, target_audio_service)
        fixes.append({
            "service": "audio_service",
            "source": str(original_audio_service),
            "target": str(target_audio_service),
            "status": "fixed"
        })
        print(f"✓ Fixed Audio service: {target_audio_service}")
    
    # Fix Child Safety Service
    print("Fixing Child Safety Service...")
    original_safety_service = backup_dir / "src/services/child_safety_service.py"
    target_safety_service = project_root / "src/application/services/child_safety_service.py"
    
    if original_safety_service.exists():
        # Copy the actual implementation
        shutil.copy2(original_safety_service, target_safety_service)
        fixes.append({
            "service": "child_safety_service",
            "source": str(original_safety_service),
            "target": str(target_safety_service),
            "status": "fixed"
        })
        print(f"✓ Fixed Child Safety service: {target_safety_service}")
    
    # Save fix log
    fix_log = {
        "timestamp": datetime.now().isoformat(),
        "fixes": fixes,
        "status": "completed"
    }
    
    with open(project_root / "service_fix_log.json", "w") as f:
        json.dump(fix_log, f, indent=2)
    
    print(f"\n✓ Fixed {len(fixes)} consolidated services")
    print("Next step: Run 'python scripts/update_service_imports.py' to update imports")


if __name__ == "__main__":
    fix_consolidated_services()