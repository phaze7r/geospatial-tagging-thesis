"""Local driver for the Colab CLI. `colab exec` runs code inside the VM kernel with a default 30 s timeout, so long steps are started as DETACHED processes
on the VM (own argv, own log, survive a dropped connection) and followed with `tail`.
  python scripts/colab_step.py new [GPU]                    create the session (A100 | L4 | T4; none = CPU), mount Drive
  python scripts/colab_step.py push                         build bootstrap_thesisv2.py and extract it into Drive thesisv2/ on the VM
  python scripts/colab_step.py launch s03_extract.py [args] start a step detached; log in Drive thesisv2/logs/<step>.log
  python scripts/colab_step.py tail s03_extract [lines]     show the end of its log (look for EXIT_CODE 0)
  python scripts/colab_step.py status                       running python processes and GPU
  python scripts/colab_step.py pull results/final.json      download Drive thesisv2/<path> to ~/thesisv2/<path>
  python scripts/colab_step.py stop                         release the VM (compute units stop burning)
Set COLAB_SESSION=name to address a named session (default: the only active one). Untested before the first real run: step C0 verifies it."""
import os, sys, subprocess, shlex
DRIVE = '/content/drive/MyDrive/thesisv2'; ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..')); S = os.environ.get('COLAB_SESSION')


def colab(*a, stdin=None):
    cmd = ['colab', *a] + (['-s', S] if S and a[0] in ('exec', 'drivemount', 'download', 'stop', 'ls') else [])
    r = subprocess.run(cmd, input=stdin, text=True, capture_output=True); print(r.stdout + r.stderr); return r.returncode


def code(src, timeout=300): return colab('exec', '--timeout', str(timeout), stdin=src)


def main():
    cmd, *a = sys.argv[1:] or ['help']
    if cmd == 'new':
        gpu = a[0] if a else None; rc = colab('new', *(['--gpu', gpu] if gpu else [])) or colab('drivemount'); sys.exit(rc)
    if cmd == 'push':
        subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'push_to_colab.py')], check=True); sys.exit(colab('exec', '--timeout', '600', '-f', os.path.join(ROOT, 'bootstrap_thesisv2.py')))
    if cmd == 'launch':
        script, args = a[0], a[1:]; name = os.path.splitext(script)[0]
        run = f"python -u {shlex.quote(DRIVE + '/scripts/' + script)} {' '.join(shlex.quote(x) for x in args)}; echo EXIT_CODE $?"
        sys.exit(code(f"import subprocess, os\nD = {DRIVE!r}\nos.makedirs(D + '/logs', exist_ok=True)\nlog = open(D + '/logs/{name}.log', 'a')\n"
                      f"p = subprocess.Popen(['sh', '-c', {run!r}], stdout=log, stderr=subprocess.STDOUT, cwd=D, start_new_session=True)\nprint('started pid', p.pid, '-> logs/{name}.log')\n"))
    if cmd == 'tail':
        # download, not exec: exec queues on the busy kernel and timed-out requests pile up behind the running step
        n = int(a[1]) if len(a) > 1 else 40; loc = os.path.join(ROOT, 'logs', a[0] + '.log'); os.makedirs(os.path.dirname(loc), exist_ok=True)
        if os.path.exists(loc): os.remove(loc)   # never show a stale copy when the download fails
        r = subprocess.run(['colab', 'download', f'{DRIVE}/logs/{a[0]}.log', loc] + (['-s', S] if S else []), capture_output=True, text=True)
        if not os.path.exists(loc): print('DOWNLOAD FAILED:', (r.stdout + r.stderr).strip()[-300:]); sys.exit(1)
        lines = open(loc, errors='replace').read().replace('\r', '\n').splitlines()
        print('\n'.join([l for l in lines if 'downloaded' not in l][-n:])); sys.exit(0)
    if cmd == 'status': sys.exit(code("import subprocess\nprint(subprocess.run('ps -eo pid,etime,cmd | grep -E \"s[0-9]+|c0_\" | grep -v grep; nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader; free -g | head -2', shell=True, capture_output=True, text=True).stdout)\n"))
    if cmd == 'pull':
        os.makedirs(os.path.dirname(os.path.join(ROOT, a[0])) or ROOT, exist_ok=True); sys.exit(colab('download', f'{DRIVE}/{a[0]}', os.path.join(ROOT, a[0])))
    if cmd == 'stop': sys.exit(colab('stop'))
    print(__doc__)


if __name__ == '__main__': main()
