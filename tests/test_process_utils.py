"""Background Windows media, speech and probe children must never allocate consoles."""
import subprocess
import unittest
from unittest.mock import patch, Mock
from spankvanc.process_utils import hidden_process_options, start_media_process
from spankvanc.engine import process_group_options, terminate_process


class HiddenProcessTests(unittest.TestCase):
    def test_windows_probes_hidden_and_managed_children_keep_group(self):
        with patch('spankvanc.process_utils.os.name','nt'), \
             patch.object(subprocess,'CREATE_NO_WINDOW',0x08000000,create=True), \
             patch.object(subprocess,'CREATE_NEW_PROCESS_GROUP',0x200,create=True):
            self.assertEqual(hidden_process_options(),{'creationflags':0x08000000})
            self.assertEqual(process_group_options(),{'creationflags':0x08000200})

    def test_non_windows_launch_behavior_is_unchanged(self):
        with patch('spankvanc.process_utils.os.name','posix'):
            self.assertEqual(hidden_process_options(),{})
            self.assertEqual(process_group_options(),{})

    def test_hidden_media_uses_quit_pipe_and_stop_preserves_diagnostics(self):
        child=Mock()
        with patch('spankvanc.process_utils.os.name','nt'), \
             patch.object(subprocess,'CREATE_NO_WINDOW',0x08000000,create=True), \
             patch.object(subprocess,'CREATE_NEW_PROCESS_GROUP',0x200,create=True), \
             patch('spankvanc.process_utils.subprocess.Popen',return_value=child) as launch:
            args=['ffmpeg','-nostdin','-i','input.ts']
            self.assertIs(start_media_process(args,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True),child)
            self.assertEqual(args[1],'-nostdin')
            self.assertEqual(launch.call_args.args[0][1],'-stdin')
            self.assertEqual(launch.call_args.kwargs['stdin'],subprocess.PIPE)
            self.assertEqual(launch.call_args.kwargs['stderr'],subprocess.PIPE)
            terminate_process(child)
            child.stdin.write.assert_called_once_with('q\n')
            child.stdin.flush.assert_called_once()
            child.send_signal.assert_not_called()
            child.terminate.assert_not_called()
