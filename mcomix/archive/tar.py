# -*- coding: utf-8 -*-

""" Unicode-aware wrapper for tarfile.TarFile. """

import tarfile
import archive_base

class TarArchive(archive_base.NonUnicodeArchive):
    def __init__(self, archive):
        super(TarArchive, self).__init__(archive)
        self.tar = tarfile.open(archive, 'r')
        # Track if archive contents have been listed at least one time: this
        # must be done before attempting to extract contents.
        self._contents_listed = False

    def is_solid(self):
        return True

    def iter_contents(self):
        # Make sure we start back at the beginning of the tar.
        self.tar.offset = 0
        while True:
            info = self.tar.next()
            if info is None:
                break
            yield self._unicode_filename(info.name)
        self._contents_listed = True

    def extract(self, filename, destination_path):
        if not self._contents_listed:
            self.list_contents()
        new = self._create_file(destination_path)
        file_object = self.tar.extractfile(self._original_filename(filename))
        new.write(file_object.read())
        file_object.close()
        new.close()

    def iter_extract(self, entries):
        if not self._contents_listed:
            self.list_contents()
        for f in super(TarArchive, self).iter_extract(entries):
            yield f

    def close(self):
        self.tar.close()

# vim: expandtab:sw=4:ts=4
