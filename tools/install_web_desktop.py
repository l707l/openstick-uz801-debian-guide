#!/usr/bin/env python3
"""
install_web_desktop.py - Instalador del Escritorio Gráfico Web ultraligero (noVNC + Openbox) para OpenStick

Instala un entorno de escritorio completo (Openbox, Tint2, PCManFM, LXTerminal)
con servidor TigerVNC y pasarela HTML5 noVNC en el puerto 6080, consumiendo menos de 180 MB de disco y 40 MB de RAM.
"""

import paramiko
import sys

STICK_IP = "192.168.200.1"
PORT = 22
USER = "user"
PASS = "1"

def main():
    print(f"[*] Conectando por SSH a {STICK_IP}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(STICK_IP, port=PORT, username=USER, password=PASS, timeout=10)

    def sudo_cmd(cmd):
        stdin, stdout, stderr = ssh.exec_command(f"echo {PASS} | sudo -S {cmd}")
        return stdout.read().decode("utf-8", errors="ignore").strip()

    print("[1/4] Limpiando repositorios y actualizando APT...")
    sudo_cmd("rm -f /etc/apt/sources.list.d/mobian.list")
    sudo_cmd("apt-get update")

    print("[2/4] Instalando paquetes de escritorio ligero...")
    packages = "openbox tint2 pcmanfm lxterminal tigervnc-standalone-server tigervnc-tools novnc websockify xauth dbus-x11 adwaita-icon-theme"
    sudo_cmd(f"apt-get install -y --no-install-recommends {packages}")

    print("[3/4] Configurando VNC y Openbox...")
    ssh.exec_command('mkdir -p /home/user/.vnc')
    ssh.exec_command(f'echo "{PASS}" | vncpasswd -f > /home/user/.vnc/passwd && chmod 600 /home/user/.vnc/passwd')
    ssh.exec_command('echo "geometry=1280x720\ndepth=24\nlocalhost=no" > /home/user/.vnc/config')

    xstartup = """#!/bin/sh
unset SESSION_MANAGER
unset DBUS_SESSION_BUS_ADDRESS
export LANG=en_US.UTF-8

if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
    eval $(dbus-launch --sh-syntax --exit-with-session)
fi

pcmanfm --desktop &
tint2 &
exec openbox-session
"""
    sftp = ssh.open_sftp()
    with sftp.open("/home/user/.vnc/xstartup", "w") as f:
        f.write(xstartup)
    sftp.close()
    ssh.exec_command('chmod +x /home/user/.vnc/xstartup')

    print("[4/4] Creando servicios systemd para TigerVNC y noVNC...")
    vnc_service = """[Unit]
Description=TigerVNC Server for User
After=network.target

[Service]
Type=simple
User=user
WorkingDirectory=/home/user
ExecStartPre=-/usr/bin/vncserver -kill :1
ExecStart=/usr/bin/vncserver :1 -geometry 1280x720 -depth 24 -localhost no -fg
ExecStop=/usr/bin/vncserver -kill :1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    novnc_service = """[Unit]
Description=noVNC Web Desktop Gateway
After=vncserver.service

[Service]
Type=simple
User=user
ExecStart=/usr/bin/websockify --web=/usr/share/novnc/ 6080 localhost:5901
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/vncserver.service", "w") as f:
        f.write(vnc_service)
    with sftp.open("/tmp/novnc.service", "w") as f:
        f.write(novnc_service)
    sftp.close()

    sudo_cmd("mv /tmp/vncserver.service /etc/systemd/system/vncserver.service")
    sudo_cmd("mv /tmp/novnc.service /etc/systemd/system/novnc.service")
    sudo_cmd("systemctl daemon-reload")
    sudo_cmd("systemctl enable --now vncserver.service novnc.service")

    ssh.close()
    print("\n[+] Escritorio Web instalado. Accede en: http://192.168.200.1:6080/vnc.html")

if __name__ == "__main__":
    main()
