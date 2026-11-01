# v0.1.71 — maintained Stig fork

- Persist rotated Aula credentials so they survive Home Assistant restarts.
- Recover expired widget JWTs with one bounded OAuth refresh and retry.
- Fetch EasyIQ's general weekly text into the existing weekplan sensor attributes
  and calendars, including when the lesson endpoint times out.
- Keep the existing `aula` domain, account and entity identities.
- Add offline regression coverage using fictitious data and a tagged release
  workflow that does not modify the tested source.

Based on upstream stable v0.1.69. Install/update through **StigCPH/aula**, not the
original HACS repository. Provider-enforced MitID reauthentication can still be
required when refresh credentials expire or are revoked.
