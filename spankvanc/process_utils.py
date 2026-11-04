"""Windows GUI child-process options; output remains in our pipes/logs."""
import os
import subprocess


def hidden_process_options(*, new_group=False):
    if os.name != 'nt':
        return {}
    flags = subprocess.CREATE_NO_WINDOW
    if new_group:
        flags |= subprocess.CREATE_NEW_PROCESS_GROUP
    return {'creationflags': flags}


def start_media_process(args, **kwargs):
    """Give hidden Windows FFmpeg a private quit pipe for graceful Stop."""
    control = os.name == 'nt'
    if control:
        args = list(args)
        if '-nostdin' in args:
            args[args.index('-nostdin')] = '-stdin'
        else:
            args.insert(1, '-stdin')
        kwargs['stdin'] = subprocess.PIPE
    kwargs.update(hidden_process_options(new_group=True))
    process = subprocess.Popen(args, **kwargs)
    if control:
        process._spank_control_stdin = True
    return process
