# -*- coding: utf-8 -*-

# Copyright 2014 Alvaro Lopez Garcia
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

import errno
import hashlib
import os


def makedirs(path):
    """Recursive directory creation function.

    If the directory exists it will not raise an exception.

    :param path: Directory to create
    """
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            if not os.path.isdir(path):
                raise
        else:
            raise


def get_file_checksum(path, block_size=2**20):
    sha512 = hashlib.sha512()
    with open(path, "rb") as f:
        buf = f.read(block_size)
        while len(buf) > 0:
            sha512.update(buf)
            buf = f.read(block_size)
    return sha512
