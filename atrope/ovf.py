# -*- coding: utf-8 -*-

# Copyright 2015 Spanish National Research Council
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
from six.moves.urllib import parse
import tarfile

from lxml import etree

from atrope import exception

SPECS = {
    'http://www.vmware.com/interfaces/specifications/vmdk.html': 'vmdk',
    'https://people.gnome.org/~markmc/qcow-image-format.html': 'qcow',
}


def _get_tarfile(ova):
    if not tarfile.is_tarfile(ova):
        raise exception.CannotOpenFile(reason="not a valid 'tar' file")

    return tarfile.open(ova)


def extract_file(ova, filename):
    tf = _get_tarfile(ova)
    fd = tf.extractfile(filename)
    return fd


def get_disk_name(ovf):
    """Get the disk format and file name from a OVF descriptor."""
    root = etree.fromstring(ovf)
    ovf_ns = root.nsmap['ovf']

    id_attr = '{%s}id' % ovf_ns
    href_attr = '{%s}href' % ovf_ns
    files = {f.get(id_attr): f.get(href_attr) for f in
             root.findall('ovf:References/ovf:File', root.nsmap)}

    # we do not care about more than one disk
    disk = root.find('ovf:DiskSection/ovf:Disk', root.nsmap)
    if disk is not None:
        format_attr = '{%s}format' % ovf_ns
        fileref_attr = '{%s}fileRef' % ovf_ns
        ovf_format = disk.get(format_attr)
        if not ovf_format:
            raise Exception("Expecting some format!")
        (format_url, _) = parse.urldefrag(ovf_format)
        try:
            disk_format = SPECS[format_url]
        except KeyError:
            raise Exception("Unknown format!")
        try:
            disk_file = files[disk.get(fileref_attr)]
        except KeyError:
            raise Exception("Unknown disk!")
        return (disk_format, disk_file)
    return None, None


def get_ovf(ova):
    """Return an OVF descriptor as stored in an OVA file, if any."""
    tf = _get_tarfile(ova)

    ovf = None
    for name in tf.getnames():
        if name.endswith(".ovf"):
            ovf = tf.extractfile(name).read()
            break

    if ovf is None:
        raise exception.InvalidOVAFile(reason="cannot find a .ovf descriptor")
    return ovf
