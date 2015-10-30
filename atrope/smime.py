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

import os

import M2Crypto
from oslo_config import cfg

from atrope import exception

opts = [
    cfg.StrOpt('ca_path',
               default='/etc/grid-security/certificates/',
               help='Where to find CA certificates to verify against.'),
]

CONF = cfg.CONF
CONF.register_opts(opts)


class SMIMEVerifier(object):
    def __init__(self):
        self._set_up_store()

        self.smime = M2Crypto.SMIME.SMIME()
        self.smime.set_x509_store(self.store)

    def _set_up_store(self):
        self.store = M2Crypto.X509.X509_Store()
        for f in os.listdir(CONF.ca_path):
            # TODO(aloga): Check here that we are actually loading anything
            # so that we can raise a proper error. If we cannot load anything
            # in the store we won't be able to verify the certificate, but
            # the error will be just a "verify errro"
            if f.endswith('.0') or f.endswith('.r0'):
                self.store.load_info(os.path.join(CONF.ca_path, f))

    def verify(self, msg):
        buf = M2Crypto.BIO.MemoryBuffer(msg)
        try:
            p7, data_bio = M2Crypto.SMIME.smime_load_pkcs7_bio(buf)
        except M2Crypto.SMIME.SMIME_Error as e:
            raise exception.SMIMEValidationError(exception=e)

        if data_bio is None:
            raise exception.SMIMEValidationError(exception='no data found')

        signers = p7.get0_signers(M2Crypto.X509.X509_Stack())
        if len(signers) == 0:
            raise exception.SMIMEValidationError(
                exception='no certificates found'
            )

        signer = [(str(c.get_subject()), str(c.get_issuer())) for c in signers]

        self.smime.set_x509_stack(signers)
        try:
            verified_data = self.smime.verify(p7, data_bio)
        except (M2Crypto.SMIME.SMIME_Error, M2Crypto.SMIME.PKCS7_Error) as e:
            raise exception.SMIMEValidationError(exception=e)

        orig_data = data_bio.read()
        if orig_data != verified_data:
            raise exception.SMIMEValidationError('verification failed: list '
                                                 'contents do not match the '
                                                 'output of SMIME.verify')
        return signer, verified_data
