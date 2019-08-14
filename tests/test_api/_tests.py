"""Tests for :mod:`filemanager.routes.upload_api`."""

from unittest import TestCase, mock
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List
from io import BytesIO
from http import HTTPStatus as status
from pprint import pprint
import shutil

from pytz import UTC
import json
import tempfile
import filecmp
from io import BytesIO
import tarfile
import os
import re
import uuid
import os.path

import jsonschema
import jwt
from requests.utils import quote
from flask import Flask

from filemanager.factory import create_web_app
from filemanager.services import database

from arxiv.users import domain, auth


TEST_FILES_STRIP_PS = os.path.join(os.getcwd(), 'tests/test_files_strip_postscript')

# TODO: Leaving these because either they were commented out originally, or
# it's not clear what to do with them. --Erick 2019-06-26

# class TestAncillaryFiles(TestCase):
#     def test_download_ancillary_file(self):
#         """Download an ancillary file."""
#         response = self.client.get(
#             f"/filemanager/api/{self.upload_id}/main_a.tex/content",
#             headers={'Authorization': self.token}
#         )
#         self.assertEqual(response.status_code, status.OK)
#         self.assertIn('ETag', response.headers, "Returns an ETag header")
