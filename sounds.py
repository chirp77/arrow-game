# -*- coding: utf-8 -*-
"""sounds.py —— 程序生成的音效（无任何外部素材，规避版权问题）。

用标准库 wave 模块在内存中合成 WAV 字节流，再交给 pygame.mixer.Sound 播放。
所有合成都是"正弦波 + 包络"：5ms 起音避免爆音，指数衰减模拟自然衰减。
音频初始化失败时静默降级（打印警告，游戏照常无音效运行）。
"""

import io
import math
import struct
import wave

import pygame

SR = 22050  # 采样率，与 pre_init_mixer 保持一致


# ---------------------------------------------------------------------------
# 波形合成
# ---------------------------------------------------------------------------
def _tone(freq, ms, decay=4.0, attack_ms=5, amp=1.0):
    """固定频率正弦音。decay 越大衰减越快；attack_ms 为起音时长。"""
    n = SR * ms // 1000
    attack = max(1, SR * attack_ms // 1000)
    out = []
    for i in range(n):
        t = i / SR
        env = min(1.0, i / attack) * math.exp(-decay * t)
        out.append(amp * env * math.sin(2 * math.pi * freq * t))
    return out


def _sweep(f0, f1, ms, decay=5.0):
    """频率线性扫变的音（相位连续积分，无爆音）。"""
    n = SR * ms // 1000
    attack = max(1, SR * 5 // 1000)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / SR
        freq = f0 + (f1 - f0) * (i / n)
        phase += 2 * math.pi * freq / SR
        env = min(1.0, i / attack) * math.exp(-decay * t)
        out.append(env * math.sin(phase))
    return out


def _concat(*tracks):
    """把多段波形首尾相接。"""
    return [v for track in tracks for v in track]


def _mix(*tracks):
    """把多段波形叠加（对齐起点）。"""
    n = max(len(t) for t in tracks)
    return [sum(t[i] if i < len(t) else 0.0 for t in tracks) for i in range(n)]


def _wav_bytes(samples):
    """采样序列（-1~1 浮点）→ 16 位单声道 WAV 字节流。"""
    raw = bytearray()
    for s in samples:
        v = max(-1.0, min(1.0, s))
        raw += struct.pack("<h", int(v * 32000))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bytes(raw))
    return buf.getvalue()


def build_sounds():
    """生成全部音效的 WAV 字节流。

    - fly：600→1400Hz 上扫 180ms，听感"嗖"；
    - collide：90Hz 与 180Hz 叠加 250ms，低沉"咚"；
    - clear：C-E-G 三音上行琶音，欢快；
    - over：两音下行，失落；
    - undo：短促"嗒"。
    """
    return {
        "fly": _wav_bytes(_sweep(600, 1400, 180)),
        "collide": _wav_bytes(_mix(_tone(90, 250, decay=5), _tone(180, 250, decay=5, amp=0.4))),
        "clear": _wav_bytes(_concat(_tone(523, 120), _tone(659, 120), _tone(784, 260))),
        "over": _wav_bytes(_concat(_tone(400, 250, decay=3), _tone(220, 400, decay=3))),
        "undo": _wav_bytes(_tone(600, 80, decay=6)),
    }


def pre_init_mixer():
    """设置 mixer 参数。必须在 pygame.init() 之前调用才生效。"""
    try:
        pygame.mixer.pre_init(SR, -16, 1)
    except Exception:
        pass  # 后续初始化失败时 SoundPlayer 会再兜底


class SoundPlayer:
    """音效播放器：加载程序生成的音效；初始化失败时静默降级。"""

    def __init__(self):
        self.enabled = False
        self._sounds = {}
        try:
            pygame.mixer.init()
            for name, wav in build_sounds().items():
                self._sounds[name] = pygame.mixer.Sound(buffer=wav)
            self.enabled = True
        except Exception as exc:  # 任何音频错误都不应阻止游戏运行
            print(f"警告：音频初始化失败，将无音效运行（{exc}）")

    def play(self, name):
        """播放指定音效；未启用或不存在时静默跳过。"""
        if not self.enabled:
            return
        sound = self._sounds.get(name)
        if sound is not None:
            sound.play()
