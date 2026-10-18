#!/usr/bin/env bash
# Remove the library this installer created.
#
#   bash ~/jellyfin-kit/uninstall.sh
#   curl -fsSL https://raw.githubusercontent.com/Cosmin-Mare/jellyfin-kit/main/uninstall.sh | bash
#
# It removes the player, the search page, the shelves, and the downloader,
# plus their settings and half-finished downloads.
# Movies and shows in media/ are kept unless you say to delete them.
# Docker and Tailscale are left installed unless you say otherwise.
# They may be used by other programs on this computer.
set -euo pipefail

ASSUME_YES=0
DELETE_MEDIA=0
REMOVE_DOCKER=0
REMOVE_TAILSCALE=0

for arg in "$@"; do
  case "$arg" in
    --yes|-y) ASSUME_YES=1 ;;
    --media) DELETE_MEDIA=1 ;;
    --docker) REMOVE_DOCKER=1 ;;
    --tailscale) REMOVE_TAILSCALE=1 ;;
    --help|-h)
      cat <<'EOF'
Remove the Jellyfin library installed by install.sh.

  bash uninstall.sh

Asks before deleting your movies, and before removing Docker or Tailscale.

  bash uninstall.sh --yes
      Remove the apps, settings, and unfinished downloads. Keep movies.
  bash uninstall.sh --yes --media
      Also delete media/ (your movies and shows).
  bash uninstall.sh --yes --docker --tailscale
      Also uninstall Docker and Tailscale from this computer.
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      echo "Run: bash uninstall.sh --help" >&2
      exit 1
      ;;
  esac
done

script_dir() {
  if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
    cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
  fi
}

looks_like_install() {
  [[ -f "$1/docker-compose.yml" || -f "$1/.env" || -d "$1/config" ]]
}

HERE="$(script_dir || true)"
if [[ -n "${JELLYFIN_DIR:-}" ]]; then
  ROOT="$JELLYFIN_DIR"
elif [[ -n "$HERE" ]] && looks_like_install "$HERE"; then
  ROOT="$HERE"
elif looks_like_install "${HOME:-}/jellyfin-kit"; then
  ROOT="${HOME}/jellyfin-kit"
else
  echo "Could not find an install to remove." >&2
  echo "Run this from the install folder, or set JELLYFIN_DIR to that folder." >&2
  echo "The curl install uses ~/jellyfin-kit." >&2
  exit 1
fi

ask() {
  local prompt="$1"
  local default_yes="$2"
  if [[ "$ASSUME_YES" == 1 ]]; then
    [[ "$default_yes" == 1 ]]
    return
  fi
  local reply=""
  if [[ -r /dev/tty ]]; then
    read -r -p "$prompt" reply </dev/tty || reply=""
  elif [[ -t 0 ]]; then
    read -r -p "$prompt" reply || reply=""
  else
    [[ "$default_yes" == 1 ]]
    return
  fi
  reply="$(printf '%s' "$reply" | tr '[:upper:]' '[:lower:]')"
  if [[ -z "$reply" ]]; then
    [[ "$default_yes" == 1 ]]
    return
  fi
  [[ "$reply" == "y" || "$reply" == "yes" ]]
}

echo "This removes the library in ${ROOT}"
echo "  the player, search page, shelves, and downloader"
echo "  their settings (config/, .env, credentials.txt)"
echo "  unfinished downloads (downloads/)"
echo "Movies and shows in media/ stay unless you agree to delete them."
echo "Docker and Tailscale stay unless you agree to remove them."
echo

if ! ask "Remove this library? [Y/n] " 1; then
  echo "Left everything in place."
  exit 0
fi

if [[ "$DELETE_MEDIA" != 1 ]]; then
  if ask "Also delete the movies and shows in media/? [y/N] " 0; then
    DELETE_MEDIA=1
  fi
fi
if [[ "$REMOVE_DOCKER" != 1 ]]; then
  if ask "Also uninstall Docker from this computer? Other apps may be using it. [y/N] " 0; then
    REMOVE_DOCKER=1
  fi
fi
if [[ "$REMOVE_TAILSCALE" != 1 ]]; then
  if ask "Also uninstall Tailscale from this computer? [y/N] " 0; then
    REMOVE_TAILSCALE=1
  fi
fi

DOCKER=()
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  DOCKER=(docker)
elif command -v sudo >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
  DOCKER=(sudo docker)
fi

if [[ ${#DOCKER[@]} -gt 0 ]]; then
  echo "Stopping the library programs..."
  for file in "$ROOT/docker-compose.yml" "$ROOT/docker-compose.novpn.yml"; do
    if [[ -f "$file" ]]; then
      "${DOCKER[@]}" compose -f "$file" down --rmi all --volumes --remove-orphans || true
    fi
  done
  leftover=()
  while IFS= read -r container_id; do
    [[ -n "$container_id" ]] && leftover+=("$container_id")
  done < <("${DOCKER[@]}" ps -aq --filter label=com.docker.compose.project=jellyfin)
  if [[ ${#leftover[@]} -gt 0 ]]; then
    "${DOCKER[@]}" rm -f "${leftover[@]}" || true
  fi
else
  echo "Docker is not running, so there are no library programs to stop."
fi

echo "Removing settings and unfinished downloads..."
rm -rf "$ROOT/config" "$ROOT/downloads" "$ROOT/.env" "$ROOT/credentials.txt"

if [[ "$DELETE_MEDIA" == 1 ]]; then
  echo "Removing movies and shows..."
  rm -rf "$ROOT/media"
else
  echo "Kept ${ROOT}/media"
fi

if [[ "$REMOVE_TAILSCALE" == 1 ]]; then
  echo "Removing Tailscale..."
  if command -v tailscale >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
    sudo tailscale down || true
  fi
  if command -v apt-get >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
    sudo apt-get remove -y tailscale || true
  elif command -v dnf >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
    sudo dnf remove -y tailscale || true
  else
    echo "Tailscale is still installed. Remove it with the package manager on this computer, then rerun with --tailscale if you want this script to try again."
  fi
fi

if [[ "$REMOVE_DOCKER" == 1 ]]; then
  echo "Removing Docker..."
  if [[ "$(uname -s)" != "Linux" ]]; then
    echo "On a Mac or Windows PC, quit Docker Desktop and uninstall it from the Applications folder."
  elif command -v apt-get >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
    sudo apt-get purge -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker-ce-rootless-extras || true
    sudo rm -rf /var/lib/docker /var/lib/containerd || true
  elif command -v dnf >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
    sudo dnf remove -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin || true
  else
    echo "Docker is still installed. Remove it with the package manager on this computer."
  fi
fi

echo
echo "The library programs from ${ROOT} are removed."
if [[ "$DELETE_MEDIA" != 1 && -d "$ROOT/media" ]]; then
  echo "Your movies and shows are still in ${ROOT}/media"
fi
echo "Run the install command again whenever you want the library back."
