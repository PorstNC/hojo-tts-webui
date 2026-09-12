---
license: apache-2.0
language:
- en
- zh
---

For usage instructions, please refer to the [Hojo-TTS-Light-40M](https://github.com/HojoAI/Hojo-TTS-Light/tree/main/Hojo-TTS-Light-40M)

## Parameter count


| Model                                | Params     | ~M    | Disk dtype | ~File size |
| ------------------------------------ | ---------- | ----- | ---------- | ---------- |
| `Hojo-TTS-Light-40M-llm.onnx`        | 31,337,600 | 31.34 | bf16       | ~61 MB     |
| `Hojo-TTS-Light-40M-fine_local.onnx` | 13,296,256 | 13.30 | bf16       | ~26 MB     |
| `Hojo-TTS-Light-40M-decoder.onnx`    | 30,910,594 | 30.91 | fp32       | ~118 MB    |


## Voices

Opaque IDs in `Hojo-TTS-Light-40M-voice.npz` (`voice_ids`).


| Voice ID       | Language | Sex    |
| -------------- | -------- | ------ |
| `hojo_zh_f_01` | zh       | female |
| `hojo_zh_f_02` | zh       | female |
| `hojo_en_f_01` | en       | female |
| `hojo_en_f_02` | en       | female |
| `hojo_en_f_03` | en       | female |
| `hojo_en_f_04` | en       | female |
| `hojo_en_f_05` | en       | female |
| `hojo_en_f_06` | en       | female |
| `hojo_en_f_07` | en       | female |
| `hojo_en_f_08` | en       | female |
| `hojo_en_m_01` | en       | male   |
| `hojo_en_m_02` | en       | male   |
| `hojo_en_m_03` | en       | male   |
| `hojo_en_m_04` | en       | male   |
| `hojo_en_m_05` | en       | male   |