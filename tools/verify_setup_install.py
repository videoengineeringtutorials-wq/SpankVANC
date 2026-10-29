"""Read-only native installer check; starts no app, media, licensing or prerequisites."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    root=Path(sys.argv[1]).resolve()
    manifest=json.loads((root/'PACKAGE.json').read_text())
    for name,expected in manifest['files'].items():
        assert (root/name).resolve().is_relative_to(root),name
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected,name
    assert (root/'Uninstall.exe').is_file()
    binary=root/'python/python.exe'
    code="import sys;sys.path.insert(0,sys.argv[1]);import spankvanc;assert spankvanc.__version__==sys.argv[2]"
    subprocess.run([str(binary),'-I','-c',code,str(root/'app'),manifest['app_version']],check=True)
    spec=importlib.util.spec_from_file_location('installed_setup',root/'setup/setup.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as folder:
        wizard=module.Setup(root,Path(folder)/'state')
        assert not wizard.state()['running'] and not wizard.state()['ready']
        assert wizard.deps['python']['url'].startswith('https://www.python.org/')
        assert not (root/'license.json').exists()
    print('Native installer payload, embedded runtime and wizard imports: PASS')


if __name__=='__main__':main()
