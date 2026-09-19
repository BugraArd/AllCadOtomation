"""Canli sematikte yanlis hedef, eski plan ve yari yazma korumalari."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from pcbqa import canli_sematik as front
from pcbqa import canli_sematik_worker as worker
from pcbqa.ipc import IpcApplyError


class Schematic:
    def __init__(self, target):
        self.name = target.name
        self.document = NS(project=NS(path=str(target.parent)))
        self.content = b'(kicad_sch (version 20260101))'
        self.begin_commit = Mock(return_value='transaction')
        self.push_commit = Mock()
        self.drop_commit = Mock()

    def save_as(self, path, **kwargs):
        Path(path).write_bytes(self.content)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.target = self.folder / 'board.kicad_sch'
        self.target.write_bytes(b'old disk schematic')
        self.sch = Schematic(self.target)
        self.kicad = NS(get_schematic=lambda: self.sch)
        live = self.folder / 'snapshot.kicad_sch'
        self.sch.save_as(live)
        self.plan = dict(target=str(self.target), fingerprint=worker.digest(live),
                         command='test', creates=[], updates=[], originals={}, signature=None)

    def test_same_filename_different_folder_is_refused(self):
        self.sch.document.project.path = str(self.folder / 'other')
        with self.assertRaisesRegex(IpcApplyError, 'farkli'):
            worker.apply(self.kicad, self.target, self.plan, {})
        self.sch.begin_commit.assert_not_called()

    def test_missing_project_path_is_refused(self):
        self.sch.document.project.path = ''
        with self.assertRaises(IpcApplyError):
            worker.check_target(self.sch, self.target)

    def test_stale_snapshot_never_opens_transaction(self):
        self.sch.content = b'(kicad_sch (version 20260102))'
        with self.assertRaisesRegex(IpcApplyError, 'sonra degisti'):
            worker.apply(self.kicad, self.target, self.plan, {})
        self.sch.begin_commit.assert_not_called()

    def test_single_sheet_snapshot_accepts_empty_children_generator(self):
        path = worker.snapshot(self.sch, self.folder, 'live.kicad_sch')
        self.assertEqual(path.read_bytes(), self.sch.content)

    def test_nested_sheet_is_refused(self):
        self.sch.content = b'(kicad_sch (sheet (uuid "child")))'
        with self.assertRaisesRegex(IpcApplyError, 'tek sayfali'):
            worker.snapshot(self.sch, self.folder, 'live.kicad_sch')

    def test_server_rejection_drops_transaction_without_push(self):
        self.plan['creates'] = [{'test': 'item'}]
        with patch.object(worker, 'decode', return_value=object()), patch.object(
                worker, 'write_checked', side_effect=IpcApplyError('rejected')):
            with self.assertRaisesRegex(IpcApplyError, 'rejected'):
                worker.apply(self.kicad, self.target, self.plan, {})
        self.sch.drop_commit.assert_called_once_with('transaction')
        self.sch.push_commit.assert_not_called()
        self.assertEqual(self.target.read_bytes(), b'old disk schematic')

    def test_missing_existing_item_is_not_reported_as_success(self):
        self.plan['originals'] = {'old-uuid': {'data': 'old'}}
        with patch.object(worker, 'items', return_value=[]):
            with self.assertRaisesRegex(IpcApplyError, r'Ctrl\+Z'):
                worker.apply(self.kicad, self.target, self.plan, {})
        self.sch.push_commit.assert_called_once()

    def test_live_connectivity_mismatch_is_reported(self):
        self.plan['signature'] = {'nets': ['expected']}
        with patch.object(worker, 'items', return_value=[]), patch.object(
                worker, 'net_signature', return_value={'nets': ['wrong']}):
            with self.assertRaisesRegex(IpcApplyError, 'netlist'):
                worker.apply(self.kicad, self.target, self.plan, {'cli': 'fake'})


class FrontTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.base = self.folder / 'app'
        (self.base / '.runtime').mkdir(parents=True)
        self.source = self.folder / 'original/card.kicad_sch'
        self.source.parent.mkdir()
        self.source.write_text('(kicad_sch)', encoding='utf-8')
        self.profile = self.base / '.runtime/profile/10.99'
        self.profile.mkdir(parents=True)
        (self.profile / 'kicad_common.json').write_text(json.dumps({'api': {'enable_server': False}, 'other': 42}))
        self.config = dict(python='python.exe', cli='kicad-cli.exe', profile=str(self.profile.parent),
                           stock=str(self.folder / 'stock'), temp=str(self.folder / 'temp'), version='nightly')
        self.enterContext(patch.object(front, 'BASE', self.base))
        self.enterContext(patch.object(front, 'PROJECTS', self.folder / 'CanliProjeler'))
        self.enterContext(patch.object(front, 'configuration', return_value=self.config))

    def test_existing_headless_profile_enables_api_before_open(self):
        with patch.object(front.subprocess, 'Popen', return_value=NS(pid=1)):
            result = front.open_copy(self.source)
        config = json.loads((self.profile / 'kicad_common.json').read_text())
        self.assertTrue(config['api']['enable_server'])
        self.assertEqual(config['other'], 42)
        self.assertNotEqual(Path(result['project']), self.source)
        self.assertEqual(Path(result['project']).read_bytes(), self.source.read_bytes())

    def test_open_original_is_not_copied_from_stale_disk(self):
        (self.source.parent / '~card.kicad_pro.lck').write_text('lock')
        with patch.object(front.subprocess, 'Popen') as launch:
            with self.assertRaisesRegex(IpcApplyError, 'Kaynak proje acik'):
                front.open_copy(self.source)
        launch.assert_not_called()

    def test_worker_has_separate_profile_from_visible_editor(self):
        result = NS(returncode=0, stdout=json.dumps({'ok': True, 'result': {}}), stderr='')
        with patch.object(front.subprocess, 'run', return_value=result) as run:
            front.request('check', self.source)
        env = run.call_args.kwargs['env']
        self.assertEqual(env['KICAD_CONFIG_HOME'], self.config['profile'] + '-worker')
        self.assertEqual(front.environment(self.config)['KICAD_CONFIG_HOME'], self.config['profile'])

    def test_worker_error_is_not_reported_as_success(self):
        result = NS(returncode=2, stdout=json.dumps({'ok': False, 'error': 'netlist mismatch'}), stderr='')
        with patch.object(front.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(IpcApplyError, 'netlist mismatch'):
                front.request('apply', self.source)


if __name__ == '__main__':
    unittest.main()
