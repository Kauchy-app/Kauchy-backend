import cloudinary
import cloudinary.uploader


def detect_media_type(uploaded_file):
    """Return 'video', 'audio', or 'image' based on the uploaded file's content type."""
    content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
    if content_type.startswith("video"):
        return "video"
    if content_type.startswith("audio"):
        return "audio"
    return "image"


def cloudinary_video_delivery(url):
    """Return a browser-compatible delivery URL for a Cloudinary-hosted video.

    iPhones record video in HEVC (H.265) by default. Apple devices decode it fine,
    but desktop Chrome/Firefox cannot decode the HEVC video track (blank video,
    audio only) even though they decode the AAC audio. Injecting ``f_auto,q_auto``
    lets Cloudinary transcode and deliver H.264 to those browsers automatically,
    while still serving HEVC/VP9 where supported. Applies to existing uploads too,
    since it only rewrites the delivery URL.
    """
    if not url or "/video/upload/" not in url:
        return url

    head, sep, tail = url.partition("/video/upload/")
    # Skip if a transformation segment is already present (avoid double-applying).
    first_segment = tail.split("/", 1)[0]
    if "f_auto" in first_segment:
        return url
    # q_auto:best keeps Cloudinary's smart format selection (f_auto) but at the
    # highest automatic quality tier, avoiding the visible softening that the
    # default q_auto ("good") causes.
    return f"{head}{sep}f_auto,q_auto:best/{tail}"


def upload_to_cloudinary(uploaded_file, folder, resource_type="image"):
    """Upload a Django UploadedFile to Cloudinary and return its secure URL.

    Mirrors the approach used in customers.views for vendor content. Cloudinary is
    configured globally via CLOUDINARY_STORAGE in settings.
    """
    options = {
        "folder": folder,
        "resource_type": resource_type,
        "invalidate": True,
    }
    if resource_type == "video":
        # Large-file friendly options, matching customers.views.
        options.update({"chunk_size": 6000000, "timeout": 600, "eager_async": True})

    result = cloudinary.uploader.upload(uploaded_file, **options)
    return result["secure_url"]
