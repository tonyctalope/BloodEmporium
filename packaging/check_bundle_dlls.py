"""Verifies every DLL a bundled binary imports is actually present in the bundle.

PyInstaller 5.3 predates delvewheel's `<package>.libs` convention, so it collects a wheel's compiled
extensions but not the hash-suffixed DLLs they were linked against. The result imports cleanly on the build
machine - which has the unmangled system copies - and dies with "DLL load failed ... The specified module
could not be found" on a user's machine. This catches that at build time.

Usage: python packaging/check_bundle_dlls.py <bundle directory>
"""
import os
import struct
import sys

# resolved by Windows itself, never shipped in a bundle
SYSTEM_PREFIXES = ("api-ms-win-", "ext-ms-win-")
SYSTEM_DLLS = {
    "advapi32.dll", "bcrypt.dll", "cabinet.dll", "comctl32.dll", "comdlg32.dll", "crypt32.dll", "d3d11.dll",
    "dbghelp.dll", "dwmapi.dll", "dxgi.dll", "gdi32.dll", "gdiplus.dll", "glu32.dll", "imm32.dll",
    "iphlpapi.dll", "kernel32.dll", "kernelbase.dll", "mf.dll", "mfplat.dll", "mfreadwrite.dll", "mpr.dll",
    "msvcrt.dll", "netapi32.dll", "normaliz.dll", "ntdll.dll", "ole32.dll", "oleaut32.dll", "opengl32.dll",
    "pdh.dll", "powrprof.dll", "psapi.dll", "rpcrt4.dll", "secur32.dll", "setupapi.dll", "shell32.dll",
    "shlwapi.dll", "user32.dll", "userenv.dll", "usp10.dll", "uxtheme.dll", "version.dll", "winmm.dll",
    "wintrust.dll", "ws2_32.dll", "wsock32.dll", "wtsapi32.dll", "dnsapi.dll", "cfgmgr32.dll",
    "d3dcompiler_47.dll", "winhttp.dll", "wldap32.dll", "authz.dll", "credui.dll", "dhcpcsvc.dll",
    "bcryptprimitives.dll", "d3d9.dll", "imagehlp.dll", "ncrypt.dll", "winspool.drv", "ntoskrnl.exe",
}


def imported_dlls(data):
    if data[:2] != b"MZ":
        return []
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        return []

    coff = e_lfanew + 4
    num_sections, = struct.unpack_from("<H", data, coff + 2)
    opt_size, = struct.unpack_from("<H", data, coff + 16)
    opt = coff + 20
    magic, = struct.unpack_from("<H", data, opt)
    directories = opt + (96 if magic == 0x10B else 112)
    import_rva, _ = struct.unpack_from("<II", data, directories + 8)
    if import_rva == 0:
        return []

    sections = []
    table = opt + opt_size
    for i in range(num_sections):
        entry = table + i * 40
        virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from("<IIII", data, entry + 8)
        sections.append((virtual_address, max(virtual_size, raw_size), raw_pointer))

    def offset_of(rva):
        for virtual_address, size, raw_pointer in sections:
            if virtual_address <= rva < virtual_address + size:
                return raw_pointer + (rva - virtual_address)
        return None

    names, index = [], 0
    base = offset_of(import_rva)
    if base is None:
        return []
    while True:
        fields = struct.unpack_from("<IIIII", data, base + index * 20)
        if not any(fields):
            break
        name_offset = offset_of(fields[3])
        if name_offset is None:
            break
        names.append(data[name_offset:data.index(b"\0", name_offset)].decode("ascii", "replace"))
        index += 1
    return names


def main(root):
    binaries = {}
    for directory, _, files in os.walk(root):
        for name in files:
            if name.lower().endswith((".dll", ".pyd", ".exe")):
                binaries.setdefault(name.lower(), os.path.join(directory, name))

    missing = {}
    for name in sorted(binaries):
        with open(binaries[name], "rb") as f:
            data = f.read()
        for dependency in imported_dlls(data):
            key = dependency.lower()
            if key in binaries or key in SYSTEM_DLLS or key.startswith(SYSTEM_PREFIXES):
                continue
            missing.setdefault(dependency, []).append(name)

    print(f"checked {len(binaries)} binaries in {root}")
    if not missing:
        print("every imported DLL is present in the bundle")
        return 0

    print(f"\n{len(missing)} imported DLL(s) are NOT in the bundle:")
    for dependency, importers in sorted(missing.items()):
        shown = ", ".join(importers[:6]) + (" ..." if len(importers) > 6 else "")
        print(f"  {dependency}\n      imported by: {shown}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
