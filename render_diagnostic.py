#!/usr/bin/env python3
"""
🏥 Render Deployment Diagnostic
Identifies why dependencies are missing on the deployed server
"""
import os
import sys
import subprocess
import importlib

def test_critical_imports():
    """Test all critical imports that are causing issues."""
    print("🔍 Testing Critical Imports...")
    
    critical_imports = [
        "redis",
        "asyncpg", 
        "pydantic_settings",
        "openai",
        "sqlalchemy",
        "fastapi",
        "uvicorn"
    ]
    
    results = {}
    
    for package in critical_imports:
        try:
            importlib.import_module(package)
            results[package] = "✅ INSTALLED"
        except ImportError as e:
            results[package] = f"❌ MISSING: {e}"
    
    return results

def get_python_environment():
    """Get Python environment information."""
    return {
        "python_version": sys.version,
        "python_path": sys.executable,
        "sys_path": sys.path[:5],  # First 5 paths only
        "working_directory": os.getcwd(),
        "environment": os.environ.get("ENVIRONMENT", "unknown"),
        "pythonpath": os.environ.get("PYTHONPATH", "not_set"),
        "pip_list_available": subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True).returncode == 0
    }

def get_pip_packages():
    """Get installed pip packages."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"], 
            capture_output=True, 
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            import json
            packages = json.loads(result.stdout)
            return {pkg["name"]: pkg["version"] for pkg in packages}
        else:
            return {"error": result.stderr}
    except Exception as e:
        return {"error": str(e)}

def check_requirements_file():
    """Check if requirements.txt exists and is readable."""
    req_files = ["requirements.txt", "/app/requirements.txt", "src/requirements.txt"]
    
    for req_file in req_files:
        if os.path.exists(req_file):
            try:
                with open(req_file, 'r') as f:
                    content = f.read()
                return {
                    "file": req_file,
                    "exists": True,
                    "size": len(content),
                    "first_10_lines": content.split('\n')[:10]
                }
            except Exception as e:
                return {"file": req_file, "exists": True, "error": str(e)}
    
    return {"exists": False, "checked_paths": req_files}

def main():
    """Main diagnostic function."""
    print("🏥 Render Deployment Diagnostic Tool")
    print("=" * 50)
    
    # Test imports
    print("\n📦 Import Test Results:")
    import_results = test_critical_imports()
    for package, status in import_results.items():
        print(f"  {package}: {status}")
    
    # Python environment
    print("\n🐍 Python Environment:")
    env_info = get_python_environment()
    for key, value in env_info.items():
        print(f"  {key}: {value}")
    
    # Requirements file
    print("\n📋 Requirements File:")
    req_info = check_requirements_file()
    print(f"  {req_info}")
    
    # Pip packages (first 20)
    print("\n📦 Installed Packages (sample):")
    pip_packages = get_pip_packages()
    if isinstance(pip_packages, dict) and "error" not in pip_packages:
        count = 0
        for package, version in pip_packages.items():
            if count < 20:  # Show first 20
                print(f"  {package}: {version}")
                count += 1
        print(f"  ... and {len(pip_packages) - 20} more packages" if len(pip_packages) > 20 else "")
    else:
        print(f"  Error getting packages: {pip_packages}")
    
    # Summary
    print("\n" + "=" * 50)
    missing_count = sum(1 for status in import_results.values() if "❌" in status)
    total_count = len(import_results)
    
    if missing_count == 0:
        print("🎉 All critical packages are installed!")
        print("The issue might be in application configuration or startup logic.")
    elif missing_count < total_count:
        print(f"⚠️ {missing_count}/{total_count} packages are missing")
        print("This is likely a deployment issue - requirements not fully installed")
    else:
        print("🚨 All critical packages are missing!")
        print("This indicates requirements.txt was not installed during deployment")
    
    # Provide specific recommendations
    print("\n💡 Recommendations:")
    if missing_count > 0:
        print("1. Check that requirements.txt is in the root directory")
        print("2. Verify Render build logs for pip installation errors")
        print("3. Consider adding a build command in render.yaml")
        print("4. Check for memory/disk space issues during pip install")

if __name__ == "__main__":
    main()