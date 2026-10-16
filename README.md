# Jellyfin at home, one command

This follows [Bryce Hoehn's automated Jellyfin guide](https://github.com/bryce-hoehn/automated-jellyfin-guide) (mirror of [the Codeberg original](https://codeberg.org/bhoehn/automated-jellyfin-guide)). The guide builds a home server from Jellyfin, qBittorrent, Gluetun, Prowlarr, FlareSolverr, Sonarr, and Radarr, then asks you to create each account in a browser. Here, one command installs that stack and creates the accounts.

You end with a movie library, a TV library, and a request page. The same login works on every app.

## 1. Start the server

On a Linux machine, install [Docker](https://docs.docker.com/engine/install/) if `docker` is not already a command. Docker Desktop is the install on macOS and Windows. Then, from a checkout of this repo:

```bash
./install.sh
```

The command asks three things:

1. One admin password. Press Enter to keep the generated one. It is shared by Jellyfin, Seerr (the request page), Sonarr, Radarr, Prowlarr, and qBittorrent.
2. Whether downloads should go through a VPN. The guide uses [IVPN](https://www.ivpn.net/) over OpenVPN. Gluetun cannot create that account for you. Paste the OpenVPN user and password from a provider Gluetun supports, or answer no and downloads use your normal network.
3. How you want to open Jellyfin from outside the house. Press 4 to keep it on this computer for now. The choices are in step 5.

To skip the questions:

```bash
./install.sh --yes --no-vpn
```

With a VPN account you already have:

```bash
OPENVPN_USER='your-vpn-user' OPENVPN_PASSWORD='your-vpn-password' ./install.sh --yes
```

WireGuard instead of OpenVPN:

```bash
VPN_TYPE=wireguard WIREGUARD_PRIVATE_KEY='...' WIREGUARD_ADDRESSES='10.x.x.x/32' ./install.sh --yes
```

Provider names and extra settings are in the [Gluetun wiki](https://github.com/qdm12/gluetun-wiki/tree/main/setup/providers). An extra setting uses a `GLUETUN_` prefix, so `GLUETUN_SERVER_COUNTRIES=Netherlands` becomes `SERVER_COUNTRIES` in the container.

When it finishes, it prints the password and saves it in `credentials.txt`. Open Jellyfin at http://127.0.0.1:8096 and sign in with that password.

| App | Address | What it is for |
| --- | --- | --- |
| Jellyfin | http://127.0.0.1:8096 | Play movies and shows |
| Seerr | http://127.0.0.1:5055 | Request a title |
| Radarr | http://127.0.0.1:7878 | Movies |
| Sonarr | http://127.0.0.1:8989 | TV series |
| Prowlarr | http://127.0.0.1:9696 | Indexers |
| qBittorrent | http://127.0.0.1:8080 | Downloads |

With the VPN on, qBittorrent, Prowlarr, and FlareSolverr leave through the VPN. Jellyfin, Seerr, Sonarr, and Radarr stay on your normal network.

If the command stops early, read the message and run the command it prints. Two common ones:

- The VPN login is missing. Pass `OPENVPN_USER` and `OPENVPN_PASSWORD`, or rerun with `--no-vpn`.
- Docker could not start. On Linux, rerun `./install.sh`. On macOS or Windows, install Docker Desktop, start it, and rerun `./install.sh`.

## 2. Add an indexer

Prowlarr is empty until you connect an indexer account you already have. Sonarr and Radarr then search through it.

1. Open http://127.0.0.1:9696 and sign in with the password from `credentials.txt`.
2. Open **Indexers → Add Indexer** and choose **Torznab**.
3. Fill in the form from that indexer account:
   - **URL**: the Torznab base URL
   - **API Path**: usually `/api`
   - **API Key**: the key from that account
4. Click **Test**, then **Save**.

You add the indexer once, in Prowlarr. Sonarr and Radarr receive it from there.

## 3. Request a movie and play it

Sonarr is for series. A movie request goes to Radarr.

1. Open http://127.0.0.1:5055 and sign in with the same admin account.
2. Search for the movie, open the matching result, and click **Request**.
3. Open http://127.0.0.1:7878. The movie is listed. With no file yet, Radarr marks it missing.
4. Open the movie and choose **Search**. qBittorrent downloads a release you have the right to store. Radarr files it into `media/movies`.
5. In Jellyfin, open the Movies library and play it. If you copied the file in by hand, use the library menu and choose **Scan library**.

A series uses the same search in Seerr. Requesting it sends the show to Sonarr, which files episodes into `media/tv`.

The short used as the example is the public-domain film *A Trip to the Moon* (1902). A copy can come from the Internet Archive. After your Torznab account is saved, the same Request button is what you use for everything else.

## 4. Watch from another network

Pick one. Jellyfin and the request page can leave the house. Sonarr, Radarr, Prowlarr, and qBittorrent stay on this computer.

Running `./install.sh` in a terminal asks you to choose. `./install.sh --yes` stays on this computer until you pass `--remote`.

### You have a domain on Cloudflare

The domain must already be Active in the [Cloudflare dashboard](https://dash.cloudflare.com). No change is required on the router.

1. Open https://dash.cloudflare.com/profile/api-tokens and choose **Create Token**, then **Create Custom Token**.
2. Add these permissions, and include your account plus that domain:
   - Account / Cloudflare Tunnel / Edit
   - Zone / DNS / Edit
   - Zone / Zone / Read
3. Run:

```bash
CLOUDFLARE_API_TOKEN='paste-token' CLOUDFLARE_HOSTNAME='watch.example.com' ./install.sh --yes --remote cloudflare
```

The command creates a tunnel named `jellyfin`, points `watch.example.com` at Jellyfin, and points `requests.example.com` at the request page. Open `https://watch.example.com`.

`CLOUDFLARE_SEERR_HOSTNAME=off` keeps the request page on this computer. If you would rather attach the names in the dashboard, pass `CLOUDFLARE_TUNNEL_TOKEN` from the tunnel page. The service addresses to enter there are `http://jellyfin:8096` and `http://seerr:5055`.

What the command does when Cloudflare is not ready yet:

| What happened | What you do |
| --- | --- |
| The token was left out | It stops before Docker and prints the token page plus the command to rerun. A password you already entered stays in `.env`. |
| Cloudflare rejected the token | Add the missing permission on the token page. The local server is left running. Rerun the same command. |
| The domain is not on this account | Add the domain, wait until it says Active, and use the nameservers Cloudflare shows you. Then rerun. |
| That hostname is already a DNS record of another type | Delete or rename it on the DNS page, then rerun. |
| The tunnel container did not connect | The local server is up at http://127.0.0.1:8096. Check outbound TCP port 7844, then `docker logs cloudflared`, then rerun. |

Long videos can fail on a free Cloudflare plan. If playback stops, use port forwarding or Tailscale below.

### You can open a port on the router

```bash
./install.sh --yes --remote forward
```

The command asks the router, over UPnP, to forward Jellyfin (`8096`) and the request page (`5055`) to this computer. From a phone that is not on the Wi-Fi, open the address it prints.

If the router does not answer, the command prints the two TCP forwards to add by hand, the LAN address to aim them at, and this command if a firewall on the computer is blocking the ports:

```bash
sudo ufw allow 8096/tcp && sudo ufw allow 5055/tcp
```

If the phone still cannot connect, the forward is aimed at a different address. In the router, point both ports at the LAN address the command printed.

If the router reports a private or carrier address, the open port does not reach the internet. Use Tailscale.

### You have no domain, and the router cannot forward a port

```bash
./install.sh --yes --remote tailscale
```

[Tailscale](https://tailscale.com/download) joins this computer and your phone into one private network. Nothing is opened on the router, and you do not buy a domain.

1. On Linux, the command installs Tailscale when it is missing. On a Mac, install the app from https://tailscale.com/download/mac if the command tells you to.
2. Open the sign-in link it prints. Create a free account, or sign in.
3. Install Tailscale on the phone or computer you watch from, and sign in with that same account.
4. Rerun `./install.sh --yes --remote tailscale`. It prints an address such as `http://100.x.x.x:8096`. Open that from the other device.

If the link expired, run `sudo tailscale up`, open the new link, and rerun the install command. If `sudo` asks for a password, run `sudo tailscale up` in a terminal on this computer.

## 5. Day to day

Put files you already have in `media/movies` and `media/tv`, then scan the library in Jellyfin. New downloads land in `downloads/completed`. Sonarr and Radarr move them into the libraries.

Run `./install.sh` again to repair the links. It keeps the password already in `.env`. `./install.sh --configure-only` skips Docker and only redoes the accounts.

Stop the stack from this directory:

```bash
docker compose down
```

With the VPN off, the file is `docker-compose.novpn.yml`:

```bash
docker compose -f docker-compose.novpn.yml down
```

Paths, ports, timezone, and the admin login can be set in `.env` before you run the command. The comments in `.env.example` name each one. `.env` and `credentials.txt` stay on this machine.

## Read the path before installing

`bash script.sh` and `./install.sh --dry-run` print the same steps and do not install Docker, pull images, or download a film. From anywhere, once this repo is public:

```bash
curl -fsSL https://raw.githubusercontent.com/Cosmin-Mare/jellyfin-kit/main/script.sh | bash
```

## What was checked

`./install.sh --yes --no-vpn` was run on a clean Ubuntu 24.04 virtual machine. Docker was not installed beforehand. After the command finished:

- Jellyfin's startup wizard was done, the admin login worked, and Movies and TV pointed at `/media/movies` and `/media/tv`.
- qBittorrent accepted the generated login and used `/downloads/completed` and `/downloads/incomplete`.
- Sonarr and Radarr signed in, had `/tv` and `/movies` as root folders, and had qBittorrent as the download client. Qualities are capped at 1080p.
- Prowlarr had Sonarr, Radarr, and the FlareSolverr proxy.
- Seerr was signed in with the Jellyfin admin, and movie requests use Physical/Web availability.

The VPN, Cloudflare, port-forward, and Tailscale paths need your own accounts or router, so those were checked as instructions and unit tests, not against a live provider.
