"""
DaDude Agent - SNMP Probe
Scansione dettagliata dispositivi di rete via SNMP
Supporta: Ubiquiti, MikroTik, Cisco, HP, Dell, Synology, QNAP, APC, Fortinet
"""
import asyncio
import re
from typing import Dict, Any, Optional
from loguru import logger


async def probe(
    target: str,
    community: str = "public",
    version: str = "2c",
    port: int = 161,
) -> Dict[str, Any]:
    """
    Esegue probe SNMP dettagliato su un target.
    
    Returns:
        Dict con info complete: vendor, model, serial, firmware, interfaces, etc.
    """
    from pysnmp.hlapi.v1arch.asyncio import (
        get_cmd, next_cmd, SnmpDispatcher, CommunityData, UdpTransportTarget,
        ObjectType, ObjectIdentity
    )
    
    logger.debug(f"SNMP probe: querying {target}:{port} community={community}")
    
    # ==========================================
    # OID DEFINITIONS
    # ==========================================
    
    # Standard MIB-II
    oids_basic = {
        "sysDescr": "1.3.6.1.2.1.1.1.0",
        "sysName": "1.3.6.1.2.1.1.5.0",
        "sysObjectID": "1.3.6.1.2.1.1.2.0",
        "sysContact": "1.3.6.1.2.1.1.4.0",
        "sysLocation": "1.3.6.1.2.1.1.6.0",
        "sysUpTime": "1.3.6.1.2.1.1.3.0",
        "sysServices": "1.3.6.1.2.1.1.7.0",
    }
    
    # Interface count
    oids_interfaces = {
        "ifNumber": "1.3.6.1.2.1.2.1.0",  # Total interfaces
    }
    
    # Entity MIB (RFC 4133)
    oids_entity = {
        "entPhysicalDescr": "1.3.6.1.2.1.47.1.1.1.1.2.1",
        "entPhysicalName": "1.3.6.1.2.1.47.1.1.1.1.7.1",
        "entPhysicalHardwareRev": "1.3.6.1.2.1.47.1.1.1.1.8.1",
        "entPhysicalFirmwareRev": "1.3.6.1.2.1.47.1.1.1.1.9.1",
        "entPhysicalSoftwareRev": "1.3.6.1.2.1.47.1.1.1.1.10.1",
        "entPhysicalSerialNum": "1.3.6.1.2.1.47.1.1.1.1.11.1",
        "entPhysicalMfgName": "1.3.6.1.2.1.47.1.1.1.1.12.1",
        "entPhysicalModelName": "1.3.6.1.2.1.47.1.1.1.1.13.1",
    }
    
    # Host Resources MIB (for servers/hosts)
    oids_host = {
        "hrSystemUptime": "1.3.6.1.2.1.25.1.1.0",
        "hrSystemNumUsers": "1.3.6.1.2.1.25.1.5.0",
        "hrSystemProcesses": "1.3.6.1.2.1.25.1.6.0",
        "hrMemorySize": "1.3.6.1.2.1.25.2.2.0",  # KB
    }
    
    # Vendor-specific OIDs
    vendor_oids = {
        # Ubiquiti (41112)
        "ubiquiti": {
            "model": "1.3.6.1.4.1.41112.1.6.3.3.0",
            "version": "1.3.6.1.4.1.41112.1.6.3.6.0",
            "mac": "1.3.6.1.4.1.41112.1.6.3.1.0",
        },
        # MikroTik (14988)
        "mikrotik": {
            "version": "1.3.6.1.4.1.14988.1.1.4.4.0",
            "serial": "1.3.6.1.4.1.14988.1.1.7.3.0",
            "model": "1.3.6.1.4.1.14988.1.1.7.1.0",
            "firmware": "1.3.6.1.4.1.14988.1.1.7.4.0",
            "license": "1.3.6.1.4.1.14988.1.1.4.1.0",
        },
        # Cisco (9)
        "cisco": {
            "serial": "1.3.6.1.4.1.9.3.6.3.0",
            "model": "1.3.6.1.4.1.9.9.25.1.1.1.2.3",
            "ios_version": "1.3.6.1.4.1.9.9.25.1.1.1.2.5",
        },
        # HP/Aruba (11, 25506)
        "hp": {
            "serial": "1.3.6.1.4.1.11.2.36.1.1.2.9.0",
            "model": "1.3.6.1.4.1.11.2.36.1.1.2.5.0",
        },
        # Dell (674)
        "dell": {
            "serial": "1.3.6.1.4.1.674.10892.5.1.3.2.0",
            "model": "1.3.6.1.4.1.674.10892.5.1.3.12.0",
        },
        # Synology (6574)
        "synology": {
            "model": "1.3.6.1.4.1.6574.1.5.1.0",
            "serial": "1.3.6.1.4.1.6574.1.5.2.0",
            "version": "1.3.6.1.4.1.6574.1.5.3.0",
            "temperature": "1.3.6.1.4.1.6574.1.2.0",
            "cpu_fan": "1.3.6.1.4.1.6574.1.4.1.0",
            "disk_count": "1.3.6.1.4.1.6574.2.1.1.2.0",
        },
        # QNAP (24681)
        "qnap": {
            "model": "1.3.6.1.4.1.24681.1.2.12.0",
            "serial": "1.3.6.1.4.1.24681.1.2.13.0",
            "version": "1.3.6.1.4.1.24681.1.2.14.0",
            "cpu_temp": "1.3.6.1.4.1.24681.1.2.5.0",
            "sys_temp": "1.3.6.1.4.1.24681.1.2.6.0",
        },
        # APC (318)
        "apc": {
            "model": "1.3.6.1.4.1.318.1.1.1.1.1.1.0",
            "serial": "1.3.6.1.4.1.318.1.1.1.1.2.3.0",
            "firmware": "1.3.6.1.4.1.318.1.1.1.1.2.1.0",
            "battery_status": "1.3.6.1.4.1.318.1.1.1.2.1.1.0",
            "battery_capacity": "1.3.6.1.4.1.318.1.1.1.2.2.1.0",
            "battery_runtime": "1.3.6.1.4.1.318.1.1.1.2.2.3.0",
            "output_load": "1.3.6.1.4.1.318.1.1.1.4.2.3.0",
        },
        # Fortinet (12356)
        "fortinet": {
            "serial": "1.3.6.1.4.1.12356.100.1.1.1.0",
            "model": "1.3.6.1.4.1.12356.100.1.1.2.0",
            "version": "1.3.6.1.4.1.12356.100.1.1.3.0",
            "cpu_usage": "1.3.6.1.4.1.12356.101.4.1.3.0",
            "mem_usage": "1.3.6.1.4.1.12356.101.4.1.4.0",
            "sessions": "1.3.6.1.4.1.12356.101.4.1.8.0",
        },
        # Juniper (2636)
        "juniper": {
            "serial": "1.3.6.1.4.1.2636.3.1.3.0",
            "model": "1.3.6.1.4.1.2636.3.1.2.0",
        },
    }
    
    info = {}
    dispatcher = SnmpDispatcher()
    
    async def query_oid(oid: str) -> Optional[str]:
        """Query single OID and return value"""
        try:
            errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
                dispatcher,
                CommunityData(community, mpModel=1 if version == "2c" else 0),
                transport,
                ObjectType(ObjectIdentity(oid))
            )
            if not errorIndication and not errorStatus:
                for varBind in varBinds:
                    value = str(varBind[1])
                    if value and "No Such" not in value and value != "":
                        return value
        except:
            pass
        return None
    
    try:
        transport = await UdpTransportTarget.create(
            (target, port),
            timeout=5,
            retries=1
        )
        
        # ==========================================
        # QUERY BASIC INFO
        # ==========================================
        for name, oid in oids_basic.items():
            value = await query_oid(oid)
            if value:
                info[name] = value
        
        # ==========================================
        # QUERY INTERFACE COUNT
        # ==========================================
        for name, oid in oids_interfaces.items():
            value = await query_oid(oid)
            if value:
                try:
                    info["interface_count"] = int(value)
                except:
                    pass
        
        # ==========================================
        # QUERY ENTITY MIB
        # ==========================================
        for name, oid in oids_entity.items():
            value = await query_oid(oid)
            if value:
                info[name] = value
        
        # ==========================================
        # QUERY HOST RESOURCES (for servers)
        # ==========================================
        for name, oid in oids_host.items():
            value = await query_oid(oid)
            if value:
                info[name] = value
        
        # ==========================================
        # DETECT VENDOR FROM sysObjectID
        # ==========================================
        sys_oid = info.get("sysObjectID", "")
        sys_descr = info.get("sysDescr", "").lower()
        detected_vendor = None
        device_type = "network"
        category = "unknown"
        
        # Vendor detection
        vendor_patterns = {
            "1.3.6.1.4.1.41112": ("Ubiquiti", "ubiquiti"),
            "1.3.6.1.4.1.10002": ("Ubiquiti", "ubiquiti"),  # UBNT
            "1.3.6.1.4.1.14988": ("MikroTik", "mikrotik"),
            "1.3.6.1.4.1.9.": ("Cisco", "cisco"),
            "1.3.6.1.4.1.11.": ("HP", "hp"),
            "1.3.6.1.4.1.25506": ("HP/H3C", "hp"),
            "1.3.6.1.4.1.674": ("Dell", "dell"),
            "1.3.6.1.4.1.6574": ("Synology", "synology"),
            "1.3.6.1.4.1.24681": ("QNAP", "qnap"),
            "1.3.6.1.4.1.318": ("APC", "apc"),
            "1.3.6.1.4.1.12356": ("Fortinet", "fortinet"),
            "1.3.6.1.4.1.2636": ("Juniper", "juniper"),
        }
        
        for prefix, (vendor_name, vendor_key) in vendor_patterns.items():
            if sys_oid.startswith(prefix):
                info["vendor"] = vendor_name
                detected_vendor = vendor_key
                break
        
        # Fallback vendor detection from sysDescr
        if not detected_vendor:
            descr_vendors = {
                "ubiquiti": "Ubiquiti", "unifi": "Ubiquiti", "ubnt": "Ubiquiti",
                "mikrotik": "MikroTik", "routeros": "MikroTik",
                "cisco": "Cisco", "ios": "Cisco",
                "hp ": "HP", "procurve": "HP", "aruba": "HP",
                "dell": "Dell",
                "synology": "Synology", "dsm": "Synology",
                "qnap": "QNAP", "qts": "QNAP",
                "apc": "APC",
                "fortinet": "Fortinet", "fortigate": "Fortinet",
                "juniper": "Juniper", "junos": "Juniper",
            }
            for pattern, vendor_name in descr_vendors.items():
                if pattern in sys_descr:
                    info["vendor"] = vendor_name
                    detected_vendor = pattern.split()[0]
                    break
        
        # ==========================================
        # QUERY VENDOR-SPECIFIC OIDs
        # ==========================================
        if detected_vendor and detected_vendor in vendor_oids:
            for name, oid in vendor_oids[detected_vendor].items():
                value = await query_oid(oid)
                if value:
                    info[f"vendor_{name}"] = value
        
        # ==========================================
        # DETERMINE DEVICE TYPE AND CATEGORY
        # ==========================================
        # Check sysDescr for device type hints
        if any(x in sys_descr for x in ["uap", "u6-", "u7-", "unifi ap", "access point"]):
            device_type = "ap"
            category = "wireless"
        elif any(x in sys_descr for x in ["usw", "switch", "procurve", "catalyst"]):
            device_type = "switch"
            category = "network"
        elif any(x in sys_descr for x in ["router", "routeros", "usg", "fortigate", "firewall"]):
            device_type = "router"
            category = "network"
        elif any(x in sys_descr for x in ["nas", "synology", "qnap", "diskstation"]):
            device_type = "nas"
            category = "storage"
        elif any(x in sys_descr for x in ["ups", "apc", "smart-ups"]):
            device_type = "ups"
            category = "power"
        elif any(x in sys_descr for x in ["linux", "windows", "server"]):
            device_type = "server"
            category = "server"
        
        info["device_type"] = device_type
        info["category"] = category
        
        # ==========================================
        # EXTRACT NORMALIZED FIELDS
        # ==========================================
        # Model
        info["model"] = (
            info.get("entPhysicalModelName") or
            info.get("vendor_model") or
            info.get("entPhysicalName") or
            _extract_model_from_descr(info.get("sysDescr", ""))
        )
        
        # Serial
        info["serial_number"] = (
            info.get("entPhysicalSerialNum") or
            info.get("vendor_serial")
        )
        
        # Firmware
        info["firmware_version"] = (
            info.get("entPhysicalFirmwareRev") or
            info.get("vendor_firmware") or
            info.get("vendor_version") or
            info.get("entPhysicalSoftwareRev")
        )
        
        # Manufacturer
        info["manufacturer"] = (
            info.get("vendor") or
            info.get("entPhysicalMfgName")
        )
        
        # Parse uptime
        if info.get("sysUpTime"):
            try:
                ticks = int(info["sysUpTime"])
                seconds = ticks // 100
                days = seconds // 86400
                hours = (seconds % 86400) // 3600
                info["uptime_formatted"] = f"{days}d {hours}h"
                info["uptime_seconds"] = seconds
            except:
                pass
        
    finally:
        dispatcher.transport_dispatcher.close_dispatcher()
    
    logger.info(f"SNMP probe successful: {info.get('sysName')} ({info.get('vendor', 'unknown')}) - {len(info)} fields")
    return info


def _extract_model_from_descr(descr: str) -> Optional[str]:
    """Extract model name from sysDescr string"""
    if not descr:
        return None
    
    # Common patterns
    patterns = [
        r'U[67]-\w+',  # Ubiquiti U6-LR, U7-Pro
        r'UAP-\w+',    # Ubiquiti UAP-*
        r'USW-\w+',    # Ubiquiti USW-*
        r'RB\d+\w*',   # MikroTik RB*
        r'CCR\d+\w*',  # MikroTik CCR*
        r'hAP\w*',     # MikroTik hAP
        r'CRS\d+\w*',  # MikroTik CRS*
        r'Catalyst \d+', # Cisco Catalyst
        r'DS\d+\w*',   # Synology DS*
        r'RS\d+\w*',   # Synology RS*
        r'TS-\d+\w*',  # QNAP TS-*
        r'Smart-UPS \w+', # APC UPS
    ]
    
    for pattern in patterns:
        match = re.search(pattern, descr, re.IGNORECASE)
        if match:
            return match.group(0)
    
    # Fallback: first word after vendor name or "Linux"
    parts = descr.split()
    if len(parts) > 1:
        if parts[0].lower() == "linux":
            return parts[1]
        return parts[0]
    
    return None
