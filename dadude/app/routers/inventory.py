"""
DaDude - Inventory Router
API per gestione inventario dispositivi
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
from loguru import logger
from datetime import datetime


router = APIRouter(prefix="/inventory", tags=["Inventory"])


# ==========================================
# SCHEMAS
# ==========================================

class DeviceImport(BaseModel):
    """Schema per importare un dispositivo nell'inventario"""
    address: Optional[str] = None
    mac_address: Optional[str] = None
    name: Optional[str] = None
    identity: Optional[str] = None
    hostname: Optional[str] = None  # Hostname risolto via DNS o rilevato
    platform: Optional[str] = None
    board: Optional[str] = None
    device_type: str = "other"  # windows, linux, mikrotik, network, printer, etc
    category: Optional[str] = None  # server, workstation, router, switch, etc
    credential_id: Optional[str] = None  # Credenziale associata per accesso
    open_ports: Optional[List[dict]] = None  # Porte TCP/UDP aperte
    os_family: Optional[str] = None
    os_version: Optional[str] = None
    identified_by: Optional[str] = None
    credential_used: Optional[str] = None


class BulkImport(BaseModel):
    """Schema per importare più dispositivi"""
    devices: List[DeviceImport]


class DeviceProbeRequest(BaseModel):
    """Schema per probe dispositivo"""
    address: str
    mac_address: Optional[str] = None
    credential_ids: Optional[List[str]] = None  # ID credenziali da usare


class BulkProbeRequest(BaseModel):
    """Schema per probe multipli dispositivi"""
    devices: List[DeviceProbeRequest]
    credential_ids: Optional[List[str]] = None  # Credenziali comuni


class EnrichRequest(BaseModel):
    """Schema per arricchire device con vendor info"""
    devices: List[dict]  # Lista di device con almeno mac_address


class AutoDetectRequest(BaseModel):
    """Schema per auto-detect dispositivo con credenziali di default"""
    address: str
    mac_address: Optional[str] = None
    device_id: Optional[str] = None  # ID device inventario (se presente, usa sua credenziale e salva risultati)
    use_default_credentials: bool = True  # Usa credenziali default del cliente
    use_assigned_credential: bool = True  # Usa credenziale assegnata al device (prioritaria)
    use_agent: bool = True  # Usa agent remoto se disponibile
    agent_id: Optional[str] = None  # ID agent specifico (se None, usa default)
    save_results: bool = True  # Salva i risultati nel device


class BulkAutoDetectRequest(BaseModel):
    """Schema per auto-detect multipli dispositivi"""
    devices: List[AutoDetectRequest]
    use_agent: bool = True  # Usa agent remoto per tutti i device


# ==========================================
# MAC VENDOR & DEVICE PROBE
# ==========================================

@router.post("/enrich-devices")
async def enrich_devices_with_vendor(data: EnrichRequest):
    """
    Arricchisce una lista di dispositivi con info vendor dal MAC address.
    Ritorna i device con vendor, suggested_type, suggested_category.
    """
    from ..services.mac_lookup_service import get_mac_lookup_service
    
    mac_service = get_mac_lookup_service()
    
    # Arricchisci ogni dispositivo con lookup MAC
    enriched = []
    found_count = 0
    for device in data.devices:
        mac = device.get("mac_address", "") or device.get("mac", "")
        if mac and mac.strip():
            mac = mac.strip()
            vendor_info = mac_service.lookup(mac)
            if vendor_info:
                device["vendor"] = vendor_info.get("vendor")
                device["suggested_type"] = vendor_info.get("device_type", "other")
                device["suggested_category"] = vendor_info.get("category")
                device["os_family"] = vendor_info.get("os_family")
                found_count += 1
                logger.info(f"Enriched device {device.get('address', 'unknown')} MAC {mac}: {vendor_info.get('vendor')}")
            else:
                # Fallback se non trovato
                device["vendor"] = device.get("vendor")
                device["suggested_type"] = device.get("suggested_type", "other")
                device["suggested_category"] = device.get("suggested_category")
                logger.debug(f"No vendor found for MAC {mac} (device {device.get('address', 'unknown')})")
        else:
            logger.debug(f"Device {device.get('address', 'unknown')} has no MAC address")
        enriched.append(device)
    
    logger.info(f"Enriched {found_count}/{len(data.devices)} devices with vendor info")
    
    return {
        "success": True,
        "devices": enriched,
    }


@router.post("/probe-device")
async def probe_single_device(
    data: DeviceProbeRequest,
    customer_id: str = Query(...),
):
    """
    Esegue probe su un singolo dispositivo per identificarlo.
    Usa le credenziali del cliente specificate.
    """
    from ..services.device_probe_service import get_device_probe_service
    from ..services.customer_service import get_customer_service
    
    probe_service = get_device_probe_service()
    customer_service = get_customer_service()
    
    # Recupera credenziali
    credentials_list = []
    if data.credential_ids:
        for cred_id in data.credential_ids:
            cred = customer_service.get_credential(cred_id, include_secrets=True)
            if cred:
                credentials_list.append({
                    "id": cred.id,
                    "name": cred.name,
                    "type": cred.credential_type,
                    "username": cred.username,
                    "password": cred.password,
                    "ssh_port": getattr(cred, 'ssh_port', 22),
                    "ssh_private_key": getattr(cred, 'ssh_private_key', None),
                    "snmp_community": getattr(cred, 'snmp_community', None),
                    "snmp_version": getattr(cred, 'snmp_version', '2c'),
                    "snmp_port": getattr(cred, 'snmp_port', 161),
                    "wmi_domain": getattr(cred, 'wmi_domain', None),
                    "mikrotik_api_port": getattr(cred, 'mikrotik_api_port', 8728),
                })
    
    # Esegui probe
    result = await probe_service.auto_identify_device(
        address=data.address,
        mac_address=data.mac_address,
        credentials_list=credentials_list
    )
    
    return {
        "success": True,
        "result": result,
    }


@router.post("/auto-detect")
async def auto_detect_device(
    data: AutoDetectRequest,
    customer_id: str = Query(...),
):
    """
    Esegue auto-detect su un dispositivo:
    1. Cerca agent remoto (Docker o MikroTik) per il cliente
    2. Scansiona le porte aperte (via agent se disponibile)
    3. Determina quali protocolli provare (SSH, SNMP, WMI) in base alle porte
    4. Cerca le credenziali di default del cliente per quei protocolli
    5. Esegue il probe con le credenziali appropriate (via agent Docker se disponibile)
    
    Logica porte → protocolli:
    - SSH (22, 23) → credenziali ssh
    - SNMP (161) → credenziali snmp  
    - RDP/SMB/LDAP/WMI (3389, 445, 139, 389, 135, 5985) → credenziali wmi
    - MikroTik API (8728, 8729, 8291) → credenziali mikrotik
    """
    from ..services.device_probe_service import get_device_probe_service
    from ..services.customer_service import get_customer_service
    from ..services.agent_service import get_agent_service
    
    probe_service = get_device_probe_service()
    customer_service = get_customer_service()
    agent_service = get_agent_service()
    
    result = {
        "address": data.address,
        "mac_address": data.mac_address,
        "success": False,
        "scan_result": None,
        "credentials_tested": [],
        "identified": False,
        "agent_used": None,
    }
    
    try:
        # 0. Cerca agent remoto
        agent_info = None
        if data.use_agent:
            if data.agent_id:
                # Agent specifico
                agent = customer_service.get_agent(data.agent_id, include_password=True)
                if agent:
                    agent_info = agent_service._agent_to_dict(agent)
            else:
                # Agent default del cliente
                agent_info = agent_service.get_agent_for_customer(customer_id)
            
            if agent_info:
                result["agent_used"] = {
                    "id": agent_info["id"],
                    "name": agent_info["name"],
                    "type": agent_info["agent_type"],
                }
                logger.info(f"Auto-detect: Using agent {agent_info['name']} ({agent_info['agent_type']})")
        
        # 1. Scansiona le porte
        logger.info(f"Auto-detect: Scanning ports on {data.address}...")
        
        if agent_info and agent_info.get("agent_type") == "docker":
            # Usa agent Docker per port scan
            port_result = await agent_service.scan_ports(agent_info, data.address)
            open_ports = port_result.get("open_ports", [])
        else:
            # Scansione diretta (o via MikroTik per porte limitate)
            open_ports = await probe_service.scan_services(data.address)
        
        result["open_ports"] = open_ports
        open_count = len([p for p in open_ports if p.get("open")])
        logger.info(f"Auto-detect: Found {open_count} open ports on {data.address}")
        
        if not open_ports or open_count == 0:
            result["error"] = "No open ports found"
            return result
        
        # 2. Determina credenziali da provare
        credentials_list = []
        device_record = None
        
        # 2a. Prima controlla se c'è una credenziale assegnata al device specifico
        if data.device_id and data.use_assigned_credential:
            from ..models.inventory import InventoryDevice
            from ..models.database import Credential as CredentialDB
            
            session = customer_service._get_session()
            try:
                device_record = session.query(InventoryDevice).filter(
                    InventoryDevice.id == data.device_id
                ).first()
                
                if device_record and device_record.credential_id:
                    cred = session.query(CredentialDB).filter(
                        CredentialDB.id == device_record.credential_id
                    ).first()
                    
                    if cred:
                        # Decripta la password
                        from ..services.encryption_service import get_encryption_service
                        encryption = get_encryption_service()
                        password = encryption.decrypt(cred.password) if cred.password else None
                        
                        credentials_list.append({
                            "id": cred.id,
                            "name": cred.name,
                            "type": cred.credential_type,
                            "username": cred.username,
                            "password": password,
                            "ssh_port": cred.ssh_port or 22,
                            "ssh_private_key": encryption.decrypt(cred.ssh_private_key) if cred.ssh_private_key else None,
                            "snmp_community": cred.snmp_community,
                            "snmp_version": cred.snmp_version or '2c',
                            "snmp_port": cred.snmp_port or 161,
                            "wmi_domain": cred.wmi_domain,
                            "mikrotik_api_port": cred.mikrotik_api_port or 8728,
                        })
                        result["credentials_tested"].append({
                            "id": cred.id,
                            "name": cred.name,
                            "type": cred.credential_type,
                            "source": "device_assigned",
                        })
                        logger.info(f"Auto-detect: Using device-assigned credential '{cred.name}' ({cred.credential_type})")
            finally:
                session.close()
        
        # 2b. Poi aggiungi credenziali di default se richiesto
        if data.use_default_credentials:
            # Ottieni credenziali di default in base alle porte aperte
            creds = customer_service.get_credentials_for_auto_detect(
                customer_id=customer_id,
                open_ports=open_ports
            )
            
            for cred in creds:
                # Skip se già presente (stessa credenziale assegnata)
                if any(c["id"] == cred.id for c in credentials_list):
                    continue
                    
                credentials_list.append({
                    "id": cred.id,
                    "name": cred.name,
                    "type": cred.credential_type,
                    "username": cred.username,
                    "password": cred.password,
                    "ssh_port": getattr(cred, 'ssh_port', 22),
                    "ssh_private_key": getattr(cred, 'ssh_private_key', None),
                    "snmp_community": getattr(cred, 'snmp_community', None),
                    "snmp_version": getattr(cred, 'snmp_version', '2c'),
                    "snmp_port": getattr(cred, 'snmp_port', 161),
                    "wmi_domain": getattr(cred, 'wmi_domain', None),
                    "mikrotik_api_port": getattr(cred, 'mikrotik_api_port', 8728),
                })
                result["credentials_tested"].append({
                    "id": cred.id,
                    "name": cred.name,
                    "type": cred.credential_type,
                    "source": "default",
                })
        
        if not credentials_list:
            logger.warning(f"Auto-detect: No credentials found for {data.address}!")
        else:
            logger.info(f"Auto-detect: Testing {len(credentials_list)} credentials on {data.address}: {[c.get('type') for c in credentials_list]}")
        
        # 3. Esegui probe con credenziali
        # Se abbiamo un agent Docker, usalo per i probe
        if agent_info and agent_info.get("agent_type") == "docker":
            # Probe via agent Docker
            probe_result = await agent_service.auto_probe(
                agent_info=agent_info,
                target=data.address,
                open_ports=open_ports,
                credentials=credentials_list,
            )
            
            # Converti risultato agent in formato compatibile
            if probe_result.get("best_result"):
                scan_result = {
                    "address": data.address,
                    "mac_address": data.mac_address,
                    "device_type": "unknown",
                    "category": None,
                    "identified_by": f"agent_{probe_result['best_result']['type']}",
                    **probe_result["best_result"].get("data", {}),
                }
            else:
                scan_result = {
                    "address": data.address,
                    "mac_address": data.mac_address,
                    "device_type": "unknown",
                    "identified_by": None,
                    "probes": probe_result.get("probes", []),
                }
        else:
            # Probe diretto (senza agent o con agent MikroTik)
            scan_result = await probe_service.auto_identify_device(
                address=data.address,
                mac_address=data.mac_address,
                credentials_list=credentials_list
            )
        
        result["scan_result"] = scan_result
        result["success"] = True
        result["identified"] = scan_result.get("identified_by") is not None
        
        # Log dettagliato dei dati raccolti
        collected_data = {k: v for k, v in scan_result.items() if v and k not in ['probe_results', 'open_ports', 'available_protocols']}
        logger.info(f"Auto-detect complete for {data.address}: identified={result['identified']}, method={scan_result.get('identified_by')}")
        logger.info(f"Auto-detect data collected: {collected_data}")
        
        # 4. Salva i risultati nel device se richiesto
        # Salva anche se non completamente identificato, ma ci sono dati utili
        has_useful_data = (
            scan_result.get("hostname") or 
            scan_result.get("os_family") or 
            scan_result.get("cpu_model") or
            scan_result.get("serial_number") or
            scan_result.get("memory_total_mb") or
            scan_result.get("manufacturer")
        )
        
        if data.save_results and data.device_id and (result["identified"] or has_useful_data):
            from ..models.inventory import InventoryDevice
            import json
            
            session = customer_service._get_session()
            try:
                device = session.query(InventoryDevice).filter(
                    InventoryDevice.id == data.device_id
                ).first()
                
                if device:
                    logger.info(f"Saving probe results for device {data.device_id}: {list(scan_result.keys())}")
                    
                    # PRESERVA credential_id esistente - NON sovrascriverlo!
                    # Se viene usata una credenziale durante il probe e non c'è già una credenziale associata,
                    # oppure se la credenziale usata corrisponde a quella già associata, preservala
                    existing_credential_id = device.credential_id
                    
                    # Se è stata usata una credenziale durante il probe e non c'è già una credenziale associata,
                    # prova ad associare quella usata
                    if result.get("credentials_tested") and not existing_credential_id:
                        # Cerca la credenziale usata tra quelle del cliente
                        # Prova prima con l'ID se disponibile
                        tested_cred = result["credentials_tested"][0]
                        cred_id = tested_cred.get("id")
                        cred_name = tested_cred.get("name")
                        
                        from ..models.database import Credential as CredentialDB
                        cred = None
                        
                        # Cerca per ID se disponibile
                        if cred_id:
                            cred = session.query(CredentialDB).filter(
                                CredentialDB.id == cred_id
                            ).first()
                        
                        # Fallback: cerca per nome se ID non disponibile o non trovato
                        if not cred and cred_name:
                            # Cerca prima tra credenziali del cliente
                            cred = session.query(CredentialDB).filter(
                                CredentialDB.customer_id == device.customer_id,
                                CredentialDB.name == cred_name
                            ).first()
                            
                            # Se non trovata, cerca tra credenziali globali
                            if not cred:
                                cred = session.query(CredentialDB).filter(
                                    CredentialDB.is_global == True,
                                    CredentialDB.name == cred_name
                                ).first()
                        
                        if cred:
                            device.credential_id = cred.id
                            logger.info(f"Auto-detect: Associated credential '{cred_name}' ({cred.id}) to device {data.device_id}")
                        else:
                            logger.warning(f"Auto-detect: Credential '{cred_name}' used but not found in database for device {data.device_id}")
                    
                    # Se c'è già una credential_id, preservala sempre
                    elif existing_credential_id:
                        logger.debug(f"Auto-detect: Preserving existing credential_id {existing_credential_id} for device {data.device_id}")
                    
                    # Hostname
                    hostname = scan_result.get("hostname") or scan_result.get("sysName") or scan_result.get("computer_name")
                    if hostname:
                        device.hostname = hostname
                    
                    # OS
                    if scan_result.get("os_family"):
                        device.os_family = scan_result["os_family"]
                    if scan_result.get("os_version") or scan_result.get("version"):
                        device.os_version = scan_result.get("os_version") or scan_result.get("version")
                    if scan_result.get("os_name"):
                        device.os_family = scan_result["os_name"]
                    
                    # Vendor/Manufacturer
                    manufacturer = (scan_result.get("manufacturer") or scan_result.get("vendor") or 
                                   scan_result.get("system_manufacturer"))
                    if manufacturer:
                        device.manufacturer = manufacturer
                    
                    # Model
                    model = scan_result.get("model") or scan_result.get("system_model")
                    if model:
                        device.model = model
                    
                    # Serial
                    serial = scan_result.get("serial_number") or scan_result.get("serial")
                    if serial:
                        device.serial_number = serial
                    
                    # CPU
                    cpu = scan_result.get("cpu_model") or scan_result.get("cpu")
                    if cpu:
                        device.cpu_model = cpu
                    cores = scan_result.get("cpu_cores") or scan_result.get("cores")
                    if cores:
                        try:
                            device.cpu_cores = int(cores)
                        except (ValueError, TypeError):
                            pass
                    
                    # RAM (vari formati: MB, GB, bytes)
                    ram_mb = scan_result.get("memory_total_mb") or scan_result.get("ram_total_mb")
                    ram_gb = scan_result.get("ram_total_gb") or scan_result.get("memory_total_gb")
                    if ram_gb:
                        try:
                            device.ram_total_gb = float(ram_gb)
                        except (ValueError, TypeError):
                            pass
                    elif ram_mb:
                        try:
                            device.ram_total_gb = float(ram_mb) / 1024
                        except (ValueError, TypeError):
                            pass
                    
                    # Disco
                    disk_gb = scan_result.get("disk_total_gb") or scan_result.get("storage_total_gb")
                    if disk_gb:
                        try:
                            device.disk_total_gb = float(disk_gb)
                        except (ValueError, TypeError):
                            pass
                    disk_free = scan_result.get("disk_free_gb") or scan_result.get("storage_free_gb")
                    if disk_free:
                        try:
                            device.disk_free_gb = float(disk_free)
                        except (ValueError, TypeError):
                            pass
                    
                    # Device Type e Category - Assegnazione automatica in base al risultato probe
                    identified_by = scan_result.get("identified_by") or scan_result.get("probe_type")
                    
                    # Determina device_type in base al metodo di identificazione e ai dati raccolti
                    if not device.device_type or device.device_type == "other":
                        if identified_by:
                            if "wmi" in identified_by.lower() or "windows" in identified_by.lower():
                                device.device_type = "windows"
                            elif "ssh" in identified_by.lower() or "linux" in identified_by.lower():
                                device.device_type = "linux"
                            elif "mikrotik" in identified_by.lower() or "routeros" in identified_by.lower():
                                device.device_type = "mikrotik"
                            elif "snmp" in identified_by.lower():
                                # SNMP può essere router, switch, server, etc.
                                device.device_type = "network"
                        
                        # Fallback: determina da os_family
                        if (not device.device_type or device.device_type == "other") and device.os_family:
                            os_family_lower = device.os_family.lower()
                            if "windows" in os_family_lower:
                                device.device_type = "windows"
                            elif "linux" in os_family_lower or "unix" in os_family_lower:
                                device.device_type = "linux"
                            elif "routeros" in os_family_lower or "mikrotik" in os_family_lower:
                                device.device_type = "mikrotik"
                            elif "ios" in os_family_lower or "nx-os" in os_family_lower:
                                device.device_type = "network"
                    
                    # Determina category in base ai dati raccolti
                    if not device.category:
                        # Categoria basata su porte aperte e tipo dispositivo
                        windows_ports = [3389, 445, 139, 389, 135, 5985, 5986]
                        server_ports = [3306, 5432, 1433, 1521, 27017, 6379]  # Database
                        network_ports = [161, 162, 8728, 8729, 8291]  # SNMP, MikroTik
                        
                        open_port_numbers = [p.get("port") for p in open_ports if p.get("open")]
                        
                        if device.device_type == "windows":
                            # Windows: determina se server o workstation
                            if any(p in open_port_numbers for p in server_ports):
                                device.category = "server"
                            elif 3389 in open_port_numbers:  # RDP
                                device.category = "workstation"
                            else:
                                device.category = "server"  # Default per Windows
                        elif device.device_type == "linux":
                            # Linux: determina se server o workstation
                            if any(p in open_port_numbers for p in server_ports):
                                device.category = "server"
                            elif 22 in open_port_numbers and not any(p in open_port_numbers for p in server_ports):
                                device.category = "workstation"
                            else:
                                device.category = "server"  # Default per Linux
                        elif device.device_type == "mikrotik":
                            device.category = "router"
                        elif device.device_type == "network":
                            # Network device: determina tipo
                            if any(p in open_port_numbers for p in [8728, 8729, 8291]):
                                device.category = "router"
                            elif 161 in open_port_numbers:
                                # SNMP: potrebbe essere switch, router, firewall
                                device.category = "switch"  # Default, può essere cambiato manualmente
                            else:
                                device.category = "network"
                        else:
                            # Tipo sconosciuto: prova a determinare da porte
                            if any(p in open_port_numbers for p in network_ports):
                                device.category = "network"
                            elif any(p in open_port_numbers for p in server_ports):
                                device.category = "server"
                            else:
                                device.category = "other"
                    
                    # Salva anche device_type e category espliciti dal scan_result se presenti
                    if scan_result.get("device_type") and scan_result["device_type"] != "unknown":
                        device.device_type = scan_result["device_type"]
                    if scan_result.get("category"):
                        device.category = scan_result["category"]
                    
                    # Firmware/Version
                    firmware = scan_result.get("firmware_version") or scan_result.get("bios_version")
                    if firmware:
                        device.firmware_version = firmware
                    
                    # Category e device_type
                    if scan_result.get("category"):
                        device.category = scan_result["category"]
                    if scan_result.get("device_type"):
                        device.device_type = scan_result["device_type"]
                    
                    # Domain
                    if scan_result.get("domain"):
                        device.domain = scan_result["domain"]
                    
                    # Metodo di identificazione
                    if scan_result.get("identified_by"):
                        device.identified_by = scan_result["identified_by"]
                    
                    # Credenziale usata
                    if result["credentials_tested"]:
                        device.credential_used = result["credentials_tested"][0].get("type")
                    
                    # Porte aperte
                    if open_ports:
                        device.open_ports = json.dumps(open_ports) if isinstance(open_ports, list) else open_ports
                    
                    # Salva dati extra nel campo custom_fields
                    extra_fields = {}
                    
                    # Dati Windows/Linux dettagliati
                    extra_field_names = [
                        "server_roles", "installed_software", "network_adapters", "local_users",
                        "important_services", "memory_modules", "disks", "antivirus",
                        "domain_role", "is_server", "is_domain_controller", "last_boot",
                        "install_date", "registered_user", "organization", "system_type",
                        "cpu_speed_mhz", "cpu_threads", "cpu_manufacturer", "bios_version", "bios_manufacturer",
                        "shell_users", "docker_containers_running", "lxc_containers", "vms",
                        "virtualization", "timezone", "uptime", "last_login", "kernel",
                        "interface_count", "license_level", "firmware"
                    ]
                    
                    for field in extra_field_names:
                        if field in scan_result and scan_result[field]:
                            extra_fields[field] = scan_result[field]
                    
                    if extra_fields:
                        # Merge con custom_fields esistenti
                        existing = device.custom_fields or {}
                        if isinstance(existing, str):
                            try:
                                existing = json.loads(existing)
                            except:
                                existing = {}
                        existing.update(extra_fields)
                        device.custom_fields = existing
                    
                    # Timestamp
                    from datetime import datetime
                    device.last_scan = datetime.utcnow()
                    
                    session.commit()
                    logger.info(f"Auto-detect: Saved results to device {data.device_id} - hostname={device.hostname}, os={device.os_family}, cpu={device.cpu_model}")
                    result["saved"] = True
            except Exception as save_err:
                logger.error(f"Failed to save auto-detect results: {save_err}", exc_info=True)
                session.rollback()
                result["save_error"] = str(save_err)
            finally:
                session.close()
        
    except Exception as e:
        logger.error(f"Auto-detect failed for {data.address}: {e}")
        result["error"] = str(e)
    
    return result


@router.post("/auto-detect-batch")
async def auto_detect_batch(
    data: BulkAutoDetectRequest,
    customer_id: str = Query(...),
):
    """
    Esegue auto-detect su più dispositivi in parallelo.
    """
    import asyncio
    
    results = []
    
    async def detect_one(device: AutoDetectRequest):
        return await auto_detect_device(device, customer_id)
    
    # Esegui in parallelo (max 5 alla volta per evitare sovraccarico)
    semaphore = asyncio.Semaphore(5)
    
    async def detect_with_semaphore(device):
        async with semaphore:
            return await detect_one(device)
    
    tasks = [detect_with_semaphore(d) for d in data.devices]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Processa risultati
    processed = []
    success_count = 0
    identified_count = 0
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed.append({
                "address": data.devices[i].address,
                "success": False,
                "error": str(result),
            })
        else:
            processed.append(result)
            if result.get("success"):
                success_count += 1
            if result.get("identified"):
                identified_count += 1
    
    return {
        "success": True,
        "total": len(data.devices),
        "scanned": success_count,
        "identified": identified_count,
        "results": processed,
    }


@router.post("/probe-devices")
async def probe_multiple_devices(
    data: BulkProbeRequest,
    customer_id: str = Query(...),
):
    """
    Esegue probe su più dispositivi in parallelo.
    """
    from ..services.device_probe_service import get_device_probe_service
    from ..services.customer_service import get_customer_service
    import asyncio
    
    probe_service = get_device_probe_service()
    customer_service = get_customer_service()
    
    # Recupera credenziali comuni
    credentials_list = []
    credential_ids = data.credential_ids or []
    
    if credential_ids:
        for cred_id in credential_ids:
            cred = customer_service.get_credential(cred_id, include_secrets=True)
            if cred:
                credentials_list.append({
                    "id": cred.id,
                    "name": cred.name,
                    "type": cred.credential_type,
                    "username": cred.username,
                    "password": cred.password,
                    "ssh_port": getattr(cred, 'ssh_port', 22),
                    "ssh_private_key": getattr(cred, 'ssh_private_key', None),
                    "snmp_community": getattr(cred, 'snmp_community', None),
                    "snmp_version": getattr(cred, 'snmp_version', '2c'),
                    "snmp_port": getattr(cred, 'snmp_port', 161),
                    "wmi_domain": getattr(cred, 'wmi_domain', None),
                    "mikrotik_api_port": getattr(cred, 'mikrotik_api_port', 8728),
                })
    
    # Probe paralleli
    async def probe_one(device):
        device_creds = credentials_list.copy()
        if device.credential_ids:
            # Aggiungi credenziali specifiche per questo device
            for cred_id in device.credential_ids:
                if cred_id not in credential_ids:
                    cred = customer_service.get_credential(cred_id, include_secrets=True)
                    if cred:
                        device_creds.append({
                            "id": cred.id,
                            "name": cred.name,
                            "type": cred.credential_type,
                            "username": cred.username,
                            "password": cred.password,
                            "ssh_port": getattr(cred, 'ssh_port', 22),
                            "snmp_community": getattr(cred, 'snmp_community', None),
                        })
        
        return await probe_service.auto_identify_device(
            address=device.address,
            mac_address=device.mac_address,
            credentials_list=device_creds
        )
    
    tasks = [probe_one(d) for d in data.devices]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Formatta risultati
    formatted = []
    for device, result in zip(data.devices, results):
        if isinstance(result, Exception):
            formatted.append({
                "address": device.address,
                "mac_address": device.mac_address,
                "error": str(result),
            })
        else:
            formatted.append(result)
    
    return {
        "success": True,
        "results": formatted,
        "probed": len([r for r in formatted if not r.get("error")]),
        "errors": len([r for r in formatted if r.get("error")]),
    }


@router.get("/detect-protocols/{address}")
async def detect_protocols(address: str):
    """Rileva quali protocolli sono disponibili su un host"""
    from ..services.device_probe_service import get_device_probe_service

    probe_service = get_device_probe_service()
    protocols = await probe_service.detect_available_protocols(address)

    return {
        "success": True,
        "address": address,
        "protocols": protocols,
    }


@router.get("/scan-ports/{address}")
async def scan_ports_for_address(address: str):
    """
    Scansiona le porte TCP/UDP di un indirizzo IP.
    Restituisce l'elenco delle porte aperte con relativi servizi.
    """
    from ..services.device_probe_service import get_device_probe_service

    probe_service = get_device_probe_service()
    
    try:
        open_ports = await probe_service.scan_services(address)
        
        # Filtra solo porte aperte
        active_ports = [p for p in open_ports if p.get("open")]
        
        return {
            "success": True,
            "address": address,
            "open_ports": open_ports,
            "active_count": len(active_ports),
            "services": [p["service"] for p in active_ports if p.get("service")],
        }
    except Exception as e:
        logger.error(f"Error scanning ports for {address}: {e}")
        return {
            "success": False,
            "address": address,
            "error": str(e),
            "open_ports": [],
        }


@router.get("/suggest-credential-type/{address}")
async def suggest_credential_type(address: str):
    """
    Suggerisce il tipo di credenziali da usare in base alle porte aperte.

    Regole:
    - Se risponde a 389 (LDAP), 445 (SMB), o 3389 (RDP) -> wmi (Windows)
    - Se risponde a 161 (SNMP) -> snmp
    - Se risponde a 22 (SSH) ma non SNMP e non WMI -> ssh (Linux)
    - Se risponde a 8728 (RouterOS API) -> mikrotik
    """
    from ..services.device_probe_service import get_device_probe_service

    probe_service = get_device_probe_service()
    suggested_type = await probe_service.suggest_credential_type(address)

    return {
        "success": True,
        "address": address,
        "suggested_type": suggested_type,
    }


@router.get("/reverse-dns/{address}")
async def reverse_dns_lookup(
    address: str,
    dns_server: Optional[str] = Query(None, description="DNS server da usare (opzionale)"),
):
    """
    Esegue reverse DNS lookup per un indirizzo IP.
    Supporta fallback DNS server se quello specificato non risponde.
    """
    from ..services.device_probe_service import get_device_probe_service
    
    probe_service = get_device_probe_service()
    
    # Usa il nuovo metodo con fallback
    result = await probe_service.reverse_dns_lookup(
        address=address,
        dns_server=dns_server,
        fallback_dns=["8.8.8.8", "1.1.1.1"],
        timeout=5
    )
    
    return result
async def reverse_dns_lookup(address: str):
    """Esegue reverse DNS lookup per ottenere hostname da IP"""
    from ..services.device_probe_service import get_device_probe_service

    probe_service = get_device_probe_service()
    hostname = await probe_service.reverse_dns_lookup(address)

    return {
        "success": True,
        "address": address,
        "hostname": hostname,
    }


# ==========================================
# INVENTORY CRUD
# ==========================================

@router.get("/devices/monitored")
async def list_monitored_devices(
    customer_id: Optional[str] = Query(None, description="Filtra per cliente"),
    monitoring_type: Optional[str] = Query(None, description="Filtra per tipo monitoraggio (none, icmp, tcp, netwatch, agent)"),
    monitored_only: bool = Query(True, description="Solo device con monitoraggio attivo"),
    limit: int = Query(500, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """
    Lista device con monitoraggio configurato o da configurare.
    """
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        query = session.query(InventoryDevice).filter(InventoryDevice.active == True)
        
        if customer_id:
            query = query.filter(InventoryDevice.customer_id == customer_id)
        
        if monitored_only:
            # Solo device con monitoraggio attivo (monitored=True) o configurato (monitoring_type != "none")
            query = query.filter(
                (InventoryDevice.monitored == True) | 
                (InventoryDevice.monitoring_type != "none")
            )
        
        if monitoring_type:
            query = query.filter(InventoryDevice.monitoring_type == monitoring_type)
        
        total = query.count()
        devices = query.order_by(InventoryDevice.name).offset(offset).limit(limit).all()
        
        # Converti in dict per JSON
        devices_list = []
        for dev in devices:
            devices_list.append({
                "id": dev.id,
                "customer_id": dev.customer_id,
                "name": dev.name,
                "hostname": dev.hostname,
                "primary_ip": dev.primary_ip,
                "primary_mac": dev.primary_mac,
                "device_type": dev.device_type,
                "category": dev.category,
                "manufacturer": dev.manufacturer,
                "status": dev.status,
                "monitored": dev.monitored,
                "monitoring_type": dev.monitoring_type or "none",
                "monitoring_port": dev.monitoring_port,
                "monitoring_agent_id": dev.monitoring_agent_id,
                "netwatch_id": dev.netwatch_id,
                "last_check": dev.last_check.isoformat() if dev.last_check else None,
                "last_seen": dev.last_seen.isoformat() if dev.last_seen else None,
            })
        
        return {
            "total": total,
            "devices": devices_list,
            "offset": offset,
            "limit": limit,
        }
    finally:
        session.close()


@router.get("/devices")
async def list_inventory_devices(
    customer_id: Optional[str] = Query(None),
    device_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Lista dispositivi inventariati"""
    from ..models.database import init_db, get_session, Credential
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        query = session.query(InventoryDevice)
        
        if customer_id:
            query = query.filter(InventoryDevice.customer_id == customer_id)
        if device_type:
            query = query.filter(InventoryDevice.device_type == device_type)
        if status:
            query = query.filter(InventoryDevice.status == status)
        
        total = query.count()
        devices = query.order_by(InventoryDevice.name).offset(offset).limit(limit).all()
        
        # Prepara dict delle credenziali per lookup veloce
        cred_ids = [d.credential_id for d in devices if d.credential_id]
        credentials_map = {}
        if cred_ids:
            creds = session.query(Credential).filter(Credential.id.in_(cred_ids)).all()
            credentials_map = {c.id: {"name": c.name, "type": c.credential_type} for c in creds}
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "devices": [
                {
                    "id": d.id,
                    "customer_id": d.customer_id,
                    "name": d.name,
                    "hostname": d.hostname,
                    "domain": d.domain,
                    "device_type": d.device_type,
                    "category": d.category,
                    "manufacturer": d.manufacturer,
                    "model": d.model,
                    "primary_ip": d.primary_ip,
                    "primary_mac": d.primary_mac,
                    "mac_address": d.mac_address or d.primary_mac,  # Usa mac_address se disponibile, altrimenti primary_mac
                    "status": d.status,
                    "os_family": d.os_family,
                    "os_version": d.os_version,
                    "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                    "dude_device_id": d.dude_device_id,
                    "tags": d.tags,
                    "credential_id": d.credential_id,
                    "credential_name": credentials_map.get(d.credential_id, {}).get("name") if d.credential_id else None,
                    "credential_type": credentials_map.get(d.credential_id, {}).get("type") if d.credential_id else None,
                    "open_ports": d.open_ports,  # Porte aperte
                    "identified_by": d.identified_by,  # Metodo identificazione
                    "serial_number": d.serial_number,
                    "cpu_model": d.cpu_model,
                    "cpu_cores": d.cpu_cores,
                    "ram_total_gb": d.ram_total_gb,
                }
                for d in devices
            ]
        }
    finally:
        session.close()


@router.get("/devices/{device_id}")
async def get_inventory_device(device_id: str):
    """Dettagli singolo dispositivo"""
    from ..models.database import init_db, get_session
    from ..models.inventory import (
        InventoryDevice, NetworkInterface, DiskInfo, 
        InstalledSoftware, ServiceInfo,
        WindowsDetails, LinuxDetails, MikroTikDetails, NetworkDeviceDetails
    )
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Dispositivo non trovato")
        
        # Base info
        result = {
            "id": device.id,
            "customer_id": device.customer_id,
            "name": device.name,
            "hostname": device.hostname,
            "domain": device.domain,
            "device_type": device.device_type,
            "category": device.category,
            "manufacturer": device.manufacturer,
            "model": device.model,
            "serial_number": device.serial_number,
            "asset_tag": device.asset_tag,
            "primary_ip": device.primary_ip,
            "primary_mac": device.primary_mac,
            "mac_address": device.mac_address or device.primary_mac,
            "site_name": device.site_name,
            "location": device.location,
            "status": device.status,
            "monitor_source": device.monitor_source,
            "dude_device_id": device.dude_device_id,
            "last_seen": device.last_seen.isoformat() if device.last_seen else None,
            "last_scan": device.last_scan.isoformat() if device.last_scan else None,
            "os_family": device.os_family,
            "os_version": device.os_version,
            "os_build": device.os_build,
            "architecture": device.architecture,
            "cpu_model": device.cpu_model,
            "cpu_cores": device.cpu_cores,
            "cpu_threads": device.cpu_threads,
            "ram_total_gb": device.ram_total_gb,
            "description": device.description,
            "notes": device.notes,
            "tags": device.tags,
            "custom_fields": device.custom_fields,
            "open_ports": device.open_ports,
            "identified_by": device.identified_by,
            "credential_used": device.credential_used,
            "credential_id": device.credential_id,
            "created_at": device.created_at.isoformat() if device.created_at else None,
            "updated_at": device.updated_at.isoformat() if device.updated_at else None,
        }
        
        # Network interfaces
        result["network_interfaces"] = [
            {
                "name": n.name,
                "mac_address": n.mac_address,
                "ip_addresses": n.ip_addresses,
                "speed_mbps": n.speed_mbps,
                "admin_status": n.admin_status,
            }
            for n in device.network_interfaces
        ]
        
        # Disks
        result["disks"] = [
            {
                "name": d.name,
                "mount_point": d.mount_point,
                "size_gb": d.size_gb,
                "used_gb": d.used_gb,
                "filesystem": d.filesystem,
            }
            for d in device.disks
        ]
        
        # Type-specific details
        if device.device_type == "windows" and device.windows_details:
            wd = device.windows_details
            result["windows_details"] = {
                "edition": wd.edition,
                "domain_role": wd.domain_role,
                "domain_name": wd.domain_name,
                "last_update_check": wd.last_update_check.isoformat() if wd.last_update_check else None,
                "antivirus_name": wd.antivirus_name,
                "antivirus_status": wd.antivirus_status,
            }
        
        if device.device_type == "linux" and device.linux_details:
            ld = device.linux_details
            result["linux_details"] = {
                "distro_name": ld.distro_name,
                "distro_version": ld.distro_version,
                "kernel_version": ld.kernel_version,
                "docker_installed": ld.docker_installed,
                "containers_running": ld.containers_running,
            }
        
        if device.device_type == "mikrotik" and device.mikrotik_details:
            md = device.mikrotik_details
            result["mikrotik_details"] = {
                "routeros_version": md.routeros_version,
                "board_name": md.board_name,
                "license_level": md.license_level,
                "cpu_load": md.cpu_load,
                "memory_free_mb": md.memory_free_mb,
                "uptime": md.uptime,
            }
        
        return result
        
    finally:
        session.close()


@router.post("/devices")
async def create_inventory_device(
    customer_id: str,
    device: DeviceImport,
):
    """Crea nuovo dispositivo inventariato"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        # Determina nome
        name = device.name or device.identity or device.address or "Unknown"
        
        # Controlla duplicati per IP
        if device.address:
            existing = session.query(InventoryDevice).filter(
                InventoryDevice.customer_id == customer_id,
                InventoryDevice.primary_ip == device.address
            ).first()
            
            if existing:
                return {
                    "success": False,
                    "error": "duplicate",
                    "message": f"Dispositivo con IP {device.address} già presente",
                    "existing_id": existing.id,
                }
        
        # Crea dispositivo
        new_device = InventoryDevice(
            customer_id=customer_id,
            name=name,
            hostname=device.identity,
            device_type=device.device_type,
            category=device.category,
            primary_ip=device.address,
            primary_mac=device.mac_address,
            mac_address=device.mac_address,  # Alias per retrocompatibilità
            manufacturer=device.platform if device.platform else None,
            model=device.board,
            os_family=device.os_family if hasattr(device, 'os_family') else None,
            os_version=device.os_version if hasattr(device, 'os_version') else None,
            identified_by=device.identified_by if hasattr(device, 'identified_by') else None,
            credential_used=device.credential_used if hasattr(device, 'credential_used') else None,
            open_ports=device.open_ports if hasattr(device, 'open_ports') else None,
            status="unknown",
            last_seen=datetime.now(),
        )
        
        session.add(new_device)
        session.commit()
        
        return {
            "success": True,
            "device_id": new_device.id,
            "name": new_device.name,
            "message": f"Dispositivo {name} creato",
        }
        
    finally:
        session.close()


@router.post("/devices/bulk-import")
async def bulk_import_devices(
    customer_id: str,
    data: BulkImport,
    skip_duplicates: bool = Query(True),
):
    """Importa più dispositivi nell'inventario"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        # Ottieni IP esistenti
        existing_ips = set()
        if skip_duplicates:
            existing = session.query(InventoryDevice.primary_ip).filter(
                InventoryDevice.customer_id == customer_id,
                InventoryDevice.primary_ip.isnot(None)
            ).all()
            existing_ips = {e[0] for e in existing}
        
        imported = 0
        skipped = 0
        skipped_no_mac = 0
        errors = []
        
        for device in data.devices:
            try:
                # MAC address è opzionale - non bloccare se mancante
                has_mac = device.mac_address and device.mac_address.strip() != ''
                if not has_mac:
                    skipped_no_mac += 1  # Conta ma non blocca
                
                # Skip se IP già presente
                if device.address and device.address in existing_ips:
                    skipped += 1
                    continue
                
                # Determina il nome: priorità a name, poi hostname, poi identity, poi address
                name = device.name or device.hostname or device.identity or device.address or "Unknown"
                
                # Determina hostname: priorità a hostname, poi identity
                hostname = device.hostname or device.identity or None

                new_device = InventoryDevice(
                    customer_id=customer_id,
                    name=name,
                    hostname=hostname,
                    device_type=device.device_type,
                    category=device.category,
                    primary_ip=device.address,
                    primary_mac=device.mac_address,
                    mac_address=device.mac_address,  # Alias per retrocompatibilità
                    manufacturer=device.platform if device.platform else None,
                    model=device.board,
                    os_family=device.os_family if hasattr(device, 'os_family') else None,
                    os_version=device.os_version if hasattr(device, 'os_version') else None,
                    identified_by=device.identified_by if hasattr(device, 'identified_by') else None,
                    credential_used=device.credential_used if hasattr(device, 'credential_used') else None,
                    open_ports=device.open_ports if hasattr(device, 'open_ports') else None,
                    status="unknown",
                    last_seen=datetime.now(),
                )
                
                logger.debug(f"Importing device: {name} ({device.address}) - hostname: {hostname}, ports: {len(device.open_ports or [])}")
                
                session.add(new_device)
                imported += 1
                
                if device.address:
                    existing_ips.add(device.address)
                    
            except Exception as e:
                errors.append(f"{device.address}: {str(e)}")
        
        session.commit()
        
        return {
            "success": True,
            "imported": imported,
            "skipped": skipped,
            "without_mac": skipped_no_mac,  # Info only, not skipped
            "errors": errors,
            "message": f"Importati {imported} dispositivi ({skipped_no_mac} senza MAC), {skipped} duplicati",
        }
        
    finally:
        session.close()


@router.delete("/devices/clear")
async def clear_inventory(customer_id: Optional[str] = Query(None)):
    """Elimina tutti i dispositivi dall'inventario di un cliente"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings

    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)

    try:
        # Costruisci query
        query = session.query(InventoryDevice)

        if customer_id:
            query = query.filter(InventoryDevice.customer_id == customer_id)
        else:
            raise HTTPException(status_code=400, detail="customer_id è richiesto")

        # Conta e elimina
        count = query.count()
        query.delete(synchronize_session=False)
        session.commit()

        logger.info(f"Cleared {count} devices from inventory for customer {customer_id}")

        return {
            "success": True,
            "deleted": count,
            "message": f"Eliminati {count} dispositivi"
        }

    except Exception as e:
        session.rollback()
        logger.error(f"Error clearing inventory: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ==========================================
# PORT SCANNING
# ==========================================

@router.post("/devices/{device_id}/scan-ports")
async def scan_device_ports(device_id: str):
    """
    Riesegue la scansione delle porte per un dispositivo inventariato.
    Aggiorna il campo open_ports nel database.
    """
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..services.device_probe_service import get_device_probe_service
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Dispositivo non trovato")
        
        if not device.primary_ip:
            raise HTTPException(status_code=400, detail="Dispositivo senza IP")
        
        # Esegui scansione porte
        probe_service = get_device_probe_service()
        open_ports = await probe_service.scan_services(device.primary_ip)
        
        # Aggiorna dispositivo
        device.open_ports = open_ports
        device.last_seen = datetime.now()
        session.commit()
        
        logger.info(f"Port scan completed for device {device_id} ({device.primary_ip}): {len([p for p in open_ports if p.get('open')])} ports open")
        
        return {
            "success": True,
            "device_id": device_id,
            "address": device.primary_ip,
            "open_ports": open_ports,
            "open_count": len([p for p in open_ports if p.get('open')]),
            "message": f"Scansione completata: {len([p for p in open_ports if p.get('open')])} porte aperte"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Error scanning ports for device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


class BatchPortScanRequest(BaseModel):
    """Schema per scansione porte batch"""
    device_ids: List[str]


@router.post("/devices/batch-scan-ports")
async def batch_scan_device_ports(
    customer_id: Optional[str] = Query(None),
    data: Optional[BatchPortScanRequest] = None,
):
    """
    Riesegue la scansione delle porte per più dispositivi inventariati.
    Se customer_id è specificato, scansiona tutti i device del cliente.
    Se data.device_ids è specificato, scansiona solo quei device.
    """
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..services.device_probe_service import get_device_probe_service
    from ..config import get_settings
    import asyncio
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        # Determina quali device scansionare
        query = session.query(InventoryDevice).filter(
            InventoryDevice.primary_ip.isnot(None)
        )
        
        if customer_id:
            query = query.filter(InventoryDevice.customer_id == customer_id)
        
        if data and data.device_ids:
            query = query.filter(InventoryDevice.id.in_(data.device_ids))
        
        devices = query.all()
        
        if not devices:
            return {
                "success": True,
                "scanned": 0,
                "errors": [],
                "message": "Nessun dispositivo da scansionare"
            }
        
        # Esegui scansione in parallelo
        probe_service = get_device_probe_service()
        
        async def scan_one_device(device):
            """Scansiona un singolo device"""
            try:
                open_ports = await probe_service.scan_services(device.primary_ip)
                device.open_ports = open_ports
                device.last_seen = datetime.now()
                return {
                    "device_id": device.id,
                    "address": device.primary_ip,
                    "success": True,
                    "open_count": len([p for p in open_ports if p.get('open')]),
                }
            except Exception as e:
                logger.error(f"Error scanning {device.primary_ip}: {e}")
                return {
                    "device_id": device.id,
                    "address": device.primary_ip,
                    "success": False,
                    "error": str(e),
                }
        
        # Esegui scansioni in parallelo (max 10 alla volta)
        tasks = [scan_one_device(d) for d in devices]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Processa risultati
        scanned = 0
        errors = []
        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
            elif result.get("success"):
                scanned += 1
            else:
                errors.append(f"{result.get('address', 'unknown')}: {result.get('error', 'unknown error')}")
        
        session.commit()
        
        logger.info(f"Batch port scan completed: {scanned}/{len(devices)} devices scanned")
        
        return {
            "success": True,
            "scanned": scanned,
            "total": len(devices),
            "errors": errors,
            "message": f"Scansione completata: {scanned}/{len(devices)} dispositivi"
        }
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error in batch port scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/devices/{device_id}")
async def delete_inventory_device(device_id: str):
    """Elimina dispositivo dall'inventario"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Dispositivo non trovato")
        
        name = device.name
        session.delete(device)
        session.commit()
        
        return {
            "success": True,
            "message": f"Dispositivo {name} eliminato",
        }
        
    finally:
        session.close()


@router.put("/devices/{device_id}")
async def update_inventory_device(device_id: str, updates: dict):
    """Aggiorna dispositivo"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Dispositivo non trovato")
        
        # PRESERVA credential_id esistente se non viene esplicitamente passato nell'update
        existing_credential_id = device.credential_id
        
        # Campi aggiornabili
        allowed_fields = [
            'name', 'hostname', 'device_type', 'category', 'manufacturer',
            'model', 'serial_number', 'asset_tag', 'site_name', 'location',
            'description', 'notes', 'tags', 'status', 'credential_id',
            'os_family', 'os_version', 'domain'
        ]
        
        for field, value in updates.items():
            if field in allowed_fields:
                # Protezione speciale per credential_id: preserva se non viene esplicitamente passato o se viene passato None
                if field == 'credential_id':
                    # Permetti solo se viene esplicitamente passato un valore non-None
                    # Se viene passato None o non viene passato, preserva quello esistente
                    if value is not None:
                        setattr(device, field, value)
                    # Se value è None, non fare nulla (preserva esistente)
                else:
                    setattr(device, field, value)
        
        # Assicurati che credential_id non venga perso accidentalmente
        if device.credential_id != existing_credential_id and 'credential_id' not in updates:
            logger.warning(f"Preserving existing credential_id {existing_credential_id} for device {device_id} (was about to be lost)")
            device.credential_id = existing_credential_id
        
        session.commit()
        
        return {
            "success": True,
            "message": f"Dispositivo {device.name} aggiornato",
        }
        
    finally:
        session.close()


@router.post("/devices/{device_id}/monitoring")
async def configure_device_monitoring(device_id: str, config: dict):
    """
    Configura il monitoraggio per un dispositivo.
    
    monitoring_type: none, icmp, tcp, mikrotik, agent
    monitoring_port: porta TCP (richiesto se monitoring_type == "tcp")
    monitoring_agent_id: ID agent per mikrotik/agent (opzionale)
    interval: intervallo check in secondi (opzionale, default: 30)
    """
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    from ..services.customer_service import get_customer_service
    from ..services.mikrotik_service import get_mikrotik_service
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Dispositivo non trovato")
        
        monitoring_type = config.get("monitoring_type", "none")
        monitoring_port = config.get("monitoring_port")
        monitoring_agent_id = config.get("monitoring_agent_id")
        interval = config.get("interval", 30)
        customer_id = config.get("customer_id", device.customer_id)
        
        # Se customer_id è fornito nel config e il device non ne ha uno, o se è diverso, aggiornalo
        if customer_id and (not device.customer_id or device.customer_id != customer_id):
            device.customer_id = customer_id
            logger.info(f"Aggiornato customer_id per device {device_id}: {customer_id}")
        
        # Validazione
        if monitoring_type == "tcp" and not monitoring_port:
            raise HTTPException(status_code=400, detail="monitoring_port è richiesto per monitoraggio TCP")
        
        # Risultato operazione
        result = {
            "success": True,
            "device_id": device_id,
            "device_ip": device.primary_ip,
            "monitoring_type": monitoring_type,
            "monitoring_port": monitoring_port,
            "monitoring_agent_id": monitoring_agent_id,
            "netwatch_configured": False,
            "agent_configured": False,
        }
        
        # Ottieni servizio clienti per sonde
        customer_service = get_customer_service()
        
        # Se disabilito il monitoraggio, rimuovi eventuali configurazioni
        if monitoring_type == "none":
            # Rimuovi Netwatch se configurato
            if device.netwatch_id and device.monitoring_agent_id:
                try:
                    agent = customer_service.get_agent(device.monitoring_agent_id, include_password=True)
                    if agent and agent.agent_type == "mikrotik":
                        mikrotik_service = get_mikrotik_service()
                        mikrotik_service.remove_netwatch(
                            address=agent.address,
                            port=agent.port or 8728,
                            username=agent.username or "admin",
                            password=agent.password or "",
                            netwatch_id=device.netwatch_id,
                            use_ssl=agent.use_ssl or False,
                        )
                        logger.info(f"Rimosso Netwatch {device.netwatch_id} da {agent.name}")
                except Exception as e:
                    logger.warning(f"Errore rimozione Netwatch: {e}")
            
            device.monitored = False
            device.monitoring_type = "none"
            device.monitoring_agent_id = None
            device.netwatch_id = None
            device.monitoring_port = None
            
        elif monitoring_type == "icmp":
            # Monitoraggio ICMP (Ping)
            device.monitored = True
            device.monitoring_type = "icmp"
            device.monitoring_port = None  # ICMP non usa porta
            # Se c'è un agent specificato, usalo, altrimenti None (monitoraggio locale)
            if monitoring_agent_id:
                device.monitoring_agent_id = monitoring_agent_id
            else:
                device.monitoring_agent_id = None
            device.netwatch_id = None
            logger.info(f"ICMP monitoring configurato per {device.primary_ip}")
            
        elif monitoring_type == "tcp":
            # Monitoraggio TCP (Porta)
            if not monitoring_port:
                raise HTTPException(status_code=400, detail="monitoring_port è richiesto per monitoraggio TCP")
            
            device.monitored = True
            device.monitoring_type = "tcp"
            device.monitoring_port = monitoring_port
            # Se c'è un agent specificato, usalo, altrimenti None (monitoraggio locale)
            if monitoring_agent_id:
                device.monitoring_agent_id = monitoring_agent_id
            else:
                device.monitoring_agent_id = None
            device.netwatch_id = None
            logger.info(f"TCP monitoring configurato per {device.primary_ip}:{monitoring_port}")
            
        elif monitoring_type == "netwatch":
            # Configura Netwatch su MikroTik
            # Cerca una sonda MikroTik per questo cliente
            agents = customer_service.list_agents(customer_id=customer_id, active_only=True)
            mikrotik_agent = None
            for ag in agents:
                if ag.agent_type == "mikrotik":
                    mikrotik_agent = customer_service.get_agent(ag.id, include_password=True)
                    break
            
            if not mikrotik_agent:
                return {
                    "success": False,
                    "error": "Nessuna sonda MikroTik configurata per questo cliente"
                }
            
            mikrotik_service = get_mikrotik_service()
            
            try:
                # Aggiungi o aggiorna Netwatch
                netwatch_result = mikrotik_service.add_netwatch(
                    address=mikrotik_agent.address,
                    port=mikrotik_agent.port or 8728,
                    username=mikrotik_agent.username or "admin",
                    password=mikrotik_agent.password or "",
                    target_ip=device.primary_ip,
                    target_name=device.name or device.hostname or device.primary_ip,
                    interval="30s",
                    use_ssl=mikrotik_agent.use_ssl or False,
                )
                
                if netwatch_result.get("success"):
                    device.monitored = True
                    device.monitoring_type = "mikrotik"
                    device.monitoring_port = None  # Netwatch usa ICMP di default
                    device.monitoring_agent_id = mikrotik_agent.id
                    device.netwatch_id = netwatch_result.get("netwatch_id")
                    result["netwatch_configured"] = True
                    result["mikrotik_name"] = mikrotik_agent.name
                    logger.info(f"Netwatch configurato per {device.primary_ip} su {mikrotik_agent.name}")
                else:
                    result["success"] = False
                    result["error"] = netwatch_result.get("error", "Errore configurazione Netwatch")
                    
            except Exception as e:
                logger.error(f"Errore configurazione Netwatch: {e}")
                result["success"] = False
                result["error"] = str(e)
                
        elif monitoring_type == "agent":
            # Configura monitoring via Docker agent
            agents = customer_service.list_agents(customer_id=customer_id, active_only=True)
            docker_agent = None
            for ag in agents:
                if ag.agent_type == "docker":
                    docker_agent = customer_service.get_agent(ag.id, include_password=True)
                    break
            
            if not docker_agent:
                # Fallback a MikroTik se non c'è Docker
                for ag in agents:
                    if ag.agent_type == "mikrotik":
                        docker_agent = customer_service.get_agent(ag.id, include_password=True)
                        break
            
            if not docker_agent:
                return {
                    "success": False,
                    "error": "Nessuna sonda configurata per questo cliente"
                }
            
            device.monitored = True
            device.monitoring_type = "agent"
            device.monitoring_agent_id = docker_agent.id
            # Per agent monitoring, monitoring_port può essere specificato per TCP check
            if monitoring_port:
                device.monitoring_port = monitoring_port
            else:
                device.monitoring_port = None  # Default ICMP per agent
            device.netwatch_id = None
            result["agent_configured"] = True
            result["agent_name"] = docker_agent.name
            logger.info(f"Agent monitoring configurato per {device.primary_ip} via {docker_agent.name}")
        else:
            # Tipo non riconosciuto
            raise HTTPException(status_code=400, detail=f"Tipo monitoraggio non valido: {monitoring_type}")
        
        # Aggiorna timestamp
        from datetime import datetime
        device.last_check = None  # Reset last_check, sarà aggiornato dal monitoring service
        device.last_seen = datetime.utcnow() if device.last_seen else None
        
        session.commit()
        logger.info(f"Monitoring config salvato: device={device_id}, type={monitoring_type}, monitored={device.monitored}, port={device.monitoring_port}, agent_id={device.monitoring_agent_id}")
        return result
        
    except Exception as e:
        session.rollback()
        logger.error(f"Errore configurazione monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        session.close()


@router.post("/devices/{device_id}/identify")
async def identify_inventory_device(
    device_id: str,
    credential_ids: List[str] = Query(default=[]),
):
    """
    Ri-identifica un dispositivo esistente e aggiorna automaticamente le info.
    """
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    from ..services.device_probe_service import get_device_probe_service
    from ..services.customer_service import get_customer_service
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Dispositivo non trovato")
        
        # Prepara credenziali
        credentials_list = []
        if credential_ids:
            customer_service = get_customer_service()
            for cred_id in credential_ids:
                cred = customer_service.get_credential(cred_id, include_secrets=True)
                if cred:
                    credentials_list.append({
                        "id": cred.id,
                        "name": cred.name,
                        "type": cred.credential_type,
                        "username": cred.username,
                        "password": cred.password,
                        "ssh_port": getattr(cred, 'ssh_port', 22),
                        "snmp_community": getattr(cred, 'snmp_community', None),
                        "snmp_version": getattr(cred, 'snmp_version', '2c'),
                        "snmp_port": getattr(cred, 'snmp_port', 161),
                        "wmi_domain": getattr(cred, 'wmi_domain', None),
                        "mikrotik_api_port": getattr(cred, 'mikrotik_api_port', 8728),
                    })
        
        # Esegui probe
        probe_service = get_device_probe_service()
        result = await probe_service.auto_identify_device(
            address=device.primary_ip,
            mac_address=device.primary_mac,
            credentials_list=credentials_list
        )
        
        # PRESERVA credential_id esistente - NON sovrascriverlo!
        # Il credential_id viene gestito solo tramite l'interfaccia utente o durante la creazione del device
        existing_credential_id = device.credential_id
        
        # Aggiorna dispositivo con info identificate
        updates_applied = []
        
        if result.get("hostname") and not device.hostname:
            device.hostname = result["hostname"]
            updates_applied.append("hostname")
        
        if result.get("device_type") and result["device_type"] != "other":
            device.device_type = result["device_type"]
            updates_applied.append("device_type")
        
        if result.get("category"):
            device.category = result["category"]
            updates_applied.append("category")
        
        if result.get("os_family"):
            device.os_family = result["os_family"]
            updates_applied.append("os_family")
        
        if result.get("model"):
            device.model = result["model"]
            updates_applied.append("model")
        
        if result.get("vendor"):
            device.manufacturer = result["vendor"]
            updates_applied.append("manufacturer")
        
        # Hardware Info
        if result.get("cpu_model"):
            device.cpu_model = result["cpu_model"]
            updates_applied.append("cpu_model")
            
        if result.get("cpu_cores"):
            device.cpu_cores = result["cpu_cores"]
            updates_applied.append("cpu_cores")
            
        if result.get("memory_total_mb"):
            device.ram_total_gb = round(result["memory_total_mb"] / 1024, 2)
            updates_applied.append("ram_total_gb")
            
        if result.get("serial_number"):
            device.serial_number = result["serial_number"]
            updates_applied.append("serial_number")
            
        # OS Version - può venire da "version" (WMI) o altri campi
        if result.get("version") and not device.os_version:
            device.os_version = result["version"]
            updates_applied.append("os_version")
        elif result.get("os_version") and not device.os_version:
            device.os_version = result["os_version"]
            updates_applied.append("os_version")

        # Disk info
        if result.get("disk_total_gb"):
            # Salva in custom_fields o in un campo specifico se disponibile
            if not device.custom_fields:
                device.custom_fields = {}
            device.custom_fields["disk_total_gb"] = result["disk_total_gb"]
            device.custom_fields["disk_free_gb"] = result.get("disk_free_gb")
            updates_applied.append("disk_info")
            
        # Manufacturer - può venire da "manufacturer" (WMI) o "vendor" (MAC)
        if result.get("manufacturer") and not device.manufacturer:
            device.manufacturer = result["manufacturer"]
            updates_applied.append("manufacturer")
            
        # Domain - può venire direttamente da WMI
        if result.get("domain") and not device.domain:
            device.domain = result["domain"]
            updates_applied.append("domain")
            
        # Architecture
        if result.get("architecture"):
            device.architecture = result["architecture"]
            updates_applied.append("architecture")
        
        # Assicurati che credential_id non venga perso
        if existing_credential_id and device.credential_id != existing_credential_id:
            logger.warning(f"Preserving existing credential_id {existing_credential_id} for device {device_id}")
            device.credential_id = existing_credential_id

        # Salva porte aperte rilevate
        if result.get("open_ports"):
            device.open_ports = result["open_ports"]
            updates_applied.append("open_ports")

        # Salva informazioni avanzate se disponibili
        # LLDP/CDP neighbors e dettagli interfacce per switch/router
        if result.get("lldp_neighbors") or result.get("cdp_neighbors") or result.get("interface_details"):
            try:
                from ..services.lldp_cdp_collector import get_lldp_cdp_collector
                from ..models.inventory import LLDPNeighbor, CDPNeighbor, NetworkInterface
                from datetime import datetime
                import uuid
                
                # Salva LLDP neighbors
                if result.get("lldp_neighbors"):
                    # Elimina vecchi neighbor
                    session.query(LLDPNeighbor).filter(LLDPNeighbor.device_id == device_id).delete()
                    
                    # Salva nuovi neighbor
                    for neighbor in result["lldp_neighbors"]:
                        lldp_neighbor = LLDPNeighbor(
                            id=uuid.uuid4().hex[:8],
                            device_id=device_id,
                            local_interface=neighbor.get("local_interface", ""),
                            remote_device_name=neighbor.get("remote_device_name"),
                            remote_device_description=neighbor.get("remote_device_description"),
                            remote_port=neighbor.get("remote_port"),
                            remote_mac=neighbor.get("remote_mac"),
                            remote_ip=neighbor.get("remote_ip"),
                            chassis_id=neighbor.get("chassis_id"),
                            chassis_id_type=neighbor.get("chassis_id_type"),
                            capabilities=neighbor.get("capabilities"),
                            last_seen=datetime.now(),
                        )
                        session.add(lldp_neighbor)
                    logger.info(f"Saved {len(result['lldp_neighbors'])} LLDP neighbors for device {device_id}")
                
                # Salva CDP neighbors
                if result.get("cdp_neighbors"):
                    # Elimina vecchi neighbor
                    session.query(CDPNeighbor).filter(CDPNeighbor.device_id == device_id).delete()
                    
                    # Salva nuovi neighbor
                    for neighbor in result["cdp_neighbors"]:
                        cdp_neighbor = CDPNeighbor(
                            id=uuid.uuid4().hex[:8],
                            device_id=device_id,
                            local_interface=neighbor.get("local_interface", ""),
                            remote_device_id=neighbor.get("remote_device_id"),
                            remote_device_name=neighbor.get("remote_device_name"),
                            remote_port=neighbor.get("remote_port"),
                            remote_ip=neighbor.get("remote_ip"),
                            remote_version=neighbor.get("remote_version"),
                            platform=neighbor.get("platform"),
                            capabilities=neighbor.get("capabilities"),
                            last_seen=datetime.now(),
                        )
                        session.add(cdp_neighbor)
                    logger.info(f"Saved {len(result['cdp_neighbors'])} CDP neighbors for device {device_id}")
                
                # Salva dettagli interfacce avanzati
                if result.get("interface_details"):
                    for iface_data in result["interface_details"]:
                        existing = session.query(NetworkInterface).filter(
                            NetworkInterface.device_id == device_id,
                            NetworkInterface.name == iface_data.get("name")
                        ).first()
                        
                        if existing:
                            # Aggiorna con dati avanzati
                            existing.lldp_enabled = iface_data.get("lldp_enabled")
                            existing.cdp_enabled = iface_data.get("cdp_enabled")
                            existing.poe_enabled = iface_data.get("poe_enabled")
                            existing.poe_power_watts = iface_data.get("poe_power_watts")
                            existing.vlan_native = iface_data.get("vlan_native")
                            existing.vlan_trunk_allowed = iface_data.get("vlan_trunk_allowed")
                            existing.stp_state = iface_data.get("stp_state")
                            existing.lacp_enabled = iface_data.get("lacp_enabled")
                            existing.last_updated = datetime.now()
                        else:
                            # Crea nuova interfaccia con dati avanzati
                            new_iface = NetworkInterface(
                                id=uuid.uuid4().hex[:8],
                                device_id=device_id,
                                name=iface_data.get("name", ""),
                                description=iface_data.get("description"),
                                interface_type=iface_data.get("interface_type"),
                                mac_address=iface_data.get("mac_address"),
                                ip_addresses=iface_data.get("ip_addresses"),
                                speed_mbps=iface_data.get("speed_mbps"),
                                duplex=iface_data.get("duplex"),
                                mtu=iface_data.get("mtu"),
                                admin_status=iface_data.get("admin_status"),
                                oper_status=iface_data.get("oper_status"),
                                lldp_enabled=iface_data.get("lldp_enabled"),
                                cdp_enabled=iface_data.get("cdp_enabled"),
                                poe_enabled=iface_data.get("poe_enabled"),
                                poe_power_watts=iface_data.get("poe_power_watts"),
                                vlan_native=iface_data.get("vlan_native"),
                                vlan_trunk_allowed=iface_data.get("vlan_trunk_allowed"),
                                stp_state=iface_data.get("stp_state"),
                                lacp_enabled=iface_data.get("lacp_enabled"),
                            )
                            session.add(new_iface)
                    logger.info(f"Updated {len(result['interface_details'])} interfaces with advanced details for device {device_id}")
            except Exception as e:
                logger.error(f"Error saving advanced network info for device {device_id}: {e}", exc_info=True)
        
        # Salva informazioni Proxmox se disponibili
        if result.get("proxmox_host_info") or result.get("proxmox_vms") or result.get("proxmox_storage"):
            try:
                from ..models.inventory import ProxmoxHost, ProxmoxVM, ProxmoxStorage
                from datetime import datetime
                import uuid
                
                host_info = result.get("proxmox_host_info")
                if host_info:
                    # Aggiorna o crea ProxmoxHost
                    existing_host = session.query(ProxmoxHost).filter(
                        ProxmoxHost.device_id == device_id
                    ).first()
                    
                    if existing_host:
                        # Aggiorna
                        for key, value in host_info.items():
                            if hasattr(existing_host, key):
                                setattr(existing_host, key, value)
                        existing_host.last_updated = datetime.now()
                        host_id = existing_host.id
                    else:
                        # Crea nuovo
                        new_host = ProxmoxHost(
                            id=uuid.uuid4().hex[:8],
                            device_id=device_id,
                            **{k: v for k, v in host_info.items() if hasattr(ProxmoxHost, k)}
                        )
                        session.add(new_host)
                        session.flush()
                        host_id = new_host.id
                    
                    # Salva VM
                    if result.get("proxmox_vms"):
                        # Elimina vecchie VM
                        session.query(ProxmoxVM).filter(ProxmoxVM.host_id == host_id).delete()
                        
                        # Salva nuove VM
                        for vm_data in result["proxmox_vms"]:
                            vm = ProxmoxVM(
                                id=uuid.uuid4().hex[:8],
                                host_id=host_id,
                                vm_id=vm_data.get("vm_id", 0),
                                name=vm_data.get("name", ""),
                                status=vm_data.get("status"),
                                cpu_cores=vm_data.get("cpu_cores"),
                                memory_mb=vm_data.get("memory_mb"),
                                disk_total_gb=vm_data.get("disk_total_gb"),
                                network_interfaces=vm_data.get("network_interfaces"),
                                os_type=vm_data.get("os_type"),
                                template=vm_data.get("template", False),
                            )
                            session.add(vm)
                        logger.info(f"Saved {len(result['proxmox_vms'])} Proxmox VMs for device {device_id}")
                    
                    # Salva storage
                    if result.get("proxmox_storage"):
                        # Elimina vecchio storage
                        session.query(ProxmoxStorage).filter(ProxmoxStorage.host_id == host_id).delete()
                        
                        # Salva nuovo storage
                        for storage_data in result["proxmox_storage"]:
                            storage = ProxmoxStorage(
                                id=uuid.uuid4().hex[:8],
                                host_id=host_id,
                                storage_name=storage_data.get("storage_name", ""),
                                storage_type=storage_data.get("storage_type"),
                                content_types=storage_data.get("content_types"),
                                total_gb=storage_data.get("total_gb"),
                                used_gb=storage_data.get("used_gb"),
                                available_gb=storage_data.get("available_gb"),
                                usage_percent=storage_data.get("usage_percent"),
                            )
                            session.add(storage)
                        logger.info(f"Saved {len(result['proxmox_storage'])} Proxmox storage for device {device_id}")
            except Exception as e:
                logger.error(f"Error saving Proxmox info for device {device_id}: {e}", exc_info=True)
        
        # Estrai dominio da hostname se non già impostato
        if not device.domain and result.get("hostname") and "." in result["hostname"]:
            parts = result["hostname"].split(".", 1)
            if len(parts) > 1:
                device.domain = parts[1]
                updates_applied.append("domain_from_hostname")
        
        # Nome OS completo (da WMI: "Windows 10 Pro", etc.)
        if result.get("name") and "Windows" in result.get("name", ""):
            # Salva il nome OS completo in description o custom_fields
            if not device.description:
                device.description = result["name"]
                updates_applied.append("os_description")
                
        # Aggiorna identificato_by e credential_used
        if result.get("identified_by"):
            device.identified_by = result["identified_by"]
            updates_applied.append("identified_by")
            
        if result.get("credential_used"):
            device.credential_used = result["credential_used"]
            updates_applied.append("credential_used")
        
        # Aggiorna last_seen
        device.last_seen = datetime.now()
        device.last_scan = datetime.now()
        
        logger.info(f"Device {device_id} identification complete. Updates: {updates_applied}")
        
        session.commit()
        
        return {
            "success": True,
            "device_id": device_id,
            "probe_result": result,
            "updates_applied": updates_applied,
            "message": f"Dispositivo aggiornato: {', '.join(updates_applied)}" if updates_applied else "Nessun aggiornamento necessario"
        }
        
    finally:
        session.close()


# ==========================================
# STATISTICS
# ==========================================

@router.get("/stats")
async def get_inventory_stats(customer_id: Optional[str] = None):
    """Statistiche inventario"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    from sqlalchemy import func
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        query = session.query(InventoryDevice)
        
        if customer_id:
            query = query.filter(InventoryDevice.customer_id == customer_id)
        
        total = query.count()
        
        # Per tipo
        by_type = session.query(
            InventoryDevice.device_type,
            func.count(InventoryDevice.id)
        )
        if customer_id:
            by_type = by_type.filter(InventoryDevice.customer_id == customer_id)
        by_type = dict(by_type.group_by(InventoryDevice.device_type).all())
        
        # Per stato
        by_status = session.query(
            InventoryDevice.status,
            func.count(InventoryDevice.id)
        )
        if customer_id:
            by_status = by_status.filter(InventoryDevice.customer_id == customer_id)
        by_status = dict(by_status.group_by(InventoryDevice.status).all())
        
        return {
            "total": total,
            "by_type": by_type,
            "by_status": by_status,
        }
        
    finally:
        session.close()


# ==========================================
# SYNC WITH THE DUDE
# ==========================================

@router.post("/devices/{device_id}/add-to-dude")
async def add_device_to_dude(device_id: str):
    """Aggiunge dispositivo a The Dude per monitoraggio"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..services.dude_service import get_dude_service
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Dispositivo non trovato")
        
        if not device.primary_ip:
            raise HTTPException(status_code=400, detail="Dispositivo senza IP")
        
        if device.dude_device_id:
            return {
                "success": True,
                "already_exists": True,
                "dude_device_id": device.dude_device_id,
                "message": "Dispositivo già in The Dude",
            }
        
        # Aggiungi a The Dude
        dude = get_dude_service()
        
        # Determina tipo dispositivo per Dude
        dude_type = "Generic Device"
        if device.device_type == "mikrotik":
            dude_type = "RouterOS"
        elif device.device_type == "windows":
            dude_type = "Windows"
        elif device.device_type == "linux":
            dude_type = "Linux"
        elif device.device_type in ["network", "switch"]:
            dude_type = "SNMP Device"
        
        result = dude.add_device(
            name=device.name,
            address=device.primary_ip,
            device_type=dude_type,
        )
        
        if result:
            # Aggiorna riferimento
            device.dude_device_id = result
            device.monitor_source = "dude"
            session.commit()
            
            return {
                "success": True,
                "dude_device_id": result,
                "message": f"Dispositivo {device.name} aggiunto a The Dude",
            }
        else:
            return {
                "success": False,
                "message": "Errore aggiunta a The Dude",
            }
        
    finally:
        session.close()


# ==========================================
# UNIQUE VALUES ENDPOINTS (for autocomplete)
# ==========================================

@router.get("/device-types")
async def get_device_types(customer_id: Optional[str] = Query(None)):
    """
    Restituisce lista di valori unici per device_type dall'inventario.
    Utile per autocompletamento nei form.
    """
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    from sqlalchemy import distinct
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        query = session.query(InventoryDevice.device_type).distinct()
        
        if customer_id:
            query = query.filter(InventoryDevice.customer_id == customer_id)
        
        types = [t[0] for t in query.filter(InventoryDevice.device_type.isnot(None)).all() if t[0]]
        types.sort()
        
        return {
            "success": True,
            "values": types
        }
    except Exception as e:
        logger.error(f"Error fetching device types: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/categories")
async def get_categories(customer_id: Optional[str] = Query(None)):
    """
    Restituisce lista di valori unici per category dall'inventario.
    Utile per autocompletamento nei form.
    """
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    from sqlalchemy import distinct
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        query = session.query(InventoryDevice.category).distinct()
        
        if customer_id:
            query = query.filter(InventoryDevice.customer_id == customer_id)
        
        categories = [c[0] for c in query.filter(InventoryDevice.category.isnot(None)).all() if c[0]]
        categories.sort()
        
        return {
            "success": True,
            "values": categories
        }
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/os-families")
async def get_os_families(customer_id: Optional[str] = Query(None)):
    """
    Restituisce lista di valori unici per os_family dall'inventario.
    Utile per autocompletamento nei form.
    """
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    from sqlalchemy import distinct
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        query = session.query(InventoryDevice.os_family).distinct()
        
        if customer_id:
            query = query.filter(InventoryDevice.customer_id == customer_id)
        
        os_families = [o[0] for o in query.filter(InventoryDevice.os_family.isnot(None)).all() if o[0]]
        os_families.sort()
        
        return {
            "success": True,
            "values": os_families
        }
    except Exception as e:
        logger.error(f"Error fetching OS families: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/manufacturers")
async def get_manufacturers(customer_id: Optional[str] = Query(None)):
    """
    Restituisce lista di valori unici per manufacturer dall'inventario.
    Utile per autocompletamento nei form.
    """
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice
    from ..config import get_settings
    from sqlalchemy import distinct
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        query = session.query(InventoryDevice.manufacturer).distinct()
        
        if customer_id:
            query = query.filter(InventoryDevice.customer_id == customer_id)
        
        manufacturers = [m[0] for m in query.filter(InventoryDevice.manufacturer.isnot(None)).all() if m[0]]
        manufacturers.sort()
        
        return {
            "success": True,
            "values": manufacturers
        }
    except Exception as e:
        logger.error(f"Error fetching manufacturers: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ==========================================
# ADVANCED DEVICE INFORMATION ENDPOINTS
# ==========================================

@router.get("/{customer_id}/devices/{device_id}/lldp-neighbors")
async def get_device_lldp_neighbors(customer_id: str, device_id: str):
    """Ottiene lista neighbor LLDP per un dispositivo"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice, LLDPNeighbor
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id,
            InventoryDevice.customer_id == customer_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        neighbors = session.query(LLDPNeighbor).filter(
            LLDPNeighbor.device_id == device_id
        ).order_by(LLDPNeighbor.local_interface, LLDPNeighbor.last_seen.desc()).all()
        
        return {
            "success": True,
            "device_id": device_id,
            "neighbors": [
                {
                    "id": n.id,
                    "local_interface": n.local_interface,
                    "remote_device_name": n.remote_device_name,
                    "remote_device_description": n.remote_device_description,
                    "remote_port": n.remote_port,
                    "remote_mac": n.remote_mac,
                    "remote_ip": n.remote_ip,
                    "chassis_id": n.chassis_id,
                    "chassis_id_type": n.chassis_id_type,
                    "capabilities": n.capabilities,
                    "last_seen": n.last_seen.isoformat() if n.last_seen else None,
                }
                for n in neighbors
            ],
            "count": len(neighbors)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching LLDP neighbors: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{customer_id}/devices/{device_id}/cdp-neighbors")
async def get_device_cdp_neighbors(customer_id: str, device_id: str):
    """Ottiene lista neighbor CDP per un dispositivo"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice, CDPNeighbor
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id,
            InventoryDevice.customer_id == customer_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        neighbors = session.query(CDPNeighbor).filter(
            CDPNeighbor.device_id == device_id
        ).order_by(CDPNeighbor.local_interface, CDPNeighbor.last_seen.desc()).all()
        
        return {
            "success": True,
            "device_id": device_id,
            "neighbors": [
                {
                    "id": n.id,
                    "local_interface": n.local_interface,
                    "remote_device_id": n.remote_device_id,
                    "remote_device_name": n.remote_device_name,
                    "remote_port": n.remote_port,
                    "remote_ip": n.remote_ip,
                    "remote_version": n.remote_version,
                    "platform": n.platform,
                    "capabilities": n.capabilities,
                    "last_seen": n.last_seen.isoformat() if n.last_seen else None,
                }
                for n in neighbors
            ],
            "count": len(neighbors)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching CDP neighbors: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{customer_id}/devices/{device_id}/interfaces")
async def get_device_interfaces(customer_id: str, device_id: str):
    """Ottiene dettagli interfacce di rete per un dispositivo"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice, NetworkInterface
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id,
            InventoryDevice.customer_id == customer_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        interfaces = session.query(NetworkInterface).filter(
            NetworkInterface.device_id == device_id
        ).order_by(NetworkInterface.name).all()
        
        return {
            "success": True,
            "device_id": device_id,
            "interfaces": [
                {
                    "id": i.id,
                    "name": i.name,
                    "description": i.description,
                    "interface_type": i.interface_type,
                    "mac_address": i.mac_address,
                    "ip_addresses": i.ip_addresses,
                    "speed_mbps": i.speed_mbps,
                    "duplex": i.duplex,
                    "mtu": i.mtu,
                    "admin_status": i.admin_status,
                    "oper_status": i.oper_status,
                    "vlan_id": i.vlan_id,
                    "is_management": i.is_management,
                    "lldp_enabled": i.lldp_enabled,
                    "cdp_enabled": i.cdp_enabled,
                    "poe_enabled": i.poe_enabled,
                    "poe_power_watts": i.poe_power_watts,
                    "vlan_native": i.vlan_native,
                    "vlan_trunk_allowed": i.vlan_trunk_allowed,
                    "stp_state": i.stp_state,
                    "lacp_enabled": i.lacp_enabled,
                    "last_updated": i.last_updated.isoformat() if i.last_updated else None,
                }
                for i in interfaces
            ],
            "count": len(interfaces)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching interfaces: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{customer_id}/devices/{device_id}/proxmox/host")
async def get_proxmox_host_info(customer_id: str, device_id: str):
    """Ottiene informazioni host Proxmox"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice, ProxmoxHost
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id,
            InventoryDevice.customer_id == customer_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        host_info = session.query(ProxmoxHost).filter(
            ProxmoxHost.device_id == device_id
        ).first()
        
        if not host_info:
            return {
                "success": False,
                "message": "Proxmox host info not available. Run refresh-advanced-info first."
            }
        
        return {
            "success": True,
            "device_id": device_id,
            "host_info": {
                "node_name": host_info.node_name,
                "cluster_name": host_info.cluster_name,
                "proxmox_version": host_info.proxmox_version,
                "kernel_version": host_info.kernel_version,
                "cpu_model": host_info.cpu_model,
                "cpu_cores": host_info.cpu_cores,
                "cpu_sockets": host_info.cpu_sockets,
                "cpu_threads": host_info.cpu_threads,
                "cpu_total_cores": host_info.cpu_total_cores,
                "memory_total_gb": host_info.memory_total_gb,
                "memory_used_gb": host_info.memory_used_gb,
                "memory_free_gb": host_info.memory_free_gb,
                "memory_usage_percent": host_info.memory_usage_percent,
                "storage_list": host_info.storage_list,
                "network_interfaces": host_info.network_interfaces,
                "license_status": host_info.license_status,
                "license_message": host_info.license_message,
                "license_level": host_info.license_level,
                "subscription_type": host_info.subscription_type,
                "subscription_key": host_info.subscription_key,
                "uptime_seconds": host_info.uptime_seconds,
                "uptime_human": host_info.uptime_human,
                "load_average_1m": host_info.load_average_1m,
                "load_average_5m": host_info.load_average_5m,
                "load_average_15m": host_info.load_average_15m,
                "cpu_usage_percent": host_info.cpu_usage_percent,
                "io_delay_percent": host_info.io_delay_percent,
                "last_updated": host_info.last_updated.isoformat() if host_info.last_updated else None,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching Proxmox host info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{customer_id}/devices/{device_id}/proxmox/vms")
async def get_proxmox_vms(customer_id: str, device_id: str):
    """Ottiene lista VM Proxmox per un host"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice, ProxmoxHost, ProxmoxVM
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id,
            InventoryDevice.customer_id == customer_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        host_info = session.query(ProxmoxHost).filter(
            ProxmoxHost.device_id == device_id
        ).first()
        
        if not host_info:
            return {
                "success": False,
                "message": "Proxmox host info not available. Run refresh-advanced-info first."
            }
        
        vms = session.query(ProxmoxVM).filter(
            ProxmoxVM.host_id == host_info.id
        ).order_by(ProxmoxVM.vm_id).all()
        
        return {
            "success": True,
            "device_id": device_id,
            "host_id": host_info.id,
            "vms": [
                {
                    "id": vm.id,
                    "vm_id": vm.vm_id,
                    "name": vm.name,
                    "status": vm.status,
                    "cpu_cores": vm.cpu_cores,
                    "memory_mb": vm.memory_mb,
                    "disk_total_gb": vm.disk_total_gb,
                    "network_interfaces": vm.network_interfaces,
                    "os_type": vm.os_type,
                    "template": vm.template,
                    "backup_enabled": vm.backup_enabled,
                    "last_backup": vm.last_backup.isoformat() if vm.last_backup else None,
                    "created_at": vm.created_at.isoformat() if vm.created_at else None,
                    "last_updated": vm.last_updated.isoformat() if vm.last_updated else None,
                }
                for vm in vms
            ],
            "count": len(vms)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching Proxmox VMs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{customer_id}/devices/{device_id}/proxmox/storage")
async def get_proxmox_storage(customer_id: str, device_id: str):
    """Ottiene lista storage Proxmox per un host"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice, ProxmoxHost, ProxmoxStorage
    from ..config import get_settings
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id,
            InventoryDevice.customer_id == customer_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        host_info = session.query(ProxmoxHost).filter(
            ProxmoxHost.device_id == device_id
        ).first()
        
        if not host_info:
            return {
                "success": False,
                "message": "Proxmox host info not available. Run refresh-advanced-info first."
            }
        
        storage_list = session.query(ProxmoxStorage).filter(
            ProxmoxStorage.host_id == host_info.id
        ).order_by(ProxmoxStorage.storage_name).all()
        
        return {
            "success": True,
            "device_id": device_id,
            "host_id": host_info.id,
            "storage": [
                {
                    "id": s.id,
                    "storage_name": s.storage_name,
                    "storage_type": s.storage_type,
                    "content_types": s.content_types,
                    "total_gb": s.total_gb,
                    "used_gb": s.used_gb,
                    "available_gb": s.available_gb,
                    "usage_percent": s.usage_percent,
                    "last_updated": s.last_updated.isoformat() if s.last_updated else None,
                }
                for s in storage_list
            ],
            "count": len(storage_list)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching Proxmox storage: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/{customer_id}/devices/{device_id}/refresh-advanced-info")
async def refresh_advanced_info(customer_id: str, device_id: str):
    """Forza refresh informazioni avanzate per un dispositivo"""
    from ..models.database import init_db, get_session
    from ..models.inventory import InventoryDevice, LLDPNeighbor, CDPNeighbor, NetworkInterface, ProxmoxHost, ProxmoxVM, ProxmoxStorage
    from ..config import get_settings
    from ..services.device_probe_service import get_device_probe_service
    from ..services.lldp_cdp_collector import get_lldp_cdp_collector
    from ..services.proxmox_collector import get_proxmox_collector
    from datetime import datetime
    import uuid
    
    settings = get_settings()
    db_url = settings.database_url
    engine = init_db(db_url)
    session = get_session(engine)
    
    try:
        device = session.query(InventoryDevice).filter(
            InventoryDevice.id == device_id,
            InventoryDevice.customer_id == customer_id
        ).first()
        
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        
        # Ottieni credenziali del cliente
        from ..models.database import Credential
        credentials = session.query(Credential).filter(
            Credential.customer_id == customer_id,
            Credential.active == True
        ).all()
        
        credentials_list = []
        for cred in credentials:
            cred_dict = {
                "id": cred.id,
                "type": cred.credential_type,
                "username": cred.username,
                "password": cred.password,
                "snmp_community": cred.snmp_community,
                "snmp_port": cred.snmp_port,
                "snmp_version": cred.snmp_version,
                "ssh_port": cred.ssh_port,
                "mikrotik_api_port": cred.mikrotik_api_port,
                "use_ssl": cred.use_ssl,
            }
            credentials_list.append(cred_dict)
        
        device_type = device.device_type or ""
        vendor = device.manufacturer or ""
        
        logger.info(f"Refresh advanced info for device {device_id}: type={device_type}, vendor={vendor}, credentials={len(credentials_list)}")
        
        # Switch/Router: raccogli LLDP/CDP e interfacce
        device_type_lower = device_type.lower()
        vendor_lower = vendor.lower()
        is_network_device = (
            device_type_lower in ["network", "router", "switch"] or 
            "mikrotik" in vendor_lower or 
            "cisco" in vendor_lower or 
            "hp" in vendor_lower or 
            "aruba" in vendor_lower or 
            "ubiquiti" in vendor_lower
        )
        
        if is_network_device:
            logger.info(f"Device {device_id} identified as network device, collecting LLDP/CDP/interfaces...")
            lldp_collector = get_lldp_cdp_collector()
            
            # LLDP neighbors
            try:
                lldp_neighbors = await lldp_collector.collect_lldp_neighbors(
                    device.primary_ip, device_type, vendor, credentials_list
                )
                
                # Elimina vecchi neighbor
                session.query(LLDPNeighbor).filter(LLDPNeighbor.device_id == device_id).delete()
                
                # Salva nuovi neighbor
                for neighbor in lldp_neighbors:
                    lldp_neighbor = LLDPNeighbor(
                        id=uuid.uuid4().hex[:8],
                        device_id=device_id,
                        local_interface=neighbor.get("local_interface", ""),
                        remote_device_name=neighbor.get("remote_device_name"),
                        remote_device_description=neighbor.get("remote_device_description"),
                        remote_port=neighbor.get("remote_port"),
                        remote_mac=neighbor.get("remote_mac"),
                        remote_ip=neighbor.get("remote_ip"),
                        chassis_id=neighbor.get("chassis_id"),
                        chassis_id_type=neighbor.get("chassis_id_type"),
                        capabilities=neighbor.get("capabilities"),
                        last_seen=datetime.now(),
                    )
                    session.add(lldp_neighbor)
                
                logger.info(f"Saved {len(lldp_neighbors)} LLDP neighbors for device {device_id}")
            except Exception as e:
                logger.error(f"Error collecting LLDP neighbors: {e}")
            
            # CDP neighbors (solo Cisco)
            if "cisco" in vendor.lower():
                try:
                    cdp_neighbors = await lldp_collector.collect_cdp_neighbors(
                        device.primary_ip, vendor, credentials_list
                    )
                    
                    # Elimina vecchi neighbor
                    session.query(CDPNeighbor).filter(CDPNeighbor.device_id == device_id).delete()
                    
                    # Salva nuovi neighbor
                    for neighbor in cdp_neighbors:
                        cdp_neighbor = CDPNeighbor(
                            id=uuid.uuid4().hex[:8],
                            device_id=device_id,
                            local_interface=neighbor.get("local_interface", ""),
                            remote_device_id=neighbor.get("remote_device_id"),
                            remote_device_name=neighbor.get("remote_device_name"),
                            remote_port=neighbor.get("remote_port"),
                            remote_ip=neighbor.get("remote_ip"),
                            remote_version=neighbor.get("remote_version"),
                            platform=neighbor.get("platform"),
                            capabilities=neighbor.get("capabilities"),
                            last_seen=datetime.now(),
                        )
                        session.add(cdp_neighbor)
                    
                    logger.info(f"Saved {len(cdp_neighbors)} CDP neighbors for device {device_id}")
                except Exception as e:
                    logger.error(f"Error collecting CDP neighbors: {e}")
            
            # Dettagli interfacce
            try:
                interfaces = await lldp_collector.collect_interface_details(
                    device.primary_ip, device_type, vendor, credentials_list
                )
                
                # Aggiorna interfacce esistenti o crea nuove
                for iface_data in interfaces:
                    existing = session.query(NetworkInterface).filter(
                        NetworkInterface.device_id == device_id,
                        NetworkInterface.name == iface_data.get("name")
                    ).first()
                    
                    if existing:
                        # Aggiorna
                        existing.description = iface_data.get("description")
                        existing.interface_type = iface_data.get("interface_type")
                        existing.mac_address = iface_data.get("mac_address")
                        existing.ip_addresses = iface_data.get("ip_addresses")
                        existing.speed_mbps = iface_data.get("speed_mbps")
                        existing.duplex = iface_data.get("duplex")
                        existing.mtu = iface_data.get("mtu")
                        existing.admin_status = iface_data.get("admin_status")
                        existing.oper_status = iface_data.get("oper_status")
                        existing.lldp_enabled = iface_data.get("lldp_enabled")
                        existing.cdp_enabled = iface_data.get("cdp_enabled")
                        existing.poe_enabled = iface_data.get("poe_enabled")
                        existing.poe_power_watts = iface_data.get("poe_power_watts")
                        existing.vlan_native = iface_data.get("vlan_native")
                        existing.vlan_trunk_allowed = iface_data.get("vlan_trunk_allowed")
                        existing.stp_state = iface_data.get("stp_state")
                        existing.lacp_enabled = iface_data.get("lacp_enabled")
                        existing.last_updated = datetime.now()
                    else:
                        # Crea nuova
                        new_iface = NetworkInterface(
                            id=uuid.uuid4().hex[:8],
                            device_id=device_id,
                            name=iface_data.get("name", ""),
                            description=iface_data.get("description"),
                            interface_type=iface_data.get("interface_type"),
                            mac_address=iface_data.get("mac_address"),
                            ip_addresses=iface_data.get("ip_addresses"),
                            speed_mbps=iface_data.get("speed_mbps"),
                            duplex=iface_data.get("duplex"),
                            mtu=iface_data.get("mtu"),
                            admin_status=iface_data.get("admin_status"),
                            oper_status=iface_data.get("oper_status"),
                            lldp_enabled=iface_data.get("lldp_enabled"),
                            cdp_enabled=iface_data.get("cdp_enabled"),
                            poe_enabled=iface_data.get("poe_enabled"),
                            poe_power_watts=iface_data.get("poe_power_watts"),
                            vlan_native=iface_data.get("vlan_native"),
                            vlan_trunk_allowed=iface_data.get("vlan_trunk_allowed"),
                            stp_state=iface_data.get("stp_state"),
                            lacp_enabled=iface_data.get("lacp_enabled"),
                        )
                        session.add(new_iface)
                
                logger.info(f"Updated {len(interfaces)} interfaces for device {device_id}")
            except Exception as e:
                logger.error(f"Error collecting interface details: {e}")
        
        # Proxmox: raccogli info host, VM, storage
        os_family_lower = (device.os_family or "").lower()
        is_proxmox = (
            device_type_lower == "hypervisor" or 
            "proxmox" in vendor_lower or 
            "proxmox" in os_family_lower
        )
        
        if is_proxmox:
            logger.info(f"Device {device_id} identified as Proxmox, collecting host/VM/storage info...")
            proxmox_collector = get_proxmox_collector()
            
            try:
                host_info = await proxmox_collector.collect_proxmox_host_info(
                    device.primary_ip, credentials_list
                )
                
                if host_info:
                    # Aggiorna o crea ProxmoxHost
                    existing_host = session.query(ProxmoxHost).filter(
                        ProxmoxHost.device_id == device_id
                    ).first()
                    
                    if existing_host:
                        # Aggiorna
                        for key, value in host_info.items():
                            if hasattr(existing_host, key):
                                setattr(existing_host, key, value)
                        existing_host.last_updated = datetime.now()
                        host_id = existing_host.id
                    else:
                        # Crea nuovo
                        new_host = ProxmoxHost(
                            id=uuid.uuid4().hex[:8],
                            device_id=device_id,
                            **{k: v for k, v in host_info.items() if hasattr(ProxmoxHost, k)}
                        )
                        session.add(new_host)
                        session.flush()
                        host_id = new_host.id
                    
                    # Raccogli VM
                    node_name = host_info.get("node_name")
                    if node_name:
                        vms = await proxmox_collector.collect_proxmox_vms(
                            device.primary_ip, node_name, credentials_list
                        )
                        
                        # Elimina vecchie VM
                        session.query(ProxmoxVM).filter(ProxmoxVM.host_id == host_id).delete()
                        
                        # Salva nuove VM
                        for vm_data in vms:
                            vm = ProxmoxVM(
                                id=uuid.uuid4().hex[:8],
                                host_id=host_id,
                                vm_id=vm_data.get("vm_id", 0),
                                name=vm_data.get("name", ""),
                                status=vm_data.get("status"),
                                cpu_cores=vm_data.get("cpu_cores"),
                                memory_mb=vm_data.get("memory_mb"),
                                disk_total_gb=vm_data.get("disk_total_gb"),
                                network_interfaces=vm_data.get("network_interfaces"),
                                os_type=vm_data.get("os_type"),
                                template=vm_data.get("template", False),
                            )
                            session.add(vm)
                        
                        logger.info(f"Saved {len(vms)} Proxmox VMs for device {device_id}")
                        
                        # Raccogli storage
                        storage_list = await proxmox_collector.collect_proxmox_storage(
                            device.primary_ip, node_name, credentials_list
                        )
                        
                        # Elimina vecchio storage
                        session.query(ProxmoxStorage).filter(ProxmoxStorage.host_id == host_id).delete()
                        
                        # Salva nuovo storage
                        for storage_data in storage_list:
                            storage = ProxmoxStorage(
                                id=uuid.uuid4().hex[:8],
                                host_id=host_id,
                                storage_name=storage_data.get("storage_name", ""),
                                storage_type=storage_data.get("storage_type"),
                                content_types=storage_data.get("content_types"),
                                total_gb=storage_data.get("total_gb"),
                                used_gb=storage_data.get("used_gb"),
                                available_gb=storage_data.get("available_gb"),
                                usage_percent=storage_data.get("usage_percent"),
                            )
                            session.add(storage)
                        
                        logger.info(f"Saved {len(storage_list)} Proxmox storage for device {device_id}")
                
            except Exception as e:
                logger.error(f"Error collecting Proxmox info for device {device_id}: {e}", exc_info=True)
        
        if not is_network_device and not is_proxmox:
            logger.info(f"Device {device_id} (type={device_type}, vendor={vendor}) does not match network or Proxmox criteria, skipping advanced info collection")
        
        session.commit()
        
        return {
            "success": True,
            "message": "Advanced info refreshed successfully",
            "device_id": device_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Error refreshing advanced info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
