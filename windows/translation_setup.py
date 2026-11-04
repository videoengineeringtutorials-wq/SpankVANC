"""Optional OPUS-MT installation, isolated from the app and Whisper packages."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time


def python_path(home):
    return Path(home)/'python/python.exe'


def install(setup):
    spec=setup.deps['translation']
    home=setup.root/'translation';home.mkdir(exist_ok=True)
    python=python_path(home)
    setup.step='Installing optional Spanish translation'
    if not python.is_file():
        archive=setup.download('python')
        python.parent.mkdir(exist_ok=True)
        # Use the wizard's checked ZIP extraction, including traversal checks.
        import zipfile
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                path=Path(item.filename.replace('\\','/'))
                if path.is_absolute() or '..' in path.parts or ':' in str(path):
                    raise ValueError('Unsafe translation Python archive')
            z.extractall(python.parent)
    packages=spec['runtime_packages']
    setup.command([python,'-I','-m','pip','install','--disable-pip-version-check',*packages,'--index-url','https://pypi.org/simple'])
    model=home/'model'
    provenance=model/'provenance.json'
    if provenance.is_file():
        try:
            saved=json.loads(provenance.read_text())
            if not isinstance(saved,dict):saved={}
        except (OSError,ValueError):
            saved={}
        hashes=saved.get('sha256',{})
        if saved.get('revision')==spec['revision'] and isinstance(hashes,dict) and hashes and all((model/name).is_file() and hashlib.sha256((model/name).read_bytes()).hexdigest()==digest for name,digest in hashes.items()):
            verify(setup,python,model)
            return
    converter=setup.data/'translation-converter'
    setup.command([setup.python,'-I','-m','pip','install','--upgrade','--target',converter,
                   '--disable-pip-version-check',*spec['converter_packages'],'--index-url','https://pypi.org/simple'])
    source=setup.data/('translation-source-'+spec['revision']);source.mkdir(exist_ok=True)
    for name,digest in spec['source_files'].items():
        key='translation-source-'+name
        setup.deps[key]={'url':spec['base_url']+'/'+spec['revision']+'/'+name,
                         'filename':'opus-en-es-'+spec['revision']+'-'+name,'sha256':digest}
        shutil.copyfile(setup.download(key),source/name)
    setup.step='Converting OPUS-MT for CPU translation'
    with tempfile.TemporaryDirectory(prefix='model-stage-',dir=home) as folder:
        stage=Path(folder)/'model'
        script="""
import sys,os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
sys.path.insert(0,sys.argv[1])
from ctranslate2.converters import TransformersConverter
TransformersConverter(sys.argv[2]).convert(sys.argv[3],quantization='int8')
"""
        setup.command([setup.python,'-I','-c',script,converter,source,stage/'ct2'])
        for name in ('source.spm','target.spm','README.md'):
            shutil.copyfile(source/name,stage/name)
        record={'model':'Helsinki-NLP/opus-mt-en-es','license':'Apache-2.0','revision':spec['revision'],
                'quantization':'int8','runtime_packages':packages,
                'sha256':{str(p.relative_to(stage)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.rglob('*') if p.is_file()}}
        (stage/'provenance.json').write_text(json.dumps(record,indent=2)+'\n')
        verify(setup,python,stage)
        if model.exists():model.rename(home/('model-before-'+str(time.time_ns())))
        stage.rename(model)
    setup.log('Spanish translation is installed. Enable CC2 separately on each desired output.')


def verify(setup,python,model):
    worker=setup.root/'app/spankvanc/translation_worker.py'
    if not worker.is_file():worker=setup.root/'spankvanc/translation_worker.py'
    output=setup.command([python,'-I',worker,model],capture=True,
                         input_text=json.dumps({'english':'Good evening.'})+'\n',timeout=60)
    messages=[json.loads(line) for line in output.splitlines() if line.strip()]
    if not messages or not messages[0].get('ready') or not any(m.get('spanish') for m in messages):
        raise ValueError('The Spanish translation model did not produce test text.')
