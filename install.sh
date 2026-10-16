#!/usr/bin/env bash
# One command for the whole server: Docker on Linux, the media apps, and their accounts.
#
#   curl -fsSL https://raw.githubusercontent.com/Cosmin-Mare/jellyfin-kit/main/install.sh | bash
#
# Flags go after bash -s --, for example: bash -s -- --yes --no-vpn
set -euo pipefail

REPO_TARBALL="${JELLYFIN_KIT_URL:-https://github.com/Cosmin-Mare/jellyfin-kit/archive/refs/heads/main.tar.gz}"

script_dir() {
  if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
    cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
  fi
}

fetch_installer() {
  local dest="$1"
  local tmp base item
  tmp="$(mktemp -d)"
  if ! curl -fsSL "$REPO_TARBALL" | tar -xz -C "$tmp" --strip-components=1; then
    rm -rf "$tmp"
    return 1
  fi
  mkdir -p "$dest"
  # Refresh the program files. Leave a server that is already here alone:
  # config, media, downloads, .env, and credentials.txt.
  shopt -s dotglob nullglob
  for item in "$tmp"/*; do
    base="$(basename "$item")"
    case "$base" in
      config|media|downloads|.env|credentials.txt)
        continue
        ;;
    esac
    rm -rf "${dest}/${base}"
    mv "$item" "${dest}/${base}"
  done
  shopt -u dotglob nullglob
  rm -rf "$tmp"
}

HERE="$(script_dir || true)"
if [[ -z "${HERE}" || ! -f "${HERE}/stacklib.py" ]]; then
  if [[ -n "${HERE}" ]]; then
    DEST="${JELLYFIN_DIR:-$HERE}"
  else
    DEST="${JELLYFIN_DIR:-${HOME:-/tmp}/jellyfin-kit}"
  fi
  echo "Saving the installer to ${DEST}"
  if fetch_installer "$DEST"; then
    echo "Installer files are in ${DEST}"
  elif [[ -f "${DEST}/stacklib.py" ]]; then
    echo "Could not download the latest installer. Using the copy in ${DEST}."
    echo "Check the network, then rerun the same curl command to update."
  else
    echo "Could not download the installer from GitHub." >&2
    echo "Check the network, then rerun:" >&2
    echo "  curl -fsSL https://raw.githubusercontent.com/Cosmin-Mare/jellyfin-kit/main/install.sh | bash" >&2
    exit 1
  fi
  exec bash "${DEST}/install.sh" "$@"
fi

ROOT="$HERE"
cd "$ROOT"
echo "Working in ${ROOT}"

ensure_python() {
  if command -v python3 >/dev/null 2>&1; then
    echo "Python 3 is already installed."
    return
  fi
  echo "Python 3 is missing. Installing it..."
  if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Install Python 3, then rerun the same command." >&2
    exit 1
  fi
  if ! command -v sudo >/dev/null 2>&1; then
    echo "sudo is required to install Python 3. Install sudo, or run this command as root." >&2
    exit 1
  fi
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y python3
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --noconfirm python
  else
    echo "Install python3 with your package manager, then rerun the same command." >&2
    exit 1
  fi
}

docker_ready() {
  docker info >/dev/null 2>&1 || sudo docker info >/dev/null 2>&1
}

allow_container_forwarding() {
  # Some hosts keep an old iptables-legacy FORWARD DROP policy while Docker
  # writes its rules with iptables-nft. Containers can then see published
  # ports on the host and still be unable to reach each other.
  if ! command -v iptables-legacy >/dev/null 2>&1; then
    return
  fi
  policy="$(sudo iptables-legacy -S FORWARD 2>/dev/null | awk 'NR==1 && $1=="-P" && $2=="FORWARD" {print $3}')"
  if [[ "$policy" == "DROP" ]]; then
    echo "Allowing Docker containers to reach each other."
    sudo iptables-legacy -P FORWARD ACCEPT
  fi
}

start_docker_daemon() {
  if ! docker_ready; then
    if command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]; then
      sudo systemctl enable --now docker || true
    fi
  fi
  if ! docker_ready; then
    echo "Starting the Docker daemon..."
    if ! pgrep -x dockerd >/dev/null 2>&1; then
      sudo mkdir -p /var/log
      sudo sh -c 'dockerd >/var/log/dockerd.log 2>&1 &'
    fi
    for _ in $(seq 1 40); do
      if docker_ready; then
        break
      fi
      sleep 1
    done
  fi
  if ! docker_ready; then
    echo "Docker is installed, but the daemon did not start." >&2
    echo "On Linux, run: sudo systemctl start docker" >&2
    echo "On macOS or Windows, open Docker Desktop." >&2
    echo "Then rerun the same command. Log: /var/log/dockerd.log" >&2
    exit 1
  fi
  allow_container_forwarding
}

install_docker() {
  if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Docker is not installed." >&2
    echo "Install Docker Desktop, start it, then rerun the same command." >&2
    echo "https://docs.docker.com/desktop/" >&2
    exit 1
  fi
  if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required to install Docker. Install curl, then rerun the same command." >&2
    exit 1
  fi
  if ! command -v sudo >/dev/null 2>&1; then
    echo "sudo is required to install Docker. Install sudo, or run this command as root." >&2
    exit 1
  fi
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | sudo sh
}

ensure_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    if docker_ready; then
      echo "Docker is already installed and running."
    else
      echo "Docker is already installed, but the daemon is not running."
      echo "Starting it. If this fails: sudo systemctl start docker"
      echo "On macOS or Windows, open Docker Desktop, then rerun this command."
      start_docker_daemon
    fi
    return
  fi
  if command -v docker >/dev/null 2>&1; then
    echo "Docker is installed, and the Compose plugin is missing."
  fi
  install_docker
  start_docker_daemon
}

need_docker=1
for arg in "$@"; do
  case "$arg" in
    --help|-h|--render-only|--dry-run)
      need_docker=0
      ;;
  esac
done

ensure_python
if [[ "$need_docker" == 1 ]]; then
  ensure_docker
fi

exec python3 "$ROOT/stacklib.py" "$@"
