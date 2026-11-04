"""Local helper: pack scripts, src, data/inputs and the pre-written basics test into one self-extracting Python file for the Colab VM.
  python scripts/push_to_colab.py            -> writes bootstrap_thesisv2.py in the thesisv2 folder
  colab exec -f bootstrap_thesisv2.py        (after `colab drivemount`; or paste the file into a colab-mcp cell)
Rerun both after any local fix to a script. It only writes inside Drive thesisv2/ (scripts, src, data/inputs, protocol/basics_test.json)."""
import io, zipfile, base64, os, glob
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
files = sorted(glob.glob(f'{root}/scripts/*.py') + glob.glob(f'{root}/src/*.py') + glob.glob(f'{root}/data/inputs/*') + [f'{root}/protocol/basics_test.json'])
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in files: z.write(f, os.path.relpath(f, root))
b = base64.b64encode(buf.getvalue()).decode()
src = ("import base64, io, zipfile, os\nD = '/content/drive/MyDrive/thesisv2'\nassert os.path.isdir('/content/drive/MyDrive'), 'mount Drive first'\nos.makedirs(D, exist_ok=True)\n"
       f"B = '{b}'\nzipfile.ZipFile(io.BytesIO(base64.b64decode(B))).extractall(D)\nprint('extracted', {len(files)}, 'files to', D)\n")
out = os.path.join(root, 'bootstrap_thesisv2.py'); open(out, 'w').write(src); print(f'wrote {out} ({len(src)/1e3:.0f} kB, {len(files)} files)')
