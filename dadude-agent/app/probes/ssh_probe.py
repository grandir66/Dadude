"""
DaDude Agent - SSH Probe
Scansione dispositivi Linux/Unix/MikroTik via SSH
"""
import asyncio
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
from io import StringIO


_executor = ThreadPoolExecutor(max_workers=5)


async def probe(
    target: str,
    username: str,
    password: Optional[str] = None,
    private_key: Optional[str] = None,
    port: int = 22,
) -> Dict[str, Any]:
    """
    Esegue probe SSH su un target Linux/Unix/MikroTik.
    Rileva automaticamente il tipo di device ed esegue comandi appropriati.
    
    Returns:
        Dict con info sistema: hostname, os, kernel, cpu, ram, disco
    """
    loop = asyncio.get_event_loop()
    
    def connect():
        import paramiko
        
        logger.debug(f"SSH probe: connecting to {target}:{port} as {username}")
        
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        connect_args = {
            "hostname": target,
            "port": port,
            "username": username,
            "timeout": 15,
            "allow_agent": False,
            "look_for_keys": False,
        }
        
        if private_key:
            key = paramiko.RSAKey.from_private_key(StringIO(private_key))
            connect_args["pkey"] = key
        else:
            connect_args["password"] = password
        
        client.connect(**connect_args)
        
        info = {}
        
        def exec_cmd(cmd: str, timeout: int = 5) -> str:
            try:
                stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
                return stdout.read().decode().strip()
            except:
                return ""
        
        # ===== PRIMA RILEVA IL TIPO DI DEVICE =====
        # Prova MikroTik RouterOS (non supporta comandi Linux)
        ros_out = exec_cmd("/system resource print")
        
        if "version:" in ros_out.lower() or "uptime:" in ros_out.lower() or "routeros" in ros_out.lower():
            # ===== MIKROTIK ROUTEROS =====
            logger.info(f"SSH probe: Detected MikroTik RouterOS on {target}")
            info["device_type"] = "mikrotik"
            info["os_name"] = "RouterOS"
            info["manufacturer"] = "MikroTik"
            info["category"] = "router"
            
            # Parse /system resource print
            for line in ros_out.split('\n'):
                ll = line.lower().strip()
                if ll.startswith('version:'):
                    info["os_version"] = line.split(':', 1)[1].strip()
                elif ll.startswith('board-name:'):
                    info["model"] = line.split(':', 1)[1].strip()
                elif ll.startswith('cpu:') and 'cpu-count' not in ll:
                    info["cpu_model"] = line.split(':', 1)[1].strip()
                elif ll.startswith('cpu-count:'):
                    try:
                        info["cpu_cores"] = int(line.split(':', 1)[1].strip())
                    except:
                        pass
                elif ll.startswith('total-memory:'):
                    try:
                        mem_str = line.split(':', 1)[1].strip()
                        if 'MiB' in mem_str:
                            info["ram_total_mb"] = int(float(mem_str.replace('MiB', '').strip()))
                        elif 'GiB' in mem_str:
                            info["ram_total_mb"] = int(float(mem_str.replace('GiB', '').strip()) * 1024)
                    except:
                        pass
                elif ll.startswith('free-memory:'):
                    try:
                        mem_str = line.split(':', 1)[1].strip()
                        if 'MiB' in mem_str:
                            info["ram_free_mb"] = int(float(mem_str.replace('MiB', '').strip()))
                    except:
                        pass
                elif ll.startswith('architecture-name:'):
                    info["architecture"] = line.split(':', 1)[1].strip()
                elif ll.startswith('uptime:'):
                    info["uptime"] = line.split(':', 1)[1].strip()
            
            # Get hostname from /system identity
            identity_out = exec_cmd("/system identity print")
            for line in identity_out.split('\n'):
                if 'name:' in line.lower():
                    info["hostname"] = line.split(':', 1)[1].strip()
                    break
            
            # Get serial/model from /system routerboard
            rb_out = exec_cmd("/system routerboard print")
            for line in rb_out.split('\n'):
                ll = line.lower().strip()
                if ll.startswith('serial-number:'):
                    info["serial_number"] = line.split(':', 1)[1].strip()
                elif ll.startswith('model:') and not info.get("model"):
                    info["model"] = line.split(':', 1)[1].strip()
                elif ll.startswith('current-firmware:'):
                    info["firmware"] = line.split(':', 1)[1].strip()
            
            # Get license
            lic_out = exec_cmd("/system license print")
            for line in lic_out.split('\n'):
                if 'level:' in line.lower():
                    info["license_level"] = line.split(':', 1)[1].strip()
            
            # Get interface count
            iface_count = exec_cmd("/interface print count-only")
            if iface_count.isdigit():
                info["interface_count"] = int(iface_count)
        
        else:
            # ===== LINUX/UNIX/OTHER =====
            logger.debug(f"SSH probe: Detecting Linux/Unix on {target}")
            
            # Hostname
            info["hostname"] = exec_cmd("hostname")
            
            # OS Info
            os_release = exec_cmd("cat /etc/os-release 2>/dev/null || cat /etc/redhat-release 2>/dev/null")
            if os_release:
                for line in os_release.split('\n'):
                    if line.startswith('PRETTY_NAME='):
                        info["os_name"] = line.split('=', 1)[1].strip('"')
                    elif line.startswith('ID='):
                        info["os_id"] = line.split('=', 1)[1].strip('"')
                    elif line.startswith('VERSION_ID='):
                        info["os_version"] = line.split('=', 1)[1].strip('"')
            
            # Check for special devices
            # Ubiquiti
            ubnt_out = exec_cmd("cat /etc/board.info 2>/dev/null")
            if ubnt_out and 'board.' in ubnt_out.lower():
                info["device_type"] = "network"
                info["manufacturer"] = "Ubiquiti"
                info["os_name"] = "UniFi"
                for line in ubnt_out.split('\n'):
                    if 'board.name' in line.lower():
                        info["model"] = line.split('=')[-1].strip()
                    elif 'board.sysid' in line.lower():
                        info["serial_number"] = line.split('=')[-1].strip()
            
            # Synology
            syno_out = exec_cmd("cat /etc/synoinfo.conf 2>/dev/null")
            if syno_out and 'synology' in syno_out.lower():
                info["device_type"] = "nas"
                info["manufacturer"] = "Synology"
                info["os_name"] = "DSM"
                for line in syno_out.split('\n'):
                    if 'upnpmodelname' in line.lower():
                        info["model"] = line.split('=')[-1].strip().strip('"')
            
            # Proxmox
            if 'proxmox' in os_release.lower():
                info["device_type"] = "hypervisor"
                pve_ver = exec_cmd("pveversion 2>/dev/null")
                if pve_ver:
                    info["os_version"] = pve_ver
            
            # Default device type
            if not info.get("device_type"):
                info["device_type"] = "linux"
            
            # Kernel
            kernel = exec_cmd("uname -r")
            if kernel:
                info["kernel"] = kernel
            
            # Architecture
            arch = exec_cmd("uname -m")
            if arch:
                info["architecture"] = arch
            
            # CPU Info
            cpu_info = exec_cmd("cat /proc/cpuinfo | grep 'model name' | head -1")
            if cpu_info and ':' in cpu_info:
                info["cpu_model"] = cpu_info.split(':')[1].strip()
            
            # CPU Cores
            cores = exec_cmd("nproc 2>/dev/null || grep -c processor /proc/cpuinfo")
            if cores.isdigit():
                info["cpu_cores"] = int(cores)
            
            # RAM
            mem = exec_cmd("free -m | grep Mem | awk '{print $2}'")
            if mem.isdigit():
                info["ram_total_mb"] = int(mem)
            
            # Disk
            disk = exec_cmd("df -BG / | awk 'NR==2 {print $2, $4}'")
            if disk:
                parts = disk.split()
                if len(parts) >= 2:
                    try:
                        info["disk_total_gb"] = int(parts[0].replace('G', ''))
                        info["disk_free_gb"] = int(parts[1].replace('G', ''))
                    except:
                        pass
            
            # Uptime
            uptime = exec_cmd("uptime -p 2>/dev/null || uptime")
            if uptime:
                info["uptime"] = uptime
            
            # Serial (DMI)
            serial = exec_cmd("cat /sys/class/dmi/id/product_serial 2>/dev/null")
            if serial and serial != "To Be Filled By O.E.M." and "Permission" not in serial:
                info["serial_number"] = serial
            
            # Manufacturer/Model (DMI)
            vendor = exec_cmd("cat /sys/class/dmi/id/sys_vendor 2>/dev/null")
            if vendor and vendor != "To Be Filled By O.E.M.":
                info["manufacturer"] = vendor
            
            model = exec_cmd("cat /sys/class/dmi/id/product_name 2>/dev/null")
            if model and model != "To Be Filled By O.E.M.":
                info["model"] = model
        
        client.close()
        
        logger.info(f"SSH probe successful: {info.get('hostname')} ({info.get('os_name', 'Unknown')})")
        return info
    
    return await loop.run_in_executor(_executor, connect)
