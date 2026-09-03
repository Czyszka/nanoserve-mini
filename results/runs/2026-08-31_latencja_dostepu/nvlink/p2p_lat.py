import json, torch

PAIRS = [(0, 1), (0, 2), (0, 3), (0, 4), (3, 4)]  # 0-3 wyspa; 0-4/3-4 cross
ITERS, WARMUP = 500, 50
out = []
for src, dst in PAIRS:
    peer_ok = torch.cuda.can_device_access_peer(src, dst)
    a = torch.ones(4, dtype=torch.float16, device=f"cuda:{src}")
    b = torch.empty(4, dtype=torch.float16, device=f"cuda:{dst}")
    torch.cuda.set_device(src)
    for _ in range(WARMUP):
        b.copy_(a)
    torch.cuda.synchronize()
    beg, end = torch.cuda.Event(True), torch.cuda.Event(True)
    beg.record()
    for _ in range(ITERS):
        b.copy_(a)
    end.record()
    torch.cuda.synchronize()
    us = beg.elapsed_time(end) * 1e3 / ITERS
    out.append({"src": src, "dst": dst, "peer_access": peer_ok,
                "lat_us": round(us, 2)})
    print(f"GPU{src}->GPU{dst}  peer={peer_ok}  {us:6.2f} us/op", flush=True)
json.dump(out, open("/out/nvlink/p2p_lat.json", "w"), indent=2)
