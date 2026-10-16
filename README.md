# Automated Jellyfin, one command

This project is derived from [bryce-hoehn/automated-jellyfin-guide](https://github.com/bryce-hoehn/automated-jellyfin-guide), a read-only mirror of [bhoehn/automated-jellyfin-guide](https://codeberg.org/bhoehn/automated-jellyfin-guide) by Bryce Hoehn. That guide walks through a home Jellyfin server with qBittorrent, Gluetun, Prowlarr, FlareSolverr, Sonarr, and Radarr, then asks you to create each account in a browser. This repo keeps that stack and does the install and the account setup in one command.

Read the whole path, from bare Ubuntu through the Torznab indexer form to pressing play, without downloading anything. From a checkout:

```bash
bash script.sh
```

Once this repo is public, the same script is what curl runs. It still only prints. It does not install Docker, pull images, or download a film:

```bash
curl -fsSL https://raw.githubusercontent.com/OWNER/REPO/main/script.sh | bash
```

Replace `OWNER/REPO` with the GitHub path after you publish. `./install.sh --dry-run` prints the same text.

From a checkout of this repo, the command that does download the container images is:

```bash
./install.sh
```

On a fresh Linux machine that is the whole setup. The command asks for one outside account: the VPN login the guide uses for Gluetun (IVPN by default). Everything else is created for you.

Non-interactive:

```bash
OPENVPN_USER='your-vpn-user' OPENVPN_PASSWORD='your-vpn-password' ./install.sh --yes
```

Without a VPN, so downloads use your normal network:

```bash
./install.sh --yes --no-vpn
```

## What you get

| Service | URL | What the command does |
| --- | --- | --- |
| Jellyfin | http://127.0.0.1:8096 | Admin account, Movies library at `/media/movies`, TV library at `/media/tv` |
| Seerr | http://127.0.0.1:5055 | Request account signed in with that same Jellyfin admin, linked to Sonarr and Radarr |
| Sonarr | http://127.0.0.1:8989 | Login, `/tv` root folder, qBittorrent client, rename on, qualities capped at 1080p |
| Radarr | http://127.0.0.1:7878 | Login, `/movies` root folder, qBittorrent client, same quality cap. Requests use Physical/Web availability |
| Prowlarr | http://127.0.0.1:9696 | Login, Sonarr and Radarr connected, FlareSolverr registered as a proxy |
| qBittorrent | http://127.0.0.1:8080 | Permanent login, completed and incomplete folders, bound to `tun0` when the VPN is on |

Jellyfin, Seerr, Sonarr, Radarr, Prowlarr, and qBittorrent share one username and password. The command prints them and saves them in `credentials.txt` (mode 600).

qBittorrent, Prowlarr, and FlareSolverr sit behind Gluetun when the VPN is on, so their traffic leaves through the VPN. Jellyfin, Seerr, Sonarr, and Radarr stay on your normal network. Prowlarr can still reach Sonarr and Radarr on the private Docker network.

## The VPN account

Gluetun cannot invent a VPN subscription. Create one with a provider it supports, then pass that login in. The guide uses IVPN over OpenVPN:

```bash
OPENVPN_USER='...' OPENVPN_PASSWORD='...' VPN_SERVICE_PROVIDER=ivpn ./install.sh --yes
```

WireGuard instead:

```bash
VPN_TYPE=wireguard WIREGUARD_PRIVATE_KEY='...' WIREGUARD_ADDRESSES='10.x.x.x/32' ./install.sh --yes
```

Extra Gluetun settings use a `GLUETUN_` prefix. `GLUETUN_SERVER_COUNTRIES=Netherlands` becomes `SERVER_COUNTRIES` in the container. Provider names and variables are in the [Gluetun wiki](https://github.com/qdm12/gluetun-wiki/tree/main/setup/providers).

## Request a movie

Sonarr never lists movies. It only tracks TV series. A movie request goes to Radarr.

1. Open Seerr at http://127.0.0.1:5055 and sign in with the admin account from `credentials.txt`.
2. Search for the movie, open the matching result, and click **Request**.
3. Open Radarr at http://127.0.0.1:7878. The movie is there. With no file yet, Radarr marks it missing.
4. In Prowlarr at http://127.0.0.1:9696, open **Indexers → Add Indexer** and choose **Torznab**. That is the generic indexer type. On the form:
   - **URL**: the Torznab base URL from an indexer account you already have
   - **API Path**: usually `/api`
   - **API Key**: the key from that same account
   Click **Test**, then **Save**. Sonarr and Radarr already receive indexers from Prowlarr, so you do not add the indexer again in those apps.
5. In Radarr, open the movie and choose **Search**. When a release you have the right to store is found, qBittorrent downloads it and Radarr files it into `media/movies`. In Jellyfin, open the Movies library and play it. If the file was already on disk, use the library menu and choose **Scan library**.

The walkthrough film is the public-domain short *A Trip to the Moon* (1902). A copy from the Internet Archive is what plays in Jellyfin in the demo. The Torznab form is the indexer example: paste the URL and API key from an account you subscribe to, then the same Request button can search.

A series uses the same Seerr search. Requesting it sends the show to Sonarr, which files episodes into `media/tv` for the Jellyfin TV library.

## After it finishes

Put media you already have in `media/movies` and `media/tv`. New downloads land in `downloads/completed`, then Sonarr and Radarr file them into the libraries.

Run `./install.sh` again to repair the links without minting a new password. `./install.sh --configure-only` skips `docker compose` and only redoes the accounts and connections.

Stop the stack with `docker compose down` from this directory. With the VPN off, the file is `docker compose -f docker-compose.novpn.yml down`.

## Layout

`media/tv`, `media/movies`, and `downloads/` are created next to this repo. Config and secrets live in `config/` and `.env`. Paths, ports, timezone, and the admin login can be set in the environment or in `.env` before you run the command. See `.env.example`.

The services follow the original guide: Jellyfin, Gluetun, qBittorrent, Prowlarr, FlareSolverr, Sonarr, and Radarr. Seerr is included because the guide's request steps (quality profile, root folder, Physical/Web availability) belong to that app.

## Tested

`./install.sh --yes --no-vpn` was run on a clean Ubuntu 24.04 virtual machine. Docker was not installed beforehand. After the command finished, these checks passed:

- Jellyfin startup wizard completed, admin login worked, and the Movies and TV libraries pointed at `/media/movies` and `/media/tv`.
- qBittorrent accepted the generated login and used `/downloads/completed` and `/downloads/incomplete`.
- Sonarr and Radarr signed in, had `/tv` and `/movies` as root folders, and had qBittorrent as the download client.
- Prowlarr had Sonarr, Radarr, and the FlareSolverr proxy.
- Seerr was initialized, signed in with the Jellyfin admin, and had both libraries enabled. Movie requests use Physical/Web availability.

The VPN path needs your own provider login, so that part was not started on the test machine.
