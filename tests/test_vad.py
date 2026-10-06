import numpy as np

from saidkeep.vad import ONNX_PATH, SR, WIN, Segmenter, SileroVad


def test_model_ships_with_the_app_and_scores_silence_low():
    assert ONNX_PATH.exists()
    vad = SileroVad()
    assert vad(np.zeros(WIN, dtype=np.float32)) < 0.1


def test_each_instance_has_its_own_state():
    rng = np.random.default_rng(0)
    noise = (rng.standard_normal(WIN * 20) * 0.1).astype("float32")
    a, b = SileroVad(), SileroVad()
    for i in range(0, len(noise), WIN):
        a(noise[i:i + WIN])                       # só A "ouve"; o estado de B não pode mudar
    fresh = SileroVad()
    assert abs(b(noise[:WIN]) - fresh(noise[:WIN])) < 1e-6


def test_segmenter_emits_nothing_for_silence_and_flushes_cleanly():
    seg = Segmenter("loop")
    assert seg.feed(np.zeros(SR * 2, dtype=np.float32), 0.0) == [] and seg.flush() == []
