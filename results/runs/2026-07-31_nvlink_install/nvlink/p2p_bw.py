import json, torch

PAIRS = [(0, 1), (0, 2), (0, 3), (4, 5), (0, 4), (3, 4)]  # 0..3 wyspa, 0-4/3-4 = kontrola
N = 1 << 28          # 512 MiB w fp16
ITERS, WARMUP = 20, 3
out = []

for src, dst in PAIRS:
    peer_ok = torch.cuda.can_device_access_peer(src, dst)
    a = torch.empty(N, dtype=torch.float16, device=f"cuda:{src}")
    b = torch.empty(N, dtype=torch.float16, device=f"cuda:{dst}")
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
    gbs = ITERS * a.numel() * 2 / 1e9 / (beg.elapsed_time(end) / 1e3)
    out.append({"src": src, "dst": dst, "peer_access": peer_ok,
                "uni_GBps": round(gbs, 1)})
    print(f"GPU{src}->GPU{dst}  peer={peer_ok}  {gbs:7.1f} GB/s", flush=True)
    del a, b
    torch.cuda.empty_cache()

json.dump(out, open("/out/nvlink/p2p_bw.json", "w"), indent=2)
