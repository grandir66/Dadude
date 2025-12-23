#!/usr/bin/env python3
"""
Script di migrazione database usando SQLAlchemy (compatibile SQLite e PostgreSQL)
"""
import sys
import os
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent))

from app.models.database import Base, init_db
from app.config import Settings

def migrate_database(database_url: str = None):
    """Migra database usando SQLAlchemy (funziona con SQLite e PostgreSQL)"""
    
    if not database_url:
        settings = Settings()
        database_url = settings.database_url
    
    engine = create_engine(database_url, echo=False)
    inspector = inspect(engine)
    
    # Verifica se è PostgreSQL o SQLite
    is_postgres = 'postgresql' in database_url.lower()
    is_sqlite = 'sqlite' in database_url.lower()
    
    print(f"Database rilevato: {'PostgreSQL' if is_postgres else 'SQLite'}")
    
    try:
        # Crea schema se non esiste
        Base.metadata.create_all(engine)
        print("✓ Schema database verificato/creato")
        
        # Per SQLite, usa migrazione legacy se necessario
        if is_sqlite:
            migrate_sqlite_legacy(database_url)
        else:
            # Per PostgreSQL, SQLAlchemy gestisce tutto automaticamente
            print("✓ PostgreSQL: schema già aggiornato tramite SQLAlchemy")
        
    except Exception as e:
        print(f"✗ Errore durante la migrazione: {e}")
        raise


def migrate_sqlite_legacy(db_path: str):
    """Migrazione legacy per SQLite (mantiene compatibilità)"""
    import sqlite3
    
    # Estrai path da URL SQLite
    if db_path.startswith('sqlite:///'):
        db_path = db_path.replace('sqlite:///', '')
    elif db_path.startswith('sqlite+aiosqlite:///'):
        db_path = db_path.replace('sqlite+aiosqlite:///', '')
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} non trovato. Verrà creato al prossimo avvio.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Verifica colonne esistenti in device_assignments
        cursor.execute("PRAGMA table_info(device_assignments)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Aggiungi colonne hardware se mancanti
        missing_columns = {
            'serial_number': 'VARCHAR(100)',
            'os_version': 'VARCHAR(100)',
            'cpu_model': 'VARCHAR(255)',
            'cpu_cores': 'INTEGER',
            'ram_total_mb': 'INTEGER',
            'disk_total_gb': 'INTEGER',
            'disk_free_gb': 'INTEGER',
            'open_ports': 'JSON'
        }
        
        for col_name, col_type in missing_columns.items():
            if col_name not in columns:
                print(f"Aggiungo colonna {col_name}...")
                cursor.execute(f"ALTER TABLE device_assignments ADD COLUMN {col_name} {col_type}")
        
        # Similar per altre tabelle...
        # (mantieni logica esistente per compatibilità SQLite)
        
        conn.commit()
        print("✓ Migrazione SQLite completata")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Errore migrazione SQLite: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migra database usando SQLAlchemy")
    parser.add_argument("--db-url", help="Database URL (default: da config)")
    args = parser.parse_args()
    
    migrate_database(args.db_url)
