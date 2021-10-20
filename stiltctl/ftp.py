"""
Utilities for accessing data from remote FTP servers.

This is just a thin wrapper around ftplib for downloading files from FTP servers
and providing basic metadata (remote file size and last modified time) that can
be used to detect upstream changes for data synchronization.

Not currently in use, since Google is now mirroring HRRR data to GCS for us.
"""
from datetime import datetime
from ftplib import FTP, error_perm
from pathlib import Path
from typing import Any, Generator, Optional, Sequence, Union

from pydantic import BaseModel


class ChangeDetectionMetadata(BaseModel):
    """Used to identify changes in files mirrorred from external sources."""

    modified_at: Optional[datetime]
    size: Optional[int]


# TODO: Implement backoff for FTP downloads to handle rate limiting. The NOAA ARL used
# by the meteorology ingest service rate limits connections, although the specific
# limitations are not documented.
class FTPFile:
    def __init__(self, path: str, storage_adapter: "FTPStorage"):
        self.path = path
        self.storage_adapter = storage_adapter
        self._ftp_client = storage_adapter.client

    def download_to_filename(self, filename: Path):
        filename.parent.mkdir(parents=True, exist_ok=True)
        with open(filename, "wb") as file_obj:
            self._ftp_client.retrbinary(f"RETR {self.path}", file_obj.write)

    def upload_from_filename(self, filename: str):
        """No use cases currently require writing to FTP FTP servers."""
        raise NotImplementedError

    @property
    def exists(self) -> bool:
        raise NotImplementedError

    @property
    def metadata(self) -> dict[str, str]:
        try:
            size = self._ftp_client.size(self.path)
        except error_perm:
            metadata = dict()
        else:
            status_code, timestamp = self._ftp_client.voidcmd(
                f"MDTM {self.path}"
            ).split()
            if status_code == "213":
                metadata = ChangeDetectionMetadata(
                    modified_at=datetime.strptime(timestamp, "%Y%m%d%H%M%S"), size=size
                ).dict()
            else:
                metadata = dict()

        return {k: str(v) for k, v in metadata.items()}

    @metadata.setter
    def metadata(self, metadata: Union[dict[str, Any], BaseModel]):
        """Write access not permitted on FTP servers."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}"
            f"(storage_adapter='{self.storage_adapter}', path='{self.path}')"
        )

    def __eq__(self, other) -> bool:
        return self.metadata == other.metadata


class FTPStorage:
    def __init__(self, resource_url: str):
        """Provide download methods for files on FTP server."""
        resource_url = resource_url.lstrip("ftp://")

        if "/" in resource_url:
            url, path_prefix = resource_url.split("/", 1)
        else:
            url = resource_url
            path_prefix = "/"

        self.client = FTP(url)
        self.client.login()
        self.client.cwd(path_prefix)
        self.path_prefix = path_prefix
        self.url = url

    def get_file(self, path: str) -> "FTPFile":
        return FTPFile(storage_adapter=self, path=path)

    @property
    def files(self) -> Generator["FTPFile", None, None]:
        for filename in self._walk_tree():
            yield self.get_file(filename)

    def _walk_tree(self, paths: Sequence[str] = ["."]) -> Generator[str, None, None]:
        """Recursively traverse and yield available file paths."""
        for path in paths:
            child_paths = self.client.nlst(path)
            if not child_paths:  # is an empty directory
                continue
            elif child_paths[0] == path:  # is a file
                yield path
            else:  # is a directory
                yield from self._walk_tree(child_paths)
