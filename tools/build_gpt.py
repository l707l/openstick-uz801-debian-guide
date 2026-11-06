#!/usr/bin/env python3
"""
build_gpt.py - Generador de tablas GPT válidas para módems 4G Qualcomm MSM8916 (UZ801 / OpenStick)

Soluciona el problema de los templates corruptos de OpenStick (gpt_both0.bin)
donde AlternateLBA y CRCs son 0, lo que provoca que la PBL caiga siempre en modo EDL 9008.
"""

import struct
import zlib
import uuid

SECTOR_SIZE = 512
TOTAL_SECTORS = 7634944  # 3.9 GB eMMC típico UZ801

# Definición de particiones estándar OpenStick Debian para MSM8916
# (nombre, primer_lba, ultimo_lba, guid_particion, guid_tipo)
PARTITIONS = [
    ("cdt",      131072,  131075,  "18285060-b8c8-7cf7-2823-fd5dd2956b88", "a19f205f-0000-0000-0000-000000000000"),
    ("sbl1",     262144,  263167,  "534641ab-51f1-f296-cf79-26e9c92e9002", "dea0ba2c-0000-0000-0000-000000000000"),
    ("rpm",      263168,  264191,  "4cd3470f-02ef-5e92-c4f4-14bb5251e8f1", "098df793-0000-0000-0000-000000000000"),
    ("tz",       264192,  266239,  "0929ef2f-5cbe-b222-9aff-64578c4e1feb", "a053aa7f-0000-0000-0000-000000000000"),
    ("hyp",      266240,  267263,  "bf2ea2b6-9f32-b528-99bb-c856cd988976", "e1a6a689-0000-0000-0000-000000000000"),
    ("sec",      267264,  267295,  "db68eec7-4c13-bc28-f720-2241bb41d057", "303e6ac3-0000-0000-0000-000000000000"),
    ("modemst1", 267296,  271391,  "f4c8387d-6628-200b-82cc-16025907d272", "ebbeadaf-0000-0000-0000-000000000000"),
    ("modemst2", 271392,  275487,  "45ba3e2a-d277-68a3-4a11-748d8ef623af", "0a288b1f-0000-0000-0000-000000000000"),
    ("fsc",      275488,  275489,  "28fa1c81-5b9f-3a57-290b-e8ca46eb0055", "57b90a16-0000-0000-0000-000000000000"),
    ("fsg",      393216,  397311,  "0d6c74b1-89bd-841e-4b2e-b7b23246967b", "638ff8e2-0000-0000-0000-000000000000"),
    ("aboot",    524288,  526335,  "2432ce91-198e-589b-5d6c-1e2953615a38", "400ffdcd-0000-0000-0000-000000000000"),
    ("boot",     526336,  657407,  "80780b1d-0fe1-27d3-23e4-9244e62f8c46", "20117f86-0000-0000-0000-000000000000"),
    ("devinfo",  657408,  659455,  "8b46880a-3de7-53e5-1e74-4602f82e1993", "1b81e7e6-0000-0000-0000-000000000000"),
    ("rootfs",   659456,  7634910, "a7ab80e8-e9d1-e8cd-f157-93f69b1d141e", "97d7b011-0000-0000-0000-000000000000"),
]

def create_gpt(total_sectors=TOTAL_SECTORS):
    # Entradas de particiones (128 entradas x 128 bytes = 16384 bytes)
    entries = bytearray(128 * 128)
    for i, (name, first, last, p_guid, t_guid) in enumerate(PARTITIONS):
        entry = bytearray(128)
        # Type GUID (LE)
        entry[0:16] = uuid.UUID(t_guid).bytes_le
        # Partition GUID (LE)
        entry[16:32] = uuid.UUID(p_guid).bytes_le
        # First LBA & Last LBA
        struct.pack_into("<QQ", entry, 32, first, last)
        # Flags (0)
        struct.pack_into("<Q", entry, 48, 0)
        # Name UTF-16LE
        name_bytes = name.encode("utf-16le")
        entry[56:56+len(name_bytes)] = name_bytes
        entries[i*128:(i+1)*128] = entry

    entries_crc = zlib.crc32(entries) & 0xffffffff

    # Cabecera primaria (LBA 1)
    primary_hdr = bytearray(512)
    disk_guid = uuid.UUID("36d76d40-f655-46f9-81aa-1a84f509e51f").bytes_le
    struct.pack_into(
        "<8sIIIIQQQQ16sQIII",
        primary_hdr, 0,
        b"EFI PART",       # Signature
        0x00010000,       # Revision 1.0
        92,               # Header size
        0,                # CRC32 placeholder
        0,                # Reserved
        1,                # MyLBA
        total_sectors - 1,# AlternateLBA
        34,               # FirstUsableLBA
        total_sectors - 34,# LastUsableLBA
        disk_guid,        # DiskGUID
        2,                # PartitionEntryLBA
        128,              # NumberOfPartitionEntries
        128,              # SizeOfPartitionEntry
        entries_crc       # PartitionEntryArrayCRC32
    )
    primary_crc = zlib.crc32(primary_hdr[:92]) & 0xffffffff
    struct.pack_into("<I", primary_hdr, 16, primary_crc)

    # Protective MBR
    mbr = bytearray(512)
    mbr[446:462] = struct.pack("<BBBBBBBBII", 0x00, 0x00, 0x02, 0x00, 0xEE, 0xFF, 0xFF, 0xFF, 1, total_sectors - 1)
    mbr[510:512] = b"\x55\xAA"

    primary_gpt = mbr + primary_hdr + entries
    
    with open("gpt_fixed.bin", "wb") as f:
        f.write(primary_gpt)
    print(f"[+] gpt_fixed.bin generado exitosamente ({len(primary_gpt)} bytes).")

if __name__ == "__main__":
    create_gpt()
