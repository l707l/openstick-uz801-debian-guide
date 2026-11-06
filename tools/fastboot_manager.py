#!/usr/bin/env python3
"""
fastboot_manager.py - Cliente Fastboot puro sobre PyUSB para Windows

Permite enviar comandos getvar, continue, reboot y oem reboot-edl a dispositivos
Qualcomm en Fastboot (18D1:D00D) utilizando libusb-1.0 sin requerir fastboot.exe ni Android SDK.
"""

import usb.core
import usb.util
import usb.backend.libusb1
import sys
import os

def get_backend():
    # Intenta encontrar libusb en ubicaciones habituales de Windows
    possible_paths = [
        r"C:\Users\syluss\Downloads\openstick-installer\edl\edlclient\Windows\libusb-1.0.dll",
        "libusb-1.0.dll"
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return usb.backend.libusb1.get_backend(find_library=lambda x: p)
    return usb.backend.libusb1.get_backend()

def main():
    backend = get_backend()
    dev = usb.core.find(idVendor=0x18D1, idProduct=0xD00D, backend=backend)
    if dev is None:
        print("[-] Dispositivo Fastboot (18D1:D00D) no encontrado.")
        return 1

    print(f"[+] Módem Fastboot detectado: Bus {dev.bus}, Dirección {dev.address}")
    try:
        dev.set_configuration()
    except Exception:
        pass

    cfg = dev.get_active_configuration()
    intf = cfg[(0, 0)]
    ep_out = None
    ep_in = None
    for ep in intf:
        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
            ep_out = ep
        else:
            ep_in = ep

    if not ep_out or not ep_in:
        print("[-] Endpoints de Fastboot no encontrados.")
        return 1

    def send_cmd(cmd):
        print(f">> {cmd}")
        ep_out.write(cmd.encode("ascii"))
        resp = b""
        while True:
            try:
                chunk = bytes(ep_in.read(512, timeout=2000))
                resp += chunk
                prefix = chunk[:4].decode("ascii", errors="ignore")
                msg = chunk[4:].decode("ascii", errors="ignore")
                print(f"<< [{prefix}] {msg}")
                if prefix in ("OKAY", "FAIL"):
                    break
            except Exception as e:
                print(f"Error de lectura: {e}")
                break
        return resp

    send_cmd("getvar:product")
    send_cmd("getvar:version")

    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "continue":
            print("[*] Enviando 'continue' para arrancar el kernel de Linux...")
            send_cmd("continue")
        elif arg == "reboot":
            print("[*] Enviando 'reboot'...")
            send_cmd("reboot")
        elif arg == "edl":
            print("[*] Enviando orden de reinicio a modo EDL 9008...")
            res = send_cmd("oem reboot-edl")
            if not res.startswith(b"OKAY"):
                send_cmd("reboot-edl")
        else:
            send_cmd(sys.argv[1])
    else:
        print("\nUso: python fastboot_manager.py [continue | reboot | edl | getvar:<var>]")

if __name__ == "__main__":
    main()
