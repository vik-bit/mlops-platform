def save_uploaded_file(file) -> bytes:
    """
    Read the uploaded file into memory and return raw bytes.
    The caller stores these bytes in the Dataset.content column in Postgres
    instead of writing to local disk — no external storage needed, and the
    file survives service restarts since Postgres is persistent.
    """
    return file.file.read()