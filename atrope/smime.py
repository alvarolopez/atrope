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

import subprocess
import tempfile

import OpenSSL
from oslo_config import cfg

from atrope import exception

opts = [
    cfg.StrOpt('ca_path',
               default='/etc/grid-security/certificates/',
               help='Where to find CA certificates to verify against.'),
]

CONF = cfg.CONF
CONF.register_opts(opts)


class Signer(object):
    def __init__(self, dn, ca):
        aux = [(i.decode("utf-8"), j.decode("utf-8"))
               for i, j in dn.get_components()]
        aux = "/".join(["=".join(i) for i in aux])
        self.dn = f"/{aux}"
        aux = [(i.decode("utf-8"), j.decode("utf-8"))
               for i, j in ca.get_components()]
        aux = "/".join(["=".join(i) for i in aux])
        self.ca = f"/{aux}"

    def __str__(self):
        return f"<Signer dn:{self.dn}, ca:{self.ca}>"


class SMIMEVerifier(object):
    def verify(self, msg):
        signer, verified_data = self._get_signer_cert_and_verify(msg)
        if not signer:
            raise exception.SMIMEValidationError(err="no certificates found")
        issuer, signer = self._extract_signer_issuer_and_subject(signer)
        return Signer(signer, issuer), verified_data

    def _extract_signer_issuer_and_subject(self, signer):
        x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM,
                                               signer)
        return x509.get_issuer(), x509.get_subject()

    def _get_signer_cert_and_verify(self, data):
        with tempfile.NamedTemporaryFile(mode="r", delete=True) as signer_file:
            process = subprocess.Popen(["openssl",
                                        "smime",
                                        "-verify",
                                        "-signer", signer_file.name,
                                        "-CApath", CONF.ca_path],
                                       stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
            output, err = process.communicate(data)
            retcode = process.poll()
            if err is not None:
                err = err.decode('utf-8')

            if retcode == 2:
                raise exception.SMIMEValidationError(err=err)
            elif retcode:
                # NOTE(dmllr): Python 2.6 compatibility:
                # CalledProcessError did not have output keyword argument
                e = subprocess.CalledProcessError(retcode, 'openssl')
                e.output = err
                raise e

            signer = signer_file.read()
        return signer, output
