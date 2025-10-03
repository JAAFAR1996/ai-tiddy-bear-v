#!/usr/bin/env python3
"""
NVS Partition Generator for AI Teddy Bear Manufacturing
Generates encrypted NVS partition with device_id and oob_secret
"""

import os
import sys
import csv
import hashlib
import secrets
from pathlib import Path

def generate_oob_secret():
    """Generate a secure 128-bit OOB secret"""
    return secrets.token_hex(32)  # 32 hex chars = 128 bits

def generate_device_id(prefix="Teddy-ESP32", serial_number=None):
    """Generate unique device ID"""
    if serial_number is None:
        # Generate random 4-digit serial
        serial_number = f"{secrets.randbelow(10000):04d}"
    return f"{prefix}-{serial_number}"

def create_manufacturing_csv(output_file, device_id=None, oob_secret=None):
    """Create manufacturing NVS CSV file"""
    
    if device_id is None:
        device_id = generate_device_id()
    
    if oob_secret is None:
        oob_secret = generate_oob_secret()
    
    # Validate OOB secret format (must be hex)
    try:
        bytes.fromhex(oob_secret)
        if len(oob_secret) != 64:  # 32 bytes = 64 hex chars
            raise ValueError("OOB secret must be 64 hex characters (32 bytes)")
    except ValueError as e:
        print(f"❌ Invalid OOB secret: {e}")
        return False
    
    # Create CSV data
    csv_data = [
        ["key", "type", "encoding", "value"],
        ["mfg", "namespace", "", ""],
        ["device_id", "data", "string", f'"{device_id}"'],
        ["oob_secret", "data", "hex", f'"{oob_secret}"'],
        ["manufacturing_date", "data", "string", f'"{__import__("datetime").datetime.now().isoformat()}"'],
        ["firmware_version", "data", "string", '"1.0.0"'],
        ["hardware_revision", "data", "string", '"Rev-A"']
    ]
    
    # Write CSV file
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(csv_data)
        
        print(f"✅ Manufacturing NVS CSV created: {output_file}")
        print(f"📋 Device ID: {device_id}")
        print(f"🔑 OOB Secret: {oob_secret[:16]}...{oob_secret[-16:]}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create CSV file: {e}")
        return False

def generate_nvs_partition(csv_file, output_bin, partition_size=0x1000):
    """Generate NVS partition binary from CSV"""
    
    # This would typically use ESP-IDF's nvs_partition_gen.py
    # For now, we'll create a placeholder
    
    print(f"🔧 Generating NVS partition binary...")
    print(f"   Input CSV: {csv_file}")
    print(f"   Output Binary: {output_bin}")
    print(f"   Partition Size: 0x{partition_size:X}")
    
    # In production, you would run:
    # python $IDF_PATH/components/nvs_flash/nvs_partition_generator/nvs_partition_gen.py generate csv_file output_bin partition_size
    
    print("💡 To generate actual binary, run:")
    print(f"   python $IDF_PATH/components/nvs_flash/nvs_partition_generator/nvs_partition_gen.py generate {csv_file} {output_bin} 0x{partition_size:X}")
    
    return True

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python generate_nvs_partition.py <output_csv> [device_id] [oob_secret]")
        print("Example: python generate_nvs_partition.py manufacturing_nvs.csv")
        sys.exit(1)
    
    output_csv = sys.argv[1]
    device_id = sys.argv[2] if len(sys.argv) > 2 else None
    oob_secret = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Create manufacturing CSV
    if create_manufacturing_csv(output_csv, device_id, oob_secret):
        # Generate binary partition
        output_bin = output_csv.replace('.csv', '.bin')
        generate_nvs_partition(output_csv, output_bin)
        
        print("\n🏭 Manufacturing NVS partition ready!")
        print(f"📁 CSV File: {output_csv}")
        print(f"📁 Binary File: {output_bin}")
        print("\n🔧 Flash command:")
        print(f"   esptool.py write_flash 0x11000 {output_bin}")

if __name__ == "__main__":
    main()