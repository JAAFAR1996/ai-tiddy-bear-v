/**
 * BLE provisioning stubs for release builds
 * BLE functionality has been removed from production builds
 */

// Stub for removed BLE provisioning
extern "C" bool isBLEProvisioningActive() { 
    return false; 
}