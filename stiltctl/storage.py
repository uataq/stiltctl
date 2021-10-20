from cloudstorage import Container, DriverName, get_driver  # type: ignore
from cloudstorage.drivers.local import LocalDriver  # type: ignore


def get_bucket(bucket_name: str, driver_name: DriverName) -> Container:
    """Create a handle to an object storage bucket."""
    driver_class = get_driver(driver_name)
    if driver_class is LocalDriver:
        storage_path = ".cloudstorage"
        storage = driver_class(storage_path)
    else:
        storage = driver_class()

    return storage.get_container(bucket_name)
