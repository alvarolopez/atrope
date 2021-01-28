# -*- coding: utf-8 -*-

# Copyright 2021 Alvaro Lopez Garcia
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

import atrope
from atrope.cmd import base


class CommandVersion(base.BaseCommand):
    def __init__(self, parser, name="version",
                 cmd_help="Show verison and exit."):
        super(CommandVersion, self).__init__(parser, name, cmd_help)

    def run(self):
        print(atrope.__version__)
