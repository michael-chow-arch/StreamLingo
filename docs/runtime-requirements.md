# Runtime requirements / 运行条件

[Getting started](getting-started.md) · [中文说明](#中文说明)

## Supported Windows preview

The current real-time speech setup requires an NVIDIA GPU. StreamLingo reports missing dependencies and stops; it does not silently switch to CPU or change your GPU environment. These requirements apply to the local speech service, separately from Ollama.

| Component | Requirement |
| --- | --- |
| Operating system | Windows x64. Windows 11 is the locally tested platform; Linux/macOS and Windows ARM are not validated release targets. |
| Browser | Chrome 116 or newer; a current stable version is preferable. |
| Python | **64-bit Python 3.11–3.13**. Setup can offer 3.12 when Python is absent. |
| GPU runtime | **CUDA 12.x cuBLAS + complete cuDNN 9.x for CUDA 12**, with their DLL directories available to the service through `PATH`. The verified combination is **CUDA 12.4.1 + cuDNN 9.3.0**. |
| GPU and driver | A compatible CUDA-capable NVIDIA GPU and driver. For the CUDA 12.4.1 setup, use **Windows driver 551.78 or newer**. See the compatibility note below before using a different combination. |
| Native runtime | Microsoft Visual C++ v14 Redistributable **x64**, current supported release. |
| Ollama | Your existing running Ollama installation and an installed text/chat model capable of Chinese/English translation. Local tests use `qwen3.5:9b`; that exact model is not mandatory. |
| Speech model | Multilingual Whisper `base`, downloaded by Setup. `base.en` cannot support Chinese or automatic language modes. |
| Memory and disk | Capacity for the chosen Ollama model, speech model and Python packages together. A universal minimum RAM/VRAM/disk size has **not been measured**. |
| Build tools | Node.js 22+ only when building from source. The prebuilt Windows ZIP needs neither Node.js nor a C++ compiler. |
| Network | Required for initial dependency/model downloads and YouTube playback. Default audio/text processing stays on the machine. |

The speech dependency versions are pinned to WhisperLiveKit **0.2.26**, faster-whisper **1.2.1**, and CTranslate2 **4.8.3**. The [faster-whisper 1.2.1 GPU instructions](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/README.md#gpu) specify CUDA 12 cuBLAS and cuDNN 9. CUDA 11, cuDNN 8, or only a CUDA 13 runtime does not satisfy this pinned setup.

For a concrete installation baseline, use the [CUDA 12.4.1 installer](https://developer.nvidia.com/cuda-12-4-1-download-archive), the CUDA 12 build of [cuDNN 9.3](https://developer.nvidia.com/cudnn-archive), and Microsoft's [supported x64 Visual C++ runtime](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist). Follow the vendors' installation instructions; Setup does not install GPU drivers or CUDA/cuDNN for you.

NVIDIA lists **551.78** as the Windows driver paired with CUDA 12.4 Update 1. Its lower **528.33** CUDA 12.x minor-compatibility floor has additional compatibility conditions; it is not StreamLingo's tested performance minimum. New GPU generations can require a newer stack, so check NVIDIA's [CUDA release notes](https://docs.nvidia.com/cuda/archive/12.4.1/cuda-toolkit-release-notes/index.html) and [cuDNN 9.3 support matrix](https://docs.nvidia.com/deeplearning/cudnn/backend/v9.3.0/reference/support-matrix.html) for your hardware. Do not downgrade a working newer driver to match a test machine.

## Check before starting

1. Confirm the CUDA and complete cuDNN DLL directories are in `PATH`, then open a **new** launcher window. `CUDA_PATH` alone is insufficient. Installing Ollama does not automatically expose its private libraries to this Python service.
2. Run **Setup-StreamLingo.cmd** to prepare Python dependencies and the speech model.
3. Run **Doctor-StreamLingo.cmd**. Its runtime check only locates required DLL files; it neither loads models nor changes your environment. Before Start, it will also report that the subtitle service is not running.
4. Run **Start-StreamLingo.cmd**. Real ASR startup checks runtime files and CUDA device availability before loading the speech engine. Missing requirements stop startup with specific details.
5. Once ready, run Doctor again and test a short livestream. File presence and device detection alone do not establish binary compatibility, sufficient memory, or real-time speed.

Missing-library messages identify files such as `cublas64_12.dll` or `cudnn_ops64_9.dll`. Install the complete matching runtime from its official source; copying only `cudnn64_9.dll` is insufficient. `nvidia-smi` shows driver capability, not proof that the required Python-side CUDA/cuDNN runtime files are installed.

## Locally verified configuration

| Component | Test machine, 2026-10-13 |
| --- | --- |
| OS / CPU | Windows 11 x64 / Intel Core i7-13700KF |
| RAM / GPU | 32 GiB RAM / NVIDIA RTX 3080, 10 GiB VRAM |
| NVIDIA driver | 616.56 |
| CUDA / cuDNN | CUDA 12.4.1 / cuDNN 9.3.0.75 |
| Models | Multilingual Whisper base + Ollama qwen3.5:9b |

**This is a tested configuration, not a minimum hardware claim.** ASR and Ollama can compete for GPU memory and compute. Smaller/larger models, quantization, speech rate, and other GPU applications change capacity and latency. See the [validation record](validation.md) for the measured tests and remaining gaps.

## 中文说明

当前 Windows 预览版的真实语音识别要求 **NVIDIA GPU、CUDA 12.x（含 cuBLAS）、适用于 CUDA 12 的完整 cuDNN 9.x**。推荐按已验证组合准备：**CUDA 12.4.1 + cuDNN 9.3，Windows 驱动 551.78 或更新版本**，另需 x64 Visual C++ v14 运行库。具体下载链接和兼容性依据见上文。

浏览器要求 **Chrome 116+**，本地服务要求 **64 位 Python 3.11–3.13**，以及已运行、已安装文本模型的 Ollama。预构建 Windows ZIP 不需要 Node.js；从源码构建才需要 **Node.js 22+**。首次 Setup 下载语音依赖和多语 Whisper base，不替换你的 Ollama 模型，也不自动安装显卡驱动或 CUDA/cuDNN。

依赖不足时明确列出缺项并停止，不自动降级到 CPU，不修改显卡环境变量。CUDA 与 cuDNN 的 DLL 目录必须能通过服务进程的 `PATH` 找到，修改后要重新打开启动窗口。**Ollama 能运行，不代表这套 Python 语音服务的运行库已经齐全。**

先运行 Setup，再运行 Doctor 检查库文件，随后 Start 启动服务。尚未启动时 Doctor 提示服务未运行是正常的；启动完成后再检查一次。DLL 存在和 GPU 可见只是必要检查，最终还需真实模型加载和短段翻译成功。

本机验证环境为 **RTX 3080 10 GiB 显存、32 GiB 内存**。这不是最低门槛：通用最低显存、内存和磁盘要求尚未测定，取决于你选择的 Ollama 模型及并行负载。我们会依据测量补充要求，不把未经验证的数字写成保证。
