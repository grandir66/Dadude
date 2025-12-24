#!/usr/bin/env python3
import sys
sys.path.insert(0, '/app')
from app.models.database import init_db
from app.config import get_settings
from sqlalchemy import text, inspect

settings = get_settings()
engine = init_db(settings.database_url)
insp = inspect(engine)
columns = [col['name'] for col in insp.get_columns('agent_assignments')]

new_cols = {
    'docker_agent_id': 'VARCHAR(8)',
    'arp_gateway_agent_id': 'VARCHAR(8)',
    'arp_gateway_snmp_address': 'VARCHAR(50)',
    'arp_gateway_snmp_community': 'VARCHAR(100)',
    'arp_gateway_snmp_version': 'VARCHAR(10)',
}

with engine.connect() as conn:
    for col, col_type in new_cols.items():
        if col not in columns:
            conn.execute(text(f'ALTER TABLE agent_assignments ADD COLUMN {col} {col_type}'))
            conn.commit()
            print(f'Added {col}')
        else:
            print(f'{col} already exists')

