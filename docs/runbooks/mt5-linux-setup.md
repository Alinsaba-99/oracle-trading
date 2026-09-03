# Runbook — MT5 Linux Bridge Setup (BL-723 / ADR-022)

Operational guide to install, configure and run the MetaTrader 5 bridge
on Linux using **Wine + `mt5linux`** at **$0/mo** cost. Target reader: an
operator who has never set up Wine + MT5 and needs to bring the bridge
online against a free demo account. See `docs/ADR/ADR-022` for the
architectural decision; this runbook is the operational counterpart.

## Architecture (one paragraph)

A MetaTrader 5 terminal (Windows GUI app) runs inside a dedicated
Wine prefix on Linux. The PyPI package `mt5linux` (v1.0.3, Feb 2026)
ships a Windows-Python executable (`mt5linux.exe`) that boots inside
the same Wine prefix and exposes the native `MetaTrader5` Python API
over an RPyC bridge. Our Linux Python process talks to that RPyC
server over a local TCP port (default 18812). `xvfb-run` provides a
headless virtual display so the MT5 terminal can render off-screen
when no monitor is attached. `MetaTraderBroker` (in
`execution/brokers/metatrader.py`) consumes an `MT5Client` Protocol,
so this backend is injected without touching OMS / governor / signal
source code. A `MetaApiClient` (cloud) is kept in the codebase as a
fallback activated by `ORACLE_MT5_BACKEND=metaapi`.

## Cost & prerequisites

- **Cost**: $0 recurring (Wine + MT5 + `mt5linux` + broker demo are all
  free). See ADR-020 hard rule.
- **Disk**: ~1.5 GB for the Wine prefix with MT5 + `mt5linux`.
- **RAM**: ~1.5-2.5 GB at runtime (terminal + RPyC + xvfb).
- **CPU**: negligible; this is not a latency-critical HFT bridge.
- **OS**: any Linux that ships Wine ≥ 8.x (CachyOS/Arch confirmed;
  Ubuntu 22.04+, Debian 12+ confirmed).
- **Display**: none required for headless use (`xvfb` provides one).

## 1. Install system packages

### CachyOS / Arch

```bash
sudo pacman -S --needed wine winetricks wine-mono wine-gecko \
    xorg-server-xvfb lib32-vulkan-icd-loader samba
# Optional for debugging with a VNC viewer:
sudo pacman -S --needed x11vnc
```

### Ubuntu 22.04+ / Debian 12+

```bash
sudo dpkg --add-architecture i386
sudo mkdir -pm755 /etc/apt/keyrings
sudo wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key
sudo wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/$(lsb_release -cs)/winehq-$(lsb_release -cs).sources
sudo apt update
sudo apt install --install-recommends winehq-staging winetricks xvfb
```

Verify:

```bash
wine --version       # expect wine-8.x or wine-9.x
xvfb-run --help      # should print usage
```

## 2. Create a dedicated Wine prefix for MT5

A separate prefix keeps Wine overrides isolated from the rest of the
system and makes the setup reproducible.

```bash
export WINEPREFIX="$HOME/.wine_mt5"
export WINEARCH=win64
wineboot --init
winetricks -q vcrun2019 corefonts
# Optional but recommended for older MT5 builds:
winetricks -q d3dx9
```

Pinned versions (write them to `infra/wine/` for reproducibility —
fill the values you installed):

```
# infra/wine/WINE_VERSION
wine-9.0

# infra/wine/MT5_VERSION
5.0.45  # or whatever terminal64.exe reports
```

## 3. Install the MT5 terminal

The official MT5 terminal installer is a Windows `.exe` distributed by
each broker. For the spike we recommend downloading the **broker-neutral**
installer from MetaQuotes:

```bash
cd /tmp
wget https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe
wine mt5setup.exe
```

The installer opens a normal Windows GUI under Wine. Accept defaults;
un-check "Send anonymous statistics" if asked. Once finished the
terminal is at:

```
$WINEPREFIX/drive_c/Program Files/MetaTrader 5/terminal64.exe
```

Smoke-test:

```bash
xvfb-run -a "$WINEPREFIX/drive_c/Program Files/MetaTrader 5/terminal64.exe"
```

A blank MT5 chart should appear in the Xvfb display. Close it.

## 4. Install `mt5linux` (RPyC bridge)

`mt5linux` ships a Windows-Python executable that boots inside Wine
and exposes the native `MetaTrader5` Python API via RPyC.

```bash
pip install --user mt5linux==1.0.3
```

This installs `mt5linux.exe` somewhere on the user's Wine-visible path.
The recommended pattern is to install it **inside the same Wine prefix**
so MT5 and the bridge share the same `python.exe`:

```bash
# inside Wine, install Python 3.11 first
winetricks -q python311
# then install mt5linux into Wine's Python
WINEPREFIX="$HOME/.wine_mt5" wine python -m pip install mt5linux==1.0.3
```

Pin: write the installed version to `infra/wine/MT5LINUX_VERSION`:

```
# infra/wine/MT5LINUX_VERSION
1.0.3
```

## 5. Open a free demo MT5 account

**No credit card, no prop-firm fee, no commitment.** Any of:

- IC Markets — https://www.icmarkets.com/
- Pepperstone — https://pepperstone.com/
- Exness — https://www.exness.com/
- FBS — https://fbs.com/

Click *Open demo account* → fill the form → you receive by email:

- `MT5_LOGIN` (numeric, e.g. `12345678`)
- `MT5_PASSWORD` (read-only investor password works for paper; trade
  password for live orders — never use a real-password in tests)
- `MT5_SERVER` (e.g. `ICMarkets-Demo01`)

## 6. Configure credentials

```bash
mkdir -p ~/.config/oracle
cat > ~/.config/oracle/mt5.env <<'EOF'
ORACLE_MT5_BACKEND=mt5linux
MT5_LOGIN=12345678
MT5_PASSWORD=...
MT5_SERVER=ICMarkets-Demo01
MT5_BROKER_SUFFIX=.r        # '' for IC Markets, '.r' for FTMO/The5ers demo
WINE_PREFIX=/home/you/.wine_mt5
MT5_RPYC_HOST=127.0.0.1
MT5_RPYC_PORT=18812
EOF
chmod 600 ~/.config/oracle/mt5.env
```

## 7. Start the bridge headless

The bridge script `scripts/mt5_bridge.sh` (created in the BL-723
follow-up commit) wraps the sequence:

```bash
xvfb-run -a "$WINE_PREFIX/drive_c/Program Files/MetaTrader 5/terminal64.exe" &
MT5_PID=$!
sleep 5  # let MT5 finish booting
WINEPREFIX="$WINE_PREFIX" wine python -m mt5linux \
    --hostname "$MT5_RPYC_HOST" --port "$MT5_RPYC_PORT" &
MT5LINUX_PID=$!

trap "kill $MT5LINUX_PID $MT5_PID 2>/dev/null" EXIT
wait
```

For interactive testing:

```bash
set -a; source ~/.config/oracle/mt5.env; set +a
./scripts/mt5_bridge.sh
# In another terminal:
python -c "
from execution.brokers.mt5linux_client import Mt5LinuxClient
client = Mt5LinuxClient(host='127.0.0.1', port=18812)
print(client.initialize(path=None,
                        login=int(os.environ["MT5_LOGIN"]),
                        password=os.environ["MT5_PASSWORD"],
                        server=os.environ["MT5_SERVER"]))
print('terminal_info:', client.terminal_info())
print('account_snapshot:', client.account_snapshot())
"
```

A successful run prints `connected=True` and a non-zero balance on the
demo account.

## 8. systemd user service (always-on)

`ops/systemd/oracle-mt5-bridge.service` (created in the BL-723 follow-up):

```ini
[Unit]
Description=Oracle MT5 Wine bridge
After=network.target

[Service]
Type=simple
EnvironmentFile=%h/.config/oracle/mt5.env
ExecStart=%h/.oracle/bin/mt5_bridge.sh
Restart=on-failure
RestartSec=5s
TimeoutStopSec=15

[Install]
WantedBy=default.target
```

Install:

```bash
cp ops/systemd/oracle-mt5-bridge.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now oracle-mt5-bridge.service
systemctl --user status oracle-mt5-bridge.service
journalctl --user -u oracle-mt5-bridge -f
```

The service restarts on crash with backoff (5s → systemd default 1m).
For the paper runner (`oracle-paper.service`) add `After=` /
`Requires=` so the bridge comes up first.

## 9. Switch to MetaApi fallback (cloud)

If Wine ever breaks and you need an immediate fallback for a demo /
smoke test, the codebase already supports `MetaApiClient` via
`ORACLE_MT5_BACKEND=metaapi`:

```bash
cat >> ~/.config/oracle/mt5.env <<'EOF'
METAAPI_TOKEN=...           # free tier at https://metaapi.cloud
METAAPI_ACCOUNT_ID=...
EOF
sed -i 's/^ORACLE_MT5_BACKEND=.*/ORACLE_MT5_BACKEND=metaapi/' ~/.config/oracle/mt5.env
systemctl --user restart oracle-paper.service
```

No code changes required. The MetaApi free tier is $0 and is fine for
CI smoke tests against demo accounts (do **not** use it for funded
prop-firm accounts at scale — see ADR-020 cost rule).

## 10. Verification matrix

| Check | Command | Expected |
|---|---|---|
| Wine works | `wine cmd /c echo hello` | prints `hello` |
| xvfb works | `xvfb-run -a glxgears` | gears spin, no DISPLAY error |
| MT5 boots | `xvfb-run -a "$WINE_PREFIX/drive_c/Program Files/MetaTrader 5/terminal64.exe"` | window appears, quotes stream |
| RPyC bridge reachable | `nc -zv 127.0.0.1 18812` | connection succeeds |
| Demo login | `client.initialize(...)` | returns `True`, `last_error()` is `None` |
| Account snapshot | `client.account_snapshot()` | balance > 0, equity > 0 |
| Live quote | `client.symbol_info_tick("EURUSD")` | non-zero bid/ask |
| History fetch | `client.copy_rates_from_pos("EURUSD", 1, 0, 100)` | 100 OHLC bars |

## 11. Troubleshooting

| Symptom | Check | Fix |
|---|---|---|
| `wine: command not found` | PATH set? | source `/etc/profile.d/wine.sh` or reinstall |
| MT5 terminal crashes on launch | DLL redist missing | `winetricks -q vcrun2019 d3dx9` |
| `mt5.initialize()` returns `False` | credentials / server name | verify `MT5_SERVER` exactly (case-sensitive); demo servers differ between brokers |
| RPyC connection refused | `mt5linux` started? | check `journalctl --user -u oracle-mt5-bridge`; wait 5-10s after MT5 boots |
| `connected=False` in `terminal_info()` | broker demo expired | brokers auto-expire inactive demos (30-90 days); open a fresh demo |
| Wine DLL conflict | mixed 32/64 prefix | delete `$WINEPREFIX`, redo `wineboot --init`, set `WINEARCH=win64` |
| High CPU usage idle | MT5 chart rendering busy | disable chart auto-scroll in MT5 settings; cap fps in terminal options |
| Bridge works in dev but not under systemd | `EnvironmentFile` path | confirm `%h` resolves correctly (use absolute path if not); `XDG_RUNTIME_DIR` may be empty in containers |
| Latency spikes (>500 ms) | xvfb backpressure | not a Wine issue; check broker network; consider reconnect to a closer demo server |

## 12. Safety invariants

- **Never run against a funded prop-firm account until the BL-722
  governor + BL-727 qualifier gate passes.** Demo accounts only here.
- **Never commit `~/.config/oracle/mt5.env`** — pre-commit hook
  `.gitleaks.toml` should already block; verify with `gitleaks detect`.
- **Demo passwords only**: the runbook never asks for funded creds.
- **Heartbeat required**: the bridge must respond to
  `mt5.terminal_info()` within 5 s — orchestrator kills the runner on
  heartbeat miss (BL-733 alerting).
- **Kill-switch wiring**: when the bridge dies, `oracle-paper.service`
  must stop within one cycle. The user service
  `Wants=oracle-mt5-bridge.service` on the paper service makes systemd
  stop the paper runner if the bridge fails.

## 13. Promotion gate

Promoting from demo to funded (real) prop-firm account requires:

1. BL-722 `PropFirmRiskGovernor` implemented and unit-tested for the
   target firm (consistency, daily-loss, news blackout, anti-HFT);
2. BL-727 qualifier verdict APPROVED on the pre-registered variant
   (`docs/research/prereg/BL-726-lane-b-composite-variant.md`);
3. BL-728 paper adapter end-to-end green against this demo account;
4. Operator explicit approval per ADR-015 §"Local-only deployment".

Only then do we paste a `MT5_LOGIN/MTS_PASSWORD` for the funded
account into `~/.config/oracle/mt5.env` and run `oracle-paper.service`
in production mode.
