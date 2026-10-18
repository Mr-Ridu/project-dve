"""Playback provider modules (Phase 6).

Each provider exposes redeem_token(context) → dict describing how the player
should actually fetch/stream the video. The choice comes from
Tutorial.video_provider; no provider sees our authorization decisions.
"""
