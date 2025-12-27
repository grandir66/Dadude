"""
DaDude - Proxmox Collector Service
Raccoglie informazioni complete da host Proxmox: host, VM, storage, backup, network
Integra logica da Proxreporter
"""
from typing import Optional, Dict, Any, List
from loguru import logger
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import re
import subprocess
import os
import urllib.request
import urllib.parse
import urllib.error
import ssl
from http.cookiejar import CookieJar
from datetime import datetime


def bytes_to_gib(value: Any) -> Optional[float]:
    """Converte byte in Gibibyte"""
    try:
        if value is None:
            return None
        return value / (1024 ** 3)
    except Exception:
        return None


def safe_round(value: Any, digits: int = 2) -> Optional[float]:
    """Arrotonda un valore numerico gestendo None"""
    try:
        if value is None:
            return None
        return round(float(value), digits)
    except Exception:
        return None


def seconds_to_human(seconds: Any) -> Optional[str]:
    """Converte secondi in formato leggibile (Xd Yh Zm Ws)"""
    try:
        if seconds is None:
            return None
        seconds = int(seconds)
        if seconds < 0:
            seconds = 0
        from datetime import timedelta
        delta = timedelta(seconds=seconds)
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if secs or not parts:
            parts.append(f"{secs}s")
        return ' '.join(parts)
    except Exception:
        return None


class ProxmoxCollector:
    """Servizio per raccogliere informazioni da Proxmox"""
    
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=3)
    
    async def collect_proxmox_host_info(
        self,
        device_address: str,
        credentials: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Raccoglie informazioni complete host Proxmox
        
        Args:
            device_address: IP dell'host Proxmox
            credentials: Lista credenziali (deve contenere username/password per API)
            
        Returns:
            Dict con informazioni host o None se fallisce
        """
        host_info = None
        
        for cred in credentials:
            cred_type = cred.get('type', '').lower()
            cred_id = cred.get('id', 'unknown')
            
            # Per credenziali SSH, prova prima SSH (più affidabile per Proxmox)
            # Per altre credenziali, prova prima API
            if cred_type == 'ssh':
                # Prova SSH prima
                try:
                    logger.info(f"Trying SSH for Proxmox {device_address} with cred {cred_id} (username: {cred.get('username', 'N/A')})")
                    host_info = await self._collect_host_info_ssh(device_address, cred)
                    if host_info:
                        logger.info(f"✓ Proxmox SSH collection successful for {device_address} with cred {cred_id}")
                        break
                    else:
                        logger.warning(f"Proxmox SSH returned None for {device_address} with cred {cred_id}")
                except Exception as e:
                    logger.warning(f"✗ Proxmox SSH failed for {device_address} with cred {cred_id}: {e}")
                
                # Fallback a API con credenziali SSH (solo se SSH fallisce)
                if not host_info:
                    try:
                        logger.info(f"Trying API (fallback) for Proxmox {device_address} with cred {cred_id}")
                        host_info = await self._collect_host_info_api(device_address, cred)
                        if host_info:
                            logger.info(f"✓ Proxmox API collection successful for {device_address} with cred {cred_id}")
                            break
                    except Exception as e:
                        logger.warning(f"✗ Proxmox API failed for {device_address} with cred {cred_id}: {e}")
            else:
                # Prova API prima per credenziali non-SSH
                try:
                    logger.debug(f"Trying API for Proxmox {device_address} with cred {cred_id}")
                    host_info = await self._collect_host_info_api(device_address, cred)
                    if host_info:
                        logger.info(f"Proxmox API collection successful for {device_address} with cred {cred_id}")
                        break
                except Exception as e:
                    logger.debug(f"Proxmox API failed for {device_address} with cred {cred_id}: {e}")
                
                # Fallback a SSH se disponibile
                if cred.get('username') and cred.get('password'):
                    try:
                        logger.debug(f"Trying SSH (fallback) for Proxmox {device_address} with cred {cred_id}")
                        host_info = await self._collect_host_info_ssh(device_address, cred)
                        if host_info:
                            logger.info(f"Proxmox SSH collection successful for {device_address} with cred {cred_id}")
                            break
                    except Exception as e:
                        logger.debug(f"Proxmox SSH failed for {device_address} with cred {cred_id}: {e}")
        
        if host_info:
            logger.info(f"Proxmox host info collected for {device_address}")
        else:
            logger.warning(f"Proxmox host info collection failed for {device_address} - no valid credentials or connection failed")
        
        return host_info
    
    async def collect_proxmox_vms(
        self,
        device_address: str,
        node_name: str,
        credentials: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Raccoglie lista VM da host Proxmox
        
        Args:
            device_address: IP dell'host Proxmox
            node_name: Nome del nodo Proxmox
            credentials: Lista credenziali
            
        Returns:
            Lista di VM trovate
        """
        vms = []
        
        for cred in credentials:
            # Prova API
            api_success = False
            try:
                vms = await self._collect_vms_api(device_address, node_name, cred)
                if vms:
                    api_success = True
                    break
            except Exception as e:
                logger.warning(f"Proxmox API VM collection failed for {device_address}: {e}")
                # Continua a provare SSH anche se API fallisce
            
            # Fallback a SSH se API non ha funzionato
            if not api_success:
                try:
                    logger.info(f"Trying SSH fallback for VM collection on {device_address}")
                    vms = await self._collect_vms_ssh(device_address, node_name, cred)
                    if vms:
                        break
                except Exception as e:
                    logger.warning(f"Proxmox SSH VM collection failed for {device_address}: {e}")
                    continue
        
        logger.info(f"Proxmox VMs collected for {device_address}: {len(vms)} found")
        return vms
    
    async def collect_proxmox_storage(
        self,
        device_address: str,
        node_name: str,
        credentials: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Raccoglie informazioni storage da host Proxmox
        
        Args:
            device_address: IP dell'host Proxmox
            node_name: Nome del nodo Proxmox
            credentials: Lista credenziali
            
        Returns:
            Lista di storage trovati
        """
        storage_list = []
        
        for cred in credentials:
            # Prova API
            api_success = False
            try:
                storage_list = await self._collect_storage_api(device_address, node_name, cred)
                if storage_list:
                    api_success = True
                    break
            except Exception as e:
                logger.warning(f"Proxmox API storage collection failed for {device_address}: {e}")
                # Continua a provare SSH anche se API fallisce
            
            # Fallback a SSH se API non ha funzionato
            if not api_success:
                try:
                    logger.info(f"Trying SSH fallback for storage collection on {device_address}")
                    storage_list = await self._collect_storage_ssh(device_address, node_name, cred)
                    if storage_list:
                        break
                except Exception as e:
                    logger.warning(f"Proxmox SSH storage collection failed for {device_address}: {e}")
                    continue
        
        logger.info(f"Proxmox storage collected for {device_address}: {len(storage_list)} found")
        return storage_list
    
    async def collect_proxmox_backups(
        self,
        device_address: str,
        node_name: str,
        vm_id: int,
        credentials: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Raccoglie informazioni backup per una VM
        
        Args:
            device_address: IP dell'host Proxmox
            node_name: Nome del nodo Proxmox
            vm_id: ID della VM
            credentials: Lista credenziali
            
        Returns:
            Lista di backup trovati
        """
        backups = []
        
        for cred in credentials:
            try:
                backups = await self._collect_backups_api(device_address, node_name, vm_id, cred)
                if backups:
                    break
            except Exception as e:
                logger.debug(f"Proxmox backup collection failed: {e}")
                continue
        
        logger.info(f"Proxmox backups collected for VM {vm_id}: {len(backups)} found")
        return backups
    
    # ==========================================
    # API IMPLEMENTATIONS
    # ==========================================
    
    async def _collect_host_info_api(
        self,
        address: str,
        credentials: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Raccoglie info host via API Proxmox"""
        try:
            loop = asyncio.get_event_loop()
            host_info = await loop.run_in_executor(
                self._executor,
                self._get_host_info_api_sync,
                address,
                credentials
            )
            return host_info
        except Exception as e:
            logger.error(f"Error collecting host info via API: {e}")
            return None
    
    def _get_host_info_api_sync(
        self,
        address: str,
        credentials: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Implementazione sincrona per API Proxmox"""
        try:
            port = credentials.get("proxmox_port", 8006)
            username = credentials.get("username", "root@pam")
            password = credentials.get("password", "")
            
            base_url = f"https://{address}:{port}/api2/json"
            ssl_context = ssl._create_unverified_context()
            auth_url = f"{base_url}/access/ticket"
            
            data = urllib.parse.urlencode({
                'username': username,
                'password': password
            }).encode('utf-8')
            
            cookie_jar = CookieJar()
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(cookie_jar),
                urllib.request.HTTPSHandler(context=ssl_context)
            )
            
            request = urllib.request.Request(auth_url, data=data, method='POST')
            response = opener.open(request, timeout=10)
            result = json.loads(response.read().decode('utf-8'))['data']
            ticket = result['ticket']
            csrf_token = result['CSRFPreventionToken']
            
            def api_get(endpoint):
                url = f"{base_url}/{endpoint}"
                req = urllib.request.Request(url)
                req.add_header('Cookie', f'PVEAuthCookie={ticket}')
                req.add_header('CSRFPreventionToken', csrf_token)
                resp = opener.open(req, timeout=10)
                return json.loads(resp.read().decode('utf-8'))['data']
            
            # Ottieni nodi
            nodes = api_get('nodes')
            if not nodes:
                return None
            
            node_name = nodes[0].get('node')
            if not node_name:
                return None
            
            # Status nodo
            node_status = api_get(f'nodes/{node_name}/status')
            if not node_status:
                return None
            
            host_info = {
                'node_name': node_name,
                'hostname': node_name,
                'status': node_status.get('status'),
                'uptime_seconds': int(node_status.get('uptime', 0)),
                'uptime_human': seconds_to_human(node_status.get('uptime')),
                'cpu_usage_percent': safe_round(float(node_status.get('cpu', 0)) * 100, 2),
                'io_delay_percent': safe_round(node_status.get('io_delay'), 2),
            }
            
            # Load average
            loadavg = node_status.get('loadavg')
            if isinstance(loadavg, (list, tuple)) and len(loadavg) >= 3:
                host_info['load_average_1m'] = safe_round(float(loadavg[0]), 2)
                host_info['load_average_5m'] = safe_round(float(loadavg[1]), 2)
                host_info['load_average_15m'] = safe_round(float(loadavg[2]), 2)
            
            # CPU info
            cpuinfo = node_status.get('cpuinfo', {})
            host_info['cpu_model'] = cpuinfo.get('model')
            host_info['cpu_cores'] = cpuinfo.get('cores')
            host_info['cpu_sockets'] = cpuinfo.get('sockets')
            host_info['cpu_threads'] = cpuinfo.get('cpus')
            host_info['cpu_total_cores'] = cpuinfo.get('cpus') or cpuinfo.get('cores')
            
            # Memory
            memory_info = node_status.get('memory', {})
            mem_total = memory_info.get('total')
            mem_used = memory_info.get('used')
            mem_free = memory_info.get('free')
            if mem_total is not None:
                host_info['memory_total_gb'] = bytes_to_gib(mem_total)
            if mem_used is not None:
                host_info['memory_used_gb'] = bytes_to_gib(mem_used)
            if mem_free is not None:
                host_info['memory_free_gb'] = bytes_to_gib(mem_free)
            if mem_total and mem_used is not None:
                host_info['memory_usage_percent'] = safe_round((mem_used / mem_total) * 100, 2)
            
            # Versione
            try:
                version_info = api_get(f'nodes/{node_name}/version')
                if version_info:
                    manager_version = version_info.get('version', '')
                    if manager_version:
                        host_info['proxmox_version'] = manager_version
                    kernel_version = version_info.get('kernel') or version_info.get('running_kernel') or version_info.get('release')
                    if kernel_version:
                        host_info['kernel_version'] = kernel_version.strip()
            except:
                pass
            
            # Subscription
            try:
                subscription_info = api_get(f'nodes/{node_name}/subscription')
                if isinstance(subscription_info, dict):
                    host_info['license_status'] = subscription_info.get('status')
                    host_info['license_message'] = subscription_info.get('message')
                    host_info['license_level'] = subscription_info.get('level')
                    host_info['subscription_type'] = subscription_info.get('type')
                    host_info['subscription_key'] = subscription_info.get('key')
            except:
                pass
            
            # Storage
            try:
                storage_list = api_get(f'nodes/{node_name}/storage')
                host_info['storage_list'] = []
                for storage in storage_list:
                    storage_info = {
                        'storage': storage.get('storage'),
                        'type': storage.get('type'),
                        'content': storage.get('content'),
                    }
                    try:
                        storage_status = api_get(f'nodes/{node_name}/storage/{storage_info["storage"]}/status')
                        if storage_status:
                            storage_info['total'] = storage_status.get('total')
                            storage_info['used'] = storage_status.get('used')
                            storage_info['available'] = storage_status.get('avail')
                    except:
                        pass
                    host_info['storage_list'].append(storage_info)
            except:
                host_info['storage_list'] = []
            
            # Network
            try:
                network_data = api_get(f'nodes/{node_name}/network')
                host_info['network_interfaces'] = network_data or []
            except:
                host_info['network_interfaces'] = []
            
            return host_info
            
        except Exception as e:
            logger.error(f"Error in API sync collection: {e}")
            return None
    
    async def _collect_vms_api(
        self,
        address: str,
        node_name: str,
        credentials: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Raccoglie VM via API Proxmox"""
        try:
            loop = asyncio.get_event_loop()
            vms = await loop.run_in_executor(
                self._executor,
                self._get_vms_api_sync,
                address,
                node_name,
                credentials
            )
            return vms or []
        except Exception as e:
            logger.error(f"Error collecting VMs via API: {e}")
            return []
    
    def _get_vms_api_sync(
        self,
        address: str,
        node_name: str,
        credentials: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Implementazione sincrona per raccolta VM via API"""
        try:
            port = credentials.get("proxmox_port", 8006)
            username = credentials.get("username", "root@pam")
            password = credentials.get("password", "")
            
            base_url = f"https://{address}:{port}/api2/json"
            ssl_context = ssl._create_unverified_context()
            auth_url = f"{base_url}/access/ticket"
            
            data = urllib.parse.urlencode({
                'username': username,
                'password': password
            }).encode('utf-8')
            
            cookie_jar = CookieJar()
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(cookie_jar),
                urllib.request.HTTPSHandler(context=ssl_context)
            )
            
            request = urllib.request.Request(auth_url, data=data, method='POST')
            response = opener.open(request, timeout=10)
            result = json.loads(response.read().decode('utf-8'))['data']
            ticket = result['ticket']
            csrf_token = result['CSRFPreventionToken']
            
            def api_get(endpoint):
                url = f"{base_url}/{endpoint}"
                req = urllib.request.Request(url)
                req.add_header('Cookie', f'PVEAuthCookie={ticket}')
                req.add_header('CSRFPreventionToken', csrf_token)
                resp = opener.open(req, timeout=10)
                return json.loads(resp.read().decode('utf-8'))['data']
            
            # Ottieni VM QEMU
            node_vms = api_get(f'nodes/{node_name}/qemu')
            vms = []
            
            for vm in node_vms:
                vmid = vm.get('vmid', 0)
                status = vm.get('status', 'unknown')
                
                vm_data = {
                    'vm_id': vmid,
                    'name': vm.get('name', f'VM-{vmid}'),
                    'status': status,
                    'type': 'qemu',
                    'cpu_cores': vm.get('maxcpu', 0),
                    'memory_mb': int(vm.get('maxmem', 0) / (1024 * 1024)) if vm.get('maxmem') else 0,
                    'disk_total_gb': bytes_to_gib(vm.get('maxdisk', 0)),
                    'template': vm.get('template', False),
                }
                
                # Configurazione VM
                try:
                    config = api_get(f'nodes/{node_name}/qemu/{vmid}/config')
                    if config:
                        vm_data['cpu_cores'] = int(config.get('cores', 1))
                        vm_data['os_type'] = config.get('ostype', '')
                        
                        # Network interfaces
                        networks = []
                        for key in config:
                            if key.startswith('net'):
                                net_info = config[key]
                                if isinstance(net_info, str):
                                    networks.append(net_info)
                        vm_data['network_interfaces'] = networks
                except:
                    pass
                
                vms.append(vm_data)
            
            # Ottieni container LXC
            try:
                node_lxcs = api_get(f'nodes/{node_name}/lxc')
                for lxc in node_lxcs:
                    vmid = lxc.get('vmid', 0)
                    status = lxc.get('status', 'unknown')
                    
                    lxc_data = {
                        'vm_id': vmid,
                        'name': lxc.get('name', f'LXC-{vmid}'),
                        'status': status,
                        'type': 'lxc',
                        'cpu_cores': lxc.get('maxcpu', 0),
                        'memory_mb': int(lxc.get('maxmem', 0) / (1024 * 1024)) if lxc.get('maxmem') else 0,
                        'disk_total_gb': bytes_to_gib(lxc.get('maxdisk', 0)),
                        'template': lxc.get('template', False),
                    }
                    
                    # Configurazione LXC
                    try:
                        config = api_get(f'nodes/{node_name}/lxc/{vmid}/config')
                        if config:
                            lxc_data['cpu_cores'] = int(config.get('cores', 1))
                            lxc_data['os_type'] = config.get('ostype', '')
                            
                            # Network interfaces
                            networks = []
                            for key in config:
                                if key.startswith('net'):
                                    net_info = config[key]
                                    if isinstance(net_info, str):
                                        networks.append(net_info)
                            lxc_data['network_interfaces'] = networks
                    except:
                        pass
                    
                    vms.append(lxc_data)
            except Exception as e:
                logger.debug(f"Failed to collect LXC containers: {e}")
            
            return vms
            
        except Exception as e:
            logger.error(f"Error in VM API sync collection: {e}")
            return []
    
    async def _collect_storage_api(
        self,
        address: str,
        node_name: str,
        credentials: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Raccoglie storage via API Proxmox"""
        try:
            loop = asyncio.get_event_loop()
            storage_list = await loop.run_in_executor(
                self._executor,
                self._get_storage_api_sync,
                address,
                node_name,
                credentials
            )
            return storage_list or []
        except Exception as e:
            logger.error(f"Error collecting storage via API: {e}")
            return []
    
    def _get_storage_api_sync(
        self,
        address: str,
        node_name: str,
        credentials: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Implementazione sincrona per raccolta storage"""
        try:
            port = credentials.get("proxmox_port", 8006)
            username = credentials.get("username", "root@pam")
            password = credentials.get("password", "")
            
            base_url = f"https://{address}:{port}/api2/json"
            ssl_context = ssl._create_unverified_context()
            auth_url = f"{base_url}/access/ticket"
            
            data = urllib.parse.urlencode({
                'username': username,
                'password': password
            }).encode('utf-8')
            
            cookie_jar = CookieJar()
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(cookie_jar),
                urllib.request.HTTPSHandler(context=ssl_context)
            )
            
            request = urllib.request.Request(auth_url, data=data, method='POST')
            response = opener.open(request, timeout=10)
            result = json.loads(response.read().decode('utf-8'))['data']
            ticket = result['ticket']
            csrf_token = result['CSRFPreventionToken']
            
            def api_get(endpoint):
                url = f"{base_url}/{endpoint}"
                req = urllib.request.Request(url)
                req.add_header('Cookie', f'PVEAuthCookie={ticket}')
                req.add_header('CSRFPreventionToken', csrf_token)
                resp = opener.open(req, timeout=10)
                return json.loads(resp.read().decode('utf-8'))['data']
            
            # Ottieni lista storage
            storage_list = api_get(f'nodes/{node_name}/storage')
            storage_info_list = []
            
            for storage in storage_list:
                storage_info = {
                    'storage': storage.get('storage'),
                    'type': storage.get('type'),
                    'content': storage.get('content', []),
                    'enabled': storage.get('enabled', 1),
                    'shared': storage.get('shared', 0),
                }
                
                # Ottieni dettagli storage
                try:
                    storage_status = api_get(f'nodes/{node_name}/storage/{storage_info["storage"]}/status')
                    if storage_status:
                        storage_info['total'] = storage_status.get('total')
                        storage_info['used'] = storage_status.get('used')
                        storage_info['available'] = storage_status.get('avail')
                        storage_info['total_gb'] = bytes_to_gib(storage_status.get('total'))
                        storage_info['used_gb'] = bytes_to_gib(storage_status.get('used'))
                        storage_info['available_gb'] = bytes_to_gib(storage_status.get('avail'))
                        if storage_info['total'] and storage_info['used']:
                            storage_info['usage_percent'] = safe_round(
                                (storage_info['used'] / storage_info['total']) * 100, 2
                            )
                except Exception as e:
                    logger.debug(f"Failed to get storage status for {storage_info['storage']}: {e}")
                
                storage_info_list.append(storage_info)
            
            return storage_info_list
            
        except Exception as e:
            logger.error(f"Error in storage API sync collection: {e}")
            return []
    
    async def _collect_backups_api(
        self,
        address: str,
        node_name: str,
        vm_id: int,
        credentials: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Raccoglie backup via API Proxmox"""
        # Implementazione semplificata
        return []
    
    # ==========================================
    # SSH IMPLEMENTATIONS
    # ==========================================
    
    async def _collect_host_info_ssh(
        self,
        address: str,
        credentials: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Raccoglie info host via SSH usando comandi pvesh"""
        import paramiko
        
        username = credentials.get('username')
        password = credentials.get('password')
        ssh_port = credentials.get('ssh_port', 22)
        ssh_key = credentials.get('ssh_private_key')
        
        if not username or not password:
            logger.warning(f"SSH credentials incomplete for {address}: missing username or password")
            return None
        
        try:
            # Connetti via SSH
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Usa chiave privata se disponibile
            pkey = None
            if ssh_key:
                try:
                    from io import StringIO
                    pkey = paramiko.RSAKey.from_private_key(StringIO(ssh_key))
                except Exception as e:
                    logger.debug(f"Failed to load SSH key, using password: {e}")
            
            logger.info(f"Connecting to Proxmox {address}:{ssh_port} via SSH (user: {username})")
            client.connect(
                address,
                port=ssh_port,
                username=username,
                password=password,
                pkey=pkey,
                timeout=30
            )
            
            def exec_cmd(cmd: str) -> Optional[str]:
                """Esegue comando SSH"""
                try:
                    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
                    exit_status = stdout.channel.recv_exit_status()
                    if exit_status == 0:
                        return stdout.read().decode('utf-8').strip()
                    else:
                        error = stderr.read().decode('utf-8').strip()
                        logger.debug(f"Command failed: {cmd[:50]}... (exit: {exit_status}, error: {error})")
                        return None
                except Exception as e:
                    logger.debug(f"Error executing command {cmd[:50]}...: {e}")
                    return None
            
            # Ottieni nome nodo
            hostname = exec_cmd('hostname') or 'unknown'
            
            # Ottieni info nodo via pvesh
            node_info_cmd = f'pvesh get /nodes/{hostname}/status --output-format json'
            node_info_json = exec_cmd(node_info_cmd)
            
            if not node_info_json:
                logger.warning(f"Failed to get node info via pvesh for {address}")
                client.close()
                return None
            
            import json
            node_data = json.loads(node_info_json)
            
            # Ottieni versione Proxmox
            version_cmd = f'pvesh get /version --output-format json'
            version_json = exec_cmd(version_cmd)
            version_data = json.loads(version_json) if version_json else {}
            
            # Ottieni info CPU/memoria
            cpuinfo = exec_cmd('lscpu')
            meminfo = exec_cmd('grep MemTotal /proc/meminfo')
            
            # Parse CPU info
            cpu_model = None
            cpu_cores = None
            cpu_sockets = None
            cpu_threads = None
            if cpuinfo:
                for line in cpuinfo.split('\n'):
                    if 'Model name:' in line:
                        cpu_model = line.split(':', 1)[1].strip()
                    elif 'CPU(s):' in line:
                        try:
                            cpu_val = line.split(':')[1].strip()
                            # Gestisci formati come "0-31" (range) prendendo solo il primo numero
                            if '-' in cpu_val:
                                cpu_val = cpu_val.split('-')[0]
                            cpu_cores = int(cpu_val)
                        except (ValueError, IndexError):
                            pass
                    elif 'Socket(s):' in line:
                        try:
                            cpu_sockets = int(line.split(':')[1].strip())
                        except (ValueError, IndexError):
                            pass
                    elif 'Thread(s) per core:' in line:
                        try:
                            cpu_threads = int(line.split(':')[1].strip())
                        except (ValueError, IndexError):
                            pass
            
            # Parse memoria
            memory_total_gb = None
            if meminfo:
                try:
                    mem_kb = int(meminfo.split()[1])
                    memory_total_gb = round(mem_kb / 1024 / 1024, 2)
                except:
                    pass
            
            # Calcola CPU totale
            cpu_total_cores = cpu_cores
            
            # Ottieni uptime
            uptime_seconds = node_data.get('uptime', 0)
            uptime_human = seconds_to_human(uptime_seconds)
            
            # Ottieni load average
            load_avg = node_data.get('loadavg', [0, 0, 0])
            load_1m = load_avg[0] if len(load_avg) > 0 else None
            load_5m = load_avg[1] if len(load_avg) > 1 else None
            load_15m = load_avg[2] if len(load_avg) > 2 else None
            
            # Ottieni CPU usage
            cpu_usage = node_data.get('cpu', 0)
            
            # Ottieni memoria
            memory_used_gb = None
            memory_free_gb = None
            memory_usage_percent = None
            if memory_total_gb:
                mem_used = node_data.get('mem', 0) / (1024**3)  # Converti byte a GB
                memory_used_gb = round(mem_used, 2)
                memory_free_gb = round(memory_total_gb - mem_used, 2)
                memory_usage_percent = round((mem_used / memory_total_gb) * 100, 2) if memory_total_gb > 0 else None
            
            # Ottieni kernel version
            kernel_version = exec_cmd('uname -r')
            
            # Ottieni versione Proxmox
            proxmox_version = version_data.get('version', '')
            manager_version = version_data.get('release', '')
            
            # Ottieni info cluster
            cluster_name = None
            try:
                cluster_cmd = f'pvesh get /cluster/config --output-format json'
                cluster_json = exec_cmd(cluster_cmd)
                if cluster_json:
                    cluster_data = json.loads(cluster_json)
                    cluster_name = cluster_data.get('cluster', {}).get('name') if isinstance(cluster_data.get('cluster'), dict) else None
            except:
                pass
            
            # Ottieni subscription/license info
            license_status = None
            license_message = None
            license_level = None
            subscription_type = None
            try:
                sub_cmd = f'pvesh get /nodes/{hostname}/subscription --output-format json'
                sub_json = exec_cmd(sub_cmd)
                if sub_json:
                    sub_data = json.loads(sub_json)
                    license_status = sub_data.get('status')
                    license_message = sub_data.get('message')
                    license_level = sub_data.get('level')
                    subscription_type = sub_data.get('type')
            except:
                pass
            
            # Ottieni network interfaces dettagliate
            network_interfaces = []
            try:
                network_cmd = f'pvesh get /nodes/{hostname}/network --output-format json'
                network_json = exec_cmd(network_cmd)
                if network_json:
                    network_data = json.loads(network_json)
                    if isinstance(network_data, list):
                        network_interfaces = network_data
            except:
                pass
            
            # Ottieni lista storage (solo base, dettagli vengono raccolti separatamente)
            storage_list = []
            try:
                storage_cmd = f'pvesh get /nodes/{hostname}/storage --output-format json'
                storage_json = exec_cmd(storage_cmd)
                if storage_json:
                    storage_data = json.loads(storage_json)
                    if isinstance(storage_data, list):
                        for storage in storage_data:
                            storage_list.append({
                                'storage': storage.get('storage'),
                                'type': storage.get('type'),
                                'content': storage.get('content', []),
                            })
            except:
                pass
            
            client.close()
            
            host_info = {
                'node_name': hostname,
                'cluster_name': cluster_name,
                'proxmox_version': proxmox_version,
                'kernel_version': kernel_version,
                'cpu_model': cpu_model,
                'cpu_cores': cpu_cores,
                'cpu_sockets': cpu_sockets,
                'cpu_threads': cpu_threads,
                'cpu_total_cores': cpu_total_cores,
                'memory_total_gb': memory_total_gb,
                'memory_used_gb': memory_used_gb,
                'memory_free_gb': memory_free_gb,
                'memory_usage_percent': memory_usage_percent,
                'uptime_seconds': uptime_seconds,
                'uptime_human': uptime_human,
                'load_average_1m': load_1m,
                'load_average_5m': load_5m,
                'load_average_15m': load_15m,
                'cpu_usage_percent': cpu_usage,
                'license_status': license_status,
                'license_message': license_message,
                'license_level': license_level,
                'subscription_type': subscription_type,
                'network_interfaces': network_interfaces,
                'storage_list': storage_list,
            }
            
            logger.info(f"Successfully collected Proxmox host info via SSH for {address}: node={hostname}")
            return host_info
            
        except Exception as e:
            logger.error(f"Error collecting Proxmox host info via SSH for {address}: {e}", exc_info=True)
            return None
    
    async def _collect_vms_ssh(
        self,
        address: str,
        node_name: str,
        credentials: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Raccoglie VM e container via SSH usando pvesh"""
        import paramiko
        
        username = credentials.get('username')
        password = credentials.get('password')
        ssh_port = credentials.get('ssh_port', 22)
        ssh_key = credentials.get('ssh_private_key')
        
        if not username or not password:
            logger.warning(f"SSH credentials incomplete for {address}: missing username or password")
            return []
        
        try:
            # Connetti via SSH
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Usa chiave privata se disponibile
            pkey = None
            if ssh_key:
                try:
                    from io import StringIO
                    pkey = paramiko.RSAKey.from_private_key(StringIO(ssh_key))
                except Exception as e:
                    logger.debug(f"Failed to load SSH key, using password: {e}")
            
            logger.info(f"Connecting to Proxmox {address}:{ssh_port} via SSH for VM collection (user: {username})")
            client.connect(
                address,
                port=ssh_port,
                username=username,
                password=password,
                pkey=pkey,
                timeout=30
            )
            
            def exec_cmd(cmd: str) -> Optional[str]:
                """Esegue comando SSH"""
                try:
                    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
                    exit_status = stdout.channel.recv_exit_status()
                    if exit_status == 0:
                        return stdout.read().decode('utf-8').strip()
                    else:
                        error = stderr.read().decode('utf-8').strip()
                        logger.debug(f"Command failed: {cmd[:50]}... (exit: {exit_status}, error: {error})")
                        return None
                except Exception as e:
                    logger.debug(f"Error executing command {cmd[:50]}...: {e}")
                    return None
            
            vms = []
            
            # Raccogli VM QEMU
            qemu_cmd = f'pvesh get /nodes/{node_name}/qemu --output-format json'
            qemu_json = exec_cmd(qemu_cmd)
            
            if qemu_json:
                try:
                    import json
                    qemu_list = json.loads(qemu_json)
                    for vm in qemu_list:
                        vmid = vm.get('vmid', 0)
                        status = vm.get('status', 'unknown')
                        
                        vm_data = {
                            'vm_id': vmid,
                            'name': vm.get('name', f'VM-{vmid}'),
                            'status': status,
                            'type': 'qemu',
                            'cpu_cores': vm.get('maxcpu', 0),
                            'memory_mb': int(vm.get('maxmem', 0) / (1024 * 1024)) if vm.get('maxmem') else 0,
                            'disk_total_gb': bytes_to_gib(vm.get('maxdisk', 0)),
                            'template': vm.get('template', False),
                        }
                        
                        # Ottieni configurazione VM
                        config_cmd = f'pvesh get /nodes/{node_name}/qemu/{vmid}/config --output-format json'
                        config_json = exec_cmd(config_cmd)
                        if config_json:
                            try:
                                config = json.loads(config_json)
                                vm_data['cpu_cores'] = int(config.get('cores', vm_data['cpu_cores']))
                                vm_data['os_type'] = config.get('ostype', '')
                                
                                # Network interfaces
                                networks = []
                                for key in config:
                                    if key.startswith('net'):
                                        net_info = config[key]
                                        if isinstance(net_info, str):
                                            networks.append(net_info)
                                vm_data['network_interfaces'] = networks
                            except Exception as e:
                                logger.debug(f"Failed to parse VM config for {vmid}: {e}")
                        
                        vms.append(vm_data)
                except Exception as e:
                    logger.warning(f"Failed to parse QEMU VM list: {e}")
            
            # Raccogli container LXC
            lxc_cmd = f'pvesh get /nodes/{node_name}/lxc --output-format json'
            lxc_json = exec_cmd(lxc_cmd)
            
            if lxc_json:
                try:
                    import json
                    lxc_list = json.loads(lxc_json)
                    for lxc in lxc_list:
                        vmid = lxc.get('vmid', 0)
                        status = lxc.get('status', 'unknown')
                        
                        lxc_data = {
                            'vm_id': vmid,
                            'name': lxc.get('name', f'LXC-{vmid}'),
                            'status': status,
                            'type': 'lxc',
                            'cpu_cores': lxc.get('maxcpu', 0),
                            'memory_mb': int(lxc.get('maxmem', 0) / (1024 * 1024)) if lxc.get('maxmem') else 0,
                            'disk_total_gb': bytes_to_gib(lxc.get('maxdisk', 0)),
                            'template': lxc.get('template', False),
                        }
                        
                        # Ottieni configurazione LXC
                        config_cmd = f'pvesh get /nodes/{node_name}/lxc/{vmid}/config --output-format json'
                        config_json = exec_cmd(config_cmd)
                        if config_json:
                            try:
                                config = json.loads(config_json)
                                lxc_data['cpu_cores'] = int(config.get('cores', lxc_data['cpu_cores']))
                                lxc_data['os_type'] = config.get('ostype', '')
                                
                                # Network interfaces
                                networks = []
                                for key in config:
                                    if key.startswith('net'):
                                        net_info = config[key]
                                        if isinstance(net_info, str):
                                            networks.append(net_info)
                                lxc_data['network_interfaces'] = networks
                            except Exception as e:
                                logger.debug(f"Failed to parse LXC config for {vmid}: {e}")
                        
                        vms.append(lxc_data)
                except Exception as e:
                    logger.warning(f"Failed to parse LXC container list: {e}")
            
            client.close()
            logger.info(f"Successfully collected {len(vms)} VMs/containers via SSH for {address}")
            return vms
            
        except Exception as e:
            logger.error(f"Error collecting VMs via SSH for {address}: {e}", exc_info=True)
            return []
    
    async def _collect_storage_ssh(
        self,
        address: str,
        node_name: str,
        credentials: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Raccoglie storage via SSH usando pvesh"""
        import paramiko
        
        username = credentials.get('username')
        password = credentials.get('password')
        ssh_port = credentials.get('ssh_port', 22)
        ssh_key = credentials.get('ssh_private_key')
        
        if not username or not password:
            logger.warning(f"SSH credentials incomplete for {address}: missing username or password")
            return []
        
        try:
            # Connetti via SSH
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Usa chiave privata se disponibile
            pkey = None
            if ssh_key:
                try:
                    from io import StringIO
                    pkey = paramiko.RSAKey.from_private_key(StringIO(ssh_key))
                except Exception as e:
                    logger.debug(f"Failed to load SSH key, using password: {e}")
            
            logger.info(f"Connecting to Proxmox {address}:{ssh_port} via SSH for storage collection (user: {username})")
            client.connect(
                address,
                port=ssh_port,
                username=username,
                password=password,
                pkey=pkey,
                timeout=30
            )
            
            def exec_cmd(cmd: str) -> Optional[str]:
                """Esegue comando SSH"""
                try:
                    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
                    exit_status = stdout.channel.recv_exit_status()
                    if exit_status == 0:
                        return stdout.read().decode('utf-8').strip()
                    else:
                        error = stderr.read().decode('utf-8').strip()
                        logger.debug(f"Command failed: {cmd[:50]}... (exit: {exit_status}, error: {error})")
                        return None
                except Exception as e:
                    logger.debug(f"Error executing command {cmd[:50]}...: {e}")
                    return None
            
            storage_list = []
            
            # Raccogli lista storage
            storage_cmd = f'pvesh get /nodes/{node_name}/storage --output-format json'
            storage_json = exec_cmd(storage_cmd)
            
            if not storage_json:
                logger.warning(f"Failed to get storage list via pvesh for {address}")
                client.close()
                return []
            
            import json
            storage_data_list = json.loads(storage_json)
            
            for storage in storage_data_list:
                storage_name = storage.get('storage')
                if not storage_name:
                    continue
                
                storage_info = {
                    'storage': storage_name,
                    'type': storage.get('type'),
                    'content': storage.get('content', []),
                    'enabled': storage.get('enabled', 1),
                    'shared': storage.get('shared', 0),
                }
                
                # Ottieni dettagli storage status
                status_cmd = f'pvesh get /nodes/{node_name}/storage/{storage_name}/status --output-format json'
                status_json = exec_cmd(status_cmd)
                
                if status_json:
                    try:
                        status_data = json.loads(status_json)
                        storage_info['total'] = status_data.get('total')
                        storage_info['used'] = status_data.get('used')
                        storage_info['available'] = status_data.get('avail')
                        storage_info['total_gb'] = bytes_to_gib(status_data.get('total'))
                        storage_info['used_gb'] = bytes_to_gib(status_data.get('used'))
                        storage_info['available_gb'] = bytes_to_gib(status_data.get('avail'))
                        if storage_info['total'] and storage_info['used']:
                            storage_info['usage_percent'] = safe_round(
                                (storage_info['used'] / storage_info['total']) * 100, 2
                            )
                    except Exception as e:
                        logger.debug(f"Failed to parse storage status for {storage_name}: {e}")
                
                storage_list.append(storage_info)
            
            client.close()
            logger.info(f"Successfully collected {len(storage_list)} storage entries via SSH for {address}")
            return storage_list
            
        except Exception as e:
            logger.error(f"Error collecting storage via SSH for {address}: {e}", exc_info=True)
            return []


# Singleton instance
_proxmox_collector: Optional[ProxmoxCollector] = None


def get_proxmox_collector() -> ProxmoxCollector:
    """Ottiene istanza singleton del collector Proxmox"""
    global _proxmox_collector
    if _proxmox_collector is None:
        _proxmox_collector = ProxmoxCollector()
    return _proxmox_collector

