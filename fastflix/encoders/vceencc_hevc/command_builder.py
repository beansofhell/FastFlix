# -*- coding: utf-8 -*-
import logging

from fastflix.encoders.common.helpers import Command
from fastflix.models.encode import VCEEncCSettings
from fastflix.models.video import Video
from fastflix.models.fastflix import FastFlix
from fastflix.encoders.common.encc_helpers import (
    build_subtitle,
    build_audio,
    rigaya_avformat_reader,
    rigaya_auto_options,
)
from fastflix.flix import clean_file_string

logger = logging.getLogger("fastflix")


def build(fastflix: FastFlix):
    video: Video = fastflix.current_video
    settings: VCEEncCSettings = fastflix.current_video.video_settings.video_encoder_settings

    master_display = None
    if fastflix.current_video.master_display:
        master_display = (
            f'--master-display "G{fastflix.current_video.master_display.green}'
            f"B{fastflix.current_video.master_display.blue}"
            f"R{fastflix.current_video.master_display.red}"
            f"WP{fastflix.current_video.master_display.white}"
            f'L{fastflix.current_video.master_display.luminance}"'
        )

    max_cll = None
    if fastflix.current_video.cll:
        max_cll = f'--max-cll "{fastflix.current_video.cll}"'

    dhdr = None
    if settings.hdr10plus_metadata:
        dhdr = f'--dhdr10-info "{settings.hdr10plus_metadata}"'

    seek = ""
    seekto = ""
    if video.video_settings.start_time:
        seek = f"--seek {video.video_settings.start_time}"
    if video.video_settings.end_time:
        seekto = f"--seekto {video.video_settings.end_time}"

    transform = ""
    if video.video_settings.vertical_flip or video.video_settings.horizontal_flip:
        transform = f"--vpp-transform flip_x={'true' if video.video_settings.horizontal_flip else 'false'},flip_y={'true' if video.video_settings.vertical_flip else 'false'}"

    remove_hdr = ""
    if video.video_settings.remove_hdr:
        remove_type = (
            video.video_settings.tone_map
            if video.video_settings.tone_map in ("mobius", "hable", "reinhard")
            else "mobius"
        )
        remove_hdr = f"--vpp-colorspace hdr2sdr={remove_type}" if video.video_settings.remove_hdr else ""

    crop = ""
    if video.video_settings.crop:
        crop = f"--crop {video.video_settings.crop.left},{video.video_settings.crop.top},{video.video_settings.crop.right},{video.video_settings.crop.bottom}"

    vbv = ""
    if video.video_settings.maxrate:
        vbv = f"--max-bitrate {video.video_settings.maxrate} --vbv-bufsize {video.video_settings.bufsize}"

    try:
        stream_id = int(video.current_video_stream["id"], 16)
    except Exception:
        if len(video.streams.video) > 1:
            logger.warning("Could not get stream ID from source, the proper video track may not be selected!")
        stream_id = None

    vsync_setting = "cfr" if video.frame_rate == video.average_frame_rate else "vfr"
    if video.video_settings.vsync == "cfr":
        vsync_setting = "forcecfr"
    elif video.video_settings.vsync == "vfr":
        vsync_setting = "vfr"

    source_fps = f"--fps {video.video_settings.source_fps}" if video.video_settings.source_fps else ""

    command = [
        f'"{clean_file_string(fastflix.config.vceencc)}"',
        rigaya_avformat_reader(fastflix),
        "--device",
        str(settings.device),
        "-i",
        f'"{clean_file_string(video.source)}"',
        (f"--video-streamid {stream_id}" if stream_id else ""),
        seek,
        seekto,
        source_fps,
        (f"--vpp-rotate {video.video_settings.rotate * 90}" if video.video_settings.rotate else ""),
        transform,
        (f'--output-res {video.scale.replace(":", "x")}' if video.scale else ""),
        crop,
        (
            f"--video-metadata clear --metadata clear"
            if video.video_settings.remove_metadata
            else "--video-metadata copy  --metadata copy"
        ),
        (f'--video-metadata title="{video.video_settings.video_title}"' if video.video_settings.video_title else ""),
        ("--chapter-copy" if video.video_settings.copy_chapters else ""),
        "-c",
        "hevc",
        (f"--vbr {settings.bitrate.rstrip('k')}" if settings.bitrate else f"--cqp {settings.cqp}"),
        vbv,
        (f"--qp-min {settings.min_q}" if settings.min_q and settings.bitrate else ""),
        (f"--qp-max {settings.max_q}" if settings.max_q and settings.bitrate else ""),
        (f"--ref {settings.ref}" if settings.ref else ""),
        "--preset",
        settings.preset,
        "--tier",
        settings.tier,
        "--level",
        (settings.level or "auto"),
        rigaya_auto_options(fastflix),
        (master_display if master_display else ""),
        (max_cll if max_cll else ""),
        (dhdr if dhdr else ""),
        "--output-depth",
        ("10" if video.current_video_stream.bit_depth > 8 and not video.video_settings.remove_hdr else "8"),
        "--motion-est",
        settings.mv_precision,
        ("--vbaq" if settings.vbaq else ""),
        ("--pe" if settings.pre_encode else ""),
        ("--pa" if settings.pre_analysis else ""),
        f"--avsync {vsync_setting}",
        (f"--interlace {video.interlaced}" if video.interlaced and video.interlaced != "False" else ""),
        ("--vpp-nnedi" if video.video_settings.deinterlace else ""),
        (f"--vpp-colorspace hdr2sdr=mobius" if video.video_settings.remove_hdr else ""),
        remove_hdr,
        "--psnr --ssim" if settings.metrics else "",
        build_audio(video.video_settings.audio_tracks, video.streams.audio),
        build_subtitle(video.video_settings.subtitle_tracks, video.streams.subtitle, video_height=video.height),
        settings.extra,
        "-o",
        f'"{clean_file_string(video.video_settings.output_path)}"',
    ]

    return [Command(command=" ".join(x for x in command if x), name="VCEEncC Encode", exe="VCEEncC")]
