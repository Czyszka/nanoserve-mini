import os, json, torch, torch.distributed as dist

dist.init_process_group("nccl")
rank, world = dist.get_rank(), dist.get_world_size()
torch.cuda.set_device(rank)
res = {}
for mb in (8, 64, 512):
    x = torch.ones(mb << 19, dtype=torch.float16, device="cuda")  # mb MiB
    for _ in range(5):
        dist.all_reduce(x)
    torch.cuda.synchronize(); dist.barrier()
    beg, end = torch.cuda.Event(True), torch.cuda.Event(True)
    beg.record()
    for _ in range(20):
        dist.all_reduce(x)
    end.record()
    torch.cuda.synchronize()
    sec = beg.elapsed_time(end) / 1e3 / 20
    nbytes = x.numel() * 2
    algbw = nbytes / sec / 1e9
    res[f"{mb}MiB"] = {"algbw_GBps": round(algbw, 1),
                       "busbw_GBps": round(algbw * 2 * (world - 1) / world, 1)}
    if rank == 0:
        print(f"{mb:4d} MiB  algbw {algbw:7.1f}  busbw "
              f"{algbw * 2 * (world - 1) / world:7.1f} GB/s", flush=True)
if rank == 0:
    json.dump(res, open("/out/nvlink/nccl_allreduce.json", "w"), indent=2)
dist.destroy_process_group()
