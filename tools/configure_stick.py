#!/usr/bin/env python3
"""
configure_stick.py - Sincroniza la hora y configura el acceso a repositorios en Debian OpenStick
"""

import paramiko
import datetime
import sys

STICK_IP = "192.168.200.1"
WINDOWS_IP = "192.168.200.149"
PORT = 22
USER = "user"
PASS = "1"

def main():
    print(f"[*] Conectando por SSH a {STICK_IP}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(STICK_IP, port=PORT, username=USER, password=PASS, timeout=10)
    except Exception as e:
        print(f"[-] Error al conectar por SSH: {e}")
        return 1

    sftp = ssh.open_sftp()
    
    # 1. Archivo proxy para APT
    with sftp.open("/tmp/01proxy", "w") as f:
        f.write(f'Acquire::http::Proxy "http://{WINDOWS_IP}:8080/";\n')
        f.write(f'Acquire::https::Proxy "http://{WINDOWS_IP}:8080/";\n')

    # 2. Archivo proxy para entorno (curl, wget)
    with sftp.open("/tmp/proxy_env", "w") as f:
        f.write(f'http_proxy=http://{WINDOWS_IP}:8080\n')
        f.write(f'https_proxy=http://{WINDOWS_IP}:8080\n')
        f.write(f'HTTP_PROXY=http://{WINDOWS_IP}:8080\n')
        f.write(f'HTTPS_PROXY=http://{WINDOWS_IP}:8080\n')
    sftp.close()

    def sudo_cmd(cmd):
        stdin, stdout, stderr = ssh.exec_command(f"echo {PASS} | sudo -S {cmd}")
        return stdout.read().decode("utf-8", errors="ignore").strip()

    # 3. Sincronizar reloj (RTC) con el reloj de la PC
    utc_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    sudo_cmd(f'date -u -s "{utc_now}"')
    print(f"[+] Reloj sincronizado con UTC: {utc_now}")

    # 4. Mover archivos de proxy
    sudo_cmd("cp /tmp/01proxy /etc/apt/apt.conf.d/01proxy")
    sudo_cmd("cat /tmp/proxy_env >> /etc/environment")
    print("[+] Configuración de APT y Proxy aplicada en Debian.")

    # 5. Probar actualización
    print("[*] Comprobando repositorios (apt-get update)...")
    res = sudo_cmd("apt-get update")
    print(res[-300:] if len(res) > 300 else res)

    ssh.close()
    print("\n[+] Configuración finalizada con éxito.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
