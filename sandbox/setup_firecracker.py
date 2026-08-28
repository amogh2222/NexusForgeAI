#!/usr/bin/env python3
import os
import urllib.request
import platform
import stat

def download_file(url, dest_path):
    print(f"Downloading {url} to {dest_path}...")
    urllib.request.urlretrieve(url, dest_path)

def main():
    if platform.system() != "Linux":
        print("Firecracker is only supported on Linux.")
        return

    arch = platform.machine()
    if arch == "x86_64":
        arch_str = "x86_64"
    elif arch == "aarch64":
        arch_str = "aarch64"
    else:
        print(f"Unsupported architecture: {arch}")
        return

    base_dir = "/var/lib/firecracker"
    os.makedirs(base_dir, exist_ok=True)

    # Download vmlinux (kernel)
    kernel_url = f"https://s3.amazonaws.com/spec.ccfc.min/img/quickstart_guide/{arch_str}/kernels/vmlinux.bin"
    kernel_path = os.path.join(base_dir, "vmlinux")
    if not os.path.exists(kernel_path):
        download_file(kernel_url, kernel_path)

    # Download rootfs
    rootfs_url = f"https://s3.amazonaws.com/spec.ccfc.min/img/quickstart_guide/{arch_str}/rootfs/bionic.rootfs.ext4"
    rootfs_path = os.path.join(base_dir, "rootfs.ext4")
    if not os.path.exists(rootfs_path):
        download_file(rootfs_url, rootfs_path)

    # Download firecracker binary
    fc_url = f"https://github.com/firecracker-microvm/firecracker/releases/download/v1.7.0/firecracker-v1.7.0-{arch_str}.tgz"
    fc_tar_path = os.path.join(base_dir, "firecracker.tgz")
    if not os.path.exists(os.path.join(base_dir, "firecracker")):
        download_file(fc_url, fc_tar_path)
        os.system(f"tar -xzf {fc_tar_path} -C {base_dir}")
        os.rename(os.path.join(base_dir, f"firecracker-v1.7.0-{arch_str}"), os.path.join(base_dir, "firecracker"))
        os.chmod(os.path.join(base_dir, "firecracker"), stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        # Link to /usr/local/bin
        os.system(f"ln -sf {os.path.join(base_dir, 'firecracker')} /usr/local/bin/firecracker")

    print("Firecracker setup complete!")

if __name__ == "__main__":
    main()
