# Getting Canopy onto a Raspberry Pi

There's no custom pre-baked OS image (yet — see "A real custom image, later"
below). Instead: flash stock Raspberry Pi OS, then run one script that installs
Docker and brings Canopy up. Takes about the same wall-clock time as building a
custom image would, without maintaining a multi-gigabyte binary artifact.

## 1. Flash Raspberry Pi OS

Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/). Pick
**Raspberry Pi OS Lite (64-bit)** — no desktop needed, Canopy is a web dashboard.

Before writing, open the advanced options (gear icon, or `Ctrl+Shift+X`) and set:

- Hostname (e.g. `canopy`)
- Enable SSH, with a password or your public key
- Username/password
- Wi-Fi, if not using Ethernet

Write the image, boot the Pi, and SSH in once it's up
(`ssh <username>@<hostname>.local`).

## 2. Run the installer

```bash
curl -fsSL https://raw.githubusercontent.com/hashking710/Canopy/main/deploy/install.sh | bash
```

This installs Docker if it isn't already present, downloads the latest Canopy
release (falling back to cloning the repo directly if no release exists yet),
and runs `docker compose up -d --build`. Takes a few minutes on a Pi 4/5 the
first time (building the frontend and edge-agent images from source).

Add `--multi-site` if this Pi should also run the MQTT broker and master
aggregator for chaining multiple sites (see the README's
"Which setup do I need?" section) — most single-tent setups don't need this.

When it finishes, it prints the dashboard URL:

```
Dashboard:  http://canopy.local:5173
```

Visit that from any device on the same network. First load walks you through
creating the facility and adding rooms — see the root
[README](../README.md#running-locally) for what that looks like.

## 3. Updating later

Re-run the installer with `--upgrade`:

```bash
curl -fsSL https://raw.githubusercontent.com/hashking710/Canopy/main/deploy/install.sh | bash -s -- --upgrade
```

(Only pulls new changes for a git-based install — see the script's own
comments if you installed from a release tarball instead.)

## Skipping SSH entirely (advanced, untested by us)

Raspberry Pi OS supports a `firstrun.sh` mechanism: a script referenced from
`cmdline.txt` on the boot partition runs once, automatically, on first boot —
no SSH session needed at all. This is the same mechanism Raspberry Pi Imager's
own "OS customisation" dialog uses internally. In outline:

1. Flash Raspberry Pi OS Lite as above, but don't boot it yet.
2. On the flashed SD card's boot partition (`bootfs`, readable from any OS),
   copy `deploy/install.sh` in as `firstrun.sh`.
3. Edit `cmdline.txt` on that same partition to prepend
   `systemd.run=/boot/firmware/firstrun.sh systemd.run_success_action=reboot
   systemd.unit=kernel-command-line.target` to the existing line (keep
   everything already there).
4. Boot the Pi. It runs the script once, reboots, and the dashboard is up with
   zero manual interaction.

We haven't verified this end-to-end against real hardware — the exact
`cmdline.txt`/`bootfs` path has shifted between Raspberry Pi OS releases
(`/boot/` vs. `/boot/firmware/`), so treat this section as a documented
starting point, not a guarantee. The plain SSH-based install above is the
tested path.

## A real custom image, later

A genuine pre-baked `.img` (built with [pi-gen](https://github.com/RPi-Distro/pi-gen),
Canopy already installed, flash-and-boot-straight-into-the-dashboard) is a
reasonable next step once this lighter-weight installer has some real usage
behind it — it's a much heavier thing to build and maintain (ARM emulation,
hour-plus CI builds, multi-gigabyte release artifacts that need testing against
real hardware to trust), so it's deliberately not what this repo ships today.
