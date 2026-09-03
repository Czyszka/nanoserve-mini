import os, json, torch, torch.distributed as dist

dist.init_process_group("nccl")
rank, world = dist.get_rank(), dist.get_world_size()
torch.cuda.set_device(rank)
tag = os.environ.get("LAT_TAG", "run")
SIZES = [4096, 16384, 65536, 524288, 8 << 20]   # bajty
ITERS, WARMUP = 200, 20
res = {}
for size in SIZES:
    x = torch.ones(size // 2, dtype=torch.float16, device="cuda")
    for _ in range(WARMUP):
        dist.all_reduce(x)
    torch.cuda.synchronize(); dist.barrier()
    beg, end = torch.cuda.Event(True), torch.cuda.Event(True)
    beg.record()
    for _ in range(ITERS):
        dist.all_reduce(x)
    end.record()
    torch.cuda.synchronize()
    us = beg.elapsed_time(end) * 1e3 / ITERS
    algbw = size / (us / 1e6) / 1e9
    busbw = algbw * 2 * (world - 1) / world
    res[f"{size}B"] = {"lat_us": round(us, 2), "busbw_GBps": round(busbw, 2)}
    if rank == 0:
        print(f"{size:>9d} B  {us:8.2f} us/op  busbw {busbw:7.2f} GB/s", flush=True)
if rank == 0:
    json.dump(res, open(f"/out/nvlink/nccl_lat_{tag}.json", "w"), indent=2)
dist.destroy_process_group()
