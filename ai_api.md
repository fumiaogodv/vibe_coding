```python
import os

# Define the markdown content for the API integration document
md_content = """# 小米 Mimo 智能体（Agent）API 接入文档

本标准集成文档旨在指导开发者或 AI Agent（如 LangChain、LlamaIndex、AutoGPT 等智能体框架）如何对接小米 Mimo 的通用 API 接口。

## 1. 接口基础信息

* **API 根地址 (Base URL):** `https://token-plan-cn.xiaomimimo.com/v1`
* **协议规范:** 统一采用 HTTPS 协议，请求与响应数据格式均为 `application/json`。
* **认证方式:** 采用 Bearer Token 认证。请在 HTTP 请求头中携带您的 API Key：

```

```text
Successfully generated mimo_agent_api_documentation.md

```http
  Authorization: Bearer YOUR_API_KEY

```

---

## 2. 支持的模型列表 (Model List)

在调用流式/非流式文本生成、语音识别（ASR）或语音合成（TTS）时，请在请求体的 `model` 参数中传入以下指定模型名称：

| 模型名称 (Model Name) | 模型类型 | 核心功能与适用场景 |
| --- | --- | --- |
| **`mimo-v2.5-pro`** | 大语言模型 (LLM) | 旗舰级大语言模型，具备极高的推理能力、复杂的逻辑分析以及长文本处理能力，适合作为 Agent 的核心大脑。 |
| **`mimo-v2.5`** | 大语言模型 (LLM) | 标准版大语言模型，在响应速度、吞吐量与理解能力上达到最佳平衡，适用于日常对话、信息提取与高并发 Agent 任务。 |
| **`mimo-v2.5-asr`** | 语音识别 (ASR) | 自动语音识别模型，可将用户的音频/语音输入精准转化为文本，赋予 Agent 语音听觉能力。 |
| **`mimo-v2.5-tts`** | 语音合成 (TTS) | 标准语音合成模型，将文本转化为自然流畅的高质量语音，赋予 Agent 语音表达能力。 |
| **`mimo-v2.5-tts-voiceclone`** | 语音克隆 (TTS) | 声音克隆专用模型，支持通过极短的音频样本（如 3-5 秒）快速克隆目标音色。 |
| **`mimo-v2.5-tts-voicedesign`** | 声音设计 (TTS) | 声音定制与设计模型，支持通过参数微调或特征文本描述生成并定制独特的全新音色。 |

---

## 3. 核心 API 接口规范

Mimo API 全面兼容行业主流的 OpenAI 格式规范，方便 Agent 框架进行无缝迁移。

### 3.1 文本生成 / 智能体对话 (`/chat/completions`)

用于驱动 Agent 进行思考、规划、工具调用（Function Calling）以及最终回复。

* **请求路径:** `POST /chat/completions`
* **请求体参数:**
* `model` (string, 必填): `mimo-v2.5-pro` 或 `mimo-v2.5`
* `messages` (array, 必填): 对话历史数组。包含 `role` (`system`, `user`, `assistant`, `tool`) 和 `content`。
* `temperature` (number, 选填): 温度系数 (0.0 ~ 2.0)，默认 0.7。
* `stream` (boolean, 选填): 是否开启流式传输，默认 `false`。



**请求示例 (Python):**

```python
import requests
import json

url = "[https://token-plan-cn.xiaomimimo.com/v1/chat/completions](https://token-plan-cn.xiaomimimo.com/v1/chat/completions)"
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}
payload = {
    "model": "mimo-v2.5-pro",
    "messages": [
        {"role": "system", "content": "你是一个严谨的 AI 智能体助手。"},
        {"role": "user", "content": "请为我规划一份去北京的3天旅游行程。"}
    ],
    "temperature": 0.7,
    "stream": False
}

response = requests.post(url, headers=headers, json=payload)
print(response.json())

```

---

### 3.2 语音识别 接口 (`/audio/transcriptions`)

当 Agent 接收到用户的语音指令时，使用此接口进行文本化解析。

* **请求路径:** `POST /audio/transcriptions`
* **请求体参数 (Multipart/Form-Data):**
* `file` (binary, 必填): 待识别的音频文件 (支持 mp3, wav, m4a 等)。
* `model` (string, 必填): 固定为 `mimo-v2.5-asr`。



**请求示例 (Python):**

```python
import requests

url = "[https://token-plan-cn.xiaomimimo.com/v1/audio/transcriptions](https://token-plan-cn.xiaomimimo.com/v1/audio/transcriptions)"
headers = {
    "Authorization": "Bearer YOUR_API_KEY"
}
files = {
    "file": open("user_voice.wav", "rb")
}
data = {
    "model": "mimo-v2.5-asr"
}

response = requests.post(url, headers=headers, files=files, data=data)
print(response.json())

```

---

### 3.3 语音合成 接口 (`/audio/speech`)

当 Agent 需要以语音形式向用户进行播报或交互时使用。

* **请求路径:** `POST /audio/speech`
* **请求体参数:**
* `model` (string, 必填): `mimo-v2.5-tts`, `mimo-v2.5-tts-voiceclone` 或 `mimo-v2.5-tts-voicedesign`。
* `input` (string, 必填): 需要转成语音的文本内容。
* `voice` (string, 选填): 目标音色标识。若是 `voiceclone` 模型，此处需传入克隆出的指定 Voice ID。
* `response_format` (string, 选填): 返回音频格式，如 `mp3`, `wav`，默认 `mp3`。



**请求示例 (Python):**

```python
import requests

url = "[https://token-plan-cn.xiaomimimo.com/v1/audio/speech](https://token-plan-cn.xiaomimimo.com/v1/audio/speech)"
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}
payload = {
    "model": "mimo-v2.5-tts",
    "input": "收到指令，正在为您执行任务。",
    "voice": "default-male"
}

response = requests.post(url, headers=headers, json=payload)
if response.status_code == 200:
    with open("agent_response.mp3", "wb") as f:
        f.write(response.content)
    print("语音合成成功，文件已保存为 agent_response.mp3")
else:
    print("语音合成失败:", response.text)

```

---

## 4. Agent 接入框架配置示例 (以 LangChain 为例)

大多数现代 Agent 框架都原生支持通过修改 `base_url` 来接入兼容 OpenAI 格式的自定义模型。以下是 Python LangChain 框架的接入代码：

```python
from langchain_openai import ChatOpenAI

# 初始化 Mimo 驱动的大语言模型
mimo_agent_brain = ChatOpenAI(
    model="mimo-v2.5-pro", # 核心思考大脑
    openai_api_key="YOUR_API_KEY",
    openai_api_base="[https://token-plan-cn.xiaomimimo.com/v1](https://token-plan-cn.xiaomimimo.com/v1)",
    temperature=0.2
)

# 示例调用
response = mimo_agent_brain.invoke("分析以下任务并规划执行步骤：更新数据库里的过期库存。")
print(response.content)

```

---

## 5. 错误码与异常处理

当 API 调用发生异常时，接口将返回标准的 HTTP 状态码及错误 JSON 结构：

```json
{
  "error": {
    "message": "错误详细描述信息",
    "type": "invalid_request_error",
    "code": "token_expired"
  }
}

```

* **401 Unauthorized:** API Key 无效或已过期，请检查请求头。
* **429 Too Many Requests:** 触发接口限流，请引入指数退避重试机制。
* **400 Bad Request:** 参数错误，请检查传入的 `model` 名称是否拼写正确。
* **500 Internal Server Error:** 服务器内部错误，请稍后重试。

---

*文档版本: v1.0.0 | 更新日期: 2026年6月*
"""

# Save the content to a markdown file

output_file_path = "mimo_agent_api_documentation.md"
with open(output_file_path, "w", encoding="utf-8") as f:
f.write(md_content)

print(f"Successfully generated {output_file_path}")

```
您的 Mimo 智能体（Agent）API 接入 Markdown 文档已经为您编写并生成完毕。

[file-tag: code-generated-file-0-1780735394972152612]

为了方便您快速预览，以下是该 Markdown 文件的完整内容：

***

# 小米 Mimo 智能体（Agent）API 接入文档

本标准集成文档旨在指导开发者或 AI Agent（如 LangChain、LlamaIndex、AutoGPT 等智能体框架）如何对接小米 Mimo 的通用 API 接口。

## 1. 接口基础信息

* **API 根地址 (Base URL):** `https://token-plan-cn.xiaomimimo.com/v1`
* **协议规范:** 统一采用 HTTPS 协议，请求与响应数据格式均为 `application/json`。
* **认证方式:** 采用 Bearer Token 认证。请在 HTTP 请求头中携带您的 API Key：
  ```http
  Authorization: Bearer YOUR_API_KEY

```

---

## 2. 支持的模型列表 (Model List)

在调用流式/非流式文本生成、语音识别（ASR）或语音合成（TTS）时，请在请求体的 `model` 参数中传入以下指定模型名称：

| 模型名称 (Model Name) | 模型类型 | 核心功能与适用场景 |
| --- | --- | --- |
| **`mimo-v2.5-pro`** | 大语言模型 (LLM) | 旗舰级大语言模型，具备极高的推理能力、复杂的逻辑分析以及长文本处理能力，适合作为 Agent 的核心大脑。 |
| **`mimo-v2.5`** | 大语言模型 (LLM) | 标准版大语言模型，在响应速度、吞吐量与理解能力上达到最佳平衡，适用于日常对话、信息提取与高并发 Agent 任务。 |
| **`mimo-v2.5-asr`** | 语音识别 (ASR) | 自动语音识别模型，可将用户的音频/语音输入精准转化为文本，赋予 Agent 语音听觉能力。 |
| **`mimo-v2.5-tts`** | 语音合成 (TTS) | 标准语音合成模型，将文本转化为自然流畅的高质量语音，赋予 Agent 语音表达能力。 |
| **`mimo-v2.5-tts-voiceclone`** | 语音克隆 (TTS) | 声音克隆专用模型，支持通过极短的音频样本（如 3-5 秒）快速克隆目标音色。 |
| **`mimo-v2.5-tts-voicedesign`** | 声音设计 (TTS) | 声音定制与设计模型，支持通过参数微调或特征文本描述生成并定制独特的全新音色。 |

---

## 3. 核心 API 接口规范

Mimo API 全面兼容行业主流的 OpenAI 格式规范，方便 Agent 框架进行无缝迁移。

### 3.1 文本生成 / 智能体对话 (`/chat/completions`)

用于驱动 Agent 进行思考、规划、工具调用（Function Calling）以及最终回复。

* **请求路径:** `POST /chat/completions`
* **请求体参数:**
* `model` (string, 必填): `mimo-v2.5-pro` 或 `mimo-v2.5`
* `messages` (array, 必填): 对话历史数组。包含 `role` (`system`, `user`, `assistant`, `tool`) 和 `content`。
* `temperature` (number, 选填): 温度系数 (0.0 ~ 2.0)，默认 0.7。
* `stream` (boolean, 选填): 是否开启流式传输，默认 `false`。



**请求示例 (Python):**

```python
import requests
import json

url = "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}
payload = {
    "model": "mimo-v2.5-pro",
    "messages": [
        {"role": "system", "content": "你是一个严谨的 AI 智能体助手。"},
        {"role": "user", "content": "请为我规划一份去北京的3天旅游行程。"}
    ],
    "temperature": 0.7,
    "stream": False
}

response = requests.post(url, headers=headers, json=payload)
print(response.json())

```

---

### 3.2 语音识别 接口 (`/audio/transcriptions`)

当 Agent 接收到用户的语音指令时，使用此接口进行文本化解析。

* **请求路径:** `POST /audio/transcriptions`
* **请求体参数 (Multipart/Form-Data):**
* `file` (binary, 必填): 待识别的音频文件 (支持 mp3, wav, m4a 等)。
* `model` (string, 必填): 固定为 `mimo-v2.5-asr`。



**请求示例 (Python):**

```python
import requests

url = "https://token-plan-cn.xiaomimimo.com/v1/audio/transcriptions"
headers = {
    "Authorization": "Bearer YOUR_API_KEY"
}
files = {
    "file": open("user_voice.wav", "rb")
}
data = {
    "model": "mimo-v2.5-asr"
}

response = requests.post(url, headers=headers, files=files, data=data)
print(response.json())

```

---

### 3.3 语音合成 接口 (`/audio/speech`)

当 Agent 需要以语音形式向用户进行播报或交互时使用。

* **请求路径:** `POST /audio/speech`
* **请求体参数:**
* `model` (string, 必填): `mimo-v2.5-tts`, `mimo-v2.5-tts-voiceclone` 或 `mimo-v2.5-tts-voicedesign`。
* `input` (string, 必填): 需要转成语音的文本内容。
* `voice` (string, 选填): 目标音色标识。若是 `voiceclone` 模型，此处需传入克隆出的指定 Voice ID。
* `response_format` (string, 选填): 返回音频格式，如 `mp3`, `wav`，默认 `mp3`。



**请求示例 (Python):**

```python
import requests

url = "https://token-plan-cn.xiaomimimo.com/v1/audio/speech"
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}
payload = {
    "model": "mimo-v2.5-tts",
    "input": "收到指令，正在为您执行任务。",
    "voice": "default-male"
}

response = requests.post(url, headers=headers, json=payload)
if response.status_code == 200:
    with open("agent_response.mp3", "wb") as f:
        f.write(response.content)
    print("语音合成成功，文件已保存为 agent_response.mp3")
else:
    print("语音合成失败:", response.text)

```

---

## 4. Agent 接入框架配置示例 (以 LangChain 为例)

大多数现代 Agent 框架都原生支持通过修改 `base_url` 来接入兼容 OpenAI 格式的自定义模型。以下是 Python LangChain 框架的接入代码：

```python
from langchain_openai import ChatOpenAI

# 初始化 Mimo 驱动的大语言模型
mimo_agent_brain = ChatOpenAI(
    model="mimo-v2.5-pro", # 核心思考大脑
    openai_api_key="YOUR_API_KEY",
    openai_api_base="https://token-plan-cn.xiaomimimo.com/v1",
    temperature=0.2
)

# 示例调用
response = mimo_agent_brain.invoke("分析以下任务并规划执行步骤：更新数据库里的过期库存。")
print(response.content)

```

---

## 5. 错误码与异常处理

当 API 调用发生异常时，接口将返回标准的 HTTP 状态码及错误 JSON 结构：

```json
{
  "error": {
    "message": "错误详细描述信息",
    "type": "invalid_request_error",
    "code": "token_expired"
  }
}

```

* **401 Unauthorized:** API Key 无效或已过期，请检查请求头。
* **429 Too Many Requests:** 触发接口限流，请引入指数退避重试机制。
* **400 Bad Request:** 参数错误，请检查传入的 `model` 名称是否拼写正确。
* **500 Internal Server Error:** 服务器内部错误，请稍后重试。

---

*文档版本: v1.0.0 | 更新日期: 2026年6月*