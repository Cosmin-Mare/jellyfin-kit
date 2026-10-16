#!/usr/bin/env bash
# Print the path from a bare Ubuntu machine to watching a movie.
# This script only prints. It does not install packages, pull images, or download media.
set -euo pipefail

cat <<'EOF'
From a bare Ubuntu machine to a movie on screen

This is derived from bryce-hoehn/automated-jellyfin-guide
(https://github.com/bryce-hoehn/automated-jellyfin-guide), a mirror of
https://codeberg.org/bhoehn/automated-jellyfin-guide by Bryce Hoehn.

Nothing in this script downloads software or a film. The install command
at the end is the one that pulls container images.

1. Bare Ubuntu
   Install Docker only if it is missing, then start the stack. From a
   checkout of this repo:

       ./install.sh --yes --no-vpn

   Add a VPN account you already have by passing OPENVPN_USER and
   OPENVPN_PASSWORD. The guide uses IVPN. Without those, --no-vpn leaves
   qBittorrent on your normal network.

   One admin username and password is created for Jellyfin, Seerr, Sonarr,
   Radarr, Prowlarr, and qBittorrent. It is printed and saved in
   credentials.txt.

2. What each app is for
   Jellyfin    http://127.0.0.1:8096   plays the files
   Seerr       http://127.0.0.1:5055   where you request a title
   Sonarr      http://127.0.0.1:8989   TV series only
   Radarr      http://127.0.0.1:7878   movies
   Prowlarr    http://127.0.0.1:9696   indexers
   qBittorrent http://127.0.0.1:8080   downloads

   Sonarr stays empty of movies. A movie request goes to Radarr.

3. Indexer example
   Prowlarr, Indexers, Add Indexer, then the card named Torznab.
   That generic form is the indexer example. Fill it from an indexer
   account you already have:

       URL        the Torznab base URL from that account
       API Path   usually /api
       API Key    the key from that account

   Test, then Save. Sonarr and Radarr already receive indexers from
   Prowlarr.

4. Request
   In Seerr, sign in with the admin account, search, open the match,
   and click Request. A movie shows up in Radarr. A series shows up
   in Sonarr. With no file yet, the title is marked missing.

5. Watch
   In Radarr or Sonarr, open the title and choose Search. A release
   you have the right to store is sent to qBittorrent, then filed into
   media/movies or media/tv. In Jellyfin, open that library and play it.
   If the file was copied in by hand, use the library menu and choose
   Scan library.

   The public-domain short used as the example is A Trip to the Moon
   (1902). A copy can come from the Internet Archive. The same Request
   button is what you use after your own Torznab account is saved.

Preview the installer without pulling images:

    bash script.sh
    curl -fsSL https://raw.githubusercontent.com/OWNER/REPO/main/script.sh | bash
    ./install.sh --dry-run

Run the real install when you want the containers:

    ./install.sh --yes --no-vpn
EOF
