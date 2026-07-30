"""Project-local FFmpeg media service."""

from .audio import extract_asr_wav, extract_asr_wav_chunk
from .errors import (
    MediaError,
    MediaFileNotFoundError,
    MediaToolNotFoundError,
    NoAudioStreamError,
    OutputExistsError,
    ProbeError,
    ProcessExecutionError,
    SubtitleError,
)
from .ffmpeg_paths import FFmpegPaths, resolve_ffmpeg_paths
from .probe import MediaProbe, StreamInfo, parse_frame_rate, probe_media
from .subtitles import (
    SubtitleCue,
    burn_subtitles,
    parse_srt_text,
    retime_cues,
    retime_srt,
)
from .sync import (
    MediaSyncMetrics,
    SyncTolerances,
    parse_sync_probe_json,
    probe_media_sync,
)
from .trim import trim_video_precise
from .validate import ExportValidation, validate_export

__all__ = [
    "ExportValidation",
    "FFmpegPaths",
    "MediaError",
    "MediaFileNotFoundError",
    "MediaProbe",
    "MediaSyncMetrics",
    "MediaToolNotFoundError",
    "NoAudioStreamError",
    "OutputExistsError",
    "ProbeError",
    "ProcessExecutionError",
    "StreamInfo",
    "SubtitleCue",
    "SubtitleError",
    "SyncTolerances",
    "burn_subtitles",
    "extract_asr_wav",
    "extract_asr_wav_chunk",
    "parse_frame_rate",
    "parse_srt_text",
    "parse_sync_probe_json",
    "probe_media",
    "probe_media_sync",
    "resolve_ffmpeg_paths",
    "retime_cues",
    "retime_srt",
    "trim_video_precise",
    "validate_export",
]
