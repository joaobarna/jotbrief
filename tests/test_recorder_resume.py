import numpy as np
import soundfile as sf

from saidkeep.audio import SR, StereoRecorder


def test_resume_appends_and_keeps_alignment(tmp_path):
    p = tmp_path / "a.wav"
    r = StereoRecorder(p)
    r.add("mic", 0.0, np.full(SR, 0.5, np.float32))          # 1 s no mic
    r.close(1.0)
    assert sf.info(str(p)).frames == SR

    r2 = StereoRecorder(p, append=True)                       # retoma: relógio continua em 1 s
    r2.add("loop", 1.0, np.full(SR, 0.25, np.float32))       # 1 s na reunião
    r2.close(2.0)
    data, sr = sf.read(str(p))
    assert sr == SR and len(data) == 2 * SR
    assert abs(data[SR // 2, 0] - 0.5) < 1e-3                 # mic do trecho antigo preservado
    assert abs(data[SR + SR // 2, 1] - 0.25) < 1e-3           # reunião no trecho novo
