#!/usr/bin/env python3
"""Genera el ZIP de entrega del proyecto y su huella SHA-256.

Uso (desde la raíz del proyecto):
    python scripts/empaquetar.py --grupo grupo03

Crea entregas/<grupo>-<fecha>.zip con el código fuente y excluye lo que no
debe entregarse: .env, dependencias instaladas, compilados y repositorio git.
Imprime la huella SHA-256 que debe registrarse en la plataforma junto al ZIP.
Solo usa la biblioteca estándar de Python 3.
"""
import argparse
import fnmatch
import hashlib
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Directorios que nunca se incluyen (en cualquier nivel).
DIRECTORIOS_EXCLUIDOS = {
    ".git", "node_modules", "dist", "__pycache__", ".venv", "venv", ".idea", ".vscode",
    "entregas", ".pytest_cache", ".mypy_cache", "__MACOSX",
}
# Archivos que nunca se incluyen.
ARCHIVOS_EXCLUIDOS = [".env", ".env.*", "*.pyc", "*.o", ".DS_Store", "Thumbs.db", "*.zip", "*.log", "worker/robot"]
# Excepción: la plantilla de variables sí se entrega.
PERMITIDOS = {".env.example"}

MAX_MB = 50


def excluido(ruta_relativa: Path) -> bool:
    if any(parte in DIRECTORIOS_EXCLUIDOS for parte in ruta_relativa.parts[:-1]):
        return True
    nombre = ruta_relativa.name
    if nombre in PERMITIDOS:
        return False
    texto = ruta_relativa.as_posix()
    return any(fnmatch.fnmatch(nombre, patron) or fnmatch.fnmatch(texto, patron) for patron in ARCHIVOS_EXCLUIDOS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--grupo", required=True, help="identificador del grupo, por ejemplo grupo03")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", args.grupo):
        print("El identificador del grupo solo admite letras, números, guion y guion bajo.", file=sys.stderr)
        return 1

    if not (RAIZ / "ENTREGA.md").exists():
        print("Falta ENTREGA.md en la raíz del proyecto.", file=sys.stderr)
        return 1

    salida_dir = RAIZ / "entregas"
    salida_dir.mkdir(exist_ok=True)
    salida = salida_dir / f"{args.grupo}-{datetime.now():%Y%m%d-%H%M}.zip"

    archivos = sorted(
        p for p in RAIZ.rglob("*")
        if p.is_file() and not p.is_symlink() and not excluido(p.relative_to(RAIZ))
    )
    with zipfile.ZipFile(salida, "w", compression=zipfile.ZIP_DEFLATED) as zip_salida:
        for archivo in archivos:
            zip_salida.write(archivo, Path(args.grupo) / archivo.relative_to(RAIZ))

    tamano_mb = salida.stat().st_size / (1024 * 1024)
    huella = hashlib.sha256(salida.read_bytes()).hexdigest()
    (salida.parent / (salida.name + ".sha256")).write_text(f"{huella}  {salida.name}\n", encoding="utf-8")

    print(f"Archivo:  {salida.relative_to(RAIZ)}  ({len(archivos)} archivos, {tamano_mb:.1f} MB)")
    print(f"SHA-256:  {huella}")
    if tamano_mb > MAX_MB:
        print(f"Advertencia: supera {MAX_MB} MB. Revise si incluyó archivos que no son código.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
