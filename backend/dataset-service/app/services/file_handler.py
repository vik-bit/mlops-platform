import os
import shutil
from fastapi import UploadFile


UPLOAD_DIR = "datasets"


def save_uploaded_file(file: UploadFile):

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    file_path = os.path.join(
        UPLOAD_DIR,
        file.filename
    )

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path