DCGM_FI_DEV_FB_USED: n=8 min=16.0 max=16.0  <-- POZA WIDELKAMI (zanotuj w NOTES)

dcgm
time=2026-08-13T05:29:31.413Z level=INFO msg="Not collecting CPU metrics; error retrieving DCGM CPU hierarchy: This request is serviced by a module of DCGM that is not currently loaded"
time=2026-08-13T05:29:31.413Z level=INFO msg="Initializing system entities of type 'CPU Core'"
time=2026-08-13T05:29:31.413Z level=INFO msg="Not collecting CPU Core metrics; error retrieving DCGM CPU hierarchy: This request is serviced by a module of DCGM that is not currently loaded"
time=2026-08-13T05:29:31.463Z level=INFO msg="Registry built successfully" collector_count=1
time=2026-08-13T05:29:31.464Z level=INFO msg="Profiling endpoints enabled at /debug/pprof/"
time=2026-08-13T05:29:31.464Z level=INFO msg="HTTP server started - ready to serve metrics"
time=2026-08-13T05:29:31.464Z level=INFO msg="Watching for changes in file" file=/etc/dcgm-exporter/nanoserve-counters.csv debounce=200ms
time=2026-08-13T05:29:31.464Z level=INFO msg="Starting webserver"
time=2026-08-13T05:29:31.465Z level=INFO msg="Listening on" address=[::]:9400
time=2026-08-13T05:29:31.465Z level=INFO msg="TLS is disabled." http2=false address=[::]:9400
# Werdykty 2026-08-12 — deploy dcgm-exporter (#34)
| kontrola | wynik |
|---|---|
| exporter up + 4 targety Prometheusa `up` | TAK/NIE |
| 11 pól × 8 GPU, w tym NVLINK_TX/RX obecne | TAK/NIE |
| sanity idle (power/FB_USED/SMACT w widelkach) | TAK/NIE |
| **koegzystencja dmon ⊕ exporter** | OK / KONFLIKT (polityka stop-na-okna-dmon) |
| mini-load widoczny na panelach (8 GPU) | TAK/NIE |
| cross-check NVL exporter vs dmon (rząd wielkości) | TAK/NIE/POMINIĘTY |
| dashboard DCGM w Grafanie + screenshot | TAK/NIE |
| serving stack nietknięty (ps start == end) | TAK/NIE |
- Odstępstwa od planu:
