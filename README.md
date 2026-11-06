# Guía Definitiva OpenStick UZ801 v3.0 (Qualcomm MSM8916) a Debian 12 (Bookworm)

[![Debian 12](https://img.shields.io/badge/Debian-12%20(Bookworm)-red?logo=debian)](https://www.debian.org/)
[![Kernel Mainline](https://img.shields.io/badge/Kernel-6.7--rc4--msm8916-blue?logo=linux)](https://github.com/msm8916-mainline)
[![SoC](https://img.shields.io/badge/SoC-Snapdragon%20410%20(MSM8916)-orange)](https://www.qualcomm.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Guía completa, paso a paso y herramientas en Python para instalar **Debian GNU/Linux 12 (Bookworm)** con kernel Linux Mainline en los módems USB 4G **OpenStick / UZ801 v3.0** (Qualcomm Snapdragon 410 / MSM8916), preservando el IMEI original, la calibración de radiofrecuencia (RF), punto de acceso Wi-Fi y pasarela de Internet por USB.

---

## 📌 Especificaciones del Dispositivo Objetivo

- **Modelo**: Módem USB 4G LTE UZ801 v3.0 (UFI / Dongle Qualcomm).
- **Procesador (SoC)**: Qualcomm Snapdragon 410 (MSM8916) Quad-Core Cortex-A53 @ 1.0 GHz (aarch64).
- **Memoria RAM**: 512 MB LPDDR3 (~381 MB utilizables por el sistema).
- **Almacenamiento (eMMC)**: 3.9 GB (~7,634,944 sectores LBA de 512 bytes).
- **Conectividad**:
  - Wi-Fi 2.4 GHz (WLAN) en modo Cliente o Punto de Acceso (AP).
  - Módem celular 4G LTE / 3G GSM integrado (controlado vía QMI / BAM-DMUX).
  - Gadget USB RNDIS (interfaz de red Ethernet virtual sobre USB).

---

## ⚠️ Los 3 Problemas Críticos Comunes y Sus Soluciones

La mayoría de tutoriales estándar de OpenStick fallan en el UZ801 v3.0 debido a tres problemas técnicos fundamentales que este repositorio resuelve:

### 1. El template de tabla GPT corrupto (`gpt_both0.bin`)
- **Problema**: El archivo `gpt_both0.bin` que viene en los paquetes habituales de OpenStick es un archivo plantilla sin inicializar (`AlternateLBA=0`, `LastUsableLBA=0` y sumas de verificación CRC32 inválidas). Cuando la ROM primaria del procesador (PBL) lee esta tabla, rechaza la memoria eMMC y entra en bucle forzado a modo EDL 9008.
- **Solución**: [`tools/build_gpt.py`](tools/build_gpt.py) genera una tabla GPT primaria y de respaldo 100% válida con cálculo correcto de CRC32 y límites para los 7,634,944 sectores.

### 2. El desfase de sectores en `rootfs` (659456 vs 660480)
- **Problema**: En la tabla de particiones GPT, la partición `rootfs` inicia exactamente en el **sector `659456`** (`0x14200000`). Muchos scripts antiguos intentaban escribir la imagen en el sector `660480`. Esa diferencia de 1024 sectores (512 KB) desplaza el superbloque de ext4, causando que el kernel de Linux lance un *kernel panic* (`VFS: Unable to mount root fs on unknown-block`) y se apague.
- **Solución**: La imagen del sistema se escribe estrictamente en el sector **`659456`**.

### 3. Formato Android Sparse Image al flashear por EDL
- **Problema**: El archivo `rootfs.img` oficial de OpenStick viene en formato comprimido *Android Sparse Image* (`magic 0xed26ff3a`). Si se graba directamente mediante EDL sin descompresión previa, el disco contiene fragmentos dispersos ilegibles para el kernel.
- **Solución**: [`tools/unsparse.py`](tools/unsparse.py) convierte el Sparse Image a un sistema de archivos ext4 crudo real (`rootfs_raw.img` de 2.0 GB) listo para montarse.

---

## 🛠️ Herramientas Incluidas

| Script | Descripción |
| :--- | :--- |
| [`tools/build_gpt.py`](tools/build_gpt.py) | Genera la tabla GPT limpia con CRCs válidos para memorias de 3.9 GB. |
| [`tools/unsparse.py`](tools/unsparse.py) | Descomprime `rootfs.img` (Android Sparse) a `rootfs_raw.img` (ext4 raw). |
| [`tools/fastboot_manager.py`](tools/fastboot_manager.py) | Envía comandos a Fastboot vía PyUSB sin requerir herramientas de Android SDK. |
| [`tools/usb_gateway.py`](tools/usb_gateway.py) | Pasarela HTTP/HTTPS en Windows para compartir Internet al stick por USB. |
| [`tools/configure_stick.py`](tools/configure_stick.py) | Sincroniza reloj y configura repositorios APT en Debian por SSH. |
| [`tools/flash_edl.py`](tools/flash_edl.py) | Script de flasheo automatizado por EDL 9008. |

---

## 🚀 Guía Paso a Paso

### Paso 1: Configurar Drivers en Windows
1. Descarga **Zadig** (o utiliza el instalado en el sistema).
2. Conecta el módem en modo EDL (**QHSUSB__BULK** / `05C6:9008`):
   - Asigna el controlador **WinUSB**.
3. Conecta el módem en modo Fastboot (**Android** / `18D1:D00D`):
   - Asigna el controlador **WinUSB**.

### Paso 2: Respaldo Obligatorio de Calibración e IMEI
Antes de modificar cualquier partición, extrae las particiones críticas de tu dispositivo con `edl.py`:
```bash
python edl.py --loader=prog_emmc_firehose_8916.mbn r sec calibration/sec.bin
python edl.py --loader=prog_emmc_firehose_8916.mbn r fsc calibration/fsc.bin
python edl.py --loader=prog_emmc_firehose_8916.mbn r fsg calibration/fsg.bin
python edl.py --loader=prog_emmc_firehose_8916.mbn r modemst1 calibration/modemst1.bin
python edl.py --loader=prog_emmc_firehose_8916.mbn r modemst2 calibration/modemst2.bin
```
> [!IMPORTANT]
> Guarda estos archivos en un lugar seguro. Contienen el IMEI único y la calibración de antenas de tu módem.

### Paso 3: Preparar Imágenes
1. Generar la tabla de particiones:
   ```bash
   python tools/build_gpt.py
   ```
2. Descomprimir el sistema de archivos:
   ```bash
   python tools/unsparse.py openstick/debian/rootfs.img openstick/debian/rootfs_raw.img
   ```

### Paso 4: Flashear el Sistema
Ejecuta el script de flasheo EDL:
```bash
python tools/flash_edl.py
```
El proceso escribirá el gestor de arranque LK1ST, firmware, kernel de Linux y el sistema ext4 en el sector **659456**.

### Paso 5: Primer Arranque
Al encenderse, el bootloader **LK1ST** esperará en modo Fastboot. Ejecuta:
```bash
python tools/fastboot_manager.py continue
```
En unos segundos, Windows reconocerá el dispositivo de red **Remote NDIS Compatible Device**.

---

## 🌐 Conexión y Acceso al Sistema

### Por Cable USB (RNDIS)
- **IP del Stick**: `192.168.200.1`
- **Usuario**: `user`
- **Contraseña**: `1`
- **Superusuario (root)**: `sudo su` (contraseña: `1`)
- **Acceso SSH**:
  ```bash
  ssh user@192.168.200.1
  ```

### Por Wi-Fi (Punto de Acceso Hotspot)
- **Nombre de Red (SSID)**: `4G-UFI-XX`
- **Contraseña Wi-Fi**: `1234567890`
- **IP del Stick en Wi-Fi**: `192.168.100.1`

---

## ⚡ Compartir Internet por USB desde Windows

Para que el módem pueda actualizar repositorios (`apt-get update`) y descargar paquetes a través del cable USB:

1. **En la PC (Windows)**, inicia la pasarela:
   ```bash
   python tools/usb_gateway.py
   ```
2. **Configura el módem automáticamente**:
   ```bash
   python tools/configure_stick.py
   ```
3. ¡Listo! Ahora puedes instalar herramientas en el módem por SSH:
   ```bash
   sudo apt install -y btop fastfetch git htop
   ```

---

## 📱 Manejo del Módem 4G LTE

El módem celular interno es gestionado por **ModemManager**:

```bash
# Ver estado del módem e IMEI
mmcli -m 0

# Conectar a la red de datos celulares (con tarjeta SIM insertada)
sudo nmcli connection up lte
```

---

## 📄 Licencia

Este proyecto está bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.
