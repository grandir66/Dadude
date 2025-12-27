"""
DaDude Agent - SNMP Probe
Scansione dettagliata dispositivi di rete via SNMP
Supporta: Ubiquiti, MikroTik, Cisco, HP, Dell, Synology, QNAP, APC, Fortinet
"""
import asyncio
import re
from typing import Dict, Any, Optional, List
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
            # Ubiquiti advanced
            "cpu_usage": "1.3.6.1.4.1.41112.1.4.7.1.5.1",
            "mem_usage": "1.3.6.1.4.1.41112.1.4.7.1.5.2",
            "temperature": "1.3.6.1.4.1.41112.1.4.7.1.5.3",
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
            # Cisco advanced
            "cpu_usage": "1.3.6.1.4.1.9.9.109.1.1.1.1.5",
            "mem_usage": "1.3.6.1.4.1.9.9.48.1.1.1.5.1",
            "temperature": "1.3.6.1.4.1.9.9.13.1.3.1.3",
        },
        # HP/Aruba (11, 25506)
        "hp": {
            "serial": "1.3.6.1.4.1.11.2.36.1.1.2.9.0",
            "model": "1.3.6.1.4.1.11.2.36.1.1.2.5.0",
            # HP ProCurve/ArubaOS specific
            "cpu_usage": "1.3.6.1.4.1.11.2.14.11.5.1.1.1.2.1.1.1.1",
            "mem_usage": "1.3.6.1.4.1.11.2.14.11.5.1.1.1.2.1.1.1.2",
            "temperature": "1.3.6.1.4.1.11.2.14.11.5.1.1.1.2.1.1.1.3",
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
        # Synology Storage OIDs (6574)
        "synology_storage": {
            # Volumi
            "volume_count": "1.3.6.1.4.1.6574.2.1.1.1",  # Numero volumi (table)
            "volume_name": "1.3.6.1.4.1.6574.2.1.1.2",   # Nome volumi (table)
            "volume_status": "1.3.6.1.4.1.6574.2.1.1.5",  # Stato volumi (table)
            "volume_total": "1.3.6.1.4.1.6574.2.1.1.6",  # Dimensione totale volumi (table)
            "volume_used": "1.3.6.1.4.1.6574.2.1.1.7",   # Spazio utilizzato volumi (table)
            "volume_free": "1.3.6.1.4.1.6574.2.1.1.8",   # Spazio libero volumi (table)
            # Dischi
            "disk_index": "1.3.6.1.4.1.6574.2.1.1.1",    # Indice dischi (table)
            "disk_name": "1.3.6.1.4.1.6574.2.1.1.2",     # Nome dischi (table)
            "disk_status": "1.3.6.1.4.1.6574.2.1.1.3",   # Stato dischi (table)
            "disk_model": "1.3.6.1.4.1.6574.2.1.1.5",    # Modello dischi (table)
            "disk_temperature": "1.3.6.1.4.1.6574.2.1.1.6", # Temperatura dischi (table)
            "disk_smart_status": "1.3.6.1.4.1.6574.2.1.1.7", # SMART status dischi (table)
            # RAID
            "raid_index": "1.3.6.1.4.1.6574.3.1.1.1",    # Indice RAID (table)
            "raid_name": "1.3.6.1.4.1.6574.3.1.1.2",     # Nome RAID (table)
            "raid_status": "1.3.6.1.4.1.6574.3.1.1.3",   # Stato RAID (table)
            "raid_level": "1.3.6.1.4.1.6574.3.1.1.4",    # Livello RAID (table)
        },
        # QNAP (24681)
        "qnap": {
            "model": "1.3.6.1.4.1.24681.1.2.12.0",
            "serial": "1.3.6.1.4.1.24681.1.2.13.0",
            "version": "1.3.6.1.4.1.24681.1.2.14.0",
            "cpu_temp": "1.3.6.1.4.1.24681.1.2.5.0",
            "sys_temp": "1.3.6.1.4.1.24681.1.2.6.0",
        },
        # QNAP Storage OIDs (24681)
        "qnap_storage": {
            # Volumi
            "volume_index": "1.3.6.1.4.1.24681.1.2.17.1.4.1",  # Indice volumi (table)
            "volume_name": "1.3.6.1.4.1.24681.1.2.17.1.4.2",  # Nome volumi (table)
            "volume_status": "1.3.6.1.4.1.24681.1.2.17.1.4.3", # Stato volumi (table)
            "volume_total": "1.3.6.1.4.1.24681.1.2.17.1.4.4",  # Dimensione totale volumi (table)
            "volume_used": "1.3.6.1.4.1.24681.1.2.17.1.4.5",  # Spazio utilizzato volumi (table)
            "volume_free": "1.3.6.1.4.1.24681.1.2.17.1.4.6",  # Spazio libero volumi (table)
            # Dischi
            "disk_index": "1.3.6.1.4.1.24681.1.2.11.1.1",     # Indice dischi (table)
            "disk_name": "1.3.6.1.4.1.24681.1.2.11.1.2",     # Nome dischi (table)
            "disk_status": "1.3.6.1.4.1.24681.1.2.11.1.3",   # Stato dischi (table)
            "disk_model": "1.3.6.1.4.1.24681.1.2.11.1.4",    # Modello dischi (table)
            "disk_temperature": "1.3.6.1.4.1.24681.1.2.11.1.5", # Temperatura dischi (table)
            # RAID
            "raid_index": "1.3.6.1.4.1.24681.1.2.12.1.1",    # Indice RAID (table)
            "raid_name": "1.3.6.1.4.1.24681.1.2.12.1.2",    # Nome RAID (table)
            "raid_status": "1.3.6.1.4.1.24681.1.2.12.1.3",  # Stato RAID (table)
            "raid_level": "1.3.6.1.4.1.24681.1.2.12.1.4",    # Livello RAID (table)
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
        # TP-Link/Omada (11863)
        "tp-link": {
            "model": "1.3.6.1.4.1.11863.1.1.1.1.0",
            "version": "1.3.6.1.4.1.11863.1.1.1.2.0",
            "serial": "1.3.6.1.4.1.11863.1.1.1.3.0",
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
    
    async def query_table(oid_base: str, max_rows: int = 100) -> List[Dict[str, Any]]:
        """Query SNMP table (walk) and return list of rows"""
        results = []
        try:
            count = 0
            async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                dispatcher,
                CommunityData(community, mpModel=1 if version == "2c" else 0),
                transport,
                ObjectType(ObjectIdentity(oid_base)),
                lexicographicMode=False
            ):
                if errorIndication or errorStatus:
                    break
                if count >= max_rows:
                    break
                row = {}
                for varBind in varBinds:
                    oid_str = str(varBind[0])
                    value = str(varBind[1])
                    if value and "No Such" not in value and value != "":
                        # Extract index from OID
                        index = oid_str.split('.')[-1] if '.' in oid_str else oid_str
                        row[oid_str] = value
                if row:
                    results.append(row)
                count += 1
        except:
            pass
        return results
    
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
            "1.3.6.1.4.1.4413": ("Ubiquiti", "ubiquiti"),  # Ubiquiti Networks (USW, USXG, etc.)
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
            "1.3.6.1.4.1.11863": ("TP-Link", "tp-link"),
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
                "tp-link": "TP-Link", "omada": "TP-Link", "tplink": "TP-Link",
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
        # STORAGE INFO COLLECTION (Synology/QNAP)
        # ==========================================
        is_storage_device = device_type == "storage" or device_type == "nas" or vendor in ["Synology", "QNAP"]
        
        if is_storage_device and vendor == "Synology":
            logger.info(f"SNMP probe: Collecting storage info for Synology device {target}")
            storage_info = {}
            
            try:
                # Volumi Synology
                volumes = []
                volume_names = {}
                volume_statuses = {}
                volume_totals = {}
                volume_useds = {}
                volume_frees = {}
                
                # Walk volume table
                try:
                    async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                        dispatcher,
                        CommunityData(community, mpModel=1 if version == "2c" else 0),
                        transport,
                        ObjectType(ObjectIdentity(oids_vendor_specific["synology_storage"]["volume_name"])),
                        lexicographicMode=False
                    ):
                        if errorIndication or errorStatus:
                            break
                        for varBind in varBinds:
                            oid_str = str(varBind[0])
                            value = str(varBind[1])
                            if value and "No Such" not in value:
                                index = oid_str.split('.')[-1]
                                volume_names[index] = value
                except Exception as e:
                    logger.debug(f"SNMP probe: Synology volume name walk failed: {e}")
                
                # Walk volume status, total, used, free
                for oid_type in ["volume_status", "volume_total", "volume_used", "volume_free"]:
                    oid = oids_vendor_specific["synology_storage"][oid_type]
                    try:
                        async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                            dispatcher,
                            CommunityData(community, mpModel=1 if version == "2c" else 0),
                            transport,
                            ObjectType(ObjectIdentity(oid)),
                            lexicographicMode=False
                        ):
                            if errorIndication or errorStatus:
                                break
                            for varBind in varBinds:
                                oid_str = str(varBind[0])
                                value = str(varBind[1])
                                if value and "No Such" not in value:
                                    index = oid_str.split('.')[-1]
                                    if oid_type == "volume_status":
                                        volume_statuses[index] = value
                                    elif oid_type == "volume_total":
                                        try:
                                            volume_totals[index] = int(value) / (1024 * 1024 * 1024)  # Converti bytes to GB
                                        except:
                                            pass
                                    elif oid_type == "volume_used":
                                        try:
                                            volume_useds[index] = int(value) / (1024 * 1024 * 1024)
                                        except:
                                            pass
                                    elif oid_type == "volume_free":
                                        try:
                                            volume_frees[index] = int(value) / (1024 * 1024 * 1024)
                                        except:
                                            pass
                    except Exception as e:
                        logger.debug(f"SNMP probe: Synology {oid_type} walk failed: {e}")
                
                # Build volumes list
                for index in volume_names.keys():
                    total_gb = volume_totals.get(index, 0)
                    used_gb = volume_useds.get(index, 0)
                    free_gb = volume_frees.get(index, 0)
                    usage_percent = (used_gb / total_gb * 100) if total_gb > 0 else 0
                    
                    volumes.append({
                        "name": volume_names.get(index, f"volume{index}"),
                        "mount_point": f"/volume{index}",
                        "total_gb": round(total_gb, 2),
                        "used_gb": round(used_gb, 2),
                        "free_gb": round(free_gb, 2),
                        "filesystem": "ext4",  # Default per Synology
                        "usage_percent": round(usage_percent, 1),
                        "status": volume_statuses.get(index, "unknown")
                    })
                
                if volumes:
                    storage_info["volumes"] = volumes
                
                # Dischi Synology
                disks = []
                disk_names = {}
                disk_statuses = {}
                disk_models = {}
                disk_temperatures = {}
                
                # Walk disk table
                try:
                    async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                        dispatcher,
                        CommunityData(community, mpModel=1 if version == "2c" else 0),
                        transport,
                        ObjectType(ObjectIdentity(oids_vendor_specific["synology_storage"]["disk_name"])),
                        lexicographicMode=False
                    ):
                        if errorIndication or errorStatus:
                            break
                        for varBind in varBinds:
                            oid_str = str(varBind[0])
                            value = str(varBind[1])
                            if value and "No Such" not in value:
                                index = oid_str.split('.')[-1]
                                disk_names[index] = value
                except Exception as e:
                    logger.debug(f"SNMP probe: Synology disk name walk failed: {e}")
                
                # Walk disk status, model, temperature
                for oid_type in ["disk_status", "disk_model", "disk_temperature"]:
                    oid = oids_vendor_specific["synology_storage"][oid_type]
                    try:
                        async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                            dispatcher,
                            CommunityData(community, mpModel=1 if version == "2c" else 0),
                            transport,
                            ObjectType(ObjectIdentity(oid)),
                            lexicographicMode=False
                        ):
                            if errorIndication or errorStatus:
                                break
                            for varBind in varBinds:
                                oid_str = str(varBind[0])
                                value = str(varBind[1])
                                if value and "No Such" not in value:
                                    index = oid_str.split('.')[-1]
                                    if oid_type == "disk_status":
                                        disk_statuses[index] = value
                                    elif oid_type == "disk_model":
                                        disk_models[index] = value
                                    elif oid_type == "disk_temperature":
                                        try:
                                            disk_temperatures[index] = int(value)
                                        except:
                                            pass
                    except Exception as e:
                        logger.debug(f"SNMP probe: Synology {oid_type} walk failed: {e}")
                
                # Build disks list
                for index in disk_names.keys():
                    health = "good" if disk_statuses.get(index, "").lower() in ["normal", "healthy"] else "warning"
                    disks.append({
                        "name": disk_names.get(index, f"disk{index}"),
                        "model": disk_models.get(index, ""),
                        "health": health,
                        "temperature": disk_temperatures.get(index)
                    })
                
                if disks:
                    storage_info["disks"] = disks
                
                # RAID Synology
                raid_names = {}
                raid_statuses = {}
                raid_levels = {}
                
                # Walk RAID table
                try:
                    async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                        dispatcher,
                        CommunityData(community, mpModel=1 if version == "2c" else 0),
                        transport,
                        ObjectType(ObjectIdentity(oids_vendor_specific["synology_storage"]["raid_name"])),
                        lexicographicMode=False
                    ):
                        if errorIndication or errorStatus:
                            break
                        for varBind in varBinds:
                            oid_str = str(varBind[0])
                            value = str(varBind[1])
                            if value and "No Such" not in value:
                                index = oid_str.split('.')[-1]
                                raid_names[index] = value
                    
                    # Walk RAID status and level
                    for oid_type in ["raid_status", "raid_level"]:
                        oid = oids_vendor_specific["synology_storage"][oid_type]
                        async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                            dispatcher,
                            CommunityData(community, mpModel=1 if version == "2c" else 0),
                            transport,
                            ObjectType(ObjectIdentity(oid)),
                            lexicographicMode=False
                        ):
                            if errorIndication or errorStatus:
                                break
                            for varBind in varBinds:
                                oid_str = str(varBind[0])
                                value = str(varBind[1])
                                if value and "No Such" not in value:
                                    index = oid_str.split('.')[-1]
                                    if oid_type == "raid_status":
                                        raid_statuses[index] = value
                                    elif oid_type == "raid_level":
                                        raid_levels[index] = value
                except Exception as e:
                    logger.debug(f"SNMP probe: Synology RAID walk failed: {e}")
                
                # Build RAID info
                if raid_names:
                    raid_devices = list(raid_names.values())
                    raid_status = raid_statuses.get(list(raid_names.keys())[0], "unknown")
                    raid_level = raid_levels.get(list(raid_names.keys())[0], "unknown")
                    degraded = "degraded" in raid_status.lower() or "error" in raid_status.lower()
                    
                    storage_info["raid"] = {
                        "level": raid_level,
                        "status": raid_status,
                        "devices": raid_devices,
                        "degraded": degraded
                    }
                
                # Temperatura sistema (già raccolta sopra)
                if info.get("temperature"):
                    storage_info["temperature"] = {
                        "system": int(info["temperature"]) if str(info["temperature"]).isdigit() else None
                    }
                
                if storage_info:
                    info["storage_info"] = storage_info
                    logger.info(f"SNMP probe: Collected storage info for Synology: {len(volumes)} volumes, {len(disks)} disks")
            except Exception as e:
                logger.warning(f"SNMP probe: Error collecting Synology storage info: {e}", exc_info=True)
        
        elif is_storage_device and vendor == "QNAP":
            logger.info(f"SNMP probe: Collecting storage info for QNAP device {target}")
            storage_info = {}
            
            try:
                # Volumi QNAP
                volumes = []
                volume_names = {}
                volume_statuses = {}
                volume_totals = {}
                volume_useds = {}
                volume_frees = {}
                
                # Walk volume table
                try:
                    async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                        dispatcher,
                        CommunityData(community, mpModel=1 if version == "2c" else 0),
                        transport,
                        ObjectType(ObjectIdentity(oids_vendor_specific["qnap_storage"]["volume_name"])),
                        lexicographicMode=False
                    ):
                        if errorIndication or errorStatus:
                            break
                        for varBind in varBinds:
                            oid_str = str(varBind[0])
                            value = str(varBind[1])
                            if value and "No Such" not in value:
                                index = oid_str.split('.')[-1]
                                volume_names[index] = value
                except Exception as e:
                    logger.debug(f"SNMP probe: QNAP volume name walk failed: {e}")
                
                # Walk volume status, total, used, free
                for oid_type in ["volume_status", "volume_total", "volume_used", "volume_free"]:
                    oid = oids_vendor_specific["qnap_storage"][oid_type]
                    try:
                        async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                            dispatcher,
                            CommunityData(community, mpModel=1 if version == "2c" else 0),
                            transport,
                            ObjectType(ObjectIdentity(oid)),
                            lexicographicMode=False
                        ):
                            if errorIndication or errorStatus:
                                break
                            for varBind in varBinds:
                                oid_str = str(varBind[0])
                                value = str(varBind[1])
                                if value and "No Such" not in value:
                                    index = oid_str.split('.')[-1]
                                    if oid_type == "volume_status":
                                        volume_statuses[index] = value
                                    elif oid_type == "volume_total":
                                        try:
                                            volume_totals[index] = int(value) / (1024 * 1024 * 1024)  # Converti bytes to GB
                                        except:
                                            pass
                                    elif oid_type == "volume_used":
                                        try:
                                            volume_useds[index] = int(value) / (1024 * 1024 * 1024)
                                        except:
                                            pass
                                    elif oid_type == "volume_free":
                                        try:
                                            volume_frees[index] = int(value) / (1024 * 1024 * 1024)
                                        except:
                                            pass
                    except Exception as e:
                        logger.debug(f"SNMP probe: QNAP {oid_type} walk failed: {e}")
                
                # Build volumes list
                for index in volume_names.keys():
                    total_gb = volume_totals.get(index, 0)
                    used_gb = volume_useds.get(index, 0)
                    free_gb = volume_frees.get(index, 0)
                    usage_percent = (used_gb / total_gb * 100) if total_gb > 0 else 0
                    
                    volumes.append({
                        "name": volume_names.get(index, f"volume{index}"),
                        "mount_point": f"/share/{volume_names.get(index, f'volume{index}')}",
                        "total_gb": round(total_gb, 2),
                        "used_gb": round(used_gb, 2),
                        "free_gb": round(free_gb, 2),
                        "filesystem": "ext4",
                        "usage_percent": round(usage_percent, 1),
                        "status": volume_statuses.get(index, "unknown")
                    })
                
                if volumes:
                    storage_info["volumes"] = volumes
                
                # Dischi QNAP
                disks = []
                disk_names = {}
                disk_statuses = {}
                disk_models = {}
                disk_temperatures = {}
                
                # Walk disk table
                try:
                    async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                        dispatcher,
                        CommunityData(community, mpModel=1 if version == "2c" else 0),
                        transport,
                        ObjectType(ObjectIdentity(oids_vendor_specific["qnap_storage"]["disk_name"])),
                        lexicographicMode=False
                    ):
                        if errorIndication or errorStatus:
                            break
                        for varBind in varBinds:
                            oid_str = str(varBind[0])
                            value = str(varBind[1])
                            if value and "No Such" not in value:
                                index = oid_str.split('.')[-1]
                                disk_names[index] = value
                except Exception as e:
                    logger.debug(f"SNMP probe: QNAP disk name walk failed: {e}")
                
                # Walk disk status, model, temperature
                for oid_type in ["disk_status", "disk_model", "disk_temperature"]:
                    oid = oids_vendor_specific["qnap_storage"][oid_type]
                    try:
                        async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                            dispatcher,
                            CommunityData(community, mpModel=1 if version == "2c" else 0),
                            transport,
                            ObjectType(ObjectIdentity(oid)),
                            lexicographicMode=False
                        ):
                            if errorIndication or errorStatus:
                                break
                            for varBind in varBinds:
                                oid_str = str(varBind[0])
                                value = str(varBind[1])
                                if value and "No Such" not in value:
                                    index = oid_str.split('.')[-1]
                                    if oid_type == "disk_status":
                                        disk_statuses[index] = value
                                    elif oid_type == "disk_model":
                                        disk_models[index] = value
                                    elif oid_type == "disk_temperature":
                                        try:
                                            disk_temperatures[index] = int(value)
                                        except:
                                            pass
                    except Exception as e:
                        logger.debug(f"SNMP probe: QNAP {oid_type} walk failed: {e}")
                
                # Build disks list
                for index in disk_names.keys():
                    health = "good" if disk_statuses.get(index, "").lower() in ["normal", "healthy", "ready"] else "warning"
                    disks.append({
                        "name": disk_names.get(index, f"disk{index}"),
                        "model": disk_models.get(index, ""),
                        "health": health,
                        "temperature": disk_temperatures.get(index)
                    })
                
                if disks:
                    storage_info["disks"] = disks
                
                # RAID QNAP
                raid_names = {}
                raid_statuses = {}
                raid_levels = {}
                
                # Walk RAID table
                try:
                    async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                        dispatcher,
                        CommunityData(community, mpModel=1 if version == "2c" else 0),
                        transport,
                        ObjectType(ObjectIdentity(oids_vendor_specific["qnap_storage"]["raid_name"])),
                        lexicographicMode=False
                    ):
                        if errorIndication or errorStatus:
                            break
                        for varBind in varBinds:
                            oid_str = str(varBind[0])
                            value = str(varBind[1])
                            if value and "No Such" not in value:
                                index = oid_str.split('.')[-1]
                                raid_names[index] = value
                    
                    # Walk RAID status and level
                    for oid_type in ["raid_status", "raid_level"]:
                        oid = oids_vendor_specific["qnap_storage"][oid_type]
                        async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                            dispatcher,
                            CommunityData(community, mpModel=1 if version == "2c" else 0),
                            transport,
                            ObjectType(ObjectIdentity(oid)),
                            lexicographicMode=False
                        ):
                            if errorIndication or errorStatus:
                                break
                            for varBind in varBinds:
                                oid_str = str(varBind[0])
                                value = str(varBind[1])
                                if value and "No Such" not in value:
                                    index = oid_str.split('.')[-1]
                                    if oid_type == "raid_status":
                                        raid_statuses[index] = value
                                    elif oid_type == "raid_level":
                                        raid_levels[index] = value
                except Exception as e:
                    logger.debug(f"SNMP probe: QNAP RAID walk failed: {e}")
                
                # Build RAID info
                if raid_names:
                    raid_devices = list(raid_names.values())
                    raid_status = raid_statuses.get(list(raid_names.keys())[0], "unknown")
                    raid_level = raid_levels.get(list(raid_names.keys())[0], "unknown")
                    degraded = "degraded" in raid_status.lower() or "error" in raid_status.lower()
                    
                    storage_info["raid"] = {
                        "level": raid_level,
                        "status": raid_status,
                        "devices": raid_devices,
                        "degraded": degraded
                    }
                
                # Temperatura sistema
                temp_info = {}
                if info.get("cpu_temp"):
                    try:
                        temp_info["cpu"] = int(info["cpu_temp"])
                    except:
                        pass
                if info.get("sys_temp"):
                    try:
                        temp_info["system"] = int(info["sys_temp"])
                    except:
                        pass
                
                if temp_info:
                    storage_info["temperature"] = temp_info
                
                if storage_info:
                    info["storage_info"] = storage_info
                    logger.info(f"SNMP probe: Collected storage info for QNAP: {len(volumes)} volumes, {len(disks)} disks")
            except Exception as e:
                logger.warning(f"SNMP probe: Error collecting QNAP storage info: {e}", exc_info=True)
        
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
        
        # ==========================================
        # COLLECT ADVANCED DATA FOR NETWORK DEVICES
        # ==========================================
        is_network_device = device_type in ["router", "switch", "ap", "network"]
        is_router = device_type == "router"
        
        logger.info(f"SNMP probe: device_type={device_type}, category={category}, vendor={info.get('vendor', 'unknown')}, sysObjectID={sys_oid}, is_network_device={is_network_device}, is_router={is_router}")
        
        if is_network_device:
            logger.info(f"SNMP probe: Collecting advanced data for network device {target} (type={device_type}, vendor={info.get('vendor', 'unknown')})")
            try:
                # ==========================================
                # LLDP NEIGHBORS (IEEE 802.1AB)
                # ==========================================
                logger.info(f"SNMP probe: Collecting LLDP neighbors for {target}...")
                lldp_neighbors = []
                
                # LLDP Remote Table OIDs
                lldp_oids = {
                    "local_port": "1.0.8802.1.1.2.1.4.1.1.1",  # lldpRemLocalPortNum
                    "chassis_id": "1.0.8802.1.1.2.1.4.1.1.5",   # lldpRemChassisId
                    "sys_name": "1.0.8802.1.1.2.1.4.1.1.9",     # lldpRemSysName
                    "sys_desc": "1.0.8802.1.1.2.1.4.1.1.10",    # lldpRemSysDesc
                    "man_addr": "1.0.8802.1.1.2.1.4.1.1.11",    # lldpRemManAddr
                }
                
                # Try to walk LLDP table
                try:
                    # LLDP OID structure: lldpRemEntry = lldpRemLocalPortNum.timeMark.lldpRemLocalPortNum.lldpRemIndex
                    # OID format: 1.0.8802.1.1.2.1.4.1.1.X.timeMark.localPortNum.remoteIndex
                    # We need to match by timeMark.localPortNum.remoteIndex
                    
                    # Get local port numbers first
                    local_ports = {}  # Key: "timeMark.localPortNum.remoteIndex", Value: port number
                    async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                        dispatcher,
                        CommunityData(community, mpModel=1 if version == "2c" else 0),
                        transport,
                        ObjectType(ObjectIdentity(lldp_oids["local_port"])),
                        lexicographicMode=False
                    ):
                        if errorIndication or errorStatus:
                            logger.debug(f"SNMP probe: LLDP local_port walk error: {errorIndication or errorStatus}")
                            break
                        for varBind in varBinds:
                            oid_str = str(varBind[0])
                            value = str(varBind[1])
                            if value and "No Such" not in value and value != "":
                                # Extract index: last 3 parts (timeMark.localPortNum.remoteIndex)
                                oid_parts = oid_str.split('.')
                                if len(oid_parts) >= 3:
                                    index_key = '.'.join(oid_parts[-3:])
                                    local_ports[index_key] = value
                    
                    logger.debug(f"SNMP probe: Collected {len(local_ports)} LLDP local ports")
                    
                    # Get system names
                    sys_names = {}  # Key: "timeMark.localPortNum.remoteIndex", Value: system name
                    async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                        dispatcher,
                        CommunityData(community, mpModel=1 if version == "2c" else 0),
                        transport,
                        ObjectType(ObjectIdentity(lldp_oids["sys_name"])),
                        lexicographicMode=False
                    ):
                        if errorIndication or errorStatus:
                            logger.debug(f"SNMP probe: LLDP sys_name walk error: {errorIndication or errorStatus}")
                            break
                        for varBind in varBinds:
                            oid_str = str(varBind[0])
                            value = str(varBind[1])
                            if value and "No Such" not in value and value != "":
                                # Extract index: last 3 parts (timeMark.localPortNum.remoteIndex)
                                oid_parts = oid_str.split('.')
                                if len(oid_parts) >= 3:
                                    index_key = '.'.join(oid_parts[-3:])
                                    sys_names[index_key] = value
                    
                    logger.debug(f"SNMP probe: Collected {len(sys_names)} LLDP system names")
                    
                    # Match by index key to build neighbor list
                    for index_key, port in list(local_ports.items())[:50]:  # Limit to 50 neighbors
                        sys_name = sys_names.get(index_key, "")
                        if sys_name:  # Only add if we have a system name
                            neighbor = {
                                "local_interface": port,
                                "remote_device_name": sys_name,
                                "discovered_by": "lldp"
                            }
                            lldp_neighbors.append(neighbor)
                    
                    logger.debug(f"SNMP probe: Built {len(lldp_neighbors)} LLDP neighbors from {len(local_ports)} ports and {len(sys_names)} names")
                    
                    if lldp_neighbors:
                        info["lldp_neighbors"] = lldp_neighbors
                        info["neighbors"] = lldp_neighbors  # Also set in neighbors for compatibility
                        info["lldp_neighbors_count"] = len(lldp_neighbors)
                        info["neighbors_count"] = len(lldp_neighbors)
                        logger.info(f"SNMP probe: Found {len(lldp_neighbors)} LLDP neighbors")
                    else:
                        logger.debug(f"SNMP probe: No LLDP neighbors found (sys_names={len(sys_names)}, local_ports={len(local_ports)})")
                except Exception as e:
                    logger.warning(f"SNMP probe: LLDP query failed for {target}: {e}", exc_info=True)
                
                # ==========================================
                # CDP NEIGHBORS (Cisco Discovery Protocol)
                # ==========================================
                if detected_vendor == "cisco":
                    try:
                        logger.debug(f"Collecting CDP neighbors for Cisco device {target}...")
                        cdp_neighbors = []
                        
                        # CDP Cache OIDs
                        cdp_cache_device_id = "1.3.6.1.4.1.9.9.23.1.2.1.1.6"  # cdpCacheDeviceId
                        cdp_cache_port = "1.3.6.1.4.1.9.9.23.1.2.1.1.7"        # cdpCacheDevicePort
                        cdp_cache_platform = "1.3.6.1.4.1.9.9.23.1.2.1.1.8"    # cdpCachePlatform
                        cdp_cache_version = "1.3.6.1.4.1.9.9.23.1.2.1.1.9"      # cdpCacheVersion
                        
                        device_ids = {}
                        async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                            dispatcher,
                            CommunityData(community, mpModel=1 if version == "2c" else 0),
                            transport,
                            ObjectType(ObjectIdentity(cdp_cache_device_id)),
                            lexicographicMode=False
                        ):
                            if errorIndication or errorStatus:
                                break
                            for varBind in varBinds:
                                oid_str = str(varBind[0])
                                value = str(varBind[1])
                                if value and "No Such" not in value and value != "":
                                    device_ids[oid_str] = value
                        
                        ports = {}
                        async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                            dispatcher,
                            CommunityData(community, mpModel=1 if version == "2c" else 0),
                            transport,
                            ObjectType(ObjectIdentity(cdp_cache_port)),
                            lexicographicMode=False
                        ):
                            if errorIndication or errorStatus:
                                break
                            for varBind in varBinds:
                                oid_str = str(varBind[0])
                                value = str(varBind[1])
                                if value and "No Such" not in value:
                                    ports[oid_str] = value
                        
                        platforms = {}
                        async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                            dispatcher,
                            CommunityData(community, mpModel=1 if version == "2c" else 0),
                            transport,
                            ObjectType(ObjectIdentity(cdp_cache_platform)),
                            lexicographicMode=False
                        ):
                            if errorIndication or errorStatus:
                                break
                            for varBind in varBinds:
                                oid_str = str(varBind[0])
                                value = str(varBind[1])
                                if value and "No Such" not in value:
                                    platforms[oid_str] = value
                        
                        # Match by OID index
                        for oid, device_id in list(device_ids.items())[:50]:  # Limit to 50
                            neighbor = {
                                "remote_device_name": device_id,
                                "local_interface": ports.get(oid, ""),
                                "platform": platforms.get(oid, ""),
                                "discovered_by": "cdp"
                            }
                            if neighbor["remote_device_name"]:
                                cdp_neighbors.append(neighbor)
                        
                        if cdp_neighbors:
                            # Merge with LLDP neighbors if any
                            if "lldp_neighbors" in info:
                                info["neighbors"] = info["lldp_neighbors"] + cdp_neighbors
                            else:
                                info["neighbors"] = cdp_neighbors
                            info["neighbors_count"] = len(info["neighbors"])
                            logger.debug(f"Found {len(cdp_neighbors)} CDP neighbors")
                    except Exception as e:
                        logger.debug(f"CDP query failed: {e}")
                
                # ==========================================
                # ROUTING TABLE (IP Forwarding Table MIB)
                # ==========================================
                try:
                    logger.info(f"SNMP probe: Collecting routing table for {target}...")
                    routes = []
                    
                    # IP Route Table OIDs
                    ip_route_dest = "1.3.6.1.2.1.4.21.1.1"  # ipRouteDest
                    ip_route_next_hop = "1.3.6.1.2.1.4.21.1.7"  # ipRouteNextHop
                    ip_route_type = "1.3.6.1.2.1.4.21.1.8"  # ipRouteType
                    ip_route_proto = "1.3.6.1.2.1.4.21.1.9"  # ipRouteProto
                    
                    route_dests = {}
                    async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                        dispatcher,
                        CommunityData(community, mpModel=1 if version == "2c" else 0),
                        transport,
                        ObjectType(ObjectIdentity(ip_route_dest)),
                        lexicographicMode=False
                    ):
                        if errorIndication or errorStatus:
                            break
                        if len(routes) >= 100:  # Limit to 100 routes
                            break
                        for varBind in varBinds:
                            oid_str = str(varBind[0])
                            value = str(varBind[1])
                            if value and "No Such" not in value and value != "0.0.0.0":
                                route_dests[oid_str] = value
                    
                    next_hops = {}
                    async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                        dispatcher,
                        CommunityData(community, mpModel=1 if version == "2c" else 0),
                        transport,
                        ObjectType(ObjectIdentity(ip_route_next_hop)),
                        lexicographicMode=False
                    ):
                        if errorIndication or errorStatus:
                            break
                        for varBind in varBinds:
                            oid_str = str(varBind[0])
                            value = str(varBind[1])
                            if value and "No Such" not in value:
                                next_hops[oid_str] = value
                    
                    # Build route list
                    for oid, dest in list(route_dests.items())[:100]:
                        route = {
                            "dst": dest,
                            "gateway": next_hops.get(oid, ""),
                            "interface": ""  # Would need additional query for interface
                        }
                        routes.append(route)
                    
                    if routes:
                        info["routing_table"] = routes
                        info["routing_count"] = len(routes)
                        logger.info(f"SNMP probe: Found {len(routes)} routes")
                    else:
                        logger.debug(f"SNMP probe: No routes found (route_dests={len(route_dests)}, next_hops={len(next_hops)})")
                except Exception as e:
                    logger.warning(f"SNMP probe: Routing table query failed for {target}: {e}", exc_info=True)
                
                # ==========================================
                # ARP TABLE (SOLO per Router)
                # ==========================================
                if is_router:
                    try:
                        logger.info(f"SNMP probe: Collecting ARP table for router {target}...")
                        arp_entries = []
                        
                        # ARP Table OIDs
                        arp_net_address = "1.3.6.1.2.1.4.22.1.3"  # ipNetToMediaNetAddress
                        arp_phys_address = "1.3.6.1.2.1.4.22.1.2"  # ipNetToMediaPhysAddress
                        arp_type = "1.3.6.1.2.1.4.22.1.4"  # ipNetToMediaType
                        
                        arp_ips = {}
                        async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                            dispatcher,
                            CommunityData(community, mpModel=1 if version == "2c" else 0),
                            transport,
                            ObjectType(ObjectIdentity(arp_net_address)),
                            lexicographicMode=False
                        ):
                            if errorIndication or errorStatus:
                                break
                            if len(arp_entries) >= 100:  # Limit to 100 ARP entries
                                break
                            for varBind in varBinds:
                                oid_str = str(varBind[0])
                                value = str(varBind[1])
                                if value and "No Such" not in value:
                                    arp_ips[oid_str] = value
                        
                        arp_macs = {}
                        async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                            dispatcher,
                            CommunityData(community, mpModel=1 if version == "2c" else 0),
                            transport,
                            ObjectType(ObjectIdentity(arp_phys_address)),
                            lexicographicMode=False
                        ):
                            if errorIndication or errorStatus:
                                break
                            for varBind in varBinds:
                                oid_str = str(varBind[0])
                                value = str(varBind[1])
                                if value and "No Such" not in value:
                                    arp_macs[oid_str] = value
                        
                        # Build ARP list
                        for oid, ip in list(arp_ips.items())[:100]:
                            arp_entry = {
                                "address": ip,
                                "mac-address": arp_macs.get(oid, ""),
                                "interface": ""  # Would need additional query
                            }
                            arp_entries.append(arp_entry)
                        
                        if arp_entries:
                            info["arp_table"] = arp_entries
                            info["arp_count"] = len(arp_entries)
                            logger.info(f"SNMP probe: Found {len(arp_entries)} ARP entries")
                        else:
                            logger.debug(f"SNMP probe: No ARP entries found (arp_ips={len(arp_ips)}, arp_macs={len(arp_macs)})")
                    except Exception as e:
                        logger.warning(f"SNMP probe: ARP table query failed for {target}: {e}", exc_info=True)
                
                # ==========================================
                # INTERFACES DETTAGLIATE (IF-MIB)
                # ==========================================
                try:
                    logger.info(f"SNMP probe: Collecting detailed interfaces for {target}...")
                    interfaces = []
                    
                    # IF-MIB OIDs
                    if_descr = "1.3.6.1.2.1.2.2.1.2"  # ifDescr
                    if_type = "1.3.6.1.2.1.2.2.1.3"    # ifType
                    if_speed = "1.3.6.1.2.1.2.2.1.5"    # ifSpeed
                    if_admin_status = "1.3.6.1.2.1.2.2.1.7"  # ifAdminStatus
                    if_oper_status = "1.3.6.1.2.1.2.2.1.8"    # ifOperStatus
                    if_phys_address = "1.3.6.1.2.1.2.2.1.6"   # ifPhysAddress
                    
                    if_descriptions = {}
                    async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                        dispatcher,
                        CommunityData(community, mpModel=1 if version == "2c" else 0),
                        transport,
                        ObjectType(ObjectIdentity(if_descr)),
                        lexicographicMode=False
                    ):
                        if errorIndication or errorStatus:
                            break
                        if len(interfaces) >= 100:  # Limit to 100 interfaces
                            break
                        for varBind in varBinds:
                            oid_str = str(varBind[0])
                            value = str(varBind[1])
                            if value and "No Such" not in value:
                                if_descriptions[oid_str] = value
                    
                    if_speeds = {}
                    async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                        dispatcher,
                        CommunityData(community, mpModel=1 if version == "2c" else 0),
                        transport,
                        ObjectType(ObjectIdentity(if_speed)),
                        lexicographicMode=False
                    ):
                        if errorIndication or errorStatus:
                            break
                        for varBind in varBinds:
                            oid_str = str(varBind[0])
                            value = str(varBind[1])
                            if value and "No Such" not in value:
                                try:
                                    speed_mbps = int(value) // 1000000  # Convert to Mbps
                                    if_speeds[oid_str] = speed_mbps
                                except:
                                    pass
                    
                    if_admin_statuses = {}
                    async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                        dispatcher,
                        CommunityData(community, mpModel=1 if version == "2c" else 0),
                        transport,
                        ObjectType(ObjectIdentity(if_admin_status)),
                        lexicographicMode=False
                    ):
                        if errorIndication or errorStatus:
                            break
                        for varBind in varBinds:
                            oid_str = str(varBind[0])
                            value = str(varBind[1])
                            if value and "No Such" not in value:
                                status_map = {"1": "up", "2": "down", "3": "testing"}
                                if_admin_statuses[oid_str] = status_map.get(value, value)
                    
                    if_oper_statuses = {}
                    async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                        dispatcher,
                        CommunityData(community, mpModel=1 if version == "2c" else 0),
                        transport,
                        ObjectType(ObjectIdentity(if_oper_status)),
                        lexicographicMode=False
                    ):
                        if errorIndication or errorStatus:
                            break
                        for varBind in varBinds:
                            oid_str = str(varBind[0])
                            value = str(varBind[1])
                            if value and "No Such" not in value:
                                status_map = {"1": "up", "2": "down", "3": "testing", "4": "unknown", "5": "dormant"}
                                if_oper_statuses[oid_str] = status_map.get(value, value)
                    
                    if_macs = {}
                    async for (errorIndication, errorStatus, errorIndex, varBinds) in next_cmd(
                        dispatcher,
                        CommunityData(community, mpModel=1 if version == "2c" else 0),
                        transport,
                        ObjectType(ObjectIdentity(if_phys_address)),
                        lexicographicMode=False
                    ):
                        if errorIndication or errorStatus:
                            break
                        for varBind in varBinds:
                            oid_str = str(varBind[0])
                            value = str(varBind[1])
                            if value and "No Such" not in value and len(value) > 5:
                                if_macs[oid_str] = value
                    
                    # Build interface list
                    # OID format: 1.3.6.1.2.1.2.2.1.X.ifIndex
                    # Extract ifIndex (last number) as key for matching
                    for oid, descr in list(if_descriptions.items())[:100]:
                        # Extract ifIndex from OID (last number)
                        if_index = oid.split('.')[-1] if '.' in oid else oid
                        
                        interface = {
                            "name": descr,
                            "if_index": if_index,
                            "speed_mbps": if_speeds.get(oid, 0),
                            "admin_status": if_admin_statuses.get(oid, ""),
                            "oper_status": if_oper_statuses.get(oid, ""),
                            "mac_address": if_macs.get(oid, "")
                        }
                        interfaces.append(interface)
                    
                    logger.debug(f"SNMP probe: Built {len(interfaces)} interfaces from {len(if_descriptions)} descriptions")
                    
                    if interfaces:
                        info["interfaces"] = interfaces
                        info["interfaces_count"] = len(interfaces)
                        info["interface_details"] = interfaces  # Alias per compatibilità
                        logger.info(f"SNMP probe: Found {len(interfaces)} interfaces")
                    else:
                        logger.debug(f"SNMP probe: No interfaces found (if_descriptions={len(if_descriptions)}, if_speeds={len(if_speeds)})")
                except Exception as e:
                    logger.warning(f"SNMP probe: Interface details query failed for {target}: {e}", exc_info=True)
                
                # Log summary of advanced data collected
                advanced_data_summary = []
                if info.get("neighbors") or info.get("lldp_neighbors") or info.get("cdp_neighbors"):
                    neighbors_count = len(info.get("neighbors", [])) or len(info.get("lldp_neighbors", [])) or len(info.get("cdp_neighbors", []))
                    advanced_data_summary.append(f"{neighbors_count} neighbors")
                if info.get("routing_table"):
                    advanced_data_summary.append(f"{len(info.get('routing_table', []))} routes")
                if info.get("arp_table"):
                    advanced_data_summary.append(f"{len(info.get('arp_table', []))} ARP entries")
                if info.get("interfaces"):
                    advanced_data_summary.append(f"{len(info.get('interfaces', []))} interfaces")
                
                if advanced_data_summary:
                    logger.info(f"SNMP probe: Advanced data collected for {target}: {', '.join(advanced_data_summary)}")
            except Exception as e:
                logger.warning(f"SNMP probe: Error collecting advanced data for {target}: {e}", exc_info=True)
        
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
