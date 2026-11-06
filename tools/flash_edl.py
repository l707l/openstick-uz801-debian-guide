#!/usr/bin/env python3
"""
flash_edl.py - Flasheador directo EDL para OpenStick MSM8916 (UZ801 v3.0)

Escribe el bootloader LK1ST, firmware de Qualcomm, calibraciones originales de RF (IMEI),
kernel de Debian y el sistema de archivos rootfs en sus sectores exactos de la eMMC.
"""

import os
import sys
import subprocess
from pathlib import Path

py = sys.executable
edl = r"edl.py"
loader = r"prog_emmc_firehose_8916.mbn"

def run_edl(args, timeout=600):
    cmd = [py, edl, f"--loader={loader}"] + args
    print(f"\n[*] Ejecutando: {' '.join(args)}", flush=True)
    res = subprocess.run(cmd, env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=timeout)
    if res.returncode != 0:
        print(f"[-] Error ejecutando: {' '.join(args)}", flush=True)
        sys.exit(1)

def main():
    base_dir = Path("openstick/base")
    deb_dir = Path("openstick/debian")
    cal_dir = Path("calibration")

    print("=====================================================")
    print("  OpenStick UZ801 v3.0 - Flashing a Debian 12 (EDL)  ")
    print("=====================================================")

    # 1. Tabla de particiones GPT
    print("[1/5] Escribiendo tabla de particiones GPT corregida...", flush=True)
    run_edl(["w", "partition", str(base_dir / "gpt_fixed.bin")])

    # 2. Firmware Qualcomm
    print("[2/5] Escribiendo firmware Qualcomm (SBL1, RPM, TZ, HYP, CDT, LK)...", flush=True)
    run_edl(["w", "sbl1", str(base_dir / "sbl1.mbn")])
    run_edl(["w", "rpm", str(base_dir / "rpm.mbn")])
    run_edl(["w", "tz", str(base_dir / "tz.mbn")])
    run_edl(["w", "hyp", str(base_dir / "hyp.mbn")])
    run_edl(["w", "cdt", str(base_dir / "sbc_1.0_8016.bin")])
    run_edl(["w", "aboot", str(base_dir / "aboot.bin")])

    # 3. Calibraciones originales (preserva IMEI)
    print("[3/5] Restaurando particiones de calibración RF (IMEI)...", flush=True)
    for p in ["sec", "fsc", "fsg", "modemst1", "modemst2"]:
        p_path = cal_dir / f"{p}.bin"
        if p_path.exists():
            run_edl(["w", p, str(p_path)])

    # 4. Kernel Debian (boot.img)
    print("[4/5] Escribiendo kernel Linux de Debian...", flush=True)
    run_edl(["w", "boot", str(deb_dir / "boot.img")])

    # 5. Sistema de archivos Rootfs (sector exacto 659456 = 0x14200000)
    print("[5/5] Escribiendo rootfs ext4 descompreso al sector 659456...", flush=True)
    raw_rootfs = deb_dir / "rootfs_raw.img"
    if not raw_rootfs.exists():
        print(f"[-] No se encontró {raw_rootfs}. Use unsparse.py primero.")
        sys.exit(1)
    run_edl(["ws", "659456", str(raw_rootfs)], timeout=1800)

    # 6. Reinicio
    print("[*] Proceso completado. Enviando reinicio a Debian...", flush=True)
    run_edl(["reset"])
    print("\n[+] El módem se ha reiniciado exitosamente.")

if __name__ == "__main__":
    main()
