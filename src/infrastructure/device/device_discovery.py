"""
Device Discovery for ESP32 and network devices.
Scans and registers available devices on the network.
"""

import asyncio
import socket
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from ipaddress import IPv4Network
import json

logger = logging.getLogger(__name__)


@dataclass
class Device:
    """Discovered device information."""
    device_id: str
    device_type: str
    ip_address: str
    mac_address: str = ""
    hostname: str = ""
    last_seen: datetime = field(default_factory=datetime.now)
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)


class DeviceDiscovery:
    """Network device discovery service."""
    
    def __init__(self, network_range: str = "192.168.1.0/24"):
        self.devices: Dict[str, Device] = {}
        self.network_range = network_range
        self.esp32_ports = [80, 8080, 8266]  # Common ESP32 ports
        self.timeout = 2.0
    
    async def discover(self) -> List[Device]:
        """Scan network for ESP32 and other devices."""
        logger.info(f"Scanning network {self.network_range}")
        
        try:
            network = IPv4Network(self.network_range, strict=False)
        except Exception as e:
            logger.error(f"Invalid network range: {e}")
            return []
        
        active_ips = await self._ping_sweep(network)
        devices = []
        
        for ip in active_ips:
            device = await self._probe_device(ip)
            if device:
                devices.append(device)
                self.register(device.__dict__)
        
        logger.info(f"Found {len(devices)} devices")
        return devices
    
    async def _ping_sweep(self, network: IPv4Network) -> List[str]:
        """Find active IP addresses."""
        active_ips = []
        semaphore = asyncio.Semaphore(20)  # Limit concurrent pings
        
        async def ping_ip(ip_str: str):
            async with semaphore:
                if await self._ping_host(ip_str):
                    active_ips.append(ip_str)
        
        tasks = [ping_ip(str(ip)) for ip in list(network.hosts())[:50]]  # Limit scan range
        await asyncio.gather(*tasks, return_exceptions=True)
        return active_ips
    
    async def _ping_host(self, ip: str) -> bool:
        """Ping single host."""
        try:
            proc = await asyncio.create_subprocess_exec(
                'ping', '-n', '1', '-w', '1000', ip,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.wait()
            return proc.returncode == 0
        except Exception:
            return False
    
    async def _probe_device(self, ip: str) -> Optional[Device]:
        """Probe device for information."""
        try:
            hostname = self._get_hostname(ip)
            open_ports = await self._scan_ports(ip)
            device_type = self._identify_device_type(open_ports, hostname)
            
            device = Device(
                device_id=f"{ip}_{device_type}",
                device_type=device_type,
                ip_address=ip,
                hostname=hostname,
                capabilities=self._get_capabilities(open_ports),
                metadata={"open_ports": ",".join(map(str, open_ports))}
            )
            
            return device
        except Exception as e:
            logger.debug(f"Failed to probe {ip}: {e}")
            return None
    
    def _get_hostname(self, ip: str) -> str:
        """Get hostname for IP."""
        try:
            hostname, _, _ = socket.gethostbyaddr(ip)
            return hostname
        except Exception:
            return ip
    
    async def _scan_ports(self, ip: str) -> List[int]:
        """Scan common ports."""
        open_ports = []
        
        async def check_port(port: int):
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=self.timeout
                )
                writer.close()
                await writer.wait_closed()
                open_ports.append(port)
            except Exception:
                pass
        
        await asyncio.gather(*[check_port(p) for p in self.esp32_ports], return_exceptions=True)
        return sorted(open_ports)
    
    def _identify_device_type(self, open_ports: List[int], hostname: str) -> str:
        """Identify device type."""
        hostname_lower = hostname.lower()
        
        if any(port in open_ports for port in self.esp32_ports):
            if 'esp' in hostname_lower or 'arduino' in hostname_lower:
                return "esp32"
            return "microcontroller"
        
        if 80 in open_ports or 443 in open_ports:
            return "web_device"
        
        return "unknown"
    
    def _get_capabilities(self, open_ports: List[int]) -> List[str]:
        """Get device capabilities."""
        capabilities = []
        if 80 in open_ports:
            capabilities.append("http")
        if 8080 in open_ports:
            capabilities.append("web_service")
        if 8266 in open_ports:
            capabilities.append("esp_service")
        return capabilities
    
    def register(self, device_info: dict) -> bool:
        """Register discovered device."""
        try:
            device_id = device_info.get('device_id')
            if not device_id:
                return False
            
            # Convert dict to Device if needed
            if isinstance(device_info, dict):
                device = Device(
                    device_id=device_info['device_id'],
                    device_type=device_info.get('device_type', 'unknown'),
                    ip_address=device_info['ip_address'],
                    hostname=device_info.get('hostname', ''),
                    capabilities=device_info.get('capabilities', []),
                    metadata=device_info.get('metadata', {})
                )
            else:
                device = device_info
            
            self.devices[device_id] = device
            logger.info(f"Registered device: {device_id} at {device.ip_address}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register device: {e}")
            return False
    
    def get_devices(self) -> List[Device]:
        """Get all registered devices."""
        return list(self.devices.values())
    
    def get_device_by_id(self, device_id: str) -> Optional[Device]:
        """Get device by ID."""
        return self.devices.get(device_id)
    
    def get_esp32_devices(self) -> List[Device]:
        """Get ESP32 devices only."""
        return [d for d in self.devices.values() if d.device_type == "esp32"]
    
    def export_devices(self) -> str:
        """Export devices as JSON."""
        devices_data = []
        for device in self.devices.values():
            devices_data.append({
                "device_id": device.device_id,
                "device_type": device.device_type,
                "ip_address": device.ip_address,
                "hostname": device.hostname,
                "capabilities": device.capabilities,
                "metadata": device.metadata,
                "last_seen": device.last_seen.isoformat()
            })
        return json.dumps(devices_data, indent=2)
