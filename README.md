# RED//MEDIA

Public media gallery with private Flask admin panel. Turso stores metadata and Cloudinary stores actual media files.

## GitHub repository structure

Upload all files and folders in this ZIP to the root of your repository.

## Render settings

Build command:
`pip install -r requirements.txt`

Start command:
`gunicorn app:app`

## Render environment variables

Set these under Render → Web Service → Environment:

- `SECRET_KEY`: generate a long random string, e.g. locally run `python -c "import secrets; print(secrets.token_hex(32))"`
- `ADMIN_USERNAME`: admin username
- `ADMIN_PASSWORD`: strong unique password
- `TURSO_DATABASE_URL`: your Turso database URL
- `TURSO_AUTH_TOKEN`: your Turso auth token
- `CLOUDINARY_URL`: Cloudinary URL from your Cloudinary dashboard
- `MAX_UPLOAD_MB`: optional, defaults to 50

Do not commit secrets or `.env` files to GitHub. If a token is ever exposed, revoke and rotate it.

## Services

- Render: Flask hosting
- Turso: media metadata database
- Cloudinary: file/image/video storage

Free tiers have quotas and restrictions. Check current quotas in each provider dashboard before uploading large videos.

## Admin URL

After deployment, open `/admin/login`.

## Features

- Categories: Bilder, Videos, Dateien, Musik, Sonstiges
- Search
- Image previews and detail pages
- Video playback
- File links/downloads
- Admin upload/delete
- CSRF protection

## Security notes

- Public uploads are visible to every visitor. Do not upload private or sensitive material.
- Use strong unique admin credentials.
- Cloudinary files are public media by design in this app.
- Consider adding login rate limiting and moderation before a large public launch.
- Ensure your site's privacy/legal pages are appropriate for your use and jurisdiction.
