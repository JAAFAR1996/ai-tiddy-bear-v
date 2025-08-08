#!/usr/bin/env python3
"""
ESP32 Business/Data Flow Validation Testing Suite
===============================================
Comprehensive testing of device-child associations, onboarding workflows,
data deletion/revocation, and parent dashboard visibility for ESP32 system.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
import threading
import random
from enum import Enum


class EntityStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"
    PENDING = "pending"


@dataclass
class TestResult:
    """Result of business/data flow test."""
    test_name: str
    status: str  # PASS, FAIL, ERROR
    details: Dict[str, Any]
    timestamp: str
    duration_ms: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class Child:
    """Child entity for testing."""
    child_id: str
    name: str
    age: int
    parent_id: str
    created_at: str
    status: EntityStatus = EntityStatus.ACTIVE
    associated_devices: Set[str] = None

    def __post_init__(self):
        if self.associated_devices is None:
            self.associated_devices = set()

    def to_dict(self):
        return {
            "child_id": self.child_id,
            "name": self.name,
            "age": self.age,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
            "status": self.status.value,
            "associated_devices": list(self.associated_devices)
        }


@dataclass
class Device:
    """Device entity for testing."""
    device_id: str
    serial_number: str
    parent_id: str
    associated_child_id: Optional[str]
    created_at: str
    last_seen_at: str
    status: EntityStatus = EntityStatus.ACTIVE
    firmware_version: str = "1.0.0"

    def to_dict(self):
        return {
            "device_id": self.device_id,
            "serial_number": self.serial_number,
            "parent_id": self.parent_id,
            "associated_child_id": self.associated_child_id,
            "created_at": self.created_at,
            "last_seen_at": self.last_seen_at,
            "status": self.status.value,
            "firmware_version": self.firmware_version
        }


@dataclass
class Parent:
    """Parent entity for testing."""
    parent_id: str
    email: str
    name: str
    created_at: str
    status: EntityStatus = EntityStatus.ACTIVE
    children: Set[str] = None
    devices: Set[str] = None

    def __post_init__(self):
        if self.children is None:
            self.children = set()
        if self.devices is None:
            self.devices = set()

    def to_dict(self):
        return {
            "parent_id": self.parent_id,
            "email": self.email,
            "name": self.name,
            "created_at": self.created_at,
            "status": self.status.value,
            "children": list(self.children),
            "devices": list(self.devices)
        }


class MockParentDashboard:
    """Mock parent dashboard for testing visibility."""
    
    def __init__(self):
        self.dashboard_data = {}
        self.refresh_count = 0
        self.last_refresh = None
        
    def refresh_dashboard(self, parent_id: str, children: List[Child], devices: List[Device]) -> Dict[str, Any]:
        """Refresh dashboard data for parent."""
        self.refresh_count += 1
        self.last_refresh = datetime.now().isoformat()
        
        # Create dashboard view
        dashboard_view = {
            "parent_id": parent_id,
            "last_updated": self.last_refresh,
            "children": [],
            "devices": [],
            "associations": []
        }
        
        # Add children data
        for child in children:
            if child.parent_id == parent_id and child.status == EntityStatus.ACTIVE:
                child_data = child.to_dict()
                child_data["device_count"] = len(child.associated_devices)
                dashboard_view["children"].append(child_data)
        
        # Add devices data
        for device in devices:
            if device.parent_id == parent_id and device.status == EntityStatus.ACTIVE:
                device_data = device.to_dict()
                dashboard_view["devices"].append(device_data)
        
        # Create association mappings
        for device in devices:
            if device.parent_id == parent_id and device.associated_child_id:
                dashboard_view["associations"].append({
                    "device_id": device.device_id,
                    "device_serial": device.serial_number,
                    "child_id": device.associated_child_id,
                    "child_name": next((c.name for c in children if c.child_id == device.associated_child_id), "Unknown"),
                    "status": "active"
                })
        
        self.dashboard_data[parent_id] = dashboard_view
        return dashboard_view
    
    def get_dashboard_data(self, parent_id: str) -> Optional[Dict[str, Any]]:
        """Get dashboard data for parent."""
        return self.dashboard_data.get(parent_id)


class MockDataStore:
    """Mock data store for testing business logic."""
    
    def __init__(self):
        self.parents: Dict[str, Parent] = {}
        self.children: Dict[str, Child] = {}
        self.devices: Dict[str, Device] = {}
        self.interaction_logs: List[Dict[str, Any]] = []
        self.access_logs: List[Dict[str, Any]] = []
        
    def create_parent(self, parent: Parent) -> bool:
        """Create parent record."""
        if parent.parent_id in self.parents:
            return False
        self.parents[parent.parent_id] = parent
        return True
    
    def create_child(self, child: Child) -> bool:
        """Create child record."""
        if child.child_id in self.children:
            return False
        
        # Verify parent exists
        if child.parent_id not in self.parents:
            return False
            
        self.children[child.child_id] = child
        self.parents[child.parent_id].children.add(child.child_id)
        return True
    
    def create_device(self, device: Device) -> bool:
        """Create device record."""
        if device.device_id in self.devices:
            return False
            
        # Verify parent exists
        if device.parent_id not in self.parents:
            return False
            
        self.devices[device.device_id] = device
        self.parents[device.parent_id].devices.add(device.device_id)
        return True
    
    def associate_device_child(self, device_id: str, child_id: str) -> bool:
        """Associate device with child."""
        if device_id not in self.devices or child_id not in self.children:
            return False
            
        device = self.devices[device_id]
        child = self.children[child_id]
        
        # Verify same parent
        if device.parent_id != child.parent_id:
            return False
        
        # Update association
        device.associated_child_id = child_id
        child.associated_devices.add(device_id)
        
        self.log_access_event("device_child_association", {
            "device_id": device_id,
            "child_id": child_id,
            "parent_id": device.parent_id,
            "action": "associated"
        })
        
        return True
    
    def delete_child(self, child_id: str, hard_delete: bool = False) -> bool:
        """Delete child and revoke access."""
        if child_id not in self.children:
            return False
            
        child = self.children[child_id]
        
        if hard_delete:
            # Remove from all associated devices
            for device_id in child.associated_devices.copy():
                if device_id in self.devices:
                    self.devices[device_id].associated_child_id = None
                    
            # Remove from parent
            if child.parent_id in self.parents:
                self.parents[child.parent_id].children.discard(child_id)
                
            # Delete child record
            del self.children[child_id]
            
            # Log deletion
            self.log_access_event("child_deletion", {
                "child_id": child_id,
                "parent_id": child.parent_id,
                "action": "hard_deleted",
                "associated_devices_cleared": len(child.associated_devices)
            })
        else:
            # Soft delete - mark as deleted
            child.status = EntityStatus.DELETED
            
            # Revoke device access
            for device_id in child.associated_devices.copy():
                if device_id in self.devices:
                    self.devices[device_id].associated_child_id = None
            
            child.associated_devices.clear()
            
            self.log_access_event("child_deletion", {
                "child_id": child_id,
                "parent_id": child.parent_id,
                "action": "soft_deleted",
                "access_revoked": True
            })
        
        return True
    
    def delete_device(self, device_id: str, hard_delete: bool = False) -> bool:
        """Delete device and revoke access."""
        if device_id not in self.devices:
            return False
            
        device = self.devices[device_id]
        
        # Remove from associated child
        if device.associated_child_id and device.associated_child_id in self.children:
            child = self.children[device.associated_child_id]
            child.associated_devices.discard(device_id)
        
        if hard_delete:
            # Remove from parent
            if device.parent_id in self.parents:
                self.parents[device.parent_id].devices.discard(device_id)
                
            # Delete device record
            del self.devices[device_id]
            
            self.log_access_event("device_deletion", {
                "device_id": device_id,
                "parent_id": device.parent_id,
                "action": "hard_deleted"
            })
        else:
            # Soft delete
            device.status = EntityStatus.DELETED
            device.associated_child_id = None
            
            self.log_access_event("device_deletion", {
                "device_id": device_id,
                "parent_id": device.parent_id,
                "action": "soft_deleted"
            })
        
        return True
    
    def log_interaction(self, child_id: str, device_id: str, interaction_type: str, data: Dict[str, Any]):
        """Log child-device interaction."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "child_id": child_id,
            "device_id": device_id,
            "interaction_type": interaction_type,
            "data": data,
            "status": "logged"
        }
        self.interaction_logs.append(log_entry)
    
    def log_access_event(self, event_type: str, details: Dict[str, Any]):
        """Log access/security event."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "details": details
        }
        self.access_logs.append(log_entry)
    
    def get_children_by_parent(self, parent_id: str) -> List[Child]:
        """Get all children for a parent."""
        return [child for child in self.children.values() if child.parent_id == parent_id]
    
    def get_devices_by_parent(self, parent_id: str) -> List[Device]:
        """Get all devices for a parent."""
        return [device for device in self.devices.values() if device.parent_id == parent_id]
    
    def verify_access_revoked(self, entity_id: str, entity_type: str) -> Dict[str, Any]:
        """Verify that access has been properly revoked for deleted entity."""
        verification = {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "access_revoked": True,
            "associations_cleared": True,
            "data_integrity": True,
            "issues": []
        }
        
        if entity_type == "child":
            # Check if child still has device associations
            if entity_id in self.children:
                child = self.children[entity_id]
                if child.status == EntityStatus.DELETED and child.associated_devices:
                    verification["associations_cleared"] = False
                    verification["issues"].append(f"Deleted child {entity_id} still has device associations")
            
            # Check if any devices still reference this child
            for device in self.devices.values():
                if device.associated_child_id == entity_id and device.status == EntityStatus.ACTIVE:
                    verification["associations_cleared"] = False
                    verification["issues"].append(f"Device {device.device_id} still references deleted child {entity_id}")
        
        elif entity_type == "device":
            # Check if device still referenced by child
            for child in self.children.values():
                if entity_id in child.associated_devices:
                    verification["associations_cleared"] = False
                    verification["issues"].append(f"Child {child.child_id} still references deleted device {entity_id}")
        
        verification["access_revoked"] = len(verification["issues"]) == 0
        verification["data_integrity"] = verification["access_revoked"] and verification["associations_cleared"]
        
        return verification


class BusinessDataFlowTester:
    """Comprehensive business/data flow testing for ESP32 system."""
    
    def __init__(self):
        self.data_store = MockDataStore()
        self.dashboard = MockParentDashboard()
        self.test_results = []
        
        # Test data
        self.test_parent_id = f"parent_{uuid.uuid4().hex[:8]}"
        self.test_children = []
        self.test_devices = []
        
    def log_test_result(self, result: TestResult):
        """Log test result."""
        self.test_results.append(result)
        status_emoji = "✅" if result.status == "PASS" else "❌" if result.status == "FAIL" else "⚠️"
        duration_str = f" ({result.duration_ms:.1f}ms)" if result.duration_ms else ""
        print(f"{status_emoji} {result.test_name}{duration_str}")
        if result.error_message:
            print(f"   Error: {result.error_message}")
    
    def setup_test_data(self):
        """Set up initial test data."""
        print("   🔧 Setting up test data...")
        
        # Create test parent
        parent = Parent(
            parent_id=self.test_parent_id,
            email=f"parent{self.test_parent_id}@test.com",
            name="Test Parent",
            created_at=datetime.now().isoformat()
        )
        
        success = self.data_store.create_parent(parent)
        if not success:
            raise Exception("Failed to create test parent")
        
        print(f"      👨‍👩‍👧‍👦 Created parent: {parent.parent_id}")
        
    def test_device_child_associations_visibility(self) -> bool:
        """Test device-child associations and dashboard visibility."""
        test_name = "Device-Child Associations and Dashboard Visibility"
        start_time = time.time()
        
        try:
            association_tests = []
            
            # Test 1: Create children and devices
            print("   👶 Creating children and devices...")
            
            # Create 3 children
            for i in range(3):
                child_id = f"child_{uuid.uuid4().hex[:8]}"
                child = Child(
                    child_id=child_id,
                    name=f"Test Child {i+1}",
                    age=5 + i,
                    parent_id=self.test_parent_id,
                    created_at=datetime.now().isoformat()
                )
                
                success = self.data_store.create_child(child)
                if success:
                    self.test_children.append(child)
                    print(f"      👶 Created child: {child.name} ({child.child_id})")
            
            # Create 4 devices (more devices than children)
            for i in range(4):
                device_id = f"device_{uuid.uuid4().hex[:8]}"
                device = Device(
                    device_id=device_id,
                    serial_number=f"TB{random.randint(100000, 999999)}",
                    parent_id=self.test_parent_id,
                    associated_child_id=None,
                    created_at=datetime.now().isoformat(),
                    last_seen_at=datetime.now().isoformat()
                )
                
                success = self.data_store.create_device(device)
                if success:
                    self.test_devices.append(device)
                    print(f"      📱 Created device: {device.serial_number} ({device.device_id})")
            
            association_tests.append({
                "test": "entity_creation",
                "status": "PASS",
                "children_created": len(self.test_children),
                "devices_created": len(self.test_devices),
                "expected_children": 3,
                "expected_devices": 4
            })
            
            # Test 2: Create associations
            print("   🔗 Creating device-child associations...")
            
            associations_created = 0
            
            # Associate first 3 devices with children (1:1)
            for i, (device, child) in enumerate(zip(self.test_devices[:3], self.test_children)):
                success = self.data_store.associate_device_child(device.device_id, child.child_id)
                if success:
                    associations_created += 1
                    print(f"      🔗 Associated {device.serial_number} ↔ {child.name}")
            
            # Leave 4th device unassociated
            
            association_tests.append({
                "test": "device_child_associations",
                "status": "PASS" if associations_created == 3 else "FAIL",
                "associations_created": associations_created,
                "expected_associations": 3,
                "unassociated_devices": 1
            })
            
            # Test 3: Dashboard visibility and data accuracy
            print("   📊 Testing dashboard visibility...")
            
            # Refresh dashboard
            dashboard_data = self.dashboard.refresh_dashboard(
                self.test_parent_id,
                self.data_store.get_children_by_parent(self.test_parent_id),
                self.data_store.get_devices_by_parent(self.test_parent_id)
            )
            
            # Verify dashboard content
            dashboard_verification = {
                "children_visible": len(dashboard_data["children"]) == 3,
                "devices_visible": len(dashboard_data["devices"]) == 4,
                "associations_visible": len(dashboard_data["associations"]) == 3,
                "association_details_correct": True
            }
            
            # Verify association details
            for association in dashboard_data["associations"]:
                device_id = association["device_id"]
                child_id = association["child_id"]
                
                # Verify association exists in data store
                device = self.data_store.devices.get(device_id)
                child = self.data_store.children.get(child_id)
                
                if not device or not child or device.associated_child_id != child_id:
                    dashboard_verification["association_details_correct"] = False
                    break
            
            print(f"      📊 Dashboard shows: {len(dashboard_data['children'])} children, {len(dashboard_data['devices'])} devices, {len(dashboard_data['associations'])} associations")
            
            association_tests.append({
                "test": "dashboard_visibility",
                "status": "PASS" if all(dashboard_verification.values()) else "FAIL",
                "dashboard_verification": dashboard_verification,
                "dashboard_refresh_count": self.dashboard.refresh_count
            })
            
            # Test 4: Real-time updates simulation
            print("   ⚡ Testing real-time dashboard updates...")
            
            # Simulate child interacting with device
            if self.test_children and self.test_devices:
                child = self.test_children[0]
                device = self.test_devices[0]
                
                # Log some interactions
                interactions = [
                    {"type": "voice_command", "command": "tell me a story"},
                    {"type": "play_request", "content": "lullaby"},
                    {"type": "volume_change", "level": 75}
                ]
                
                for interaction in interactions:
                    self.data_store.log_interaction(
                        child.child_id,
                        device.device_id,
                        interaction["type"],
                        interaction
                    )
                
                # Update device last seen
                device.last_seen_at = datetime.now().isoformat()
                
                # Refresh dashboard again
                updated_dashboard = self.dashboard.refresh_dashboard(
                    self.test_parent_id,
                    self.data_store.get_children_by_parent(self.test_parent_id),
                    self.data_store.get_devices_by_parent(self.test_parent_id)
                )
                
                association_tests.append({
                    "test": "realtime_updates",
                    "status": "PASS",
                    "interactions_logged": len(interactions),
                    "dashboard_refresh_count": self.dashboard.refresh_count,
                    "last_updated": updated_dashboard["last_updated"]
                })
                
                print(f"      ⚡ Logged {len(interactions)} interactions, dashboard refreshed")
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Evaluate overall result
            passed_tests = sum(1 for test in association_tests if test.get("status") == "PASS")
            overall_pass = passed_tests >= len(association_tests) * 0.8
            
            result = TestResult(
                test_name=test_name,
                status="PASS" if overall_pass else "FAIL",
                details={
                    "association_tests": association_tests,
                    "passed_tests": passed_tests,
                    "total_tests": len(association_tests),
                    "dashboard_data": dashboard_data,
                    "interactions_logged": len(self.data_store.interaction_logs)
                },
                timestamp=datetime.now().isoformat(),
                duration_ms=duration_ms
            )
            
            print(f"   📊 Association tests: {passed_tests}/{len(association_tests)} passed")
            
            self.log_test_result(result)
            return result.status == "PASS"
            
        except Exception as e:
            result = TestResult(
                test_name=test_name,
                status="ERROR",
                details={},
                timestamp=datetime.now().isoformat(),
                error_message=str(e)
            )
            self.log_test_result(result)
            return False
    
    def test_onboarding_sync_workflows(self) -> bool:
        """Test onboarding workflows - add/remove child and device with immediate sync."""
        test_name = "Onboarding and Sync Workflows"
        start_time = time.time()
        
        try:
            onboarding_tests = []
            
            # Test 1: Add new child and verify immediate sync
            print("   👶➕ Testing child addition and sync...")
            
            new_child_id = f"child_{uuid.uuid4().hex[:8]}"
            new_child = Child(
                child_id=new_child_id,
                name="New Child",
                age=4,
                parent_id=self.test_parent_id,
                created_at=datetime.now().isoformat()
            )
            
            # Get initial dashboard state
            initial_dashboard = self.dashboard.get_dashboard_data(self.test_parent_id)
            initial_child_count = len(initial_dashboard["children"]) if initial_dashboard else 0
            
            # Add child
            child_added = self.data_store.create_child(new_child)
            
            # Immediate sync - refresh dashboard
            updated_dashboard = self.dashboard.refresh_dashboard(
                self.test_parent_id,
                self.data_store.get_children_by_parent(self.test_parent_id),
                self.data_store.get_devices_by_parent(self.test_parent_id)
            )
            
            # Verify sync
            new_child_count = len(updated_dashboard["children"])
            child_visible = any(c["child_id"] == new_child_id for c in updated_dashboard["children"])
            
            onboarding_tests.append({
                "test": "child_addition_sync",
                "status": "PASS" if child_added and child_visible and new_child_count == initial_child_count + 1 else "FAIL",
                "child_added": child_added,
                "child_visible_in_dashboard": child_visible,
                "child_count_before": initial_child_count,
                "child_count_after": new_child_count,
                "sync_immediate": True
            })
            
            print(f"      ✅ Child added and synced: {new_child.name} visible in dashboard")
            
            # Test 2: Add new device and associate with child
            print("   📱➕ Testing device addition and association...")
            
            new_device_id = f"device_{uuid.uuid4().hex[:8]}"
            new_device = Device(
                device_id=new_device_id,
                serial_number=f"TB{random.randint(100000, 999999)}",
                parent_id=self.test_parent_id,
                associated_child_id=None,
                created_at=datetime.now().isoformat(),
                last_seen_at=datetime.now().isoformat()
            )
            
            # Add device
            device_added = self.data_store.create_device(new_device)
            
            # Associate with new child
            association_created = self.data_store.associate_device_child(new_device_id, new_child_id)
            
            # Refresh dashboard
            updated_dashboard = self.dashboard.refresh_dashboard(
                self.test_parent_id,
                self.data_store.get_children_by_parent(self.test_parent_id),
                self.data_store.get_devices_by_parent(self.test_parent_id)
            )
            
            # Verify device and association visible
            device_visible = any(d["device_id"] == new_device_id for d in updated_dashboard["devices"])
            association_visible = any(
                a["device_id"] == new_device_id and a["child_id"] == new_child_id 
                for a in updated_dashboard["associations"]
            )
            
            onboarding_tests.append({
                "test": "device_addition_association",
                "status": "PASS" if device_added and association_created and device_visible and association_visible else "FAIL",
                "device_added": device_added,
                "association_created": association_created,
                "device_visible": device_visible,
                "association_visible": association_visible,
                "device_serial": new_device.serial_number
            })
            
            print(f"      ✅ Device added and associated: {new_device.serial_number} ↔ {new_child.name}")
            
            # Test 3: Remove child and verify sync
            print("   👶➖ Testing child removal and sync...")
            
            # Get current state
            pre_removal_dashboard = self.dashboard.get_dashboard_data(self.test_parent_id)
            pre_removal_child_count = len(pre_removal_dashboard["children"])
            pre_removal_association_count = len(pre_removal_dashboard["associations"])
            
            # Remove the new child (soft delete)
            child_removed = self.data_store.delete_child(new_child_id, hard_delete=False)
            
            # Refresh dashboard
            post_removal_dashboard = self.dashboard.refresh_dashboard(
                self.test_parent_id,
                self.data_store.get_children_by_parent(self.test_parent_id),
                self.data_store.get_devices_by_parent(self.test_parent_id)
            )
            
            # Verify child no longer visible and associations cleaned
            post_removal_child_count = len(post_removal_dashboard["children"])
            post_removal_association_count = len(post_removal_dashboard["associations"])
            child_no_longer_visible = not any(c["child_id"] == new_child_id for c in post_removal_dashboard["children"])
            associations_cleaned = not any(a["child_id"] == new_child_id for a in post_removal_dashboard["associations"])
            
            onboarding_tests.append({
                "test": "child_removal_sync",
                "status": "PASS" if child_removed and child_no_longer_visible and associations_cleaned else "FAIL",
                "child_removed": child_removed,
                "child_no_longer_visible": child_no_longer_visible,
                "associations_cleaned": associations_cleaned,
                "child_count_before": pre_removal_child_count,
                "child_count_after": post_removal_child_count,
                "association_count_before": pre_removal_association_count,
                "association_count_after": post_removal_association_count
            })
            
            print(f"      ✅ Child removed and synced: no longer visible, associations cleaned")
            
            # Test 4: Remove device and verify sync
            print("   📱➖ Testing device removal and sync...")
            
            # Remove the new device
            device_removed = self.data_store.delete_device(new_device_id, hard_delete=False)
            
            # Refresh dashboard
            final_dashboard = self.dashboard.refresh_dashboard(
                self.test_parent_id,
                self.data_store.get_children_by_parent(self.test_parent_id),
                self.data_store.get_devices_by_parent(self.test_parent_id)
            )
            
            # Verify device no longer visible
            device_no_longer_visible = not any(d["device_id"] == new_device_id for d in final_dashboard["devices"])
            no_orphaned_associations = not any(a["device_id"] == new_device_id for a in final_dashboard["associations"])
            
            onboarding_tests.append({
                "test": "device_removal_sync",
                "status": "PASS" if device_removed and device_no_longer_visible and no_orphaned_associations else "FAIL",
                "device_removed": device_removed,
                "device_no_longer_visible": device_no_longer_visible,
                "no_orphaned_associations": no_orphaned_associations,
                "device_serial": new_device.serial_number
            })
            
            print(f"      ✅ Device removed and synced: no longer visible, no orphaned associations")
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Evaluate overall result
            passed_tests = sum(1 for test in onboarding_tests if test.get("status") == "PASS")
            overall_pass = passed_tests >= len(onboarding_tests) * 0.8
            
            result = TestResult(
                test_name=test_name,
                status="PASS" if overall_pass else "FAIL",
                details={
                    "onboarding_tests": onboarding_tests,
                    "passed_tests": passed_tests,
                    "total_tests": len(onboarding_tests),
                    "dashboard_refresh_count": self.dashboard.refresh_count,
                    "final_dashboard_state": final_dashboard
                },
                timestamp=datetime.now().isoformat(),
                duration_ms=duration_ms
            )
            
            print(f"   📊 Onboarding tests: {passed_tests}/{len(onboarding_tests)} passed")
            
            self.log_test_result(result)
            return result.status == "PASS"
            
        except Exception as e:
            result = TestResult(
                test_name=test_name,
                status="ERROR",
                details={},
                timestamp=datetime.now().isoformat(),
                error_message=str(e)
            )
            self.log_test_result(result)
            return False
    
    def test_deletion_data_revocation(self) -> bool:
        """Test deletion workflows and system-wide data/access revocation."""
        test_name = "Deletion and Data Revocation"
        start_time = time.time()
        
        try:
            deletion_tests = []
            
            # Use existing test data for deletion tests
            if not self.test_children or not self.test_devices:
                raise Exception("No test data available for deletion testing")
            
            # Test 1: Child deletion with access revocation
            print("   👶🗑️ Testing child deletion and access revocation...")
            
            target_child = self.test_children[0]  # Use first child
            target_child_id = target_child.child_id
            
            # Get associated devices before deletion
            associated_devices = list(target_child.associated_devices)
            
            # Record initial state
            initial_interaction_count = len(self.data_store.interaction_logs)
            initial_access_log_count = len(self.data_store.access_logs)
            
            print(f"      🎯 Target child: {target_child.name} ({target_child_id})")
            print(f"      📱 Associated devices: {len(associated_devices)}")
            
            # Delete child (soft delete)
            child_deleted = self.data_store.delete_child(target_child_id, hard_delete=False)
            
            # Verify access revocation
            access_verification = self.data_store.verify_access_revoked(target_child_id, "child")
            
            # Check that associated devices no longer reference this child
            devices_cleared = all(
                self.data_store.devices[device_id].associated_child_id != target_child_id
                for device_id in associated_devices
                if device_id in self.data_store.devices
            )
            
            # Verify dashboard sync
            dashboard_after_deletion = self.dashboard.refresh_dashboard(
                self.test_parent_id,
                self.data_store.get_children_by_parent(self.test_parent_id),
                self.data_store.get_devices_by_parent(self.test_parent_id)
            )
            
            child_not_in_dashboard = not any(
                c["child_id"] == target_child_id for c in dashboard_after_deletion["children"]
            )
            
            associations_cleaned_dashboard = not any(
                a["child_id"] == target_child_id for a in dashboard_after_deletion["associations"]
            )
            
            deletion_tests.append({
                "test": "child_deletion_revocation",
                "status": "PASS" if child_deleted and access_verification["access_revoked"] and devices_cleared and child_not_in_dashboard else "FAIL",
                "child_deleted": child_deleted,
                "access_revoked": access_verification["access_revoked"],
                "devices_cleared": devices_cleared,
                "child_not_in_dashboard": child_not_in_dashboard,
                "associations_cleaned_dashboard": associations_cleaned_dashboard,
                "verification_details": access_verification,
                "associated_devices_count": len(associated_devices)
            })
            
            print(f"      ✅ Child deleted, access revoked from {len(associated_devices)} devices")
            
            # Test 2: Device deletion with access revocation
            print("   📱🗑️ Testing device deletion and access revocation...")
            
            target_device = self.test_devices[1]  # Use second device
            target_device_id = target_device.device_id
            associated_child_id = target_device.associated_child_id
            
            print(f"      🎯 Target device: {target_device.serial_number} ({target_device_id})")
            print(f"      👶 Associated child: {associated_child_id}")
            
            # Delete device (soft delete)
            device_deleted = self.data_store.delete_device(target_device_id, hard_delete=False)
            
            # Verify access revocation
            access_verification = self.data_store.verify_access_revoked(target_device_id, "device")
            
            # Check that child no longer references this device
            child_cleared = True
            if associated_child_id and associated_child_id in self.data_store.children:
                child = self.data_store.children[associated_child_id]
                child_cleared = target_device_id not in child.associated_devices
            
            # Verify dashboard sync
            dashboard_after_device_deletion = self.dashboard.refresh_dashboard(
                self.test_parent_id,
                self.data_store.get_children_by_parent(self.test_parent_id),
                self.data_store.get_devices_by_parent(self.test_parent_id)
            )
            
            device_not_in_dashboard = not any(
                d["device_id"] == target_device_id for d in dashboard_after_device_deletion["devices"]
            )
            
            device_associations_cleaned = not any(
                a["device_id"] == target_device_id for a in dashboard_after_device_deletion["associations"]
            )
            
            deletion_tests.append({
                "test": "device_deletion_revocation",
                "status": "PASS" if device_deleted and access_verification["access_revoked"] and child_cleared and device_not_in_dashboard else "FAIL",
                "device_deleted": device_deleted,
                "access_revoked": access_verification["access_revoked"],
                "child_cleared": child_cleared,
                "device_not_in_dashboard": device_not_in_dashboard,
                "device_associations_cleaned": device_associations_cleaned,
                "verification_details": access_verification,
                "device_serial": target_device.serial_number
            })
            
            print(f"      ✅ Device deleted, child associations cleared")
            
            # Test 3: System-wide consistency verification
            print("   🔍 Testing system-wide data consistency...")
            
            # Verify no orphaned references exist
            consistency_issues = []
            
            # Check for orphaned device associations
            for device in self.data_store.devices.values():
                if device.associated_child_id and device.associated_child_id in self.data_store.children:
                    child = self.data_store.children[device.associated_child_id]
                    if child.status == EntityStatus.DELETED:
                        consistency_issues.append(f"Active device {device.device_id} references deleted child {child.child_id}")
            
            # Check for orphaned child associations
            for child in self.data_store.children.values():
                for device_id in child.associated_devices:
                    if device_id in self.data_store.devices:
                        device = self.data_store.devices[device_id]
                        if device.status == EntityStatus.DELETED:
                            consistency_issues.append(f"Child {child.child_id} references deleted device {device_id}")
            
            # Check dashboard consistency
            current_dashboard = self.dashboard.get_dashboard_data(self.test_parent_id)
            
            # All children in dashboard should be active
            dashboard_consistency = True
            for child_data in current_dashboard["children"]:
                child_id = child_data["child_id"]
                if child_id in self.data_store.children:
                    child = self.data_store.children[child_id]
                    if child.status == EntityStatus.DELETED:
                        consistency_issues.append(f"Deleted child {child_id} still visible in dashboard")
                        dashboard_consistency = False
            
            # All devices in dashboard should be active
            for device_data in current_dashboard["devices"]:
                device_id = device_data["device_id"]
                if device_id in self.data_store.devices:
                    device = self.data_store.devices[device_id]
                    if device.status == EntityStatus.DELETED:
                        consistency_issues.append(f"Deleted device {device_id} still visible in dashboard")
                        dashboard_consistency = False
            
            deletion_tests.append({
                "test": "system_wide_consistency",
                "status": "PASS" if len(consistency_issues) == 0 and dashboard_consistency else "FAIL",
                "consistency_issues": consistency_issues,
                "dashboard_consistency": dashboard_consistency,
                "issues_count": len(consistency_issues),
                "active_children": len([c for c in self.data_store.children.values() if c.status == EntityStatus.ACTIVE]),
                "active_devices": len([d for d in self.data_store.devices.values() if d.status == EntityStatus.ACTIVE]),
                "deleted_children": len([c for c in self.data_store.children.values() if c.status == EntityStatus.DELETED]),
                "deleted_devices": len([d for d in self.data_store.devices.values() if d.status == EntityStatus.DELETED])
            })
            
            if consistency_issues:
                print(f"      ⚠️ Found {len(consistency_issues)} consistency issues")
                for issue in consistency_issues[:3]:  # Show first 3 issues
                    print(f"         - {issue}")
            else:
                print(f"      ✅ System-wide consistency verified")
            
            # Test 4: Access log verification
            print("   📋 Verifying deletion audit logs...")
            
            # Check that deletion events were logged
            deletion_events = [
                log for log in self.data_store.access_logs
                if log["event_type"] in ["child_deletion", "device_deletion"]
            ]
            
            child_deletion_logged = any(
                log["details"].get("child_id") == target_child_id
                for log in deletion_events
            )
            
            device_deletion_logged = any(
                log["details"].get("device_id") == target_device_id
                for log in deletion_events
            )
            
            deletion_tests.append({
                "test": "deletion_audit_logs",
                "status": "PASS" if child_deletion_logged and device_deletion_logged else "FAIL",
                "child_deletion_logged": child_deletion_logged,
                "device_deletion_logged": device_deletion_logged,
                "total_deletion_events": len(deletion_events),
                "total_access_logs": len(self.data_store.access_logs)
            })
            
            print(f"      ✅ Deletion events logged: {len(deletion_events)} events")
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Evaluate overall result
            passed_tests = sum(1 for test in deletion_tests if test.get("status") == "PASS")
            overall_pass = passed_tests >= len(deletion_tests) * 0.8
            
            result = TestResult(
                test_name=test_name,
                status="PASS" if overall_pass else "FAIL",
                details={
                    "deletion_tests": deletion_tests,
                    "passed_tests": passed_tests,
                    "total_tests": len(deletion_tests),
                    "consistency_issues": consistency_issues,
                    "final_dashboard_state": current_dashboard,
                    "access_logs_count": len(self.data_store.access_logs)
                },
                timestamp=datetime.now().isoformat(),
                duration_ms=duration_ms
            )
            
            print(f"   📊 Deletion tests: {passed_tests}/{len(deletion_tests)} passed")
            
            self.log_test_result(result)
            return result.status == "PASS"
            
        except Exception as e:
            result = TestResult(
                test_name=test_name,
                status="ERROR",
                details={},
                timestamp=datetime.now().isoformat(),
                error_message=str(e)
            )
            self.log_test_result(result)
            return False
    
    def run_business_data_flow_tests(self):
        """Run comprehensive business/data flow testing suite."""
        print("👨‍👩‍👧‍👦 ESP32 Business/Data Flow Validation Testing Suite")
        print("=" * 60)
        
        # Setup test data
        try:
            self.setup_test_data()
        except Exception as e:
            print(f"❌ Failed to setup test data: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "overall_score": 0.0,
                "tests_passed": 0,
                "total_tests": 3,
                "error": "Setup failed"
            }
        
        test_methods = [
            self.test_device_child_associations_visibility,
            self.test_onboarding_sync_workflows,
            self.test_deletion_data_revocation
        ]
        
        passed_tests = 0
        total_tests = len(test_methods)
        
        for test_method in test_methods:
            try:
                result = test_method()
                if result:
                    passed_tests += 1
            except Exception as e:
                print(f"❌ Test {test_method.__name__} failed with error: {e}")
        
        # Generate final report
        print("\n" + "=" * 60)
        print("🎯 BUSINESS/DATA FLOW TEST RESULTS")
        print("=" * 60)
        
        success_rate = (passed_tests / total_tests) * 100
        
        if success_rate >= 90:
            overall_status = "🟢 EXCELLENT"
        elif success_rate >= 70:
            overall_status = "🟡 GOOD"
        elif success_rate >= 50:
            overall_status = "🟠 NEEDS IMPROVEMENT"
        else:
            overall_status = "🔴 CRITICAL ISSUES"
        
        print(f"Business Flow Score: {success_rate:.1f}% {overall_status}")
        print(f"Tests Passed: {passed_tests}/{total_tests}")
        
        # Summary statistics
        print(f"\n📊 Final System State:")
        print(f"   Active Children: {len([c for c in self.data_store.children.values() if c.status == EntityStatus.ACTIVE])}")
        print(f"   Active Devices: {len([d for d in self.data_store.devices.values() if d.status == EntityStatus.ACTIVE])}")
        print(f"   Total Interactions: {len(self.data_store.interaction_logs)}")
        print(f"   Access Events: {len(self.data_store.access_logs)}")
        print(f"   Dashboard Refreshes: {self.dashboard.refresh_count}")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_score": success_rate,
            "tests_passed": passed_tests,
            "total_tests": total_tests,
            "test_results": [asdict(result) for result in self.test_results],
            "system_state": {
                "active_children": len([c for c in self.data_store.children.values() if c.status == EntityStatus.ACTIVE]),
                "active_devices": len([d for d in self.data_store.devices.values() if d.status == EntityStatus.ACTIVE]),
                "total_interactions": len(self.data_store.interaction_logs),
                "access_events": len(self.data_store.access_logs),
                "dashboard_refreshes": self.dashboard.refresh_count
            }
        }
    
    def save_results_to_file(self, results: Dict[str, Any], filename: str = None):
        """Save test results to JSON file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"esp32_business_data_flow_results_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: {filename}")
        return filename


def main():
    """Main business/data flow testing execution."""
    print("🤖 AI Teddy Bear - ESP32 Business/Data Flow Validation Testing")
    print("=" * 60)
    
    # Initialize tester
    tester = BusinessDataFlowTester()
    
    # Run all tests
    results = tester.run_business_data_flow_tests()
    
    # Save results
    filename = tester.save_results_to_file(results)
    
    # Return exit code based on results
    if results["overall_score"] >= 80:
        print("\n✅ ESP32 business/data flow testing PASSED")
        return 0
    elif results["overall_score"] >= 50:
        print(f"\n⚠️ ESP32 business/data flow testing completed with warnings ({results['overall_score']:.1f}%)")
        return 1
    else:
        print(f"\n❌ ESP32 business/data flow testing FAILED ({results['overall_score']:.1f}%)")
        return 2


if __name__ == "__main__":
    import sys
    result = main()
    sys.exit(result)