# ThisData Community (separate from KJB)

This folder contains a **new** community backend named **ThisData** so the existing KJB code remains untouched.

## Implemented requirements

- Multiple servers with server list and per-server channel list (`GET /api/servers`)
- Public and private servers (`is_public`)
- Invite links with `/invite?code=<code>` behavior
- Server creator becomes admin (not first joiner)
- Per-server admin role separation
- Server admins can ban specific users
- Bot support with API token (`X-Bot-Token`) for reading/sending messages like normal users
- DM support between friends
- Friend request/add/list flow
- Removed from ThisData scope: shop/KC/notification systems

## Quick start

```bash
cd ThisData
python -m venv .venv
source .venv/bin/activate
pip install -r ../requirements.txt
python run.py
```

## Main API examples

- `POST /api/auth/signup`
- `POST /api/auth/signin`
- `POST /api/servers`
- `GET /api/servers`
- `POST /api/servers/<server_id>/invite-links`
- `GET /api/invite?code=<code>`
- `POST /api/invite`
- `POST /api/servers/<server_id>/ban`
- `POST /api/bots`
- `POST /api/friends/request`
- `POST /api/friends/request/<request_id>/accept`
- `POST /api/dm`
- `GET /api/dm/<user_id>`
