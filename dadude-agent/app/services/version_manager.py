"""
Version Manager per DaDude Agent
Gestisce versioni multiple con backup e rollback automatico
"""
import os
import shutil
import subprocess
import json
import logging
import hashlib
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class VersionManager:
    """
    Gestisce versioni multiple dell'agent con backup e rollback automatico.
    """
    
    def __init__(self, agent_dir: str = "/opt/dadude-agent"):
        self.agent_dir = Path(agent_dir)
        self.versions_dir = self.agent_dir / "versions"
        self.backups_dir = self.agent_dir / "backups"
        self.current_version_file = self.agent_dir / ".current_version"
        self.bad_versions_file = self.agent_dir / ".bad_versions"
        self.health_check_timeout = 300  # 5 minuti per verificare connessione
        
        # Crea directory se non esistono
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
    
    def get_current_version(self) -> Optional[str]:
        """Ottiene la versione corrente."""
        if self.current_version_file.exists():
            try:
                with open(self.current_version_file, 'r') as f:
                    data = json.load(f)
                    return data.get("version")
            except Exception as e:
                logger.warning(f"Could not read current version: {e}")
        return None
    
    def get_current_commit(self) -> Optional[str]:
        """Ottiene il commit hash corrente."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.agent_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.warning(f"Could not get current commit: {e}")
        return None
    
    def is_bad_version(self, version: str) -> bool:
        """Verifica se una versione è marcata come bad."""
        if not self.bad_versions_file.exists():
            return False
        
        try:
            with open(self.bad_versions_file, 'r') as f:
                bad_versions = json.load(f)
                return version in bad_versions.get("versions", [])
        except Exception as e:
            logger.warning(f"Could not read bad versions: {e}")
        return False
    
    def mark_version_bad(self, version: str):
        """Marca una versione come bad."""
        bad_versions = []
        if self.bad_versions_file.exists():
            try:
                with open(self.bad_versions_file, 'r') as f:
                    data = json.load(f)
                    bad_versions = data.get("versions", [])
            except Exception:
                pass
        
        if version not in bad_versions:
            bad_versions.append(version)
            with open(self.bad_versions_file, 'w') as f:
                json.dump({"versions": bad_versions}, f, indent=2)
            logger.warning(f"Marked version {version} as bad")
    
    def backup_current_version(self) -> Optional[str]:
        """
        Crea un backup della versione corrente.
        Ritorna il path del backup o None se fallisce.
        """
        try:
            current_commit = self.get_current_commit()
            if not current_commit:
                logger.warning("Could not get current commit for backup")
                return None
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{current_commit[:8]}_{timestamp}"
            backup_path = self.backups_dir / backup_name
            
            logger.info(f"Creating backup: {backup_name}")
            
            # Copia la directory app (escludendo versioni e backup)
            if (self.agent_dir / "app").exists():
                shutil.copytree(
                    self.agent_dir / "app",
                    backup_path / "app",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
                )
            
            # Copia docker-compose.yml se esiste
            compose_file = self.agent_dir / "dadude-agent" / "docker-compose.yml"
            if compose_file.exists():
                backup_path.mkdir(parents=True, exist_ok=True)
                shutil.copy2(compose_file, backup_path / "docker-compose.yml")
            
            # Salva metadata del backup
            metadata = {
                "commit": current_commit,
                "timestamp": timestamp,
                "backup_path": str(backup_path),
            }
            with open(backup_path / "metadata.json", 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Backup created: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}", exc_info=True)
            return None
    
    def restore_backup(self, backup_path: str) -> bool:
        """
        Ripristina un backup.
        """
        try:
            backup_dir = Path(backup_path)
            if not backup_dir.exists():
                logger.error(f"Backup path does not exist: {backup_path}")
                return False
            
            logger.info(f"Restoring backup: {backup_path}")
            
            # Ripristina app directory
            app_backup = backup_dir / "app"
            if app_backup.exists():
                app_target = self.agent_dir / "app"
                if app_target.exists():
                    shutil.rmtree(app_target)
                shutil.copytree(app_backup, app_target)
            
            # Ripristina docker-compose.yml se presente
            compose_backup = backup_dir / "docker-compose.yml"
            if compose_backup.exists():
                compose_target = self.agent_dir / "dadude-agent" / "docker-compose.yml"
                compose_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(compose_backup, compose_target)
            
            logger.info("Backup restored successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}", exc_info=True)
            return False
    
    def check_for_updates(self) -> Optional[str]:
        """
        Verifica se ci sono aggiornamenti disponibili.
        Ritorna il commit hash della nuova versione o None.
        """
        try:
            # Verifica che siamo in un repository git
            if not (self.agent_dir / ".git").exists():
                logger.warning("Not a git repository, cannot check for updates")
                return None
            
            # Fetch latest
            fetch_result = subprocess.run(
                ["git", "fetch", "origin", "main"],
                cwd=self.agent_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            if fetch_result.returncode != 0:
                logger.warning(f"Git fetch failed: {fetch_result.stderr}")
                return None
            
            # Verifica se ci sono commit nuovi
            current_commit = self.get_current_commit()
            result = subprocess.run(
                ["git", "rev-parse", "origin/main"],
                cwd=self.agent_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode != 0:
                return None
            
            latest_commit = result.stdout.strip()
            
            if current_commit != latest_commit:
                logger.info(f"Update available: {current_commit[:8]} -> {latest_commit[:8]}")
                return latest_commit
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to check for updates: {e}", exc_info=True)
            return None
    
    def update_to_version(self, commit_hash: str) -> bool:
        """
        Aggiorna alla versione specificata.
        """
        try:
            logger.info(f"Updating to commit {commit_hash[:8]}")
            
            # Backup versione corrente
            backup_path = self.backup_current_version()
            if not backup_path:
                logger.error("Failed to create backup, aborting update")
                return False
            
            # Reset a origin/main
            reset_result = subprocess.run(
                ["git", "reset", "--hard", "origin/main"],
                cwd=self.agent_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            if reset_result.returncode != 0:
                logger.error(f"Git reset failed: {reset_result.stderr}")
                # Ripristina backup
                self.restore_backup(backup_path)
                return False
            
            # Verifica che il commit sia corretto
            new_commit = self.get_current_commit()
            if new_commit != commit_hash:
                logger.warning(f"Commit mismatch: expected {commit_hash[:8]}, got {new_commit[:8] if new_commit else 'None'}")
            
            # Salva nuova versione
            with open(self.current_version_file, 'w') as f:
                json.dump({
                    "version": commit_hash,
                    "updated_at": datetime.now().isoformat(),
                    "backup_path": backup_path,
                }, f, indent=2)
            
            logger.info(f"Updated to commit {commit_hash[:8]}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update: {e}", exc_info=True)
            return False
    
    def rollback_to_backup(self, backup_path: Optional[str] = None) -> bool:
        """
        Ripristina l'ultimo backup.
        """
        try:
            if backup_path:
                return self.restore_backup(backup_path)
            
            # Trova l'ultimo backup dal metadata corrente
            if self.current_version_file.exists():
                try:
                    with open(self.current_version_file, 'r') as f:
                        data = json.load(f)
                        backup_path = data.get("backup_path")
                        if backup_path and Path(backup_path).exists():
                            return self.restore_backup(backup_path)
                except Exception as e:
                    logger.warning(f"Could not read backup path from metadata: {e}")
            
            # Cerca l'ultimo backup nella directory
            backups = sorted(self.backups_dir.glob("backup_*"), key=os.path.getmtime, reverse=True)
            if backups:
                return self.restore_backup(str(backups[0]))
            
            logger.error("No backup found to restore")
            return False
            
        except Exception as e:
            logger.error(f"Failed to rollback: {e}", exc_info=True)
            return False

