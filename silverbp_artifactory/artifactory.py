"""
Artifactory API
"""
import logging
import re
import hashlib
from collections import namedtuple

import requests

ApiReturn = namedtuple('ApiReturn', 'status_code response')

HashReturn = namedtuple('HashReturn', 'md5 sha1')

class ArtifactApiError(Exception):
    def __init__(self, message):
        super(ArtifactApiError, self).__init__(message)

class Artifact(object):
    def __init__(self, artifact_id, group_id, repo, extension=None):
        self._artifact_id = artifact_id
        self._repo = repo
        self._version = None
        self._remote = True
        self._group_id = group_id
        self._extension = extension or ''
        self._subpath = ''

    @property
    def version(self):
        return self._version

    @version.setter
    def version(self, version):
        self._version = version

    @property
    def artifact_id(self):
        return self._artifact_id

    @artifact_id.setter
    def artifact_id(self, artifact_id):
        self._artifact_id = artifact_id

    @property
    def repo(self):
        return self._repo

    @repo.setter
    def repo(self, repo):
        self._repo = repo

    @property
    def remote(self):
        return self._remote

    @remote.setter
    def remote(self, remote):
        self._remote = remote

    @property
    def group_id(self):
        return self._group_id

    @group_id.setter
    def group_id(self, group_id):
        self._group_id = group_id

    @property
    def extension(self):
        return self._extension

    @extension.setter
    def extension(self, extension):
        self._extension = extension

    @property
    def subpath(self):
        return self._subpath

    @subpath.setter
    def subpath(self, subpath):
        self._subpath = subpath

    def get_path(self, base_url):
        if not self.version or not self.extension:
            raise ArtifactApiError('version and extension must be specified to get the path')

        path = "{0}/{1}/{2}/{3}/{3}.{4}.{5}".format(
            base_url, self.repo, self.group_id, self.artifact_id, self.version, self.extension)
        if self.subpath:
            path = path + '!/' + self.subpath
        return path

    @property
    def name(self):
        if not self.version or not self.extension:
            raise ArtifactApiError('version and extension must be specified to get the name')

        return self._artifact_id + '.' + self._version + '.' + self._extension

class Api(object):
    def __init__(self, base_url, api_key, logger=None):
        self._base_url = base_url.strip('/')
        self._api_url = self._base_url + '/' + 'api'
        self._api_key = api_key
        self._headers = {'X-JFrog-Art-Api': self._api_key}
        self._logger = logger or logging.getLogger('silverbp_artifactory')

    def get_latest_version(self, artifact):
        if not isinstance(artifact, Artifact):
            raise ArtifactApiError('The artifact parameter must be of type Artifact')

        latest_version_url = "{0}/search/latestVersion?g={1}&a={2}&repos={3}&remote={4}".format(
            self._api_url, artifact.group_id, artifact.artifact_id,
            artifact.repo, int(artifact.remote))

        if artifact.version:
            latest_version_url = "{0}&v={1}".format(latest_version_url,
                                                    artifact.version)

        response = requests.get(latest_version_url, headers=self._headers)
        return ApiReturn(response.status_code, response.text)

    def search_artifacts(self, name, repos):
        search_url = "{0}/search/artifact?name={1}&repos={2}".format(
            self._api_url, name, repos)
        response = requests.get(search_url, headers=self._headers)
        return ApiReturn(response.status_code, response.json())

    def get_artifact_metadata(self, artifact):
        if not isinstance(artifact, Artifact):
            raise ArtifactApiError('The artifact parameter must be of type Artifact')

        metadata_url = "{0}/storage/{1}/{2}/{3}/{3}.{4}.{5}?properties".format(
            self._api_url, artifact.repo, artifact.group_id, artifact.artifact_id, artifact.version, artifact.extension)
        response = requests.get(metadata_url, headers=self._headers)

        json_response = response.json()
        properties = json_response['properties']

        # if this is a nuget package, see if there's a semvar version encoded in the description
        if 'nuget.description' in properties:
            nuget_description = properties['nuget.description'][0]
            semver_regex = r"\d+\.\d+(\.\d+)?(\.\d+)?\+\d+g[0-9a-f]{7}"
            semver_regex_match = re.search(semver_regex, nuget_description)
            if semver_regex_match:
                properties['sem_version'] = semver_regex_match.group()
            else:
                properties['sem_version'] = artifact.version

        return ApiReturn(response.status_code, json_response)

    def download_artifact(self, artifact, dest):
        if not isinstance(artifact, Artifact):
            raise ArtifactApiError('The artifact parameter must be of type Artifact')

        response = requests.get(artifact.get_path(self._base_url), headers=self._headers)

        if response.status_code != 200:
            return ApiReturn(response.status_code, response.text)

        with open(dest, 'wb') as f:
            f.write(response.content)

        return ApiReturn(response.status_code, None)

    def _hash_file(self, filename):
        buffer_size = 65536
        md5 = hashlib.md5()
        sha1 = hashlib.sha1()
        with open(filename, 'rb') as f:
            while True:
                data = f.read(buffer_size)
                if not data:
                    break
                md5.update(data)
                sha1.update(data)
        return HashReturn(md5.hexdigest(), sha1.hexdigest())

    def publish_artifact(self, artifact, src):
        file_hash = self._hash_file(src)

        headers = {
            'X-JFrog-Art-Api': self._api_key,
            'X-Checksum-Deploy': 'true',
            'X-Checksum-Sha1': file_hash.sha1,
            'X-Checksum-MD5': file_hash.md5
        }

        response = requests.put(artifact.get_path(self._base_url), data=open(src, 'rb'), headers=headers)
        return ApiReturn(response.status_code, response.json())
