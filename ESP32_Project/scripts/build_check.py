#!/usr/bin/env python3
"""
ESP32 Build Compatibility Check
Validates that all files are compatible with ESP32 platform
"""

import os
import re
from pathlib import Path

def check_esp32_compatibility():
    """Check ESP32 specific compatibility"""
    issues = []
    
    # Check for ESP32 specific includes
    required_includes = {
        'src/security/secure_nvs.c': ['nvs_flash.h', 'nvs.h', 'esp_log.h'],
        'src/net/time_sync.c': ['esp_sntp.h', 'freertos/FreeRTOS.h', 'freertos/task.h'],
        'src/net/ws_client.c': ['esp_websocket_client.h', 'esp_crt_bundle.h'],
        'src/provision/ble_pairing.c': ['nimble/ble.h', 'host/ble_hs.h', 'mbedtls/md.h'],
        'src/app/state_machine.c': ['freertos/FreeRTOS.h', 'freertos/task.h']
    }
    
    project_root = Path(__file__).parent.parent
    
    for file_path, includes in required_includes.items():
        full_path = project_root / file_path
        if full_path.exists():
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            for include in includes:
                if f'#include "{include}"' not in content and f'#include <{include}>' not in content:
                    issues.append(f"Missing include {include} in {file_path}")
                else:
                    print(f"OK: {include} found in {file_path}")
        else:
            issues.append(f"File not found: {file_path}")
    
    # Check for ESP32 specific functions
    esp32_functions = {
        'nvs_flash_init': 'src/security/secure_nvs.c',
        'sntp_init': 'src/net/time_sync.c',
        'esp_websocket_client_init': 'src/net/ws_client.c',
        'ble_hs_cfg': 'src/provision/ble_pairing.c',
        'vTaskDelay': 'src/app/state_machine.c'
    }
    
    for func, file_path in esp32_functions.items():
        full_path = project_root / file_path
        if full_path.exists():
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if func in content:
                print(f"OK: ESP32 function {func} found in {file_path}")
            else:
                issues.append(f"ESP32 function {func} not found in {file_path}")
    
    return issues

def check_platformio_config():
    """Check PlatformIO configuration"""
    project_root = Path(__file__).parent.parent
    platformio_ini = project_root / 'platformio.ini'
    
    if not platformio_ini.exists():
        return ["platformio.ini not found"]
    
    with open(platformio_ini, 'r', encoding='utf-8') as f:
        content = f.read()
    
    required_flags = [
        'CONFIG_NVS_ENCRYPTION=1',
        'CONFIG_MBEDTLS_CERTIFICATE_BUNDLE=1',
        'BLE_PROVISIONING_ENABLED=1'
    ]
    
    issues = []
    for flag in required_flags:
        if flag in content:
            print(f"OK: Build flag {flag} found")
        else:
            issues.append(f"Missing build flag: {flag}")
    
    return issues

def main():
    print("Checking ESP32 compatibility...")
    
    compatibility_issues = check_esp32_compatibility()
    config_issues = check_platformio_config()
    
    all_issues = compatibility_issues + config_issues
    
    if not all_issues:
        print("\nAll files are ESP32 compatible!")
        print("Ready for compilation")
    else:
        print(f"\nFound {len(all_issues)} issues:")
        for issue in all_issues:
            print(f"  {issue}")
        print("\nPlease fix these issues before building")
    
    return len(all_issues)

if __name__ == "__main__":
    exit(main())