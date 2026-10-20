#!/usr/bin/env python3
"""Validate the OCI image layout and manifest/config media types in an archive."""
import json
from pathlib import Path
import sys
import tarfile


def check(path):
    with tarfile.open(path) as archive:
        members = {item.name.lstrip('./'): item for item in archive.getmembers()}

        def read(name):
            return json.load(archive.extractfile(members[name]))

        assert read('oci-layout')['imageLayoutVersion'] == '1.0.0'
        index = read('index.json')
        assert index['schemaVersion'] == 2
        manifests = []

        def visit(descriptor):
            media_type = descriptor['mediaType']
            assert media_type in ('application/vnd.oci.image.index.v1+json',
                                  'application/vnd.oci.image.manifest.v1+json'), media_type
            blob = read('blobs/' + descriptor['digest'].replace(':', '/'))
            if 'manifests' in blob:
                for child in blob['manifests']:
                    visit(child)
            else:
                assert blob['config']['mediaType'] == 'application/vnd.oci.image.config.v1+json'
                manifests.append(blob)

        for descriptor in index['manifests']:
            visit(descriptor)
        assert manifests, 'No OCI image manifests'
    print('OCI layout and manifest/config media types: OK')


if __name__ == '__main__':
    check(Path(sys.argv[1]))
