#!/usr/bin/env python3

import os
import argparse
import subprocess
from pathlib import Path
import sys
import yaml
import fnmatch
import platform
import logging
import json
from datetime import datetime, timedelta

def setup_logging(log_file='collect_context.log'):
    """Configure logging for the script."""
    logging.basicConfig(
        filename=log_file,
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filemode='w'  # Overwrite log file each run
    )
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

def gather_system_info(project_root="."):
    system_info = {}
    
    # Operating System and Kernel
    system_info['operating_system'] = platform.platform()
    system_info['kernel_version'] = platform.release()
    
    # Hardware Information
    try:
        cpu_info = subprocess.check_output("lscpu | grep 'Model name'", shell=True).decode().strip()
        memory_info = subprocess.check_output("free -h | grep 'Mem:'", shell=True).decode().strip()
        swap_info = subprocess.check_output("free -h | grep 'Swap:'", shell=True).decode().strip()
        system_info['hardware'] = {
            'cpu': cpu_info.split(":")[1].strip(),
            'memory': memory_info.split(":")[1].strip(),
            'swap': swap_info.split(":")[1].strip()
        }
        logging.info("Hardware information gathered successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error gathering hardware info: {e}")
        system_info['hardware'] = "Error gathering hardware info."
    
    # Disk Usage
    try:
        disk_info = subprocess.check_output("df -h /", shell=True).decode().strip().split("\n")[1]
        system_info['disk_usage'] = {
            'root_partition': disk_info
        }
        
        # Additional Mounts
        additional_mounts = subprocess.check_output("df -h | grep '^/dev/' | grep -v '/$'", shell=True).decode().strip().split("\n")
        system_info['disk_usage']['additional_mounts'] = [
            f"{mount.split()[5]} ({mount.split()[3]} free out of {mount.split()[1]})" for mount in additional_mounts
        ]
        logging.info("Disk usage information gathered successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error gathering disk usage info: {e}")
        system_info['disk_usage'] = "Error gathering disk usage info."
    
    # Docker Environment
    try:
        docker_client_version = subprocess.check_output("docker --version", shell=True).decode().strip()
        docker_server_version = subprocess.check_output("docker version -f '{{.Server.Version}}'", shell=True).decode().strip()
        storage_driver = subprocess.check_output("docker info -f '{{.Driver}}'", shell=True).decode().strip()
        containers_running = subprocess.check_output("docker ps -q | wc -l", shell=True).decode().strip()
        images_available = subprocess.check_output("docker images -q | wc -l", shell=True).decode().strip()
        # Docker extensions can be manually listed if not available via CLI
        docker_extensions = "Buildx, Compose, Debug, Dev Environments, Docker Scout"
        system_info['docker_environment'] = {
            'client_version': docker_client_version,
            'server_version': docker_server_version,
            'storage_driver': storage_driver,
            'containers_running': containers_running,
            'images_available': images_available,
            'docker_extensions_installed': docker_extensions
        }
        logging.info("Docker environment information gathered successfully.")
    except subprocess.CalledProcessError as e:
        logging.warning(f"Docker daemon may not be running or Docker is not installed: {e}")
        system_info['docker_environment'] = "Docker daemon not running or Docker not installed."
    
    # Installed Python Packages
    try:
        installed_packages = subprocess.check_output("pip list --format=freeze", shell=True).decode().strip().split("\n")
        system_info['installed_python_packages'] = {}
        for pkg in installed_packages:
            if "==" in pkg:
                name, version = pkg.split("==")
                # Categorize packages manually or using predefined categories
                # For simplicity, we'll list them under 'general_libraries'
                system_info['installed_python_packages'].setdefault('general_libraries', []).append(f"{name}=={version}")
        logging.info("Installed Python packages gathered successfully.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error gathering Python packages: {e}")
        system_info['installed_python_packages'] = "Error gathering Python packages."
    
    # Virtual Environments
    system_info['virtual_environments'] = discover_virtual_envs(project_root)
    
    # ExpressVPN Setup Details (Kept as per context)
    system_info['expressvpn_setup'] = {
        'installation': {
            'description': "Installed ExpressVPN on Ubuntu by downloading and installing the .deb package.",
            'steps': [
                "Downloaded and installed the ExpressVPN .deb package.",
                "Restarted the expressvpnd service to ensure proper operation."
            ]
        },
        'ipv6_disabled': {
            'description': "Disabled IPv6 to prevent IPv6 leaks.",
            'steps': [
                "Edited /etc/default/grub to add ipv6.disable=1.",
                "Generated a new GRUB configuration and rebooted the system.",
                "Verified IPv6 was disabled using 'ip a | grep inet6'."
            ]
        },
        'traffic_routing': {
            'description': "Ensured all traffic routes through a UK-based IP.",
            'steps': [
                "Used 'curl ifconfig.me' to check the public IP address before and after connecting to ExpressVPN.",
                "Confirmed traffic routing through a UK-based IP after connection."
            ]
        },
        'auto_connect_network_lock': {
            'description': "Enabled auto-connect and Network Lock (kill switch).",
            'steps': [
                "Enabled auto-connect at startup using 'expressvpn autoconnect true'.",
                "Enabled Network Lock with 'expressvpn preferences set network_lock on'."
            ]
        },
        'bashrc_modification': {
            'description': "Configured automatic connection to UK - London server upon terminal login.",
            'steps': [
                "Edited .bashrc to include 'expressvpn connect \"UK - London\"'."
            ]
        }
    }
    
    return system_info

def discover_virtual_envs(project_root="."):
    virtual_envs = []
    for root, dirs, files in os.walk(project_root):
        if 'bin' in dirs and 'activate' in os.listdir(os.path.join(root, 'bin')):
            venv_path = os.path.join(root, 'bin', 'activate')
            name = os.path.basename(root)
            virtual_envs.append({
                'name': name,
                'location': os.path.dirname(venv_path),
                'activation_command': f"source {venv_path}"
            })
            # Prevent descending into this directory
            dirs[:] = [d for d in dirs if d != 'bin']
    logging.info(f"Discovered {len(virtual_envs)} virtual environment(s).")
    return virtual_envs

def load_config(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        logging.info(f"Configuration loaded from {config_path}.")
        return config
    except Exception as e:
        logging.error(f"Error loading config file {config_path}: {e}")
        return {}

def should_exclude(file_name, exclude_patterns):
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(file_name, pattern):
            return True
    return False

def collect_files(target_dir, extensions, included_dirs=None, exclude_patterns=None):
    collected = []
    included_dirs_abs = [os.path.abspath(os.path.join(target_dir, d)) for d in included_dirs] if included_dirs else [target_dir]

    for included_dir in included_dirs_abs:
        if not os.path.isdir(included_dir):
            logging.warning(f"Included directory {included_dir} does not exist.")
            continue

        # Use os.scandir to list files without traversing subdirectories
        try:
            with os.scandir(included_dir) as it:
                for entry in it:
                    if entry.is_file():
                        if any(entry.name.endswith(ext) for ext in extensions):
                            if exclude_patterns and should_exclude(entry.name, exclude_patterns):
                                logging.debug(f"Excluded file: {entry.name}")
                                continue
                            file_path = os.path.join(included_dir, entry.name)
                            relative_path = os.path.relpath(file_path, target_dir)
                            collected.append((relative_path, file_path))
        except Exception as e:
            logging.error(f"Error accessing directory {included_dir}: {e}")

    logging.info(f"Collected {len(collected)} file(s) from included directories.")
    return collected

def read_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        logging.debug(f"Read file: {file_path}")
        return content
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
        return f"<!-- Error reading file {file_path}: {e} -->\n"

def get_virtual_env():
    venv = os.environ.get('VIRTUAL_ENV')
    if venv:
        logging.info(f"Active virtual environment: {venv}")
        return venv
    else:
        logging.info("No active virtual environment detected.")
        return "<!-- No virtual environment detected -->"

def get_pip_freeze():
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True, check=True)
        logging.info("Obtained pip freeze.")
        return result.stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"Error obtaining pip freeze: {e}")
        return f"<!-- Error obtaining pip freeze: {e} -->\n"

def collect_ssl_certs(cert_dir, exclude_patterns=None):
    certs = []
    if not os.path.isdir(cert_dir):
        certs.append(f"<!-- SSL cert directory {cert_dir} does not exist -->\n")
        logging.warning(f"SSL cert directory {cert_dir} does not exist.")
        return certs

    try:
        with os.scandir(cert_dir) as it:
            for entry in it:
                if entry.is_file():
                    if exclude_patterns and should_exclude(entry.name, exclude_patterns):
                        logging.debug(f"Excluded SSL cert file: {entry.name}")
                        continue
                    file_path = os.path.join(cert_dir, entry.name)
                    relative_path = os.path.relpath(file_path, cert_dir)
                    content = read_file(file_path)
                    # Exclude key files and .csr files based on patterns
                    if any(fnmatch.fnmatch(relative_path, pattern) for pattern in ['*.key', '*.pem', '*.crt', '*.csr']):
                        logging.debug(f"Excluded SSL cert file based on pattern: {relative_path}")
                        continue
                    certs.append(f"===== SSL CERT: {relative_path} =====\n{content}\n")
                    logging.debug(f"Collected SSL certificate: {relative_path}")
    except Exception as e:
        certs.append(f"<!-- Error accessing SSL cert directory {cert_dir}: {e} -->\n")
        logging.error(f"Error accessing SSL cert directory {cert_dir}: {e}")

    logging.info(f"Collected {len(certs)} SSL certificate(s).")
    return certs

def format_system_setup(system_setup):
    if not system_setup:
        return "<!-- No system setup information provided -->\n"
    
    def recurse_format(data, indent=0):
        formatted = ""
        indent_str = "  " * indent
        if isinstance(data, dict):
            for key, value in data.items():
                # Replace underscores with spaces and capitalize
                formatted += f"{indent_str}{key.replace('_', ' ').capitalize()}: "
                if isinstance(value, (dict, list)):
                    formatted += "\n" + recurse_format(value, indent + 1)
                else:
                    formatted += f"{value}\n"
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    formatted += f"{indent_str}-\n" + recurse_format(item, indent + 1)
                else:
                    formatted += f"{indent_str}- {item}\n"
        return formatted

    return recurse_format(system_setup)

def main():
    setup_logging()

    # Gather system information
    system_setup = gather_system_info()

    parser = argparse.ArgumentParser(description="Collect project context for LLM.")
    parser.add_argument(
        '-c', '--config',
        type=str,
        default='config.yaml',
        help='Path to the configuration YAML file (default: config.yaml)'
    )
    parser.add_argument(
        '-o', '--output_file',
        type=str,
        default='llm_context.txt',
        help='Output file name (default: llm_context.txt)'
    )
    parser.add_argument(
        '-cdir', '--cert_dir',
        type=str,
        default='/home/nick/betfair_certs',
        help='Directory containing SSL certificates (default: /home/nick/betfair_certs)'
    )

    args = parser.parse_args()
    config_path = os.path.abspath(args.config)
    output_file = os.path.abspath(args.output_file)
    cert_dir = os.path.abspath(args.cert_dir)

    config = load_config(config_path)

    included_dirs = config.get('included_directories', ["."])  # Default to current directory
    file_extensions = config.get('file_extensions', [".py", ".json", ".md", ".env"])
    exclude_files = config.get('exclude_files', [])
    llm_instructions = config.get('llm_instructions', [])

    logging.info(f"Included directories: {included_dirs}")
    logging.info(f"File extensions to include: {file_extensions}")
    logging.info(f"Files to exclude: {exclude_files}")

    target_dir = os.path.abspath(".")  # Assuming the script is run from the project root

    # Collect files
    logging.info(f"Collecting files from {target_dir}...")
    files = collect_files(
        target_dir,
        extensions=file_extensions,
        included_dirs=included_dirs,
        exclude_patterns=exclude_files
    )

    # Include .env separately if it's in the included directories and not excluded
    env_path = os.path.join(target_dir, '.env')
    if os.path.isfile(env_path):
        env_included = any(
            os.path.abspath(env_path).startswith(os.path.abspath(os.path.join(target_dir, d))) for d in included_dirs
        )
        env_excluded = should_exclude('.env', exclude_files)
        if env_included and not env_excluded:
            # Check if .env is already in collected files to prevent duplication
            if not any(rel_path == '.env' for rel_path, _ in files):
                files.append(('.env', env_path))
                logging.info(".env file included in context collection.")
            else:
                logging.info(".env file is already included; skipping duplicate.")
        else:
            logging.info(".env file is excluded based on the configuration.")
    else:
        logging.warning(".env file not found.")

    # Ensure the output directory exists
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            logging.info(f"Created output directory: {output_dir}")
        except Exception as e:
            logging.error(f"Error creating output directory {output_dir}: {e}")
            sys.exit(1)

    # Delete the existing output file if it exists
    if os.path.isfile(output_file):
        try:
            os.remove(output_file)
            logging.info(f"Deleted existing output file: {output_file}")
        except Exception as e:
            logging.error(f"Error deleting output file {output_file}: {e}")
            sys.exit(1)

    try:
        with open(output_file, 'w', encoding='utf-8') as out:
            # Write LLM Instructions
            if llm_instructions:
                out.write("===== LLM INSTRUCTIONS =====\n")
                for instruction in llm_instructions:
                    out.write(f"{instruction}\n")
                out.write("\n")
                logging.info("LLM Instructions written to context file.")

            # Write System Setup Summary
            if system_setup:
                out.write("===== SYSTEM SETUP SUMMARY =====\n")
                formatted_system_setup = format_system_setup(system_setup)
                out.write(formatted_system_setup + "\n")
                logging.info("System Setup Summary written to context file.")
            else:
                out.write("<!-- No system setup information provided -->\n\n")
                logging.warning("No system setup information available.")

            # Write collected files
            for relative_path, full_path in files:
                out.write(f"===== FILE: {relative_path} =====\n")
                content = read_file(full_path)
                out.write(content + "\n\n")
                logging.info(f"Collected file: {relative_path}")

            # Write virtual environment details
            out.write("===== VIRTUAL ENVIRONMENT =====\n")
            venv = get_virtual_env()
            out.write(f"{venv}\n\n")
            logging.info("Virtual environment details written to context file.")
            
            # Write pip freeze
            out.write("===== INSTALLED PACKAGES (pip freeze) =====\n")
            pip_freeze = get_pip_freeze()
            out.write(pip_freeze + "\n")
            logging.info("Installed Python packages written to context file.")
            
            # Write SSL certificates
            out.write("===== SSL CERTIFICATES =====\n")
            ssl_certs = collect_ssl_certs(cert_dir, exclude_patterns=['*.key', '*.pem', '*.crt', '*.csr'])
            for cert in ssl_certs:
                out.write(cert + "\n")
                cert_name = cert.split('===== SSL CERT: ')[1].split(' =====')[0]
                logging.info(f"Collected SSL certificate: {cert_name}")

        logging.info(f"Context collection complete. Output written to {output_file}")
        print(f"Context collection complete. Output written to {output_file}")

    except Exception as e:
        logging.error(f"Error writing to output file {output_file}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
