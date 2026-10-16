#!/usr/bin/env bash
# Print the path from a bare Ubuntu machine to watching a movie.
# This script only prints. It does not install packages, pull images, or download media.
set -euo pipefail

cat <<'EOF'
Jellyfin at home, one command

Derived from bryce-hoehn/automated-jellyfin-guide
(https://github.com/bryce-hoehn/automated-jellyfin-guide), a mirror of
https://codeberg.org/bhoehn/automated-jellyfin-guide by Bryce Hoehn.

This text only prints the steps. The install command at the end is the
one that pulls container images.

1. Start the server
   On Linux this also installs Docker and Python 3 when they are missing.
   On a Mac or Windows machine, install Docker Desktop first.

       curl -fsSL https://raw.githubusercontent.com/Cosmin-Mare/jellyfin-kit/main/install.sh | bash

   The files land in ~/jellyfin-kit. It asks for an admin password, a VPN
   login if you want one, and how to open Jellyfin from outside. Press
   Enter to keep the generated password. Answer no to the VPN, or pass
   an OpenVPN login you already have (the guide uses IVPN).

   If Docker or any app is already installed, the command says so. When
   a config is already there, it asks before repairing it, and it still
   installs whatever is missing.

   To skip the questions:

       curl -fsSL https://raw.githubusercontent.com/Cosmin-Mare/jellyfin-kit/main/install.sh | bash -s -- --yes --no-vpn

   The password is printed and saved in credentials.txt. The same login
   is used for every app below.

   Jellyfin    http://127.0.0.1:8096   play the files
   Seerr       http://127.0.0.1:5055   request a title
   Radarr      http://127.0.0.1:7878   movies
   Sonarr      http://127.0.0.1:8989   TV series
   Prowlarr    http://127.0.0.1:9696   indexers
   qBittorrent http://127.0.0.1:8080   downloads

   If the command stops early, run the command it prints.
   A missing VPN login wants OPENVPN_USER and OPENVPN_PASSWORD,
   or --no-vpn. A missing Docker install wants Docker Desktop on a Mac
   or Windows machine, then the same ./install.sh again.

2. Add an indexer
   In Prowlarr, open Indexers, Add Indexer, and choose Torznab.
   Fill it from an indexer account you already have:

       URL        the Torznab base URL
       API Path   usually /api
       API Key    the key from that account

   Test, then Save. Sonarr and Radarr receive the indexer from Prowlarr.

3. Request a movie and play it
   In Seerr, sign in, search, open the match, and click Request.
   A movie shows up in Radarr. A series shows up in Sonarr.
   Open the title and choose Search. A release you have the right to
   store is filed into media/movies or media/tv. Play it in Jellyfin.
   If you copied the file in by hand, scan the library.

   The example film is the public-domain short A Trip to the Moon (1902).

4. Watch from another network
   Jellyfin and Seerr can leave the house. Sonarr, Radarr, Prowlarr,
   and qBittorrent stay on this computer. Pick one.

   A domain already Active on Cloudflare:

       CLOUDFLARE_API_TOKEN='...' CLOUDFLARE_HOSTNAME='watch.example.com' \
         ./install.sh --yes --remote cloudflare

   Create the token at https://dash.cloudflare.com/profile/api-tokens
   with Account / Cloudflare Tunnel / Edit, Zone / DNS / Edit, and
   Zone / Zone / Read. watch.example.com plays Jellyfin.
   requests.example.com is the request page.
   A missing token stops before Docker and prints the page to open.
   A rejected token, a domain that is not on the account, or a hostname
   that is already a different DNS record leaves the local server up
   and prints what to fix. Long videos can fail on a free Cloudflare
   plan. If playback stops, use one of the two commands below.

   A router you can open:

       ./install.sh --yes --remote forward

   Test the printed address from a phone that is not on the Wi-Fi.
   If the router does not answer, the command prints the two TCP
   forwards and, when a firewall is in the way:

       sudo ufw allow 8096/tcp && sudo ufw allow 5055/tcp

   If the router reports a private or carrier address, use Tailscale.

   No domain, and the router cannot forward a port:

       ./install.sh --yes --remote tailscale

   Open the sign-in link, then install Tailscale on the device you
   watch from and use the same account:
   https://tailscale.com/download
   Rerun the command. It prints an address such as http://100.x.x.x:8096.
   If Tailscale is missing, or the link expired, it prints the command
   to finish. On a Mac that is https://tailscale.com/download/mac
   and then: sudo tailscale up

Full write-up, including day-to-day commands:

    https://github.com/Cosmin-Mare/jellyfin-kit

Preview again without pulling images:

    bash script.sh
    ./install.sh --dry-run
EOF
