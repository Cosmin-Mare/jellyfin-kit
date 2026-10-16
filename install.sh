#!/usr/bin/env bash
# One command for the automated Jellyfin guide:
# Docker, the media stack, and every local account the web UIs ask you to create.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required." >&2
  exit 1
fi

need_docker=1
for arg in "$@"; do
  case "$arg" in
    --help|-h|--render-only|--dry-run)
      need_docker=0
      ;;
  esac
done

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
    echo "Docker installed, but the daemon did not start. See /var/log/dockerd.log." >&2
    exit 1
  fi
  allow_container_forwarding
}

if [[ "$need_docker" == 1 ]]; then
  if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
    if [[ "$(uname -s)" != "Linux" ]]; then
      echo "Install Docker Desktop, then run ./install.sh again." >&2
      exit 1
    fi
    if ! command -v curl >/dev/null 2>&1; then
      echo "curl is required to install Docker." >&2
      exit 1
    fi
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sudo sh
  fi
  start_docker_daemon
fi

exec python3 "$ROOT/stacklib.py" "$@"
