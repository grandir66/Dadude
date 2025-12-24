#!/usr/bin/env python3
"""
Script di migrazione per aggiungere campi agent Docker e ARP gateway
"""
import sys
import os
from pathlib import Path
from sqlalchemy import create_engine, inspect, text

sys.path.insert(0, str(Path(__file__).parent))
from app.models.database import Base, init_db
from app.config import Settings

def migrate_agent_fields(database_url: str = None):
    """Aggiunge campi per Docker agent e ARP gateway"""
    
    if not database_url:
        settings = Settings()
        database_url = settings.database_url
    
    engine = create_engine(database_url, echo=False)
    inspector = inspect(engine)
    
    # Verifica se è PostgreSQL o SQLite
    is_postgres = 'postgresql' in database_url.lower()
    
    try:
        # Verifica colonne esistenti
        if 'agent_assignments' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('agent_assignments')]
            
            # Colonne da aggiungere
            new_columns = {
                'docker_agent_id': 'VARCHAR(8)',
                'arp_gateway_agent_id': 'VARCHAR(8)',
                'arp_gateway_snmp_address': 'VARCHAR(50)',
                'arp_gateway_snmp_community': 'VARCHAR(100)',
                'arp_gateway_snmp_version': 'VARCHAR(10)',
            }
            
            with engine.connect() as conn:
                for col_name, col_type in new_columns.items():
                    if col_name not in columns:
                        print(f"Aggiungo colonna {col_name}...")
                        if is_postgres:
                            # PostgreSQL
                            if col_name in ['docker_agent_id', 'arp_gateway_agent_id']:
                                # Foreign key columns
                                conn.execute(text(f"ALTER TABLE agent_assignments ADD COLUMN {col_name} VARCHAR(8)"))
                                conn.execute(text(f"ALTER TABLE agent_assignments ADD CONSTRAINT fk_{col_name} FOREIGN KEY ({col_name}) REFERENCES agent_assignments(id)"))
                            else:
                                conn.execute(text(f"ALTER TABLE agent_assignments ADD COLUMN {col_name} {col_type}"))
                        else:
                            # SQLite
                            conn.execute(text(f"ALTER TABLE agent_assignments ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                        print(f"✓ Colonna {col_name} aggiunta")
                    else:
                        print(f"  Colonna {col_name} già esistente")
        
        print("\n✓ Migrazione completata")
        
    except Exception as e:
        print(f"Errore migrazione: {e}")
        raise

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", help="Database URL")
    args = parser.parse_args()
    migrate_agent_fields(args.db_url)

