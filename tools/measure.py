#!/usr/bin/env python3
"""Development-only resource comparison. Supply an explicit scratch destination.

Three repeats, four physical grids, idle/working/32-tool+32-branch activity,
20-second CPU windows after two-second warmup. Controls disable decorative
pacing in the same renderer; they are not historical released binaries.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pty
import select
import shutil
import statistics
import struct
import subprocess
import sys
import termios
import time

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT/'plugins/cyclops-keeper/scripts'
sys.path.insert(0, str(SCRIPTS))
import activity

WARMUP = 2
WINDOW = 20
GRIDS = [(100, 32), (48, 20), (24, 12), (6, 1)]
PHASES = ['idle', 'working', 'dense']
CPU = max(os.sched_getaffinity(0))


def frequency():
    values = {}
    for path in Path('/sys/devices/system/cpu').glob('cpu[0-9]*/cpufreq/scaling_cur_freq'):
        try:
            values[path.parents[1].name] = int(path.read_text())
        except OSError:
            pass
    return values


def process(pid):
    raw = Path(f'/proc/{pid}/stat').read_text()
    fields = raw[raw.rindex(')')+2:].split()
    return dict(pid=pid, start=fields[19], ticks=int(fields[11])+int(fields[12]),
                rss_bytes=int(fields[21])*os.sysconf('SC_PAGE_SIZE'),
                processor=int(fields[36]), monotonic=time.monotonic(),
                load=list(os.getloadavg()), frequency_khz=frequency())


def fixture(folder, phase):
    folder.mkdir()
    payloads = [dict(hook_event_name='SessionStart', source='startup', session_id='fixture')]
    if phase != 'idle':
        payloads.append(dict(hook_event_name='UserPromptSubmit', session_id='fixture', turn_id='turn'))
    if phase == 'dense':
        for index in range(32):
            payloads.extend([
                dict(hook_event_name='PreToolUse', session_id='fixture', turn_id='turn',
                     tool_use_id=f'tool-{index}', tool_name='Bash'),
                dict(hook_event_name='SubagentStart', session_id='fixture', turn_id='turn',
                     agent_id=f'branch-{index}')])
    receipts = [activity.update(folder, payload) for payload in payloads]
    if not all(receipt and receipt['status']=='accepted' for receipt in receipts):
        raise RuntimeError('fixture event was not acknowledged')
    (folder/'receipts.json').write_text(json.dumps(receipts, indent=2)+'\n')


def collect(folder, grid, phase, strategy, colour=False):
    folder.mkdir()
    data = folder/'data'
    fixture(data, phase)
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', grid[1], grid[0], 0, 0))
    env = dict(os.environ, TERM='xterm-256color', NO_COLOR='1',
               PLUGIN_DATA=str(data), LANG='C.UTF-8', PYTHONDONTWRITEBYTECODE='1')
    if colour:
        env.pop('NO_COLOR', None)
        env['COLORTERM']='truecolor'
    for key in ['COLUMNS','LINES','KEEPER_LAUNCH_SOCKET','KEEPER_LAUNCH_TOKEN','TMUX','TMUX_PANE']:
        env.pop(key, None)
    program = """import sys
sys.path.insert(0,sys.argv[1])
import terminal
if sys.argv[2]=='native':
 original=terminal.PacedRenderCache
 class Native(original):
  def __init__(self):super().__init__(interval=0)
 terminal.PacedRenderCache=Native
sys.argv=['terminal','--data',sys.argv[3],'--metrics']
terminal.main()
"""
    stderr = (folder/'stderr.log').open('w')
    output = (folder/'output.bin').open('wb')
    chunks = (folder/'chunks.jsonl').open('w')
    sample_log = (folder/'samples.jsonl').open('w')
    child = subprocess.Popen([sys.executable, '-B', '-c', program, str(SCRIPTS), strategy, str(data)],
                             env=env, stdin=slave, stdout=slave, stderr=stderr)
    offset = 0
    samples = []
    first = last = None
    parent_cpu = time.process_time()
    started = time.monotonic()
    sample_at = started
    try:
        os.sched_setaffinity(child.pid, {CPU})
        while last is None:
            now = time.monotonic()
            if child.poll() is not None:
                raise RuntimeError('renderer ended during a sample')
            if first is None and now-started >= WARMUP:
                first = process(child.pid)
                sample_at = now
            if first is not None and now-first['monotonic'] >= WINDOW:
                last = process(child.pid)
            if now >= sample_at:
                sample = process(child.pid)
                samples.append(sample)
                sample_log.write(json.dumps(sample)+'\n')
                sample_log.flush()
                sample_at = now+1
            if select.select([master], [], [], .02)[0]:
                raw = os.read(master, 1024*1024)
                output.write(raw)
                chunks.write(json.dumps(dict(monotonic=time.monotonic(),offset=offset,bytes=len(raw)))+'\n')
                offset += len(raw)
        os.write(master, b'q')
        deadline = time.monotonic()+5
        while child.poll() is None and time.monotonic()<deadline:
            if select.select([master], [], [], .02)[0]:
                raw = os.read(master, 1024*1024)
                output.write(raw)
                chunks.write(json.dumps(dict(monotonic=time.monotonic(),offset=offset,bytes=len(raw)))+'\n')
                offset += len(raw)
        status = child.wait(timeout=5)
        stderr.flush()
        metrics = json.loads((folder/'stderr.log').read_text())
        if first['start'] != last['start'] or status != 0:
            raise RuntimeError('process identity or exit was invalid')
        elapsed = last['monotonic']-first['monotonic']
        if not WINDOW <= elapsed <= WINDOW+.05:
            raise RuntimeError('CPU window duration was outside the fixed 50 ms tolerance')
        result = dict(strategy=strategy, grid=list(grid), phase=phase, colour=colour, first=first, last=last,
                      cpu_percent=100*(last['ticks']-first['ticks'])/os.sysconf('SC_CLK_TCK')/elapsed,
                      sampled_peak_rss_bytes=max(s['rss_bytes'] for s in samples),
                      samples=samples, metrics=metrics, output_bytes=offset,
                      harness_cpu_ms=(time.process_time()-parent_cpu)*1000)
        (folder/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        return result
    finally:
        if child.poll() is None:
            child.terminate()
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        stderr.close();output.close();chunks.close();sample_log.close();os.close(master);os.close(slave)


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 tools/measure.py /explicit/scratch/destination')
    dest = Path(sys.argv[1]).resolve()
    if shutil.disk_usage(dest.parent).free < 512*1024*1024:
        raise SystemExit('Need at least 512 MiB free scratch space (estimated output <=256 MiB).')
    dest.mkdir(parents=True, exist_ok=False)
    order = []
    for repeat in range(3):
        grids = GRIDS if repeat%2==0 else list(reversed(GRIDS))
        for grid in grids:
            for phase in PHASES:
                for strategy in (['native','paced'] if repeat%2==0 else ['paced','native']):
                    order.append(dict(repeat=repeat,grid=list(grid),strategy=strategy,phase=phase,colour=False))
        for phase in PHASES:
            for strategy in (['native','paced'] if repeat%2==0 else ['paced','native']):
                order.append(dict(repeat=repeat,grid=[100,32],strategy=strategy,phase=phase,colour=True))
    manifest = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((ROOT/'plugins').rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    plan = dict(warmup_seconds=WARMUP,window_seconds=WINDOW,order=order,
                cpu='renderer utime+stime endpoints / monotonic duration; percent of one core',
                rss='maximum of 1 Hz resident-page samples, not exhaustive peak',
                cpu_nonregression='paced median <= native median + max(1 pp, 10 percent native)',
                rss_nonregression='paced sampled peak <= native sampled peak + 8 MiB',
                repeatability='(max-min)/max(median,1 pp) <= 0.10; retain all failures',
                composition_nonregression='median loop p95 <= native median loop p95 * 1.10 + 0.5 ms; includes cache hits, not newly drawn frame cost',
                scope='synthetic steady-state fixture, one renderer, metrics enabled equally; four uncoloured grids plus full-size truecolour; no physical FPS claim; adjacent AB/BA/AB pairs',
                affinity_cpu=CPU,frequency_at_start_khz=frequency(),
                source=manifest,harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                expected_maximum_bytes=256*1024*1024)
    (dest/'PLAN.json').write_text(json.dumps(plan,indent=2)+'\n')
    # Preserve exactly what ran, including the harness, before any sampling.
    shutil.copytree(ROOT/'plugins',dest/'source/plugins',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (dest/'source/tools').mkdir()
    shutil.copy2(__file__,dest/'source/tools/measure.py')
    results = []
    for index, case in enumerate(order):
        folder = dest/f"{index:02d}-r{case['repeat']}-{case['grid'][0]}x{case['grid'][1]}-{case['strategy']}-{case['phase']}-c{int(case['colour'])}"
        try:
            result = collect(folder,case['grid'],case['phase'],case['strategy'],case['colour'])
        except BaseException as error:
            (dest/'FAILED.json').write_text(json.dumps(dict(index=index,type=type(error).__name__,reason=str(error)),indent=2)+'\n')
            raise
        result['repeat']=case['repeat'];result['index']=index
        results.append(result)
        (dest/'results.json').write_text(json.dumps(results,indent=2)+'\n')
        print(f"{index+1}/{len(order)} {case['grid']} {case['strategy']} {case['phase']}: {result['cpu_percent']:.2f}% core",flush=True)
    (dest/'COMPLETE.json').write_text(json.dumps(dict(cases=len(results)))+'\n')
    gates = []
    for grid, colour in [(grid,False) for grid in GRIDS]+[([100,32],True)]:
        for phase in PHASES:
            group = {strategy:[r for r in results if r['grid']==list(grid)
                     and r['phase']==phase and r['colour']==colour and r['strategy']==strategy]
                     for strategy in ['native','paced']}
            medians = {s:statistics.median(r['cpu_percent'] for r in rows) for s,rows in group.items()}
            spreads = {s:(max(r['cpu_percent'] for r in rows)-min(r['cpu_percent'] for r in rows))
                       /max(medians[s],1) for s,rows in group.items()}
            rss = {s:max(r['sampled_peak_rss_bytes'] for r in rows) for s,rows in group.items()}
            work = {s:statistics.median(r['metrics']['p95_render_ms'] for r in rows) for s,rows in group.items()}
            gates.append(dict(grid=list(grid),colour=colour,phase=phase,cpu_medians=medians,
                 cpu_spreads=spreads,rss_sampled_peaks=rss,loop_p95_medians_ms=work,
                 cpu_pass=medians['paced']<=medians['native']+max(1,.1*medians['native']),
                 rss_pass=rss['paced']<=rss['native']+8*1024*1024,
                 composition_loop_pass=work['paced']<=work['native']*1.1+.5,
                 repeatability_pass=all(value<=.1 for value in spreads.values())))
    report = dict(cells=gates, recommendation='PASS' if all(all(row[key] for key in
                  ['cpu_pass','rss_pass','composition_loop_pass','repeatability_pass']) for row in gates) else 'HOLD',
                  limitations='Same-renderer native control is not a historical release. CPU affinity and 1 Hz frequency/load are diagnostic controls; whole-host work and physical presentation are not measured. Historical gates and interrupted/negative runs remain unchanged.')
    (dest/'SUMMARY.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Resource recommendation:',report['recommendation'],flush=True)


if __name__ == '__main__':
    main()
