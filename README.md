# Your own movie and TV library, one command

This sets up a private streaming library on a computer you control. You type the name of a movie or a show, click Request, and the computer downloads it and files it. You then press play in a browser, or in a TV app, the way you would on a streaming service. The files stay on your machine.

You do not sign up for a website. One command installs the programs that do each job, creates one login for all of them, and connects them. When it finishes, it prints that username and password and saves them in a file called `credentials.txt`.

Here is the path, in the order you will use it:

1. **Search.** You look up a title and request it.
2. **Fetch.** The computer finds a copy and downloads it.
3. **File.** A movie goes into the movie shelf. A series goes into the TV shelf.
4. **Play.** You watch it.

Those jobs have program names. You will see the names in the browser. You do not need to learn them first.

| What you are doing | Program | Where it opens |
| --- | --- | --- |
| Watch | Jellyfin | http://127.0.0.1:8096 |
| Search and request | Seerr | http://127.0.0.1:5055 |
| Keep the movie shelf | Radarr | http://127.0.0.1:7878 |
| Keep the TV shelf | Sonarr | http://127.0.0.1:8989 |
| Tell the search where to look | Prowlarr | http://127.0.0.1:9696 |
| Download the file | qBittorrent | http://127.0.0.1:8080 |

`127.0.0.1` means "this computer." Open those addresses in a web browser on the machine that ran the command.

Two smaller programs stay in the background. FlareSolverr helps the search get past sites that demand a real browser. Gluetun is optional: it sends the downloads through a VPN account you already have.

The command can install everything except two things it cannot invent for you:

- A **search source**. Prowlarr is empty until you paste the address and key from an indexer account you already use. That account is what knows where copies of a title are listed. You add it once. After that, Request can search.
- A **VPN**, and only if you want downloads to leave through one. If you do not have one, answer no. Downloads then use your normal internet connection.

Only download a title you have the right to store.

This follows [Bryce Hoehn's automated Jellyfin guide](https://github.com/bryce-hoehn/automated-jellyfin-guide) (mirror of [the Codeberg original](https://codeberg.org/bhoehn/automated-jellyfin-guide)). That guide asks you to create each account by hand in a browser. Here the command does that.

## Watching at home or away

The player starts on the computer that ran the command. The install then asks where else you want to watch. Press Enter to keep the suggested answer. Skip this only when you pass `--remote` yourself, or when you pass `--yes`, which stays on this computer until you choose.

**1. At home, on this Wi-Fi.** Phones, laptops, and TVs on the same network open the player. When the install finishes, it prints that address, usually starting with `192.168`, and the steps to keep it from changing. Those steps follow the router it recognizes, such as Digi, Orange, Vodafone, TP-Link, or Asus. Nothing is opened to the internet. A phone on mobile data cannot use that address. To choose this without the question:

```bash
curl -fsSL https://raw.githubusercontent.com/Cosmin-Mare/jellyfin-kit/main/install.sh | bash -s -- --remote lan
```

**2. Away from home as well.** A phone on mobile data, or a computer somewhere else, can open the player and the search page. The movie shelf, the TV shelf, and the downloader stay on the home computer. The installer then asks how:

| Choice | Pick it when | What you get | If it cannot finish |
| --- | --- | --- | --- |
| Cloudflare Tunnel | You already have a domain on Cloudflare | `https://watch.example.com` | The command names the missing token, domain, or DNS record, and the page to open |
| Open a port on the router | You can change the router, or it allows it automatically | `http://your-public-address:8096` | It prints the two ports to add by hand. If the router only has a carrier address, it sends you to Tailscale |
| Tailscale | You have no domain and cannot open a port | `http://100.x.x.x:8096` after the same login on both devices | It prints the sign-in link, or the install command, and you rerun |

Long movies can fail on a free Cloudflare plan. If playback stops, run the installer again and pick the router or Tailscale.

The shelves and the downloader are not opened to the internet in any of these choices.

## 1. Start the server

You need a computer that can stay on, such as a home PC or a small Linux machine. On Linux, the command also installs Docker and Python 3 if they are missing. Docker is the box these programs run in. You do not have to learn it. On a Mac or a Windows PC, install [Docker Desktop](https://docs.docker.com/desktop/) and start it, then run the same command.

```bash
curl -fsSL https://raw.githubusercontent.com/Cosmin-Mare/jellyfin-kit/main/install.sh | bash
```

The files land in `~/jellyfin-kit`. Your movies, config, and password stay there if you run it again.

The command asks three things. Press Enter whenever you want to keep what it suggests.

1. **A password.** One login for the player, the search page, the shelves, and the downloader. It must be at least 6 characters, because qBittorrent refuses anything shorter. Press Enter to keep the password it made up. If a saved password is too short, the command says so and asks for a new one. If account setup then fails, it offers to set a new password and try that step again.
2. **A VPN, if you want one.** This hides download traffic behind a VPN company you already pay. The usual example is [IVPN](https://www.ivpn.net/). Paste that login, or answer **n**. Answering **n** is fine. Downloads then use your normal connection.
3. **Where you watch.** **1** is this Wi-Fi. **2** is away from home, and then you pick Cloudflare, the router, or Tailscale. Press Enter for at home. The section above explains each one.

If Docker, Python, or any of the apps are already installed, the command says so. When an app's config is already there, it asks before repairing it, and it still installs whatever is missing. Press Enter to allow the repair. `./install.sh --yes` allows it without asking.

To skip the questions:

```bash
curl -fsSL https://raw.githubusercontent.com/Cosmin-Mare/jellyfin-kit/main/install.sh | bash -s -- --yes --no-vpn
```

With a VPN account you already have:

```bash
curl -fsSL https://raw.githubusercontent.com/Cosmin-Mare/jellyfin-kit/main/install.sh | \
  OPENVPN_USER='your-vpn-user' OPENVPN_PASSWORD='your-vpn-password' bash -s -- --yes
```

WireGuard instead of OpenVPN:

```bash
curl -fsSL https://raw.githubusercontent.com/Cosmin-Mare/jellyfin-kit/main/install.sh | \
  VPN_TYPE=wireguard WIREGUARD_PRIVATE_KEY='...' WIREGUARD_ADDRESSES='10.x.x.x/32' bash -s -- --yes
```

From a checkout of this repo, `./install.sh` does the same thing in that directory.

Provider names and extra settings are in the [Gluetun wiki](https://github.com/qdm12/gluetun-wiki/tree/main/setup/providers). An extra setting uses a `GLUETUN_` prefix, so `GLUETUN_SERVER_COUNTRIES=Netherlands` becomes `SERVER_COUNTRIES` in the container.

When it finishes, it prints the password and saves it in `credentials.txt`. Sign in with that password on every address in the table above. Start with Seerr at http://127.0.0.1:5055 if you want to request something, or Jellyfin at http://127.0.0.1:8096 if you only want to play what is already on disk.

Radarr is at http://127.0.0.1:7878, Sonarr at http://127.0.0.1:8989, Prowlarr at http://127.0.0.1:9696, and qBittorrent at http://127.0.0.1:8080.

With the VPN on, qBittorrent, Prowlarr, and FlareSolverr leave through the VPN. Jellyfin, Seerr, Sonarr, and Radarr stay on your normal network.

If the command stops early, read the message and run the command it prints. Two common ones:

- The VPN login is missing. Pass `OPENVPN_USER` and `OPENVPN_PASSWORD`, or rerun with `--no-vpn`.
- Docker could not start. On Linux, run `sudo systemctl start docker` and rerun the curl command. On macOS or Windows, open Docker Desktop and rerun it.

## 2. Tell it where to search

The search page cannot invent a catalog of files. You connect one indexer: an account you already have on a site that lists available copies. You do this once, in Prowlarr. The movie shelf and the TV shelf then search through it.

1. Open http://127.0.0.1:9696 and sign in with the password from `credentials.txt`.
2. Open **Indexers → Add Indexer** and choose **Torznab**.
3. Fill in the form from that indexer account:
   - **URL**: the Torznab base URL
   - **API Path**: usually `/api`
   - **API Key**: the key from that account
4. Click **Test**, then **Save**.

You add the indexer once, in Prowlarr. Sonarr and Radarr receive it from there.

## 3. Request a movie and play it

This is the whole point of the setup. You search, you request, the computer downloads, you watch.

Open Seerr, the search page. A movie request is handed to Radarr, the movie shelf, which sends the download to qBittorrent. A series request is handed to Sonarr, the TV shelf, and the episodes land in the TV library. Jellyfin is where you press play.

1. Open Seerr at http://127.0.0.1:5055 and sign in with the same admin account.
2. Search for the movie, open the matching result, and click **Request**.
3. Open Radarr at http://127.0.0.1:7878. The movie is listed. With no file yet, Radarr marks it missing.
4. Open the movie and choose **Search**. qBittorrent downloads a release you have the right to store. Radarr files it into `media/movies`.
5. In Jellyfin, open the Movies library and play it. If you copied the file in by hand, use the library menu and choose **Scan library**.

A series uses the same search in Seerr. Requesting it sends the show to Sonarr, which files episodes into `media/tv`.

The short used as the example is the public-domain film *A Trip to the Moon* (1902). A copy can come from the Internet Archive. After your Torznab account is saved, the same Request button is what you use for everything else.

## 4. Open it on a phone

Use the address printed at the end of the install. It is also in `credentials.txt`.

At home, that address starts with `192.168`. Open it from a phone on the same Wi-Fi. Away from home, use the Cloudflare name, the public address, or the Tailscale address from the choice you made. The explanation of each choice is in **Watching at home or away** at the top.

To change your mind later, run the same install command again and answer the question, or pass one flag: `--remote lan`, `--remote cloudflare`, `--remote forward`, or `--remote tailscale`. `--yes` by itself does not ask, and leaves watching on this computer.

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

The command creates a tunnel named `jellyfin`, points `watch.example.com` at Jellyfin, and points `requests.example.com` at Seerr. Open `https://watch.example.com`.

`CLOUDFLARE_SEERR_HOSTNAME=off` keeps Seerr on this computer. If you would rather attach the names in the dashboard, pass `CLOUDFLARE_TUNNEL_TOKEN` from the tunnel page. The service addresses to enter there are `http://jellyfin:8096` and `http://seerr:5055`.

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

The command asks the router, over UPnP, to forward Jellyfin (`8096`) and Seerr (`5055`) to this computer. From a phone that is not on the Wi-Fi, open the address it prints.

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

After the first request works, daily use is the search page and the player. Open Seerr, request a title, and later open Jellyfin to watch it.

Movies you already own can be copied into the `media/movies` folder, and shows into `media/tv`. In Jellyfin, open that library's menu and choose **Scan library** so they appear. New downloads arrive in `downloads/completed`, then the movie shelf or the TV shelf moves them into those folders for you.

Run the curl command again, or `./install.sh` from `~/jellyfin-kit`, to repair the links. It keeps the password already in `.env` and asks before changing a config that is already there. `./install.sh --configure-only` skips Docker and only redoes the accounts.

To remove the library, run:

```bash
bash ~/jellyfin-kit/uninstall.sh
```

It stops the player, the search page, the shelves, and the downloader, and deletes their settings and half-finished downloads. It asks before deleting the movies and shows in `media/`. It also asks before uninstalling Docker or Tailscale, because other programs on the computer may be using them.

```bash
bash ~/jellyfin-kit/uninstall.sh --yes --media
```

That line also deletes `media/`. Add `--docker` or `--tailscale` only when you want those removed from the whole computer.

Stop the programs and leave the files in place with:

```bash
docker compose down
```

With the VPN off, the file is `docker-compose.novpn.yml`:

```bash
docker compose -f docker-compose.novpn.yml down
```

Paths, ports, timezone, and the admin login can be set in `.env` before you run the command. The comments in `.env.example` name each one. `.env` and `credentials.txt` stay on this machine.

## Read the path before installing

`bash script.sh` and `./install.sh --dry-run` print the steps and do not install Docker, pull images, or download a film:

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
