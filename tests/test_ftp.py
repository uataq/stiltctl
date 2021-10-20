import tempfile
from pathlib import Path

import pytest  # type: ignore

from stiltctl.ftp import FTPFile, FTPStorage

LOCAL_FILE = str(Path(__file__).parent.parent / "README.md")


@pytest.fixture(scope="session")
def noaa_ftp_storage() -> FTPStorage:
    """Provide FTP storage adapter for testing.

    NOAA ARL uses an old FTP server version which doesn't support the MLSD command for
    standardized directory listings or MLST for fetching file metadata. We test against
    this to ensure data retrieval commands are supported.
    """
    return FTPStorage("arlftp.arlhq.noaa.gov/archives/utility/")


def test_ftp_iterate_files(noaa_ftp_storage: FTPStorage):
    file_generator = noaa_ftp_storage.files
    file = next(file_generator)
    assert file == FTPFile(storage_adapter=noaa_ftp_storage, path="GAMDUP.CFG")
    file = next(file_generator)
    assert file == FTPFile(storage_adapter=noaa_ftp_storage, path="METFILE.BAK")


def test_ftp_get_metadata(noaa_ftp_storage: FTPStorage):
    file = noaa_ftp_storage.get_file("chk_data.f")
    expected_metadata = {"modified_at": "2009-01-15 08:42:44", "size": "4597"}
    assert file.metadata == expected_metadata


def test_ftp_download_file(noaa_ftp_storage: FTPStorage):
    file = noaa_ftp_storage.get_file("chk_data.f")
    with tempfile.NamedTemporaryFile() as file_obj:
        file.download_to_filename(Path(file_obj.name))
        content = file_obj.read()
    assert b"Simple program" in content
