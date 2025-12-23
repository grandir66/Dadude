"""Initial schema migration - all DaDude tables

Revision ID: 001
Revises:
Create Date: 2024-12-18

This migration creates all tables from the existing SQLite schema
for PostgreSQL compatibility.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================
    # CUSTOMERS TABLE
    # ===========================================
    op.create_table('customers',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('contact_name', sa.String(length=255), nullable=True),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('contact_phone', sa.String(length=50), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_customer_code', 'customers', ['code'], unique=True)

    # ===========================================
    # NETWORKS TABLE
    # ===========================================
    op.create_table('networks',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('customer_id', sa.String(length=8), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('network_type', sa.String(length=50), nullable=True, default='lan'),
        sa.Column('ip_network', sa.String(length=50), nullable=False),
        sa.Column('gateway', sa.String(length=50), nullable=True),
        sa.Column('vlan_id', sa.Integer(), nullable=True),
        sa.Column('vlan_name', sa.String(length=100), nullable=True),
        sa.Column('dns_primary', sa.String(length=50), nullable=True),
        sa.Column('dns_secondary', sa.String(length=50), nullable=True),
        sa.Column('dhcp_start', sa.String(length=50), nullable=True),
        sa.Column('dhcp_end', sa.String(length=50), nullable=True),
        sa.Column('gateway_agent_id', sa.String(length=8), nullable=True),
        sa.Column('gateway_snmp_address', sa.String(length=50), nullable=True),
        sa.Column('gateway_snmp_community', sa.String(length=100), nullable=True),
        sa.Column('gateway_snmp_version', sa.String(length=10), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_network_customer', 'networks', ['customer_id'])
    op.create_index('idx_network_vlan', 'networks', ['vlan_id'])

    # ===========================================
    # CREDENTIALS TABLE
    # ===========================================
    op.create_table('credentials',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('customer_id', sa.String(length=8), nullable=True),
        sa.Column('is_global', sa.Boolean(), nullable=True, default=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('credential_type', sa.String(length=50), nullable=True, default='device'),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('password', sa.String(length=255), nullable=True),
        sa.Column('ssh_port', sa.Integer(), nullable=True),
        sa.Column('ssh_private_key', sa.Text(), nullable=True),
        sa.Column('ssh_passphrase', sa.String(length=255), nullable=True),
        sa.Column('ssh_key_type', sa.String(length=20), nullable=True),
        sa.Column('snmp_community', sa.String(length=100), nullable=True),
        sa.Column('snmp_version', sa.String(length=10), nullable=True),
        sa.Column('snmp_port', sa.Integer(), nullable=True),
        sa.Column('snmp_security_level', sa.String(length=20), nullable=True),
        sa.Column('snmp_auth_protocol', sa.String(length=20), nullable=True),
        sa.Column('snmp_priv_protocol', sa.String(length=20), nullable=True),
        sa.Column('snmp_auth_password', sa.String(length=255), nullable=True),
        sa.Column('snmp_priv_password', sa.String(length=255), nullable=True),
        sa.Column('wmi_domain', sa.String(length=255), nullable=True),
        sa.Column('wmi_namespace', sa.String(length=255), nullable=True),
        sa.Column('mikrotik_api_port', sa.Integer(), nullable=True),
        sa.Column('mikrotik_api_ssl', sa.Boolean(), nullable=True),
        sa.Column('api_key', sa.String(length=500), nullable=True),
        sa.Column('api_secret', sa.String(length=500), nullable=True),
        sa.Column('api_endpoint', sa.String(length=500), nullable=True),
        sa.Column('vpn_type', sa.String(length=50), nullable=True),
        sa.Column('vpn_config', sa.Text(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=True, default=False),
        sa.Column('device_filter', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_credential_customer', 'credentials', ['customer_id'])
    op.create_index('idx_credential_type', 'credentials', ['credential_type'])

    # ===========================================
    # CUSTOMER CREDENTIAL LINKS TABLE
    # ===========================================
    op.create_table('customer_credential_links',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('customer_id', sa.String(length=8), nullable=False),
        sa.Column('credential_id', sa.String(length=8), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=True, default=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['credential_id'], ['credentials.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('customer_id', 'credential_id', name='uq_customer_credential')
    )
    op.create_index('idx_cred_link_customer', 'customer_credential_links', ['customer_id'])
    op.create_index('idx_cred_link_credential', 'customer_credential_links', ['credential_id'])

    # ===========================================
    # AGENT ASSIGNMENTS TABLE
    # ===========================================
    op.create_table('agent_assignments',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('dude_agent_id', sa.String(length=50), nullable=True),
        sa.Column('customer_id', sa.String(length=8), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('address', sa.String(length=255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=True, default=8728),
        sa.Column('status', sa.String(length=20), nullable=True, default='unknown'),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('version', sa.String(length=50), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('site_name', sa.String(length=100), nullable=True),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('password', sa.String(length=255), nullable=True),
        sa.Column('use_ssl', sa.Boolean(), nullable=True, default=False),
        sa.Column('connection_type', sa.String(length=20), nullable=True, default='api'),
        sa.Column('ssh_port', sa.Integer(), nullable=True, default=22),
        sa.Column('ssh_key', sa.Text(), nullable=True),
        sa.Column('agent_type', sa.String(length=20), nullable=True, default='mikrotik'),
        sa.Column('agent_api_port', sa.Integer(), nullable=True, default=8080),
        sa.Column('agent_token', sa.String(length=255), nullable=True),
        sa.Column('agent_url', sa.String(length=255), nullable=True),
        sa.Column('dns_server', sa.String(length=255), nullable=True),
        sa.Column('default_scan_type', sa.String(length=20), nullable=True, default='ping'),
        sa.Column('auto_add_devices', sa.Boolean(), nullable=True, default=False),
        sa.Column('assigned_networks', postgresql.JSONB(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_agent_customer', 'agent_assignments', ['customer_id'])
    op.create_index('idx_agent_dude_id', 'agent_assignments', ['dude_agent_id'])

    # ===========================================
    # DEVICE ASSIGNMENTS TABLE
    # ===========================================
    op.create_table('device_assignments',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('dude_device_id', sa.String(length=50), nullable=False),
        sa.Column('dude_device_name', sa.String(length=255), nullable=True),
        sa.Column('customer_id', sa.String(length=8), nullable=False),
        sa.Column('local_name', sa.String(length=255), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=100), nullable=True),
        sa.Column('primary_network_id', sa.String(length=8), nullable=True),
        sa.Column('management_ip', sa.String(length=50), nullable=True),
        sa.Column('serial_number', sa.String(length=100), nullable=True),
        sa.Column('os_version', sa.String(length=100), nullable=True),
        sa.Column('cpu_model', sa.String(length=255), nullable=True),
        sa.Column('cpu_cores', sa.Integer(), nullable=True),
        sa.Column('ram_total_mb', sa.Integer(), nullable=True),
        sa.Column('disk_total_gb', sa.Integer(), nullable=True),
        sa.Column('disk_free_gb', sa.Integer(), nullable=True),
        sa.Column('open_ports', postgresql.JSONB(), nullable=True),
        sa.Column('credential_id', sa.String(length=8), nullable=True),
        sa.Column('contract_type', sa.String(length=50), nullable=True),
        sa.Column('sla_level', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSONB(), nullable=True),
        sa.Column('custom_fields', postgresql.JSONB(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True, default=True),
        sa.Column('monitored', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['primary_network_id'], ['networks.id'], ),
        sa.ForeignKeyConstraint(['credential_id'], ['credentials.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_assignment_customer', 'device_assignments', ['customer_id'])
    op.create_index('idx_assignment_dude_id', 'device_assignments', ['dude_device_id'], unique=True)

    # ===========================================
    # ALERT HISTORY TABLE
    # ===========================================
    op.create_table('alert_history',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('customer_id', sa.String(length=8), nullable=True),
        sa.Column('dude_device_id', sa.String(length=50), nullable=True),
        sa.Column('device_name', sa.String(length=255), nullable=True),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('acknowledged', sa.Boolean(), nullable=True, default=False),
        sa.Column('acknowledged_by', sa.String(length=100), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=True, default=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('extra_data', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_alert_customer', 'alert_history', ['customer_id'])
    op.create_index('idx_alert_created', 'alert_history', ['created_at'])
    op.create_index('idx_alert_severity', 'alert_history', ['severity'])
    op.create_index('idx_alert_dude_device', 'alert_history', ['dude_device_id'])

    # ===========================================
    # SCAN RESULTS TABLE
    # ===========================================
    op.create_table('scan_results',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('customer_id', sa.String(length=8), nullable=False),
        sa.Column('agent_id', sa.String(length=8), nullable=True),
        sa.Column('network_id', sa.String(length=8), nullable=True),
        sa.Column('network_cidr', sa.String(length=50), nullable=True),
        sa.Column('scan_type', sa.String(length=20), nullable=True, default='arp'),
        sa.Column('devices_found', sa.Integer(), nullable=True, default=0),
        sa.Column('status', sa.String(length=20), nullable=True, default='completed'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_assignments.id'], ),
        sa.ForeignKeyConstraint(['network_id'], ['networks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_scan_customer', 'scan_results', ['customer_id'])
    op.create_index('idx_scan_created', 'scan_results', ['created_at'])

    # ===========================================
    # DISCOVERED DEVICES TABLE
    # ===========================================
    op.create_table('discovered_devices',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('scan_id', sa.String(length=8), nullable=False),
        sa.Column('customer_id', sa.String(length=8), nullable=False),
        sa.Column('address', sa.String(length=50), nullable=True),
        sa.Column('mac_address', sa.String(length=20), nullable=True),
        sa.Column('identity', sa.String(length=255), nullable=True),
        sa.Column('hostname', sa.String(length=255), nullable=True),
        sa.Column('reverse_dns', sa.String(length=255), nullable=True),
        sa.Column('platform', sa.String(length=100), nullable=True),
        sa.Column('board', sa.String(length=100), nullable=True),
        sa.Column('interface', sa.String(length=100), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=True),
        sa.Column('os_family', sa.String(length=100), nullable=True),
        sa.Column('os_version', sa.String(length=100), nullable=True),
        sa.Column('vendor', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('cpu_cores', sa.Integer(), nullable=True),
        sa.Column('ram_total_mb', sa.Integer(), nullable=True),
        sa.Column('disk_total_gb', sa.Integer(), nullable=True),
        sa.Column('serial_number', sa.String(length=100), nullable=True),
        sa.Column('open_ports', postgresql.JSONB(), nullable=True),
        sa.Column('imported', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['scan_id'], ['scan_results.id'], ),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_discovered_scan', 'discovered_devices', ['scan_id'])
    op.create_index('idx_discovered_customer', 'discovered_devices', ['customer_id'])
    op.create_index('idx_discovered_address', 'discovered_devices', ['address'])

    # ===========================================
    # INVENTORY DEVICES TABLE
    # ===========================================
    op.create_table('inventory_devices',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('customer_id', sa.String(length=8), nullable=False),
        sa.Column('credential_id', sa.String(length=8), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('hostname', sa.String(length=255), nullable=True),
        sa.Column('domain', sa.String(length=255), nullable=True),
        sa.Column('device_type', sa.String(length=20), nullable=True, default='other'),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('manufacturer', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('serial_number', sa.String(length=100), nullable=True),
        sa.Column('asset_tag', sa.String(length=50), nullable=True),
        sa.Column('primary_ip', sa.String(length=50), nullable=True),
        sa.Column('primary_mac', sa.String(length=20), nullable=True),
        sa.Column('mac_address', sa.String(length=20), nullable=True),
        sa.Column('identified_by', sa.String(length=50), nullable=True),
        sa.Column('credential_used', sa.String(length=255), nullable=True),
        sa.Column('open_ports', postgresql.JSONB(), nullable=True),
        sa.Column('site_name', sa.String(length=100), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True, default='unknown'),
        sa.Column('monitored', sa.Boolean(), nullable=True, default=False),
        sa.Column('monitoring_type', sa.String(length=20), nullable=True, default='none'),
        sa.Column('monitor_source', sa.String(length=20), nullable=True),
        sa.Column('monitoring_agent_id', sa.String(length=8), nullable=True),
        sa.Column('netwatch_id', sa.String(length=50), nullable=True),
        sa.Column('dude_device_id', sa.String(length=50), nullable=True),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('last_scan', sa.DateTime(), nullable=True),
        sa.Column('last_check', sa.DateTime(), nullable=True),
        sa.Column('os_family', sa.String(length=50), nullable=True),
        sa.Column('os_version', sa.String(length=100), nullable=True),
        sa.Column('os_build', sa.String(length=50), nullable=True),
        sa.Column('architecture', sa.String(length=20), nullable=True),
        sa.Column('cpu_model', sa.String(length=200), nullable=True),
        sa.Column('cpu_cores', sa.Integer(), nullable=True),
        sa.Column('cpu_threads', sa.Integer(), nullable=True),
        sa.Column('ram_total_gb', sa.Float(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSONB(), nullable=True),
        sa.Column('custom_fields', postgresql.JSONB(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['credential_id'], ['credentials.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_inventory_customer', 'inventory_devices', ['customer_id'])
    op.create_index('idx_inventory_type', 'inventory_devices', ['device_type'])
    op.create_index('idx_inventory_ip', 'inventory_devices', ['primary_ip'])
    op.create_index('idx_inventory_status', 'inventory_devices', ['status'])
    op.create_index('idx_inventory_dude', 'inventory_devices', ['dude_device_id'])

    # ===========================================
    # INVENTORY NETWORK INTERFACES TABLE
    # ===========================================
    op.create_table('inventory_network_interfaces',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('device_id', sa.String(length=8), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('interface_type', sa.String(length=50), nullable=True),
        sa.Column('mac_address', sa.String(length=20), nullable=True),
        sa.Column('ip_addresses', postgresql.JSONB(), nullable=True),
        sa.Column('speed_mbps', sa.Integer(), nullable=True),
        sa.Column('duplex', sa.String(length=20), nullable=True),
        sa.Column('mtu', sa.Integer(), nullable=True),
        sa.Column('admin_status', sa.String(length=20), nullable=True),
        sa.Column('oper_status', sa.String(length=20), nullable=True),
        sa.Column('vlan_id', sa.Integer(), nullable=True),
        sa.Column('is_management', sa.Boolean(), nullable=True, default=False),
        sa.Column('bytes_in', sa.BigInteger(), nullable=True),
        sa.Column('bytes_out', sa.BigInteger(), nullable=True),
        sa.Column('packets_in', sa.BigInteger(), nullable=True),
        sa.Column('packets_out', sa.BigInteger(), nullable=True),
        sa.Column('errors_in', sa.Integer(), nullable=True),
        sa.Column('errors_out', sa.Integer(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['device_id'], ['inventory_devices.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_nic_device', 'inventory_network_interfaces', ['device_id'])
    op.create_index('idx_nic_mac', 'inventory_network_interfaces', ['mac_address'])

    # ===========================================
    # INVENTORY DISKS TABLE
    # ===========================================
    op.create_table('inventory_disks',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('device_id', sa.String(length=8), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('mount_point', sa.String(length=255), nullable=True),
        sa.Column('disk_type', sa.String(length=20), nullable=True),
        sa.Column('filesystem', sa.String(length=50), nullable=True),
        sa.Column('size_gb', sa.Float(), nullable=True),
        sa.Column('used_gb', sa.Float(), nullable=True),
        sa.Column('free_gb', sa.Float(), nullable=True),
        sa.Column('percent_used', sa.Float(), nullable=True),
        sa.Column('model', sa.String(length=200), nullable=True),
        sa.Column('serial', sa.String(length=100), nullable=True),
        sa.Column('smart_status', sa.String(length=50), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_removable', sa.Boolean(), nullable=True, default=False),
        sa.Column('last_updated', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['device_id'], ['inventory_devices.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_disk_device', 'inventory_disks', ['device_id'])

    # ===========================================
    # INVENTORY SOFTWARE TABLE
    # ===========================================
    op.create_table('inventory_software',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('device_id', sa.String(length=8), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('version', sa.String(length=100), nullable=True),
        sa.Column('vendor', sa.String(length=200), nullable=True),
        sa.Column('install_date', sa.DateTime(), nullable=True),
        sa.Column('install_location', sa.String(length=500), nullable=True),
        sa.Column('size_mb', sa.Float(), nullable=True),
        sa.Column('is_update', sa.Boolean(), nullable=True, default=False),
        sa.Column('license_key', sa.String(length=255), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['device_id'], ['inventory_devices.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_software_device', 'inventory_software', ['device_id'])
    op.create_index('idx_software_name', 'inventory_software', ['name'])

    # ===========================================
    # INVENTORY SERVICES TABLE
    # ===========================================
    op.create_table('inventory_services',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('device_id', sa.String(length=8), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('service_type', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('start_type', sa.String(length=20), nullable=True),
        sa.Column('user_account', sa.String(length=100), nullable=True),
        sa.Column('executable_path', sa.String(length=500), nullable=True),
        sa.Column('pid', sa.Integer(), nullable=True),
        sa.Column('memory_mb', sa.Float(), nullable=True),
        sa.Column('cpu_percent', sa.Float(), nullable=True),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('is_critical', sa.Boolean(), nullable=True, default=False),
        sa.Column('monitored', sa.Boolean(), nullable=True, default=False),
        sa.Column('last_updated', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['device_id'], ['inventory_devices.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_service_device', 'inventory_services', ['device_id'])
    op.create_index('idx_service_status', 'inventory_services', ['status'])

    # ===========================================
    # WINDOWS DETAILS TABLE
    # ===========================================
    op.create_table('inventory_windows_details',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('device_id', sa.String(length=8), nullable=False),
        sa.Column('edition', sa.String(length=100), nullable=True),
        sa.Column('product_key', sa.String(length=50), nullable=True),
        sa.Column('activation_status', sa.String(length=50), nullable=True),
        sa.Column('domain_role', sa.String(length=50), nullable=True),
        sa.Column('domain_name', sa.String(length=255), nullable=True),
        sa.Column('ou_path', sa.String(length=500), nullable=True),
        sa.Column('bios_version', sa.String(length=100), nullable=True),
        sa.Column('bios_date', sa.DateTime(), nullable=True),
        sa.Column('secure_boot', sa.Boolean(), nullable=True),
        sa.Column('tpm_version', sa.String(length=20), nullable=True),
        sa.Column('last_update_check', sa.DateTime(), nullable=True),
        sa.Column('pending_updates', sa.Integer(), nullable=True),
        sa.Column('last_reboot', sa.DateTime(), nullable=True),
        sa.Column('uptime_days', sa.Float(), nullable=True),
        sa.Column('antivirus_name', sa.String(length=100), nullable=True),
        sa.Column('antivirus_status', sa.String(length=50), nullable=True),
        sa.Column('firewall_enabled', sa.Boolean(), nullable=True),
        sa.Column('bitlocker_status', sa.String(length=50), nullable=True),
        sa.Column('local_admins', postgresql.JSONB(), nullable=True),
        sa.Column('logged_users', postgresql.JSONB(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['device_id'], ['inventory_devices.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('device_id')
    )

    # ===========================================
    # LINUX DETAILS TABLE
    # ===========================================
    op.create_table('inventory_linux_details',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('device_id', sa.String(length=8), nullable=False),
        sa.Column('distro_name', sa.String(length=100), nullable=True),
        sa.Column('distro_version', sa.String(length=50), nullable=True),
        sa.Column('distro_codename', sa.String(length=50), nullable=True),
        sa.Column('kernel_version', sa.String(length=100), nullable=True),
        sa.Column('kernel_arch', sa.String(length=20), nullable=True),
        sa.Column('package_manager', sa.String(length=20), nullable=True),
        sa.Column('packages_installed', sa.Integer(), nullable=True),
        sa.Column('packages_upgradable', sa.Integer(), nullable=True),
        sa.Column('init_system', sa.String(length=20), nullable=True),
        sa.Column('selinux_status', sa.String(length=20), nullable=True),
        sa.Column('virtualization', sa.String(length=50), nullable=True),
        sa.Column('last_reboot', sa.DateTime(), nullable=True),
        sa.Column('uptime_days', sa.Float(), nullable=True),
        sa.Column('load_average', sa.String(length=50), nullable=True),
        sa.Column('root_login_enabled', sa.Boolean(), nullable=True),
        sa.Column('ssh_port', sa.Integer(), nullable=True),
        sa.Column('logged_users', postgresql.JSONB(), nullable=True),
        sa.Column('docker_installed', sa.Boolean(), nullable=True),
        sa.Column('docker_version', sa.String(length=50), nullable=True),
        sa.Column('containers_running', sa.Integer(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['device_id'], ['inventory_devices.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('device_id')
    )

    # ===========================================
    # MIKROTIK DETAILS TABLE
    # ===========================================
    op.create_table('inventory_mikrotik_details',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('device_id', sa.String(length=8), nullable=False),
        sa.Column('routeros_version', sa.String(length=50), nullable=True),
        sa.Column('routeros_channel', sa.String(length=20), nullable=True),
        sa.Column('firmware_version', sa.String(length=50), nullable=True),
        sa.Column('factory_firmware', sa.String(length=50), nullable=True),
        sa.Column('board_name', sa.String(length=100), nullable=True),
        sa.Column('platform', sa.String(length=50), nullable=True),
        sa.Column('cpu_model', sa.String(length=100), nullable=True),
        sa.Column('cpu_count', sa.Integer(), nullable=True),
        sa.Column('cpu_frequency', sa.Integer(), nullable=True),
        sa.Column('cpu_load', sa.Float(), nullable=True),
        sa.Column('memory_total_mb', sa.Integer(), nullable=True),
        sa.Column('memory_free_mb', sa.Integer(), nullable=True),
        sa.Column('hdd_total_mb', sa.Integer(), nullable=True),
        sa.Column('hdd_free_mb', sa.Integer(), nullable=True),
        sa.Column('identity', sa.String(length=100), nullable=True),
        sa.Column('license_level', sa.String(length=20), nullable=True),
        sa.Column('license_key', sa.String(length=50), nullable=True),
        sa.Column('has_wireless', sa.Boolean(), nullable=True),
        sa.Column('has_lte', sa.Boolean(), nullable=True),
        sa.Column('has_gps', sa.Boolean(), nullable=True),
        sa.Column('dude_agent_enabled', sa.Boolean(), nullable=True),
        sa.Column('dude_agent_status', sa.String(length=20), nullable=True),
        sa.Column('dude_server_address', sa.String(length=100), nullable=True),
        sa.Column('uptime', sa.String(length=100), nullable=True),
        sa.Column('last_reboot', sa.DateTime(), nullable=True),
        sa.Column('bgp_peers', sa.Integer(), nullable=True),
        sa.Column('ospf_neighbors', sa.Integer(), nullable=True),
        sa.Column('filter_rules', sa.Integer(), nullable=True),
        sa.Column('nat_rules', sa.Integer(), nullable=True),
        sa.Column('mangle_rules', sa.Integer(), nullable=True),
        sa.Column('ipsec_peers', sa.Integer(), nullable=True),
        sa.Column('l2tp_clients', sa.Integer(), nullable=True),
        sa.Column('pptp_clients', sa.Integer(), nullable=True),
        sa.Column('wireguard_peers', sa.Integer(), nullable=True),
        sa.Column('simple_queues', sa.Integer(), nullable=True),
        sa.Column('queue_trees', sa.Integer(), nullable=True),
        sa.Column('netwatch_count', sa.Integer(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['device_id'], ['inventory_devices.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('device_id')
    )

    # ===========================================
    # NETWORK DEVICE DETAILS TABLE
    # ===========================================
    op.create_table('inventory_network_device_details',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('device_id', sa.String(length=8), nullable=False),
        sa.Column('device_class', sa.String(length=50), nullable=True),
        sa.Column('vendor', sa.String(length=50), nullable=True),
        sa.Column('firmware_version', sa.String(length=100), nullable=True),
        sa.Column('is_managed', sa.Boolean(), nullable=True),
        sa.Column('supports_snmp', sa.Boolean(), nullable=True),
        sa.Column('snmp_version', sa.String(length=10), nullable=True),
        sa.Column('snmp_community', sa.String(length=100), nullable=True),
        sa.Column('supports_ssh', sa.Boolean(), nullable=True),
        sa.Column('supports_telnet', sa.Boolean(), nullable=True),
        sa.Column('supports_web', sa.Boolean(), nullable=True),
        sa.Column('total_ports', sa.Integer(), nullable=True),
        sa.Column('ports_up', sa.Integer(), nullable=True),
        sa.Column('poe_capable', sa.Boolean(), nullable=True),
        sa.Column('poe_budget_watts', sa.Float(), nullable=True),
        sa.Column('poe_consumed_watts', sa.Float(), nullable=True),
        sa.Column('stacking_enabled', sa.Boolean(), nullable=True),
        sa.Column('stack_member_id', sa.Integer(), nullable=True),
        sa.Column('vlans_configured', postgresql.JSONB(), nullable=True),
        sa.Column('stp_enabled', sa.Boolean(), nullable=True),
        sa.Column('stp_root_bridge', sa.Boolean(), nullable=True),
        sa.Column('ap_clients_connected', sa.Integer(), nullable=True),
        sa.Column('ssids_configured', postgresql.JSONB(), nullable=True),
        sa.Column('radio_channels', postgresql.JSONB(), nullable=True),
        sa.Column('fw_policies_count', sa.Integer(), nullable=True),
        sa.Column('fw_active_sessions', sa.Integer(), nullable=True),
        sa.Column('vpn_tunnels_count', sa.Integer(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['device_id'], ['inventory_devices.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('device_id')
    )

    # ===========================================
    # NETWATCH CONFIGS TABLE
    # ===========================================
    op.create_table('netwatch_configs',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('customer_id', sa.String(length=8), nullable=False),
        sa.Column('agent_id', sa.String(length=8), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('host', sa.String(length=255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('interval', sa.String(length=20), nullable=True, default='30s'),
        sa.Column('timeout', sa.String(length=20), nullable=True, default='3s'),
        sa.Column('status', sa.String(length=20), nullable=True, default='unknown'),
        sa.Column('last_check', sa.DateTime(), nullable=True),
        sa.Column('last_change', sa.DateTime(), nullable=True),
        sa.Column('up_script', sa.Text(), nullable=True),
        sa.Column('down_script', sa.Text(), nullable=True),
        sa.Column('mikrotik_id', sa.String(length=20), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_assignments.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_netwatch_customer', 'netwatch_configs', ['customer_id'])
    op.create_index('idx_netwatch_agent', 'netwatch_configs', ['agent_id'])

    # ===========================================
    # DUDE AGENTS TABLE
    # ===========================================
    op.create_table('dude_agents',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('dude_id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('address', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True, default='unknown'),
        sa.Column('version', sa.String(length=50), nullable=True),
        sa.Column('customer_id', sa.String(length=8), nullable=True),
        sa.Column('agent_assignment_id', sa.String(length=8), nullable=True),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['agent_assignment_id'], ['agent_assignments.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dude_id')
    )
    op.create_index('idx_dude_agent_dude_id', 'dude_agents', ['dude_id'])
    op.create_index('idx_dude_agent_customer', 'dude_agents', ['customer_id'])

    # ===========================================
    # DEVICE BACKUPS TABLE
    # ===========================================
    op.create_table('device_backups',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('device_assignment_id', sa.String(length=8), nullable=True),
        sa.Column('customer_id', sa.String(length=8), nullable=False),
        sa.Column('network_id', sa.String(length=8), nullable=True),
        sa.Column('device_ip', sa.String(length=50), nullable=False),
        sa.Column('device_hostname', sa.String(length=255), nullable=True),
        sa.Column('device_type', sa.String(length=50), nullable=False),
        sa.Column('device_model', sa.String(length=100), nullable=True),
        sa.Column('device_serial', sa.String(length=100), nullable=True),
        sa.Column('backup_type', sa.String(length=50), nullable=True, default='config'),
        sa.Column('backup_format', sa.String(length=20), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('checksum', sa.String(length=64), nullable=True),
        sa.Column('compressed', sa.Boolean(), nullable=True, default=False),
        sa.Column('device_info', postgresql.JSONB(), nullable=True),
        sa.Column('credential_id', sa.String(length=8), nullable=True),
        sa.Column('collector_type', sa.String(length=50), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True, default=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('triggered_by', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['device_assignment_id'], ['device_assignments.id'], ),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['network_id'], ['networks.id'], ),
        sa.ForeignKeyConstraint(['credential_id'], ['credentials.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_backup_customer_date', 'device_backups', ['customer_id', 'created_at'])
    op.create_index('idx_backup_device_date', 'device_backups', ['device_ip', 'created_at'])
    op.create_index('idx_backup_type', 'device_backups', ['device_type', 'backup_type'])
    op.create_index('idx_backup_success', 'device_backups', ['success'])

    # ===========================================
    # BACKUP SCHEDULES TABLE
    # ===========================================
    op.create_table('backup_schedules',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('customer_id', sa.String(length=8), nullable=False),
        sa.Column('network_id', sa.String(length=8), nullable=True),
        sa.Column('device_type_filter', postgresql.JSONB(), nullable=True),
        sa.Column('device_role_filter', postgresql.JSONB(), nullable=True),
        sa.Column('device_tag_filter', postgresql.JSONB(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True, default=True),
        sa.Column('schedule_type', sa.String(length=20), nullable=True, default='daily'),
        sa.Column('schedule_time', sa.String(length=5), nullable=True, default='03:00'),
        sa.Column('schedule_days', postgresql.JSONB(), nullable=True),
        sa.Column('schedule_day_of_month', sa.Integer(), nullable=True),
        sa.Column('cron_expression', sa.String(length=100), nullable=True),
        sa.Column('backup_types', postgresql.JSONB(), nullable=True),
        sa.Column('retention_days', sa.Integer(), nullable=True, default=30),
        sa.Column('retention_count', sa.Integer(), nullable=True),
        sa.Column('retention_strategy', sa.String(length=20), nullable=True, default='time'),
        sa.Column('compress_backups', sa.Boolean(), nullable=True, default=False),
        sa.Column('compression_format', sa.String(length=10), nullable=True, default='gzip'),
        sa.Column('notify_on_success', sa.Boolean(), nullable=True, default=False),
        sa.Column('notify_on_failure', sa.Boolean(), nullable=True, default=True),
        sa.Column('notification_emails', postgresql.JSONB(), nullable=True),
        sa.Column('notification_webhook', sa.String(length=500), nullable=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('last_run_success', sa.Boolean(), nullable=True),
        sa.Column('last_run_devices_count', sa.Integer(), nullable=True),
        sa.Column('last_run_errors_count', sa.Integer(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('total_runs', sa.Integer(), nullable=True, default=0),
        sa.Column('total_successes', sa.Integer(), nullable=True, default=0),
        sa.Column('total_failures', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['network_id'], ['networks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_schedule_customer', 'backup_schedules', ['customer_id', 'enabled'])
    op.create_index('idx_schedule_next_run', 'backup_schedules', ['next_run_at', 'enabled'])

    # ===========================================
    # BACKUP JOBS TABLE
    # ===========================================
    op.create_table('backup_jobs',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('customer_id', sa.String(length=8), nullable=True),
        sa.Column('schedule_id', sa.String(length=8), nullable=True),
        sa.Column('job_type', sa.String(length=50), nullable=True, default='manual'),
        sa.Column('job_scope', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True, default='pending'),
        sa.Column('progress_current', sa.Integer(), nullable=True, default=0),
        sa.Column('progress_total', sa.Integer(), nullable=True, default=0),
        sa.Column('progress_percent', sa.Integer(), nullable=True, default=0),
        sa.Column('devices_total', sa.Integer(), nullable=True, default=0),
        sa.Column('devices_success', sa.Integer(), nullable=True, default=0),
        sa.Column('devices_failed', sa.Integer(), nullable=True, default=0),
        sa.Column('devices_skipped', sa.Integer(), nullable=True, default=0),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('result_summary', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['schedule_id'], ['backup_schedules.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_job_status', 'backup_jobs', ['status', 'created_at'])
    op.create_index('idx_job_customer', 'backup_jobs', ['customer_id', 'status'])

    # ===========================================
    # BACKUP TEMPLATES TABLE
    # ===========================================
    op.create_table('backup_templates',
        sa.Column('id', sa.String(length=8), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('device_type', sa.String(length=50), nullable=False),
        sa.Column('vendor', sa.String(length=100), nullable=True),
        sa.Column('model_pattern', sa.String(length=200), nullable=True),
        sa.Column('commands_config', postgresql.JSONB(), nullable=True),
        sa.Column('commands_binary', postgresql.JSONB(), nullable=True),
        sa.Column('commands_pre', postgresql.JSONB(), nullable=True),
        sa.Column('commands_post', postgresql.JSONB(), nullable=True),
        sa.Column('collector_type', sa.String(length=50), nullable=True, default='ssh'),
        sa.Column('connection_timeout', sa.Integer(), nullable=True, default=30),
        sa.Column('command_delay', sa.Integer(), nullable=True, default=2),
        sa.Column('cleanup_patterns', postgresql.JSONB(), nullable=True),
        sa.Column('extract_info_commands', postgresql.JSONB(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_builtin', sa.Boolean(), nullable=True, default=False),
        sa.Column('priority', sa.Integer(), nullable=True, default=100),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('idx_template_type', 'backup_templates', ['device_type', 'active'])


def downgrade() -> None:
    # Drop all tables in reverse order
    op.drop_table('backup_templates')
    op.drop_table('backup_jobs')
    op.drop_table('backup_schedules')
    op.drop_table('device_backups')
    op.drop_table('dude_agents')
    op.drop_table('netwatch_configs')
    op.drop_table('inventory_network_device_details')
    op.drop_table('inventory_mikrotik_details')
    op.drop_table('inventory_linux_details')
    op.drop_table('inventory_windows_details')
    op.drop_table('inventory_services')
    op.drop_table('inventory_software')
    op.drop_table('inventory_disks')
    op.drop_table('inventory_network_interfaces')
    op.drop_table('inventory_devices')
    op.drop_table('discovered_devices')
    op.drop_table('scan_results')
    op.drop_table('alert_history')
    op.drop_table('device_assignments')
    op.drop_table('agent_assignments')
    op.drop_table('customer_credential_links')
    op.drop_table('credentials')
    op.drop_table('networks')
    op.drop_table('customers')
