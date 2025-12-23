#!/usr/bin/env python3
"""
Test diretto scansione MikroTik
Esegui con: python test_mikrotik_scan.py
"""
import routeros_api
import sys

# Configurazione - MODIFICA QUESTI VALORI
ROUTER_IP = "192.168.99.254"
ROUTER_PORT = 8728
ROUTER_USER = "admin"
ROUTER_PASS = ""  # Inserisci la password

def test_scan():
    print(f"=== Test Scansione MikroTik ===")
    print(f"Router: {ROUTER_IP}:{ROUTER_PORT}")
    print(f"User: {ROUTER_USER}")
    print()

    try:
        # Connessione
        print("[1] Connessione al router...")
        connection = routeros_api.RouterOsApiPool(
            host=ROUTER_IP,
            username=ROUTER_USER,
            password=ROUTER_PASS,
            port=ROUTER_PORT,
            use_ssl=False,
            ssl_verify=False,
            plaintext_login=True,
        )
        api = connection.get_api()
        print("    ✓ Connesso!")

        # Identity
        print("\n[2] Ottengo identity...")
        try:
            identity = api.get_resource('/system/identity').get()
            print(f"    Router name: {identity[0].get('name', 'Unknown')}")
        except Exception as e:
            print(f"    ✗ Errore: {e}")

        # Neighbors
        print("\n[3] Ottengo neighbor discovery...")
        try:
            neighbors = api.get_resource('/ip/neighbor').get()
            print(f"    Trovati {len(neighbors)} neighbors:")
            for n in neighbors[:10]:  # Max 10
                print(f"      - {n.get('address', 'N/A')} | {n.get('mac-address', 'N/A')} | {n.get('identity', 'N/A')}")
        except Exception as e:
            print(f"    ✗ Errore: {e}")

        # ARP
        print("\n[4] Ottengo tabella ARP...")
        try:
            arps = api.get_resource('/ip/arp').get()
            print(f"    Trovati {len(arps)} entry ARP:")
            for a in arps[:20]:  # Max 20
                ip = a.get('address', 'N/A')
                mac = a.get('mac-address', 'N/A')
                iface = a.get('interface', 'N/A')
                print(f"      - {ip} | {mac} | {iface}")
        except Exception as e:
            print(f"    ✗ Errore: {e}")

        # DHCP Leases
        print("\n[5] Ottengo DHCP leases...")
        try:
            leases = api.get_resource('/ip/dhcp-server/lease').get()
            print(f"    Trovati {len(leases)} leases:")
            for l in leases[:20]:  # Max 20
                ip = l.get('address', 'N/A')
                mac = l.get('mac-address', 'N/A')
                hostname = l.get('host-name', 'N/A')
                status = l.get('status', 'N/A')
                print(f"      - {ip} | {mac} | {hostname} | status={status}")
        except Exception as e:
            print(f"    ✗ Errore: {e}")

        # Interfaces
        print("\n[6] Ottengo interfacce...")
        try:
            ifaces = api.get_resource('/interface').get()
            print(f"    Trovate {len(ifaces)} interfacce:")
            for i in ifaces[:10]:
                name = i.get('name', 'N/A')
                itype = i.get('type', 'N/A')
                running = i.get('running', 'N/A')
                print(f"      - {name} ({itype}) running={running}")
        except Exception as e:
            print(f"    ✗ Errore: {e}")

        connection.disconnect()
        print("\n=== Test completato ===")

    except Exception as e:
        print(f"\n✗ ERRORE CONNESSIONE: {e}")
        print("\nVerifica:")
        print("  - IP corretto?")
        print("  - Porta API abilitata su MikroTik? (default 8728)")
        print("  - Username/password corretti?")
        print("  - Firewall permette connessione?")
        sys.exit(1)

if __name__ == "__main__":
    test_scan()
