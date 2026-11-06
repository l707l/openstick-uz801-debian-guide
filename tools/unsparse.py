#!/usr/bin/env python3
"""
unsparse.py - Convierte una imagen Android Sparse (.img) a formato crudo (raw ext4)

Necesario cuando se flashea rootfs.img por EDL en lugar de Fastboot, ya que
escribir la imagen sparse directamente provoca que el kernel no reconozca el sistema de archivos.
"""

import struct
import sys
import os

SPARSE_HEADER_MAGIC = 0xed26ff3a
CHUNK_TYPE_RAW = 0xcac1
CHUNK_TYPE_FILL = 0xcac2
CHUNK_TYPE_DONT_CARE = 0xcac3
CHUNK_TYPE_CRC32 = 0xcac4

def unsparse(in_path, out_path):
    if not os.path.exists(in_path):
        print(f"[-] Archivo de entrada no existe: {in_path}")
        return False

    with open(in_path, "rb") as fin, open(out_path, "wb") as fout:
        header_data = fin.read(28)
        magic, major, minor, file_hdr_sz, chunk_hdr_sz, blk_sz, total_blks, total_chunks, img_checksum = struct.unpack(
            "<IHHHHIIII", header_data
        )

        if magic != SPARSE_HEADER_MAGIC:
            print("[-] No es una imagen sparse de Android válida. Ya puede ser un archivo raw.")
            return False

        print(f"[*] Sparse detectado: Bloques={total_blks}, Tamaño bloque={blk_sz}, Chunks={total_chunks}")
        total_out_size = total_blks * blk_sz
        print(f"[*] Tamaño expandido final: {total_out_size / (1024*1024*1024):.2f} GB")

        bytes_written = 0
        for i in range(total_chunks):
            chunk_header = fin.read(chunk_hdr_sz)
            chunk_type, reserved, chunk_sz, total_sz = struct.unpack("<2H2I", chunk_header[:12])
            data_sz = chunk_sz * blk_sz

            if chunk_type == CHUNK_TYPE_RAW:
                data = fin.read(data_sz)
                fout.write(data)
                bytes_written += len(data)
            elif chunk_type == CHUNK_TYPE_FILL:
                fill_val = fin.read(4)
                fill_data = fill_val * (data_sz // 4)
                fout.write(fill_data)
                bytes_written += len(fill_data)
            elif chunk_type == CHUNK_TYPE_DONT_CARE:
                fout.seek(data_sz, os.SEEK_CUR)
                bytes_written += data_sz
            elif chunk_type == CHUNK_TYPE_CRC32:
                fin.seek(4, os.SEEK_CUR)

            if i % 100 == 0 or i == total_chunks - 1:
                progress = (i + 1) / total_chunks * 100
                sys.stdout.write(f"\rProgreso: {progress:.1f}% ({bytes_written / (1024*1024):.1f} MB)")
                sys.stdout.flush()

        # Asegurar tamaño exacto del archivo al final
        fout.truncate(total_out_size)

    print(f"\n[+] Descompresión completada: {out_path} ({os.path.getsize(out_path)} bytes)")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python unsparse.py <rootfs.img> <rootfs_raw.img>")
        sys.exit(1)
    unsparse(sys.argv[1], sys.argv[2])
