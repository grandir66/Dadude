"""
DaDude - Device Monitoring Service
Gestisce il monitoraggio periodico dei dispositivi (ICMP, TCP, Agent)
"""
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..config import Settings, get_settings
from ..models.database import init_db, get_session
from ..models.inventory import InventoryDevice
from ..services.customer_service import get_customer_service
from ..services.device_probe_service import get_device_probe_service
from ..services.websocket_hub import get_websocket_hub
from ..services.agent_service import get_agent_service
from ..routers.agents import CommandType


class DeviceMonitoringService:
    """Servizio per monitoraggio periodico dispositivi"""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.scheduler = AsyncIOScheduler()
        self.probe_service = get_device_probe_service()
        self.customer_service = get_customer_service()
        self.agent_service = get_agent_service()
        self.check_interval = 30  # Secondi tra un check e l'altro
        
    async def check_device(self, device: InventoryDevice) -> Dict[str, Any]:
        """Esegue un check di monitoraggio su un dispositivo"""
        result = {
            "device_id": device.id,
            "device_ip": device.primary_ip,
            "monitoring_type": device.monitoring_type,
            "success": False,
            "status": "unknown",
            "error": None,
        }
        
        try:
            if device.monitoring_type == "icmp":
                # Ping check
                if device.monitoring_agent_id:
                    # Check via agent remoto
                    agent = self.customer_service.get_agent(device.monitoring_agent_id, include_password=True)
                    if agent and agent.agent_type == "docker":
                        # Via Docker agent
                        ws_hub = get_websocket_hub()
                        ws_agent_id = f"agent-{agent.dude_agent_id}" if hasattr(agent, 'dude_agent_id') else None
                        
                        if ws_agent_id and ws_agent_id in ws_hub.agents:
                            ping_result = await ws_hub.send_command(
                                ws_agent_id,
                                CommandType.PING,
                                params={"target": device.primary_ip, "count": 3},
                                timeout=10.0
                            )
                            if ping_result.status == "success":
                                result["success"] = True
                                result["status"] = "up" if ping_result.data.get("packet_loss", 100) < 100 else "down"
                            else:
                                result["error"] = ping_result.error or "Ping failed"
                        else:
                            # Fallback a ping locale
                            result["success"] = True
                            result["status"] = "up" if await self.probe_service.probe_port(device.primary_ip, 0) else "down"
                    else:
                        # MikroTik agent - usa ping locale per ora
                        result["success"] = True
                        result["status"] = "up" if await self._ping_check(device.primary_ip) else "down"
                else:
                    # Ping locale
                    result["success"] = True
                    result["status"] = "up" if await self._ping_check(device.primary_ip) else "down"
                    
            elif device.monitoring_type == "tcp":
                # TCP port check
                port = device.monitoring_port or 80
                
                if device.monitoring_agent_id:
                    # Check via agent remoto
                    agent = self.customer_service.get_agent(device.monitoring_agent_id, include_password=True)
                    if agent and agent.agent_type == "docker":
                        # Via Docker agent
                        ws_hub = get_websocket_hub()
                        ws_agent_id = f"agent-{agent.dude_agent_id}" if hasattr(agent, 'dude_agent_id') else None
                        
                        if ws_agent_id and ws_agent_id in ws_hub.agents:
                            port_result = await ws_hub.send_command(
                                ws_agent_id,
                                CommandType.SCAN_PORTS,
                                params={"target": device.primary_ip, "ports": [port]},
                                timeout=10.0
                            )
                            if port_result.status == "success":
                                open_ports = port_result.data.get("open_ports", [])
                                result["success"] = True
                                result["status"] = "up" if any(p.get("port") == port for p in open_ports) else "down"
                            else:
                                result["error"] = port_result.error or "Port check failed"
                        else:
                            # Fallback a check locale
                            result["success"] = True
                            result["status"] = "up" if await self.probe_service.probe_port(device.primary_ip, port) else "down"
                    else:
                        # MikroTik agent - usa check locale per ora
                        result["success"] = True
                        result["status"] = "up" if await self.probe_service.probe_port(device.primary_ip, port) else "down"
                else:
                    # Check locale
                    result["success"] = True
                    result["status"] = "up" if await self.probe_service.probe_port(device.primary_ip, port) else "down"
                    
            elif device.monitoring_type == "agent":
                # Agent-based monitoring (ICMP o TCP a seconda di monitoring_port)
                agent = self.customer_service.get_agent(device.monitoring_agent_id, include_password=True) if device.monitoring_agent_id else None
                
                if not agent:
                    result["error"] = "Agent non trovato"
                    return result
                
                if agent.agent_type == "docker":
                    ws_hub = get_websocket_hub()
                    ws_agent_id = f"agent-{agent.dude_agent_id}" if hasattr(agent, 'dude_agent_id') else None
                    
                    if ws_agent_id and ws_agent_id in ws_hub.agents:
                        if device.monitoring_port:
                            # TCP check
                            port_result = await ws_hub.send_command(
                                ws_agent_id,
                                CommandType.SCAN_PORTS,
                                params={"target": device.primary_ip, "ports": [device.monitoring_port]},
                                timeout=10.0
                            )
                            if port_result.status == "success":
                                open_ports = port_result.data.get("open_ports", [])
                                result["success"] = True
                                result["status"] = "up" if any(p.get("port") == device.monitoring_port for p in open_ports) else "down"
                            else:
                                result["error"] = port_result.error or "Port check failed"
                        else:
                            # ICMP check
                            ping_result = await ws_hub.send_command(
                                ws_agent_id,
                                CommandType.PING,
                                params={"target": device.primary_ip, "count": 3},
                                timeout=10.0
                            )
                            if ping_result.status == "success":
                                result["success"] = True
                                result["status"] = "up" if ping_result.data.get("packet_loss", 100) < 100 else "down"
                            else:
                                result["error"] = ping_result.error or "Ping failed"
                    else:
                        result["error"] = "Agent non connesso via WebSocket"
                else:
                    result["error"] = "Agent type non supportato per monitoring"
                    
        except Exception as e:
            logger.error(f"Error checking device {device.primary_ip}: {e}")
            result["error"] = str(e)
            result["status"] = "unknown"
        
        return result
    
    async def _ping_check(self, address: str) -> bool:
        """Esegue un ping check locale"""
        try:
            import subprocess
            import platform
            
            # Comando ping dipende dal sistema operativo
            if platform.system().lower() == "windows":
                cmd = ["ping", "-n", "1", "-w", "1000", address]
            else:
                cmd = ["ping", "-c", "1", "-W", "1", address]
            
            result = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, timeout=2)
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"Ping check failed for {address}: {e}")
            return False
    
    async def check_all_monitored_devices(self):
        """Esegue check su tutti i dispositivi monitorati"""
        settings = get_settings()
        db_url = settings.database_url
        engine = init_db(db_url)
        session = get_session(engine)
        
        try:
            # Carica tutti i dispositivi con monitoraggio attivo
            devices = session.query(InventoryDevice).filter(
                InventoryDevice.active == True,
                InventoryDevice.monitored == True,
                InventoryDevice.monitoring_type != "none",
                InventoryDevice.monitoring_type != "mikrotik"  # Netwatch gestito da MikroTik stesso
            ).all()
            
            logger.debug(f"Checking {len(devices)} monitored devices...")
            
            # Esegui check in parallelo (max 10 alla volta)
            semaphore = asyncio.Semaphore(10)
            
            async def check_with_semaphore(device):
                async with semaphore:
                    return await self.check_device(device)
            
            tasks = [check_with_semaphore(device) for device in devices]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Aggiorna database con risultati
            for device, result in zip(devices, results):
                if isinstance(result, Exception):
                    logger.error(f"Error checking device {device.primary_ip}: {result}")
                    continue
                
                if result.get("success"):
                    old_status = device.status
                    new_status = result.get("status", "unknown")
                    
                    # Aggiorna status
                    device.status = new_status
                    device.last_check = datetime.utcnow()
                    
                    if new_status == "up":
                        device.last_seen = datetime.utcnow()
                    
                    # Log cambio stato
                    if old_status != new_status:
                        logger.info(f"Device {device.primary_ip} status changed: {old_status} -> {new_status}")
                else:
                    logger.warning(f"Device {device.primary_ip} check failed: {result.get('error')}")
                    device.status = "unknown"
                    device.last_check = datetime.utcnow()
            
            session.commit()
            logger.debug(f"Completed monitoring check for {len(devices)} devices")
            
        except Exception as e:
            logger.error(f"Error in check_all_monitored_devices: {e}")
            session.rollback()
        finally:
            session.close()
    
    def start(self):
        """Avvia scheduler monitoring"""
        logger.info(f"Starting device monitoring scheduler (interval: {self.check_interval}s)")
        
        self.scheduler.add_job(
            self.check_all_monitored_devices,
            trigger=IntervalTrigger(seconds=self.check_interval),
            id="monitor_devices",
            name="Monitor Devices",
        )
        
        self.scheduler.start()
        logger.success("Device monitoring scheduler started")
    
    def stop(self):
        """Ferma scheduler"""
        self.scheduler.shutdown()
        logger.info("Device monitoring scheduler stopped")


# Singleton
_monitoring_service: Optional[DeviceMonitoringService] = None


def get_monitoring_service() -> DeviceMonitoringService:
    """Ottiene istanza singleton del monitoring service"""
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = DeviceMonitoringService()
    return _monitoring_service

