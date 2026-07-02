"""S3-backed media storage: profile images and generated voice files.

Wraps the boto3 client (lazily constructed so a bare checkout / test run boots
without AWS credentials) and centralizes the upload/delete logic that used to
live inline in the route handlers.
"""

import datetime
import logging

import boto3
from flask import current_app

from src.extensions import db

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Lazily-created S3 client (avoids import-time AWS client construction).
_s3_client = None


def get_s3():
    """Return a shared, lazily-created boto3 S3 client."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            's3',
            aws_access_key_id=current_app.config['S3_KEY'],
            aws_secret_access_key=current_app.config['S3_SECRET'],
        )
    return _s3_client


def allowed_file(filename):
    """Return True if the filename has an allowed image extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_profile_picture(profile_image, model, model_type):
    """Upload a profile picture to S3 and persist its URL on the model.

    Input: profile_image (file), model (User or AIModel), model_type (str).
    Returns False on failure (and rolls back), None on success.
    """
    try:
        timestamp = datetime.datetime.now(datetime.UTC).timestamp()
        filename = f'{model_type}_profile_image{str(model.id)}{timestamp}.png'
        # upload to s3
        get_s3().upload_fileobj(
            profile_image,
            current_app.config['S3_BUCKET_NAME'],
            filename,
            ExtraArgs={'CacheControl': 'max-age=31536000, public'},
        )
        # Generate a versioned URL to force browser to load the new image
        versioned_url = f'{current_app.config["S3_LOCATION"]}{filename}'
        logger.debug(f'Profile image for {model.id} has been saved to S3! ImageURL: {versioned_url}')
        model.profile_image_url = versioned_url

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error saving profile picture for {model_type} {model.id}: {e}')
        return False


def delete_profile_image(profile_image_url):
    """Delete an AI's profile image from S3 given its public URL.

    Raises on S3 failure so the caller can roll back the surrounding
    transaction (behavior preserved from the original delete_ai handler).
    """
    profile_url_parts = profile_image_url.split('.amazonaws.com/')
    if len(profile_url_parts) > 1:
        profile_image_key = profile_url_parts[1].split('?')[0]
        logger.info(f'Deleting profile image: {profile_image_key}')
        get_s3().delete_object(
            Bucket=current_app.config['S3_BUCKET_NAME'],
            Key=profile_image_key,
        )


def delete_voice_files(messages):
    """Batch-delete the S3 voice files attached to a list of messages.

    Does not touch the database — the caller deletes the message rows. Raises
    on S3 failure so the caller can roll back.
    """
    voice_files_to_delete = []
    for message in messages:
        if message.voice_url:
            voice_url_parts = message.voice_url.split('.amazonaws.com/')
            if len(voice_url_parts) > 1:
                voice_key = voice_url_parts[1].split('?')[0]
                voice_files_to_delete.append({'Key': voice_key})
                logger.info(f'Adding voice file to deletion queue: {voice_key}')

    if voice_files_to_delete:
        get_s3().delete_objects(
            Bucket=current_app.config['S3_BUCKET_NAME'],
            Delete={'Objects': voice_files_to_delete, 'Quiet': True},
        )
