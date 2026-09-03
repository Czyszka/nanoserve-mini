import sys, time, torch, torch.multiprocessing as mp

def burn(i, minutes):
    torch.cuda.set_device(i)
    n = 8192
    a = torch.randn(n, n, dtype=torch.float16, device="cuda")
    b = torch.randn(n, n, dtype=torch.float16, device="cuda")
    c = torch.empty(n, n, dtype=torch.float16, device="cuda")
    t_end = time.time() + minutes * 60
    it = 0
    while time.time() < t_end:
        torch.matmul(a, b, out=c)
        it += 1
        if it % 5000 == 0:
            torch.cuda.synchronize()
            print(f"gpu{i} iter {it} t={time.strftime('%H:%M:%S')}", flush=True)
    torch.cuda.synchronize()
    print(f"gpu{i} DONE iters={it}", flush=True)

if __name__ == "__main__":
    minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 120
    mp.set_start_method("spawn")
    procs = [mp.Process(target=burn, args=(i, minutes))
             for i in range(torch.cuda.device_count())]
    [p.start() for p in procs]
    [p.join() for p in procs]
