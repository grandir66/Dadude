#!/usr/bin/env python3
"""
Script di migrazione dati da SQLite a PostgreSQL per DaDude v2.0

Utilizzo:
    python migrate_sqlite_to_postgres.py --sqlite-path /path/to/sqlite.db --postgres-url postgresql://user:pass@host:port/db

Il script:
1. Legge tutti i dati dal database SQLite esistente
2. Li inserisce nel database PostgreSQL
3. Gestisce le relazioni e le foreign keys
4. Riporta statistiche di migrazione
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("Errore: psycopg2 non installato. Esegui: pip install psycopg2-binary")
    sys.exit(1)


# Ordine delle tabelle per rispettare le foreign keys
TABLE_ORDER = [
    # Tabelle senza dipendenze
    "customers",
    "agents",
    "agent_types",
    "backup_schedules",
    "software_catalog",
    "command_queue",

    # Tabelle con dipendenze da customers/agents
    "devices",
    "audit_log",

    # Tabelle con dipendenze da devices
    "device_software",
    "device_alerts",
    "device_performance",
    "backup_jobs",
    "backup_history",
    "remote_sessions",
    "device_notes",
    "device_commands",

    # Tabelle monitoring
    "monitoring_policies",
    "device_monitoring",

    # Tabelle scripts
    "script_library",
    "script_executions",

    # Tabelle patch management
    "patch_policies",
    "device_patches",

    # Tabelle reports
    "report_templates",
    "scheduled_reports",

    # Altre tabelle
    "integrations",
    "notification_rules",
]


def get_sqlite_tables(sqlite_conn: sqlite3.Connection) -> List[str]:
    """Ottiene lista delle tabelle nel database SQLite."""
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    return [row[0] for row in cursor.fetchall()]


def get_table_columns(sqlite_conn: sqlite3.Connection, table_name: str) -> List[str]:
    """Ottiene i nomi delle colonne di una tabella."""
    cursor = sqlite_conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def get_table_data(sqlite_conn: sqlite3.Connection, table_name: str) -> Tuple[List[str], List[Tuple]]:
    """Legge tutti i dati da una tabella SQLite."""
    columns = get_table_columns(sqlite_conn, table_name)
    cursor = sqlite_conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    return columns, rows


def convert_value(value: Any) -> Any:
    """Converte valori SQLite per PostgreSQL."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return value


def check_postgres_table_exists(pg_conn, table_name: str) -> bool:
    """Verifica se una tabella esiste in PostgreSQL."""
    cursor = pg_conn.cursor()
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = %s
        )
    """, (table_name,))
    return cursor.fetchone()[0]


def get_postgres_columns(pg_conn, table_name: str) -> List[str]:
    """Ottiene le colonne di una tabella PostgreSQL."""
    cursor = pg_conn.cursor()
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    return [row[0] for row in cursor.fetchall()]


def migrate_table(
    sqlite_conn: sqlite3.Connection,
    pg_conn,
    table_name: str,
    batch_size: int = 1000
) -> Dict[str, Any]:
    """Migra una singola tabella da SQLite a PostgreSQL."""

    result = {
        "table": table_name,
        "status": "skipped",
        "rows_migrated": 0,
        "error": None
    }

    # Verifica esistenza tabella in PostgreSQL
    if not check_postgres_table_exists(pg_conn, table_name):
        result["error"] = f"Tabella {table_name} non esiste in PostgreSQL"
        return result

    # Ottiene dati SQLite
    try:
        sqlite_columns, sqlite_rows = get_table_data(sqlite_conn, table_name)
    except Exception as e:
        result["error"] = f"Errore lettura SQLite: {e}"
        return result

    if not sqlite_rows:
        result["status"] = "empty"
        return result

    # Ottiene colonne PostgreSQL
    pg_columns = get_postgres_columns(pg_conn, table_name)

    # Trova colonne comuni
    common_columns = [c for c in sqlite_columns if c in pg_columns]

    if not common_columns:
        result["error"] = "Nessuna colonna comune trovata"
        return result

    # Indici delle colonne da migrare
    column_indices = [sqlite_columns.index(c) for c in common_columns]

    # Prepara i dati
    migrated_rows = []
    for row in sqlite_rows:
        migrated_row = tuple(convert_value(row[i]) for i in column_indices)
        migrated_rows.append(migrated_row)

    # Inserisce in PostgreSQL
    try:
        cursor = pg_conn.cursor()

        # Crea query di inserimento
        columns_str = ", ".join(common_columns)
        placeholders = ", ".join(["%s"] * len(common_columns))

        insert_query = f"""
            INSERT INTO {table_name} ({columns_str})
            VALUES ({placeholders})
            ON CONFLICT DO NOTHING
        """

        # Inserisce a batch
        for i in range(0, len(migrated_rows), batch_size):
            batch = migrated_rows[i:i + batch_size]
            cursor.executemany(insert_query, batch)

        pg_conn.commit()

        result["status"] = "success"
        result["rows_migrated"] = len(migrated_rows)

    except Exception as e:
        pg_conn.rollback()
        result["status"] = "error"
        result["error"] = str(e)

    return result


def reset_sequences(pg_conn):
    """Resetta le sequence di PostgreSQL per le colonne ID."""
    cursor = pg_conn.cursor()

    cursor.execute("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND column_default LIKE 'nextval%'
    """)

    for table_name, column_name in cursor.fetchall():
        try:
            cursor.execute(f"""
                SELECT setval(
                    pg_get_serial_sequence('{table_name}', '{column_name}'),
                    COALESCE((SELECT MAX({column_name}) FROM {table_name}), 1)
                )
            """)
        except Exception as e:
            print(f"  Warning: impossibile resettare sequence per {table_name}.{column_name}: {e}")

    pg_conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Migra dati da SQLite a PostgreSQL")
    parser.add_argument(
        "--sqlite-path",
        required=True,
        help="Percorso del database SQLite sorgente"
    )
    parser.add_argument(
        "--postgres-url",
        required=True,
        help="URL di connessione PostgreSQL (postgresql://user:pass@host:port/db)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Esegue solo analisi senza migrare"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Dimensione batch per inserimenti (default: 1000)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("DaDude v2.0 - Migrazione SQLite → PostgreSQL")
    print("=" * 60)
    print(f"SQLite: {args.sqlite_path}")
    print(f"PostgreSQL: {args.postgres_url.split('@')[1] if '@' in args.postgres_url else args.postgres_url}")
    print(f"Dry run: {args.dry_run}")
    print("=" * 60)

    # Connessione SQLite
    try:
        sqlite_conn = sqlite3.connect(args.sqlite_path)
        print("✓ Connessione SQLite stabilita")
    except Exception as e:
        print(f"✗ Errore connessione SQLite: {e}")
        sys.exit(1)

    # Connessione PostgreSQL
    try:
        pg_conn = psycopg2.connect(args.postgres_url)
        print("✓ Connessione PostgreSQL stabilita")
    except Exception as e:
        print(f"✗ Errore connessione PostgreSQL: {e}")
        sys.exit(1)

    # Ottiene tabelle SQLite
    sqlite_tables = get_sqlite_tables(sqlite_conn)
    print(f"\nTabelle trovate in SQLite: {len(sqlite_tables)}")

    # Determina ordine migrazione
    tables_to_migrate = []
    for table in TABLE_ORDER:
        if table in sqlite_tables:
            tables_to_migrate.append(table)

    # Aggiungi tabelle non nell'ordine predefinito
    for table in sqlite_tables:
        if table not in tables_to_migrate:
            tables_to_migrate.append(table)

    print(f"Tabelle da migrare: {len(tables_to_migrate)}")

    if args.dry_run:
        print("\n--- DRY RUN - Nessuna modifica verrà effettuata ---\n")
        for table in tables_to_migrate:
            columns, rows = get_table_data(sqlite_conn, table)
            print(f"  {table}: {len(rows)} righe, {len(columns)} colonne")
        print("\n--- Fine DRY RUN ---")
        return

    # Migrazione
    print("\n" + "-" * 60)
    print("Inizio migrazione...")
    print("-" * 60)

    results = []
    total_rows = 0

    for table in tables_to_migrate:
        print(f"\nMigrazione: {table}...", end=" ")
        result = migrate_table(sqlite_conn, pg_conn, table, args.batch_size)
        results.append(result)

        if result["status"] == "success":
            print(f"✓ {result['rows_migrated']} righe")
            total_rows += result["rows_migrated"]
        elif result["status"] == "empty":
            print("○ (vuota)")
        elif result["status"] == "skipped":
            print(f"⊘ Saltata: {result['error']}")
        else:
            print(f"✗ Errore: {result['error']}")

    # Reset sequences
    print("\n" + "-" * 60)
    print("Reset sequences PostgreSQL...")
    reset_sequences(pg_conn)
    print("✓ Sequences resettate")

    # Riepilogo
    print("\n" + "=" * 60)
    print("RIEPILOGO MIGRAZIONE")
    print("=" * 60)

    success = sum(1 for r in results if r["status"] == "success")
    empty = sum(1 for r in results if r["status"] == "empty")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")

    print(f"Tabelle migrate con successo: {success}")
    print(f"Tabelle vuote: {empty}")
    print(f"Tabelle saltate: {skipped}")
    print(f"Errori: {errors}")
    print(f"Totale righe migrate: {total_rows}")
    print("=" * 60)

    if errors > 0:
        print("\nErrori riscontrati:")
        for r in results:
            if r["status"] == "error":
                print(f"  - {r['table']}: {r['error']}")

    # Chiusura connessioni
    sqlite_conn.close()
    pg_conn.close()

    print("\n✓ Migrazione completata!")


if __name__ == "__main__":
    main()
