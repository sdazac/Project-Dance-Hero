# OpenDance AI — Privacy and Media Rules

## Local-first architecture

OpenDance AI should process camera and reference-video data locally by default.

The MVP must not require cloud processing.

## Camera

Camera frames should remain local.

Do not upload camera frames to external services.

Do not record or persist camera video unless the user explicitly requests recording functionality.

## Reference videos

Reference videos are user-provided local media.

The application should process them locally.

Do not upload reference videos.

## Cached analysis

Reference analysis artifacts may be stored locally to avoid repeating expensive processing.

Cached artifacts should not contain unnecessary personal information.

## Logs

Logs must not contain:

* raw video;
* raw camera frames;
* unnecessary personal information.

## Permissions

The application should clearly communicate when camera access is required.

If camera access fails, show a clear user-facing error.

## Copyright

The application must not distribute copyrighted commercial videos or music without appropriate permission.

The repository should use:

* synthetic demo videos;
* public-domain media;
* appropriately licensed media;
* or user-provided local media.

Do not bundle Project Sekai, Hatsune Miku concert footage, K-pop videos or other copyrighted commercial material unless redistribution rights are explicitly confirmed.

## Future networking

If networking is introduced in a future version, it must be treated as a separate architectural feature and must not silently transmit camera or media data.
