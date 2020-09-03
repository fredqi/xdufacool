from unittest import TestCase
from xdufacool.dupcheck import fast_hash_file, load_list
from xdufacool.dupcheck import dupdict_to_yaml, simplify_dupdict
from xdufacool.dupcheck import FileList


class Test(TestCase):
    def setUp(self):
        self.filename = "/home/fred/Downloads/isos/gparted-live-1.1.0-1-amd64.iso"
        self.checksum = "eb5e0820b34ccdaf20b39b76035b907240fe8b04710fa0d842c76015fef246ca"

    def test_fast_hash_file(self):
        digest = fast_hash_file(self.filename, n_blocks=-1)
        self.assertEqual(self.checksum, digest,
                         msg="Incorrect checksum.")


class TestFileList(TestCase):
    def setUp(self):
        files = ["/home/fred/Downloads/isos/gparted-live-1.1.0-1-amd64.iso"]
        self.filesize = '372244480'
        self.sha256 = "eb5e0820b34ccdaf20b39b76035b907240fe8b04710fa0d842c76015fef246ca"
        self.filelist = FileList(files)

    def test_collect_property(self):
        firstfile = self.filelist.files[0]
        self.filelist.collect_property('size')
        self.assertEqual(self.filesize, firstfile['size'],
                         msg='Incorrect file size.')
        self.filelist.collect_property('sha256-partial')
        self.filelist.collect_property('sha256')
        self.assertEqual(self.sha256, firstfile['sha256'],
                         msg='Incorrect SHA.')

    def test_find_duplication(self):
        files = load_list('files-10M.txt')
        filelist = FileList(files)
        for prop in ['size', 'sha256-partial', 'sha256']:
            filelist.collect_property(prop)
            filelist.find_duplication(prop)
        dupdict_to_yaml('duplications.yml',
                        simplify_dupdict(filelist.duplications))